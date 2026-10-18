"""Retest of OrCAD Capture's batch-script invocation (known_blocked/unreliable)
against a real sample .opj project.

UPDATE: the "licensing is reportedly sorted" premise this script was written under was
WRONG — there was never a license problem. The real root cause (found later) is an
embedded Start Page widget making a blocking network call through a corporate proxy at
startup; see `core.tool_status.TOOL_STATUS_NOTES["capture"]` and
`core.jobs.JobManager.submit`'s docstring for the fix (`ENABLE_CAPTURE_AUTOMATION=TRUE`,
now applied automatically). That fix stops the HANG but does not make this script's
underlying mechanism (`capture_run_session`'s Tcl batch invocation) actually execute a
script — this smoke test still exercises a path that remains known_blocked for that
separate reason. For new work, prefer `capture_headless_tools.py`
(`extract_capture_netlist_headless` / `author_capture_schematic_headless`), which needs
no Capture.exe process at all.
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
    status = await job_manager.wait(job_id, timeout=300)
    print("final state:", status.state, "returncode:", status.returncode)
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        print("log:\n", log_path.read_text(errors="replace"))
    if status.state == "running":
        print("STILL RUNNING after 300s -- killing job")
        job_manager.cancel(job_id)


if __name__ == "__main__":
    asyncio.run(main())
