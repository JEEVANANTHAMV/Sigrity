"""Generic job-control tools shared by every domain.

Every `run_*` tool in this suite (PowerSI simulation, Clarity3D extraction, PowerDC
analysis, ...) launches its Sigrity process as a background job and returns a job_id
immediately instead of blocking. These tools are how a caller then tracks that job to
completion and retrieves its results — they work identically no matter which domain or
Sigrity tool started the job.
"""

from __future__ import annotations

from typing import Literal

from sigrity_mcp.core import results as result_parsers
from sigrity_mcp.core.errors import JobNotFoundError
from sigrity_mcp.core.jobs import crash_signature, job_manager
from sigrity_mcp.mcp_app import mcp


def _record_to_dict(record) -> dict:
    out = {
        "job_id": record.job_id,
        "tool": record.tool,
        "state": record.state,
        "pid": record.pid,
        "returncode": record.returncode,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "job_dir": record.job_dir,
        "log_path": record.log_path,
        "license_issue_suspected": record.license_issue_suspected,
        # Both booleans below default False and were previously set on JobRecord but
        # never surfaced past this function to any MCP tool caller -- a caller polling
        # get_job_status/wait_for_job on a job JobManager force-killed for a runaway
        # (too much) or stalled (too little, see core.config's job_stall_timeout_seconds)
        # log had no way to learn *why* state="failed" without reading job.json off disk
        # directly. Surfaced here so the reason reaches the caller through the same
        # tool-facing dict every other field already does.
        "runaway_log_killed": record.runaway_log_killed,
        "stall_timeout_killed": getattr(record, "stall_timeout_killed", False),
    }
    if out["runaway_log_killed"]:
        out["note"] = (
            "JobManager force-killed this job because its log file exceeded "
            "max_log_bytes (a runaway/unbounded output loop, not a genuine long-running "
            "result) -- see core.config's max_log_bytes docstring."
        )
    elif out["stall_timeout_killed"]:
        out["note"] = (
            "JobManager force-killed this job because its log went completely silent "
            "(zero byte growth) for job_stall_timeout_seconds -- a likely hung/stuck "
            "process (an undismissed dialog, a license wait, or a post-completion "
            "idle-stall like Celsius3D's confirmed behavior), not necessarily a clean "
            "failure. Check list_job_files/read_job_output_file before assuming no real "
            "work happened -- a stalled job can still have written complete, genuine "
            "results before going silent."
        )
    sig = crash_signature(record)
    if sig is not None:
        out["crash"] = sig
    return out


@mcp.tool
async def get_job_status(job_id: str) -> dict:
    """Get the current state of a background Sigrity job started by any run_* tool.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    try:
        return _record_to_dict(job_manager.get(job_id))
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def wait_for_job(job_id: str, timeout_seconds: float = 60.0) -> dict:
    """Block until a background job finishes or `timeout_seconds` elapses, then report its state.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    try:
        record = await job_manager.wait(job_id, timeout=timeout_seconds)
        return _record_to_dict(record)
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def tail_job_log(job_id: str, max_lines: int = 200) -> dict:
    """Return the last `max_lines` lines of a job's combined stdout/stderr log.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    try:
        lines = job_manager.tail_log(job_id, max_lines=max_lines)
        return {"job_id": job_id, "line_count": len(lines), "lines": lines}
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def list_job_files(job_id: str) -> dict:
    """List every output file a job's working directory contains (paths relative to it).
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    try:
        files = job_manager.list_output_files(job_id)
        return {"job_id": job_id, "file_count": len(files), "files": files}
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def read_job_output_file(job_id: str, relative_path: str, max_lines: int = 80) -> dict:
    """Read one output file from a job's directory (path from list_job_files), auto-detecting its kind.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    try:
        record = job_manager.get(job_id)
    except JobNotFoundError as exc:
        return {"error": str(exc)}

    from pathlib import Path

    path = Path(record.job_dir) / relative_path
    if not path.is_file():
        return {"error": f"'{relative_path}' does not exist under job {job_id}'s directory"}

    kind = result_parsers.classify_output(path)
    if kind == "touchstone":
        return {"kind": kind, **result_parsers.touchstone_summary(path)}
    if kind in {"text_report", "csv", "spice_netlist", "sigrity_design"}:
        return {"kind": kind, **result_parsers.text_preview(path, max_lines=max_lines)}
    return {"kind": kind, "path": str(path), "size_bytes": path.stat().st_size}


@mcp.tool
async def cancel_job(job_id: str) -> dict:
    """Forcibly kill a still-running background job (e.g. a simulation started with wrong inputs).
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    try:
        record = job_manager.cancel(job_id)
        return _record_to_dict(record)
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def list_all_jobs(state: Literal["any", "running", "succeeded", "failed"] = "any") -> dict:
    """List every job this server instance has launched since it started, optionally filtered by state.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    jobs = job_manager.list_jobs()
    if state != "any":
        jobs = [j for j in jobs if j.state == state]
    return {"count": len(jobs), "jobs": [_record_to_dict(j) for j in jobs]}
