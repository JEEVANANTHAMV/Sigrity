"""Launch a fresh Capture batch job (via the suite's own job_manager, not a new
MCP tool) and poll every N seconds: (a) is the job still running, (b) is a
"Capture Custom Launch" dialog present, (c) if present, click it, and record what
happened. This isolates the dialog-click mechanism from the rest of the pipeline."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core import executables
from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.capture_tools import (
    _click_button_in_window,
    _find_window,
)

MACRO = "C:/Users/aicoe/Desktop/Sigrity/runs/capture-fcba492937/macro.tcl"


async def main():
    exe = executables.resolve("capture")
    job_id, job_dir = job_manager.new_job_dir("capture")
    log_path = open(job_dir / "run.log", "wb")
    proc = await asyncio.create_subprocess_exec(
        str(exe),
        "-product=OrCAD Capture",
        MACRO,
        cwd=str(job_dir),
        stdout=log_path,
        stderr=asyncio.subprocess.STDOUT,
    )
    record = job_manager._jobs.setdefault(
        job_id,
        type("R", (), {})(),
    )
    # Manually wire into job_manager with a real JobRecord-like object by reusing submit's internals
    from sigrity_mcp.core.jobs import JobRecord

    rec = JobRecord(
        job_id=job_id,
        tool="capture",
        command=[str(exe), "-product=OrCAD Capture", MACRO],
        job_dir=str(job_dir),
        state="running",
        pid=proc.pid,
        log_path=str(job_dir / "run.log"),
        started_at=time.time(),
    )
    job_manager._jobs[job_id] = rec
    job_manager._procs[job_id] = proc
    asyncio.create_task(job_manager._watch(job_id, proc, log_path))

    print(f"started pid={proc.pid} job_id={job_id}")
    t0 = time.time()
    last_state = None
    while time.time() - t0 < 120:
        await asyncio.sleep(5)
        cur = job_manager.get(job_id)
        size = (job_dir / "run.log").stat().st_size if (job_dir / "run.log").is_file() else 0
        top = _find_window("Capture Custom Launch")
        line = f"t={time.time()-t0:5.1f}s state={cur.state:<10} log_bytes={size:<6} dialog={'YES' if top is not None else 'no'}"
        if top is not None and last_state != "clicked":
            clicked = _click_button_in_window(top, "No")
            line += f" -> clicked(No)={clicked}"
            last_state = "clicked" if clicked else "click-failed"
        elif last_state == "clicked":
            last_state = None  # only report the click once
        print(line, flush=True)
        if cur.state != "running":
            break
    print("final:", job_manager.get(job_id).state, "returncode:", job_manager.get(job_id).returncode)


if __name__ == "__main__":
    asyncio.run(main())
