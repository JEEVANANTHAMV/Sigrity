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
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from sigrity_mcp.core import win32gui_helper
from sigrity_mcp.core.config import settings
from sigrity_mcp.core.errors import JobNotFoundError, JobStillRunningError

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
    modes this guards against (an un-dismissed modal dialog, a silent license wait,
    Celsius3D's confirmed post-completion idle-stall). A job killed this way may still
    have genuinely completed real work and written real output files before going
    silent (this is exactly what happens in the Celsius3D case) — check
    `list_job_files`/output content before assuming nothing happened, don't trust
    state="failed" alone."""

    def save(self) -> None:
        Path(self.job_dir, "job.json").write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._dismiss_watchers: dict[str, win32gui_helper.DismissWatcher] = {}

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
    ) -> JobRecord:
        """`dismiss_dialogs=True` starts a `win32gui_helper.DismissWatcher` against this
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

        log_file = open(log_path, "wb")
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(job_dir),
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
        )
        record.pid = proc.pid
        self._procs[job_id] = proc
        if dismiss_dialogs:
            try:
                self._dismiss_watchers[job_id] = win32gui_helper.spawn_dismiss_watcher(proc.pid)
            except Exception:
                pass  # never let watcher setup block/break the job launch itself
        record.save()

        asyncio.create_task(self._watch(job_id, proc, log_file, stall_timeout_seconds))
        return record

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
            # a license wait / Celsius3D's confirmed post-completion idle-stall).
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
        if runaway:
            record.state = "failed"
            record.runaway_log_killed = True
        elif stalled and record.state != "cancelled":
            # A genuine race is possible here: proc.wait() and stall_watchdog's own
            # proc.kill() can both be "about to resolve" in the same instant a normal
            # completion was already happening on its own — stalled only overrides the
            # outcome when the job wasn't already explicitly cancelled by a caller.
            record.state = "failed"
            record.stall_timeout_killed = True
        elif record.state != "cancelled":
            record.state = "succeeded" if returncode == 0 else "failed"
        try:
            tail = _read_tail_text(log_path, max_bytes=1024 * 1024).lower()
            record.license_issue_suspected = any(m in tail for m in _LICENSE_MARKERS)
        except OSError:
            pass
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
        while self._jobs[job_id].state == "running" and time.monotonic() < deadline:
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
        if record.state != "running":
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
