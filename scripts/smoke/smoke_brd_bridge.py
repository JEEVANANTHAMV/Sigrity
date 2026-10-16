import asyncio
import json

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.si.powersi_tools import powersi_run_session, start_powersi_session
from sigrity_mcp.domains.platform.job_tools import wait_for_job


async def main():
    brd = r"C:\Users\aicoe\Desktop\Sigrity\runs\brd_bridge_test\board.brd"
    session = await start_powersi_session(spd_file=brd)
    sid = session["session_id"]
    # Manually inject the save-to-SPD step PowerSI's own error message told us we need
    # before it will let us simulate a design that wasn't already in native .spd format.
    tcl_sessions.add_line(sid, "sigrity::save {C:/Users/aicoe/Desktop/Sigrity/runs/brd_bridge_test/board.spd} {!}")

    run = await powersi_run_session(sid)
    print("RUN:", json.dumps(run, indent=2))

    status = await wait_for_job(run["job_id"], timeout_seconds=30)
    print("STATUS:", json.dumps(status, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
