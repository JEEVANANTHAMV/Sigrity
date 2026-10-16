"""Definitive live verification of allegro_assign_net: reassign a real pin (R1.2,
currently on net N00885) to GND, save, then re-run the report tool to check whether the
net composition actually changed on disk -- not just "the process exited 0".
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_geometry_tools import allegro_assign_net
from sigrity_mcp.domains.cad.allegro_tools import allegro_run_session, allegro_save_design, start_allegro_session

WORKDIR = Path("C:/Users/aicoe/Desktop/Sigrity/runs/verify_net_assign")


async def main():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    board = WORKDIR / "board.brd"
    shutil.copy2("C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd", board)

    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_assign_net(sid, "PIN", "R1.2", "GND", ripup=True, ignore_fixed=True)
    await allegro_save_design(sid)

    result = await allegro_run_session(sid, str(board))
    job_id = result["job_id"]
    print("command:", result["command"])
    status = await job_manager.wait(job_id, timeout=90)
    print("final state:", status.state, "returncode:", status.returncode)
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        print("log:\n", log_path.read_text(errors="replace"))

    # Now re-run the report tool directly to check the actual net composition on disk.
    proc = await asyncio.create_subprocess_exec(
        "C:/Cadence/SPB_22.1/tools/bin/report.exe", "-v", "net", str(board), str(WORKDIR / "net_after.txt"),
        cwd=str(WORKDIR),
    )
    await proc.wait()
    text = (WORKDIR / "net_after.txt").read_text(errors="replace")
    for line in text.splitlines():
        if line.startswith("GND,") or line.startswith("N00885,"):
            print(line)


if __name__ == "__main__":
    asyncio.run(main())
