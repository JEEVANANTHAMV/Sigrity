"""Two ways to invoke a Sigrity executable: a quick blocking call, or a tracked background job."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from sigrity_mcp.core import executables
from sigrity_mcp.core.jobs import JobRecord, job_manager
from sigrity_mcp.core.tclscript import TclScript


async def run_quick(tool: str, args: list[str], timeout: float = 60.0, cwd: Optional[Path] = None) -> dict:
    """Run a short-lived command (version/license/info queries) and wait for it to finish.

    Not for simulations/extractions — those go through `submit_job` so they don't block
    the MCP call for the run's full duration.
    """
    exe = executables.resolve(tool)
    proc = await asyncio.create_subprocess_exec(
        str(exe),
        *args,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        timed_out = False
    except asyncio.TimeoutError:
        proc.kill()
        stdout = b""
        timed_out = True
    return {
        "tool": tool,
        "command": [str(exe), *args],
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "output": stdout.decode(errors="replace"),
    }


async def submit_job(
    tool: str,
    build_args: list[str] | None = None,
    tcl_script: Optional[TclScript] = None,
    tcl_arg_flag: str = "-TCL",
    extra_args: list[str] | None = None,
) -> JobRecord:
    """Write `tcl_script` (if given) into a fresh job directory, then launch `tool` against it.

    `build_args` are literal argv tokens placed before the tcl flag (e.g. an input file path).
    `extra_args` are appended after the tcl script argument.
    Returns immediately once the process has been *started*; use job_manager.status()/wait()
    to track completion.
    """
    exe = executables.resolve(tool)
    job_id, job_dir = job_manager.new_job_dir(tool)

    argv: list[str] = list(build_args or [])
    if tcl_script is not None:
        script_path = tcl_script.write(job_dir / "macro.tcl")
        argv += [tcl_arg_flag, str(script_path)]
    argv += list(extra_args or [])

    command = [str(exe), *argv]
    return await job_manager.submit(tool=tool, command=command, job_dir=job_dir, job_id=job_id)
