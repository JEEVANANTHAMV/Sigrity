"""Live smoke test for the new Constraint Manager and geometry SKILL tools against a
real board, through the actual MCP tool functions.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_constraint_tools import (
    allegro_get_net_constraint,
    allegro_set_physical_constraint,
    allegro_set_spacing_constraint,
)
from sigrity_mcp.domains.cad.allegro_geometry_tools import (
    allegro_assign_net,
    allegro_create_via,
    allegro_get_module_instance_location,
)
from sigrity_mcp.domains.cad.allegro_tools import allegro_run_session, start_allegro_session

BOARD = "C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd"


async def main():
    session = await start_allegro_session()
    sid = session["session_id"]

    # Constraint Manager: set a spacing rule, a physical rule, then query a real net.
    await allegro_set_spacing_constraint(sid, "line_line", 6, cset="")
    await allegro_set_physical_constraint(sid, "width_min", 5, cset="")
    await allegro_get_net_constraint(sid, "GND", "WIDTH_MIN")

    # Geometry: place a via on a real via padstack (if one exists in this design),
    # query a real module instance's location, try a net assignment.
    await allegro_create_via(sid, "STANDARD", 1000.0, 1000.0)
    await allegro_get_module_instance_location(sid, "U1")
    await allegro_assign_net(sid, "PIN", "C1.2", "GND")

    result = await allegro_run_session(sid, BOARD)
    job_id = result["job_id"]
    print("command:", result["command"])
    status = await job_manager.wait(job_id, timeout=90)
    print("final state:", status.state, "returncode:", status.returncode)
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        print("log:\n", log_path.read_text(errors="replace"))
    if status.state == "running":
        print("STILL RUNNING -- killing job")
        job_manager.cancel(job_id)


if __name__ == "__main__":
    asyncio.run(main())
