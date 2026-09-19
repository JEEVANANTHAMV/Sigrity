"""Test Allegro's native `auto_route` command (Command: prompt, not SKILL) as a
potential fix for the confirmed-broken manual spif_batch -i round trip -- Cadence's own
docs describe auto_route as driving the whole export->SPECCTRA->import cycle internally
in one shot.
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.core.tclsession import tcl_sessions, run_session

WORKDIR = Path("C:/Users/aicoe/Desktop/Sigrity/runs/verify_auto_route")


async def main():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    board = WORKDIR / "board.brd"
    shutil.copy2("C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd", board)

    session = tcl_sessions.create("allegro")
    tcl_sessions.add_line(session.session_id, "auto_route")
    tcl_sessions.add_line(session.session_id, "save")
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id, tool="allegro", tcl_arg_flag="-s",
        extra_args=[str(board)], script_filename="macro.scr",
    )
    print("command:", record.command)
    status = await job_manager.wait(record.job_id, timeout=180)
    print("final state:", status.state, "returncode:", status.returncode)
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        print("log:\n", log_path.read_text(errors="replace"))
    if status.state == "running":
        print("STILL RUNNING after 180s -- leaving it, check manually")


if __name__ == "__main__":
    asyncio.run(main())
