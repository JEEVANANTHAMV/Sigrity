"""Heavier live smoke test for the DismissWatcher fix: a single Allegro session doing
stackup authoring + a Constraint Manager spacing-rule call + a DRC update + a save, all
before one allegro_run_session launch -- closer to what a real campaign scenario does
than the lighter 2-layer-stackup-only smoke test in scripts/smoke_allegro_auto_dismiss.py.

Like that script, this calls ONLY the real MCP tool functions with NO dismiss-dialog
code of its own -- if DismissWatcher (auto-started by JobManager.submit whenever
run_session launches tool="allegro") has any edge case under a longer, multi-step
session, this should surface it as a hang.

Run with: .venv/Scripts/python.exe scripts/smoke_allegro_combined_session.py
"""

import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_batch_tools import run_allegro_report
from sigrity_mcp.domains.cad.allegro_constraint_tools import allegro_set_spacing_constraint
from sigrity_mcp.domains.cad.allegro_tools import (
    allegro_create_stackup,
    allegro_run_drc,
    allegro_run_session,
    allegro_save_design,
    start_allegro_session,
)

SOURCE_BOARD = (
    "C:/Cadence/SPB_22.1/tools/capture/samples/PCB-Layout/Fault-Detector/allegro/"
    "fault-detector_allegro_routed.brd"
)
WORK_DIR = Path("C:/Users/aicoe/Desktop/Sigrity/runs/smoke_allegro_combined_session")
BOARD = WORK_DIR / "board.brd"
REPORT_OUT = WORK_DIR / "xsection_after.rpt"
TIMEOUT_SECONDS = 180


async def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if BOARD.exists():
        BOARD.unlink()
    shutil.copyfile(SOURCE_BOARD, BOARD)

    t0 = time.time()
    session = await start_allegro_session()
    sid = session["session_id"]

    # Stackup authoring (same shape as the existing confirmed-live finding).
    await allegro_create_stackup(sid, position="bottom", name="L2_GND", layer_type="PLANE",
                                  material="COPPER", thickness_mil=1.4)
    await allegro_create_stackup(sid, position="bottom", name="L3_SIG1", layer_type="CONDUCTOR",
                                  material="COPPER", thickness_mil=0.7)

    # Constraint Manager call.
    await allegro_set_spacing_constraint(sid, constraint="Line_To_Line", value=5.0)

    # DRC update.
    await allegro_run_drc(sid, batch_mode=True)

    await allegro_save_design(sid)
    run = await allegro_run_session(sid, board_file=str(BOARD))
    print("command:", run["command"])
    print("job_id:", run["job_id"])

    status = await job_manager.wait(run["job_id"], timeout=TIMEOUT_SECONDS)
    elapsed = time.time() - t0
    print(f"allegro run state: {status.state}  returncode: {status.returncode}  "
          f"elapsed: {elapsed:.1f}s")

    if status.state == "running":
        print(f"FAIL: job did not finish within {TIMEOUT_SECONDS}s -- hang reproduced "
              "even with the fix; see job_dir for diagnostics:", status.job_dir)
        raise SystemExit(1)

    rep = await run_allegro_report(board_file=str(BOARD), report_code="x-section",
                                    output_file=str(REPORT_OUT))
    rep_status = await job_manager.wait(rep["job_id"], timeout=60)
    print("report state:", rep_status.state, rep_status.returncode)
    print("--- x-section report ---")
    print(REPORT_OUT.read_text(errors="replace") if REPORT_OUT.exists() else "MISSING")

    if status.state == "succeeded" and rep_status.state == "succeeded" and REPORT_OUT.exists():
        print(f"PASS: combined session completed end-to-end in {elapsed:.1f}s with no "
              "manual dialog handling.")
    else:
        print("FAIL: job(s) did not succeed cleanly -- see states/returncodes above.")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
