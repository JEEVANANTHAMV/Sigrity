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
        returncode = await proc.wait()
        if returncode > 0x7FFFFFFF:
            returncode -= 0x100000000
        log_file.close()
        record = self._jobs[job_id]
        record.returncode = returncode
        record.ended_at = time.time()
        record.state = "succeeded" if returncode == 0 else "failed"
        try:
            tail = Path(record.log_path).read_text(encoding="utf-8", errors="replace").lower()
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
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
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
        lines = Path(record.log_path).read_text(encoding="utf-8", errors="replace").splitlines()
        cap = min(max_lines, settings.max_log_tail_lines)
        return lines[-cap:]

    def list_output_files(self, job_id: str) -> list[str]:
        record = self.get(job_id)
        job_dir = Path(record.job_dir)
        return sorted(str(p.relative_to(job_dir)) for p in job_dir.rglob("*") if p.is_file())

    def list_jobs(self) -> list[JobRecord]:
        return list(self._jobs.values())


job_manager = JobManager()
