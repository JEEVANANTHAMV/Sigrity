"""One-off live smoke test for the newly-added CAD tools (batch_drc, placement, ncroute,
ipc2581_out, ipc356_out, step_out, designextractor, checkplus, ibischk) against a real
sample board. Prints each job's final state and a tail of its log so results can be
eyeballed, then leaves the runs/ directories in place for manual inspection.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_drc_tools import run_allegro_batch_drc, run_allegro_checkplus
from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_design_extractor
from sigrity_mcp.domains.cad.allegro_library_tools import run_ibis_check
from sigrity_mcp.domains.cad.allegro_manufacturing_tools import (
    run_ipc2581_export,
    run_ipc356_export,
    run_step_export,
)
from sigrity_mcp.domains.cad.allegro_placement_tools import run_allegro_ncroute, run_allegro_placement

BOARD = "C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd"
IBIS = "C:/Cadence/Sigrity2024.0/share/SpeedXP/Samples/SPEEDEM/demo.ibs"


async def run_and_report(name, coro_result):
    result = await coro_result
    job_id = result["job_id"]
    status = await job_manager.wait(job_id, timeout=90)
    print(f"\n=== {name} ===")
    print(f"command: {result['command']}")
    print(f"final state: {status.state}  returncode: {status.returncode}")
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        text = log_path.read_text(errors="replace")
        print("log tail:\n" + "\n".join(text.splitlines()[-15:]))
    else:
        print("(no run.log found)")


async def main():
    await run_and_report("batch_drc", run_allegro_batch_drc(BOARD))
    await run_and_report("placement", run_allegro_placement(BOARD, output_file="placed.brd"))
    await run_and_report("ncroute", run_allegro_ncroute(BOARD, output_file="drill.rte"))
    await run_and_report("ipc2581_export", run_ipc2581_export(BOARD, output_file="out.ipc2581.xml"))
    await run_and_report("ipc356_export", run_ipc356_export(BOARD, output_file="out.ipc356"))
    await run_and_report("step_export", run_step_export(BOARD, output_file="out.step"))
    await run_and_report("design_extractor", run_allegro_design_extractor(BOARD, output_file="out.json"))
    await run_and_report("checkplus", run_allegro_checkplus(BOARD))
    await run_and_report("ibis_check", run_ibis_check(IBIS, ibis_version="6"))


if __name__ == "__main__":
    asyncio.run(main())
