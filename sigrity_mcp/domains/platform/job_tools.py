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
from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.mcp_app import mcp


def _record_to_dict(record) -> dict:
    return {
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
    }


@mcp.tool
async def get_job_status(job_id: str) -> dict:
    """Get the current state of a background Sigrity job started by any run_* tool.

    Returns state one of: pending, running, succeeded, failed, cancelled, timeout.
    `license_issue_suspected=True` means the process's own log contains a recognizable
    FlexNet/license-denial message — check `tail_job_log` for the exact text before
    concluding the run failed for a different reason.
    """
    try:
        return _record_to_dict(job_manager.get(job_id))
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def wait_for_job(job_id: str, timeout_seconds: float = 60.0) -> dict:
    """Block until a background job finishes or `timeout_seconds` elapses, then report its state.

    If the job is still 'running' when this returns, the timeout was hit — call this
    again (Sigrity simulations can legitimately run for a long time) or poll
    get_job_status instead of waiting indefinitely in one call.
    """
    try:
        record = await job_manager.wait(job_id, timeout=timeout_seconds)
        return _record_to_dict(record)
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def tail_job_log(job_id: str, max_lines: int = 200) -> dict:
    """Return the last `max_lines` lines of a job's combined stdout/stderr log.

    Use this to see solver progress messages, warnings, or the specific error text when
    a job fails — the state alone (from get_job_status) only tells you pass/fail.
    """
    try:
        lines = job_manager.tail_log(job_id, max_lines=max_lines)
        return {"job_id": job_id, "line_count": len(lines), "lines": lines}
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def list_job_files(job_id: str) -> dict:
    """List every output file a job's working directory contains (paths relative to it).

    Includes the macro.tcl that was generated and run, run.log, job.json, and whatever
    result artifacts the Sigrity tool wrote (Touchstone .sNp, reports, SPICE models, ...).
    Follow up with read_job_output_file to inspect a specific one.
    """
    try:
        files = job_manager.list_output_files(job_id)
        return {"job_id": job_id, "file_count": len(files), "files": files}
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def read_job_output_file(job_id: str, relative_path: str, max_lines: int = 80) -> dict:
    """Read one output file from a job's directory (path from list_job_files), auto-detecting its kind.

    Touchstone files (.s1p/.s2p/.s4p/...) get a header/metadata summary instead of a raw
    dump (the numeric matrix can be huge); text reports/logs/CSVs get a head+tail preview
    capped at `max_lines`. Binary/unrecognized files are reported by size only.
    """
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
    """Forcibly kill a still-running background job (e.g. a simulation started with wrong inputs)."""
    try:
        record = job_manager.cancel(job_id)
        return _record_to_dict(record)
    except JobNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def list_all_jobs(state: Literal["any", "running", "succeeded", "failed"] = "any") -> dict:
    """List every job this server instance has launched since it started, optionally filtered by state.

    Only covers jobs from the current server process's lifetime (in-memory) — jobs from a
    previous run are still inspectable individually via get_job_status/list_job_files if
    you know their job_id, but won't appear in this listing.
    """
    jobs = job_manager.list_jobs()
    if state != "any":
        jobs = [j for j in jobs if j.state == state]
    return {"count": len(jobs), "jobs": [_record_to_dict(j) for j in jobs]}
