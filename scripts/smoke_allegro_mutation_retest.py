"""Retest of an Allegro SKILL database-mutation call (previously didn't complete within
2 minutes in live testing), against a real sample board, now that licensing is reportedly
sorted.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_tools import allegro_create_net, allegro_run_session, start_allegro_session

BOARD = "C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd"


async def main():
    session = await start_allegro_session()
    await allegro_create_net(session["session_id"], "TEST_NET_1", net_type="Signal")
    result = await allegro_run_session(session["session_id"], BOARD)
    job_id = result["job_id"]
    print("command:", result["command"])
    status = await job_manager.wait(job_id, timeout=150)
    print("final state:", status.state, "returncode:", status.returncode)
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        print("log:\n", log_path.read_text(errors="replace"))
    if status.state == "running":
        print("STILL RUNNING after 150s -- killing job")
        job_manager.cancel(job_id)


if __name__ == "__main__":
    asyncio.run(main())
