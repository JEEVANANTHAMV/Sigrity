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

    def save(self) -> None:
        Path(self.job_dir, "job.json").write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}

    def new_job_dir(self, tool: str) -> tuple[str, Path]:
        job_id = f"{tool}-{uuid.uuid4().hex[:10]}"
        job_dir = settings.resolve_workdir() / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_id, job_dir

    async def submit(self, tool: str, command: list[str], job_dir: Path, job_id: str) -> JobRecord:
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
        record.save()

        asyncio.create_task(self._watch(job_id, proc, log_file))
        return record

    async def _watch(self, job_id: str, proc: asyncio.subprocess.Process, log_file) -> None:
        log_path = Path(log_file.name)
        runaway_flag = {"killed": False}

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

        watchdog_task = asyncio.ensure_future(size_watchdog())
        returncode = await proc.wait()
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        runaway = runaway_flag["killed"]
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
            return JobRecord(**data)
        raise JobNotFoundError(f"No job found with id '{job_id}'")

    async def wait(self, job_id: str, timeout: float) -> JobRecord:
        record = self.get(job_id)
        proc = self._procs.get(job_id)
        if proc is None:
            if record.state == "running":
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

    def cancel(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        proc = self._procs.get(job_id)
        if proc is not None and record.state == "running":
            proc.kill()
            record.state = "cancelled"
            record.ended_at = time.time()
            record.save()
        return record

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
