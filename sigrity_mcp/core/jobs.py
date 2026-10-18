"""Async job manager for launching Sigrity batch-mode processes.

Sigrity simulations/extractions can run for minutes to hours, which is far longer than
an MCP tool call should block for. So every "run" tool here follows the same pattern:
`submit()` launches the process in the background and returns a job_id immediately;
separate `status()` / `tail_log()` / `wait()` tools let the caller poll or block as
they choose.

Job state lives both in memory (for the life of this server process) and as a small
`job.json` file in each job's working directory, so `status()` still works after a
server restart for jobs that already finished.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from sigrity_mcp.core import win32gui_helper
from sigrity_mcp.core.config import settings
from sigrity_mcp.core.errors import JobNotFoundError, JobStillRunningError
from sigrity_mcp.core import executables
from sigrity_mcp.core import gui_tool_runner

_LICENSE_MARKERS = (
    "no license",
    "license not available",
    "flexlm",
    "flexnet",
    "unable to checkout",
    "license denied",
)


def _safe_stat_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _pid_alive(pid: int) -> bool:
    """Windows-only liveness check via OpenProcess, used to correct a job record that
    claims `state="running"` from a server instance that is no longer tracking its
    process (a restart between submit() and completion). PROCESS_QUERY_LIMITED_
    INFORMATION needs no special privileges for a same-user process. Deliberately
    conservative on the PID-reuse hazard: a reused PID belonging to a different process
    reads as "still alive", which only means we keep reporting `running` rather than
    incorrectly flipping a genuinely-running job to `failed`."""
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill `proc` AND its descendant processes on Windows via `taskkill /F /T`, not
    just the immediate child `asyncio.subprocess.Process` handle. A real, confirmed gap:
    some wrapped tools (SPDSIM's sub-process launch pattern, per `core.tool_status`'s
    `spdsim` note) spawn child workers of their own; a bare `proc.kill()` only ever
    killed the immediate parent, leaving detached grandchild processes running after a
    `cancel_job` call reported success. Falls back to a plain `proc.kill()` if
    `taskkill` itself is unavailable or fails, so the immediate child is still killed
    even in that case."""
    try:
        tree_kill = await asyncio.create_subprocess_exec(
            "taskkill", "/F", "/T", "/PID", str(proc.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await tree_kill.wait()
    except OSError:
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass  # already dead -- taskkill (or a natural exit) beat us to it


def _read_tail_text(path: Path, max_bytes: int) -> str:
    """Read at most the last `max_bytes` of a file, never the whole thing.

    Critical for safety against a runaway/huge log (a real incident on this machine
    reached ~150GB — see `max_log_bytes` in core.config) — `path.read_text()` on a file
    that size would exhaust memory (or, worse, get embedded whole into an LLM
    conversation via a calling tool) long before any caller-supplied line/size limit
    had a chance to trim it back down.
    """
    size = _safe_stat_size(path)
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read()
    return data.decode("utf-8", errors="replace")


@dataclass
class JobRecord:
    job_id: str
    tool: str
    command: list[str]
    job_dir: str
    state: str = "pending"  # pending -> running -> succeeded|failed|timeout
    pid: Optional[int] = None
    returncode: Optional[int] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    log_path: str = ""
    license_issue_suspected: bool = False
    runaway_log_killed: bool = False
    """True if JobManager force-killed this job because its log file exceeded
    `settings.max_log_bytes` — the tool entered an unbounded output loop rather than
    genuinely running long. See core.config's `max_log_bytes` docstring for the real
    incident this guards against."""

    stall_timeout_killed: bool = False
    """True if JobManager force-killed this job because its log file went completely
    silent (zero byte growth) for `settings.job_stall_timeout_seconds`. See
    core.config's `job_stall_timeout_seconds` docstring for the confirmed real failure
    modes this guards against (an un-dismissed modal product-choice/welcome dialog,
    Celsius3D's confirmed post-completion idle-stall). A job killed this way may still
    have genuinely completed real work and written real output files before going
    silent (this is exactly what happens in the Celsius3D case) — check
    `list_job_files`/output content before assuming nothing happened, don't trust
    state="failed" alone."""

    failure_note: str = ""
    """Populated only for one narrow, well-defined ambiguous-failure shape: a negative
    (NT-status-range) return code, no license-related keyword in the log, and a
    near-empty (<4KB) log -- too little signal to tell a silent abort (often a GUI
    product-choice/welcome dialog or stale design-lock prompt on this
    no-license-required install), a crash, a modal-dialog hang, and a watchdog kill
    apart. Empty string for every other failure, so its presence is itself a precise
    signal. See the assignment site in `_watch` for the full note text and
    `core.tool_status`'s per-tool notes for any known negative-rc signature this
    specific tool has."""

    gui_tool: bool = False
    """True when this job was launched via the core.gui_tool_runner GUI path (the
    tool opens real windows and blocks on interactive startup dialogs on this
    PREMIUM / no-license-required install). For such jobs the console-log heuristics
    do not apply: run.log is empty BY DESIGN (a GUI tool writing zero bytes is its
    normal state), so `license_issue_suspected` must never be read as evidence of a
    license problem, and 'needs_user_intervention' means a human must click through
    the screen, not that a license is missing."""

    gui_tool_result: str = ""
    """`core.gui_tool_runner.GuiToolResult.to_dict()` serialized to JSON, captured by
    the GUI runner's side-task the moment it observes the tool's outcome: runner
    `status`, `screenshots` (screen_01.png... under screenshots/ in the job dir),
    `dismissed_dialogs`, `error`, `returncode`. Empty string for console jobs and for
    GUI jobs whose outcome is not yet known (state still 'running') --
    running_long/timeout outcomes keep the job 'running' on purpose so the caller can
    keep polling or cancel explicitly."""

    def save(self) -> None:
        Path(self.job_dir, "job.json").write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._dismiss_watchers: dict[str, win32gui_helper.DismissWatcher] = {}
        self._gui_launches: set[str] = set()
        self._gui_running_long: set[str] = set()

    def new_job_dir(self, tool: str) -> tuple[str, Path]:
        job_id = f"{tool}-{uuid.uuid4().hex[:10]}"
        job_dir = settings.resolve_workdir() / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_id, job_dir

    async def submit(
        self,
        tool: str,
        command: list[str],
        job_dir: Path,
        job_id: str,
        dismiss_dialogs: bool = False,
        stall_timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> JobRecord:
        """`extra_env`, if given, is merged on top of this server's own environment
        (never replacing it) for this one launched process only -- e.g.
        `core.tclsession.run_session` sets `ENABLE_CAPTURE_AUTOMATION=TRUE` for every
        `tool="capture"` launch. This is a real, Cadence-provided switch (confirmed by
        reading `tools/capture/tclscripts/capOrCADStartPage/startpage.tcl`'s own source):
        when set, Capture's embedded CEF "Start Page" widget is skipped entirely instead
        of making its normal startup call (`orPrm::RequestURL ... $orPrm::WF_CEF ... {1}`
        -- a *synchronous* CEF network request) to `https://pcb.cadence.com/startpage/
        health`. On a machine whose WinHTTP system proxy demands authentication (common
        behind a corporate gateway), that request can never complete non-interactively --
        CEF raises a native, unanswerable Windows "Proxy Server Credential" dialog and the
        whole process blocks on it forever, pegging one core at ~100% CPU with zero log
        output and zero *visible* windows of its own (the credential prompt is a separate
        top-level window, easy to miss when watching only the main Capture window).
        CONFIRMED LIVE on this exact install: reproduced the hang with the env var unset
        (indefinite CPU climb, no log, Capture Custom Launch crash-recovery dialog on the
        next relaunch from the resulting unclean exit), then reproduced a clean, idle
        startup with it set -- same machine, same proxy, same install, only this one
        env var different. This is almost certainly the real root cause of this suite's
        long-standing `capture` `known_blocked` status (previously attributed solely to
        the `Open <project>` step itself); see `core.tool_status.TOOL_STATUS_NOTES["capture"]`
        for the full writeup and what is/isn't fixed by it.

        `dismiss_dialogs=True` starts a `win32gui_helper.DismissWatcher` against this
        job's pid for its whole lifetime -- for interactive Cadence GUI launches (Allegro
        session jobs: `allegro.exe -s <script> <board>`) that can raise a modal dialog
        mid-startup with nothing else present to click it. See `DismissWatcher`'s
        docstring for the confirmed live failure mode this closes. Batch-only tools
        (report.exe, batch_drc.exe, ...) never pass this -- they have no GUI to dismiss
        a dialog from in the first place.

        `stall_timeout_seconds` overrides `settings.job_stall_timeout_seconds` for this
        one job -- pass `None` (the default) to keep the global default. See
        `core.tclsession.run_session`'s use of this for why Allegro/Capture interactive
        sessions need a much shorter override than long batch simulations.

        GUI tools (PowerDC/PowerSI/XtractIM/... on this PREMIUM no-license-required
        install) open windows and their run.log is empty BY DESIGN (confirmed:
        PowerSI and OptimizePI have produced a fully successful 0-byte run.log),
        so the log-silence stall watchdog is meaningless for them. For any
        command whose first token's exe stem is in
        `core.gui_tool_runner.GUI_TOOL_EXE_NAMES`, submit() launches the process
        the normal way (so proc/_procs/cancel()/stale-state correction in
        get()/wait() all keep working) and then starts the screen-based runner
        task `_gui_observe` (core.gui_tool_runner.run_gui_tool): pyautogui
        screenshots every 2s into screenshots/ in the job dir, dialog dismissal
        via the common confirm buttons, and an honest outcome written to the
        record's `gui_tool_result`.
          * 'running_long' (still running after the stall-timeout window) keeps
            the job 'running' on purpose: it is a real long simulator run, not a
            hang -- the caller polls or cancel()s it, and cancel() still works
            because the proc handle is in _procs. Screenshots keep accumulating
            for the process's whole lifetime (attach mode);
          * 'needs_user_intervention' (a dialog survived all dismissal attempts,
            STUCK_Here screenshot saved) becomes the job's state -- a human must
            click, NEVER a license label. The process is left alive so the job
            stays cancellable and the screenshots readable;
          * the process's real exit is still finalized by `_watch` (the
            completion authority); the runner only adds gui_tool_result and the
            needs_user_intervention state on top of it.
        """
        log_path = job_dir / "run.log"
        record = JobRecord(
            job_id=job_id,
            tool=tool,
            command=command,
            job_dir=str(job_dir),
            state="running",
            started_at=time.time(),
            log_path=str(log_path),
        )
        self._jobs[job_id] = record

        # GUI tools (PowerDC/PowerSI/XtractIM/... on this PREMIUM no-license-required
        # install) open real windows and block on interactive startup dialogs; their
        # console log is empty BY DESIGN. For these, the job is launched the normal
        # way (so _procs/cancel/stale-state correction keep working) plus a
        # screen-based runner (screenshot every 2s, dialog dismissal,
        # needs_user_intervention / running_long reporting) -- see submit() docstring
        # and `JobRecord.gui_tool`.
        gui_tool = False
        try:
            gui_tool = gui_tool_runner.is_gui_tool(command[0])
        except Exception:
            gui_tool = False

        log_file = open(log_path, "wb")
        env = {**os.environ, **extra_env} if extra_env else None
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(job_dir),
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        record.pid = proc.pid
        self._procs[job_id] = proc
        if dismiss_dialogs:
            try:
                self._dismiss_watchers[job_id] = win32gui_helper.spawn_dismiss_watcher(proc.pid)
            except Exception:
                pass  # never let watcher setup block/break the job launch itself
        if gui_tool:
            record.gui_tool = True
            record.save()
            self._gui_launches.add(job_id)
            asyncio.create_task(self._gui_observe(job_id, proc, stall_timeout_seconds))
        asyncio.create_task(
            self._watch(job_id, proc, log_file, stall_timeout_seconds, stall_disabled=gui_tool)
        )
        return record

    async def _gui_observe(
        self,
        job_id: str,
        proc: asyncio.subprocess.Process,
        stall_timeout_seconds: int | None,
    ) -> None:
        """Screen-based runner pass for a GUI job (see submit's docstring).

        `run_gui_tool` LAUNCHES a short-lived monitoring session against the
        already-running tool process: it screenshots the screen every 2s into
        `runs/<job_id>/screenshots/` and dismisses dialogs while it lasts, but
        it does NOT own the process and never reaps anything except its own
        launch attempt. Only TWO outcomes are acted on here:
        - "running_long" -> the tool is a genuine long run (still alive after
          the timeout window): the job STAYS 'running', `_watch` keeps running
          with the log-stall watchdog disabled (an empty log is a GUI tool's
          normal state) and only the runaway-log size watchdog plus cancel()
          remain available. `_watch` finalizes the record on the process's
          real exit. Nothing else to do.
        - "needs_user_intervention" -> a dialog survived every dismissal
          attempt (STUCK_Here screenshot saved). This install is PREMIUM /
          no-license-required, so the only honest explanation for an un-clicked
          dialog is "a human has to click it" -- NEVER a license failure,
          never a stall label. Set that state on the record (a human, or an
          agent driving the desktop, must act; cancel() still terminates the
          job if the caller gives up). We deliberately do NOT kill the process
          from here: the job stays cancellable and its screenshots stay
          readable.
        Every OTHER runner outcome (success/failed/timeout from the monitoring
        pass, or a headless-host degradation) is stored verbatim on
        `gui_tool_result`; the process's own normal lifecycle (via `_watch`)
        then finalizes the record, exactly like a console tool.
        """
        record = self._jobs.get(job_id)
        if record is None:
            return
        timeout_s = stall_timeout_seconds
        if timeout_s is None:
            timeout_s = settings.job_stall_timeout_seconds or settings.default_timeout_seconds

        def _on_running_long(_timeout: float) -> None:
            # One-shot: the tool outlived the 'quick run' window. The job
            # stays 'running' (it's a long simulator run, not a hang); just
            # surface RUNNING_LONG on the record so a status() call made
            # while the run is in progress tells the caller the truth.
            rec = self._jobs.get(job_id)
            if rec is None:
                return
            self._gui_running_long.add(job_id)
            if rec.state == "running":
                # Keep state 'running' (the process is alive and producing
                # screenshots); RUNNING_LONG is signalled via gui_tool_result
                # error notes and the _gui_running_long bookkeeping set, and
                # via the `note` in _record_to_dict for GUI tools.
                rec.save()

        try:
            result = await gui_tool_runner.run_gui_tool(
                exe_path=Path(record.command[0]),
                args=[],
                workdir=Path(record.job_dir),
                timeout_s=float(timeout_s),
                job_name=job_id,
                pid=proc.pid,  # ATTACH mode: we already launched it
                on_running_long=_on_running_long,
            )
        except Exception as e:  # the runner must never break the job itself
            result = gui_tool_runner.GuiToolResult(
                status="failed",
                screenshots=[],
                dismissed_dialogs=[],
                error=f"gui runner internal error: {type(e).__name__}: {e}",
                returncode=None,
            )
        record = self._jobs.get(job_id)
        if record is None:
            return
        record.gui_tool_result = json.dumps(result.to_dict())
        # Attach-mode outcomes:
        #  - needs_user_intervention: dialog survived dismissal; mark the job
        #    (process is left alive so the human/cancel() can still act).
        #  - success / failed: the process exited on its own; _watch will
        #    finalize state from proc.wait() (authoritative rc); we only
        #    surface the richer gui_tool_result alongside.
        #  - running_long shouldn't return in attach mode (monitoring
        #    continues until exit), but if an executor-side timeout fired
        #    first we still keep the job running.
        if result.status == "needs_user_intervention" and record.state == "running":
            record.state = "needs_user_intervention"
        record.save()

    def _stop_dismiss_watcher(self, job_id: str) -> None:
        """Signal and join the job's DismissWatcher thread (if any) WITHOUT blocking the
        asyncio event loop that every other concurrent MCP tool call shares -- `.stop()`
        itself is a blocking call (thread.join()), so it runs on the default executor's
        worker thread instead of inline here."""
        watcher = self._dismiss_watchers.pop(job_id, None)
        if watcher is not None:
            try:
                asyncio.get_running_loop().run_in_executor(None, watcher.stop)
            except RuntimeError:  # no running loop (e.g. cancel() called from sync code)
                watcher.stop()

    async def _watch(
        self,
        job_id: str,
        proc: asyncio.subprocess.Process,
        log_file,
        stall_timeout_seconds: int | None = None,
        stall_disabled: bool = False,
    ) -> None:
        log_path = Path(log_file.name)
        runaway_flag = {"killed": False}
        stall_flag = {"killed": False}

        async def size_watchdog() -> None:
            # Fully independent of the completion signal below — never touches
            # `proc.wait()` itself, only `proc.kill()` if the log grows too large.
            # An earlier version had this watchdog itself co-own the completion
            # signal (wrapping `proc.wait()` in a reusable Task, polled via
            # `asyncio.wait(..., timeout=...)`), which reproducibly caused two
            # distinct real problems on this machine's (Windows/Proactor) event
            # loop: every single job took a full extra `log_watchdog_poll_seconds`
            # to be detected as complete (185 tests x ~2s each turned an ~12s test
            # suite into 5+ minutes), and it was still intermittently unreliable
            # (a job occasionally never got marked complete at all). Keeping this
            # watchdog fully separate from the one proven-reliable completion path
            # below (a bare, single `await proc.wait()`) avoids both.
            while True:
                await asyncio.sleep(settings.log_watchdog_poll_seconds)
                if _safe_stat_size(log_path) > settings.max_log_bytes:
                    runaway_flag["killed"] = True
                    proc.kill()
                    return

        async def stall_watchdog() -> None:
            # Same "fully independent, only ever calls proc.kill(), never touches
            # proc.wait()" shape as size_watchdog above, for the opposite failure
            # shape: not too much output, but none at all for too long. See
            # `settings.job_stall_timeout_seconds`'s docstring for exactly which real
            # failure modes this is a last-resort safety net for (DismissWatcher /
            # a modal product-choice/welcome dialog wait / Celsius3D's confirmed
            # post-completion idle-stall).
            if stall_disabled:
                return  # GUI tool: empty log is its NORMAL state (see submit docstring)
            limit = (
                settings.job_stall_timeout_seconds
                if stall_timeout_seconds is None
                else stall_timeout_seconds
            )
            if limit <= 0:
                return  # disabled
            last_size = -1
            last_change = time.monotonic()
            while True:
                await asyncio.sleep(settings.stall_watchdog_poll_seconds)
                size = _safe_stat_size(log_path)
                now = time.monotonic()
                if size != last_size:
                    last_size = size
                    last_change = now
                    continue
                if now - last_change >= limit:
                    stall_flag["killed"] = True
                    proc.kill()
                    return

        watchdog_task = asyncio.ensure_future(size_watchdog())
        stall_task = asyncio.ensure_future(stall_watchdog())
        returncode = await proc.wait()
        self._stop_dismiss_watcher(job_id)
        self._gui_running_long.discard(job_id)
        self._gui_launches.discard(job_id)
        for t in (watchdog_task, stall_task):
            t.cancel()
        for t in (watchdog_task, stall_task):
            try:
                await t
            except asyncio.CancelledError:
                pass
        runaway = runaway_flag["killed"]
        stalled = stall_flag["killed"]
        if returncode > 0x7FFFFFFF:
            returncode -= 0x100000000
        log_file.close()
        record = self._jobs[job_id]
        record.returncode = returncode
        record.ended_at = time.time()
        # cancel() already set state="cancelled" synchronously before killing the
        # process; this task was already awaiting proc.wait() at that point and would
        # otherwise overwrite it with "failed" once the kill's exit code arrives — a
        # cancelled job must stay reported as cancelled, not misreported as a failure.
        # The GUI observer's "needs_user_intervention" (a dialog a human must click)
        # gets the same protection: reaching here at all means the process has exited
        # (the human unblocked it and the tool proceeded, or it was cancelled), so
        # below the honest return-code outcome overwrites the intervention state.
        if runaway:
            record.state = "failed"
            record.runaway_log_killed = True
        elif stalled and record.state not in ("cancelled", "needs_user_intervention"):
            # A genuine race is possible here: proc.wait() and stall_watchdog's own
            # proc.kill() can both be "about to resolve" in the same instant a normal
            # completion was already happening on its own — stalled only overrides the
            # outcome when the job wasn't already explicitly cancelled by a caller.
            record.state = "failed"
            record.stall_timeout_killed = True
        elif record.state not in ("cancelled", "needs_user_intervention"):
            record.state = "succeeded" if returncode == 0 else "failed"
        elif record.state == "needs_user_intervention" and returncode == 0:
            # The human clicked through the dialog and the tool then completed
            # normally — report the honest success, not the stale intervention state.
            record.state = "succeeded"
        try:
            tail = _read_tail_text(log_path, max_bytes=1024 * 1024).lower()
            record.license_issue_suspected = any(m in tail for m in _LICENSE_MARKERS)
            if record.gui_tool:
                # This install is PREMIUM / no-license-required: for GUI tools the log
                # is empty BY DESIGN, so the keyword scan is pure noise and must never
                # be surfaced as a suspected license problem for them.
                record.license_issue_suspected = False
        except OSError:
            pass
        if (
            record.state == "failed"
            and (record.returncode or 0) < 0
            and not record.license_issue_suspected
            and _safe_stat_size(log_path) < 4096
        ):
            record.failure_note = (
                "Negative return code with a near-empty log and no license-related "
                "markers — the cause is AMBIGUOUS (a silent abort, on this "
                "no-license-required install most often a GUI product-choice/welcome "
                "dialog or stale .lck design-lock prompt left un-clicked; vs. a crash; "
                "vs. a modal-dialog hang; vs. a watchdog kill). No tool in this suite "
                "fails for a real license reason, so do NOT read this as evidence of a "
                "license problem. Do not auto-retry on this flag alone. Run the "
                "inspection trio: tail_job_log(job_id), check_design_lock(design_path) "
                "(a silent Allegro/Capture failure typically orphans a .lck), and check "
                "for real artifacts in the input file's own directory. See "
                "core.tool_status's per-tool note for this tool's known negative-rc "
                "signature, if any."
            )
        record.save()

    def get(self, job_id: str) -> JobRecord:
        if job_id in self._jobs:
            return self._jobs[job_id]
        job_dir = settings.resolve_workdir() / job_id
        job_json = job_dir / "job.json"
        if job_json.is_file():
            data = json.loads(job_json.read_text(encoding="utf-8"))
            record = JobRecord(**data)
            if record.state == "running" and record.pid is not None and not _pid_alive(record.pid):
                # This server instance never observed this job's completion (it was
                # submitted by an earlier server process that restarted/crashed before
                # the process exited) -- the OS confirms the PID is gone, so the stale
                # "running" state is corrected here rather than lying forever. The real
                # exit code is unknowable at this point; leave it unset rather than
                # inventing one.
                record.state = "failed"
                record.returncode = None
                record.ended_at = time.time()
                record.save()
            return record
        raise JobNotFoundError(f"No job found with id '{job_id}'")

    async def wait(self, job_id: str, timeout: float) -> JobRecord:
        record = self.get(job_id)
        proc = self._procs.get(job_id)
        if proc is None:
            if record.state == "running":
                # `get()` already re-checks PID liveness when it reads this record off
                # disk and corrects a truly-dead process to "failed" -- so reaching
                # "running" here with no live proc handle means either the OS says the
                # PID is still genuinely alive (truly unwaitable from this server
                # instance), or `record` came from the in-memory dict without a disk
                # round-trip. Re-check directly rather than assume the worse case.
                if record.pid is not None and not _pid_alive(record.pid):
                    record.state = "failed"
                    record.returncode = None
                    record.ended_at = time.time()
                    record.save()
                    return record
                raise JobStillRunningError(
                    f"Job '{job_id}' is running in a process this server instance is not "
                    "tracking (likely a previous server run) — poll status()/tail_log() instead."
                )
            return record
        # Poll this job's OWN record/state instead of calling `proc.wait()` directly.
        # `_watch()` (started once per job in `submit()`) is the sole owner of
        # `proc.wait()` for a given process — confirmed via direct testing that a
        # second concurrent caller awaiting the same asyncio subprocess's `.wait()`
        # (even via `asyncio.wait_for`) causes `_watch`'s own completion notification to
        # never fire on this machine's (Windows/Proactor) event loop, leaving the job
        # stuck reporting "running" forever even after the real process has exited.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # "running" and "needs_user_intervention" are both non-terminal from the
            # CALLER's point of view: the process may still exit (the human unblocks
            # the dialog and the tool proceeds, or the caller cancels). wait() polls
            # until one of {succeeded, failed, cancelled, timeout} happens.
            if self._jobs[job_id].state not in ("running", "needs_user_intervention"):
                break
            await asyncio.sleep(0.05)
        return self.get(job_id)

    async def cancel(self, job_id: str) -> tuple[JobRecord, str]:
        """Returns `(record, outcome)` where `outcome` is one of:
        - "killed" — a live process handle was found and killed (the normal case).
        - "already-terminal" — the job had already finished; nothing to kill.
        - "no-live-handle" — `record.state` is still "running" but this server instance
          holds no process handle for it (submitted by an earlier server run). NO kill
          is performed in this case — silently returning the unchanged record here (the
          previous behavior) looked identical to a successful cancel from the caller's
          side, with the real process left running undetected.
        """
        record = self.get(job_id)
        proc = self._procs.get(job_id)
        if proc is None:
            return record, "no-live-handle"
        # "needs_user_intervention" (GUI job waiting on a human to click a dialog) is
        # non-terminal too: the process is still alive and must be killable.
        if record.state not in ("running", "needs_user_intervention"):
            return record, "already-terminal"
        await _kill_process_tree(proc)
        record.state = "cancelled"
        record.ended_at = time.time()
        record.save()
        self._stop_dismiss_watcher(job_id)
        return record, "killed"

    def tail_log(self, job_id: str, max_lines: int) -> list[str]:
        record = self.get(job_id)
        if not record.log_path or not Path(record.log_path).is_file():
            return []
        # Bounded-bytes read first (never loads a multi-GB file whole — see
        # _read_tail_text), THEN split into lines and cap by count. A truncated first
        # line at the byte boundary is an acceptable trade-off; unbounded memory use
        # from a runaway log is not.
        text = _read_tail_text(Path(record.log_path), max_bytes=4 * 1024 * 1024)
        lines = text.splitlines()
        cap = min(max_lines, settings.max_log_tail_lines)
        return lines[-cap:]

    def list_output_files(self, job_id: str) -> list[str]:
        record = self.get(job_id)
        job_dir = Path(record.job_dir)
        return sorted(str(p.relative_to(job_dir)) for p in job_dir.rglob("*") if p.is_file())

    def list_jobs(self) -> list[JobRecord]:
        return list(self._jobs.values())


job_manager = JobManager()


def crash_signature(record: JobRecord) -> Optional[dict]:
    """Detect a tool *crash* (not a clean error-exit) from a finished job record.

    A crash is the combination of a Windows NT-status code exit (the 0xC0000005 access-violation
    family, which the OS reports as an *unsigned* 32-bit value because a signed negative
    exit code cannot be returned through the normal API) plus a non-empty log. This is the
    exact fingerprint of `spif_batch.exe -i` on this installation: it prints
    `ERROR(SPMHDB-238): The design is corrupted...` and then dies with a real
    `..._AllegroMiniDump.dmp` file and exit code 3221225477 (0xC0000005). A clean
    error-exit (rc 4, rc 2, etc.) has a small positive return code and never matches —
    so callers can stop confusing "the route finished with warnings" with "the process
    crashed". Returns None when the record does not look like a crash.
    """
    rc = record.returncode
    if rc is None:
        return None
    code = rc if rc <= 0x7FFFFFFF else rc  # keep the unsigned form for the 0xC0... codes
    if code < 0xC0000000:
        return None
    tail = ""
    try:
        tail = _read_tail_text(Path(record.log_path), max_bytes=64 * 1024)
    except (OSError, TypeError):
        tail = ""
    return {
        "is_crash": True,
        "nt_status": f"0x{code:08X}",
        "message": (tail.strip().splitlines() or [""])[-1].strip(),
        "note": (
            "Process exited with a Windows NT status code (not a normal tool exit code) — "
            "this is a crash, not a clean error. For spif_batch.exe -i this is the known "
            "SPMHDB-238 import crash; the export/route half of the pipeline is unaffected."
        ),
    }
