"""Retest of OrCAD Capture's batch-script invocation (previously known_blocked/unreliable)
against a real sample .opj project, now that licensing is reportedly sorted.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.capture_tools import capture_run_session, capture_save, start_capture_session

PROJECT = "C:/Cadence/SPB_22.1/tools/capture/samples/PCB-Layout/Fault-Detector/Fault-Detector.opj"


async def main():
    session = await start_capture_session(PROJECT)
    await capture_save(session["session_id"])
    result = await capture_run_session(session["session_id"])
    job_id = result["job_id"]
    print("command:", result["command"])
    status = await job_manager.wait(job_id, timeout=60)
    print("final state:", status.state, "returncode:", status.returncode)
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        print("log:\n", log_path.read_text(errors="replace"))
    if status.state == "running":
        print("STILL RUNNING after 60s -- killing job")
        job_manager.cancel(job_id)


if __name__ == "__main__":
    asyncio.run(main())
