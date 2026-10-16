"""Live smoke test for generate_multilayer_stackup (rigid_flex_stackup_tools.py) and the
upgraded allegro_create_stackup (allegro_tools.py), through the actual MCP tool functions,
against a real board copy.

Runs the actual production `build_18layer_rigid_flex_stackup_definition()` list end-to-end:
start a session, queue all 18 layers, save, run, dismiss the modal dialog this workflow
reliably raises on this machine (see rigid_flex_stackup_tools.py's module docstring and
core/tool_status.py's "allegro" note), then independently verify via
`run_allegro_report(..., report_code="x-section")` -- SKILL return values never surface in
the job log, so this downstream report read is the only real confirmation that layers
actually landed on disk, in the right order, with the right attributes.
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.core.win32gui_helper import auto_dismiss_dialogs
from sigrity_mcp.domains.cad.allegro_batch_tools import run_allegro_report
from sigrity_mcp.domains.cad.allegro_tools import allegro_run_session, allegro_save_design, start_allegro_session
from sigrity_mcp.domains.cad.rigid_flex_stackup_tools import (
    build_18layer_rigid_flex_stackup_definition,
    generate_multilayer_stackup,
)

SOURCE_BOARD = (
    "C:/Cadence/SPB_22.1/tools/capture/samples/PCB-Layout/Fault-Detector/allegro/"
    "fault-detector_allegro_routed.brd"
)
WORK_DIR = Path("C:/Users/aicoe/Desktop/Sigrity/runs/smoke_multilayer_stackup")
BOARD = WORK_DIR / "board.brd"
REPORT_OUT = WORK_DIR / "xsection_after.rpt"


async def dismiss_watcher(pid_holder: dict, stop_event: asyncio.Event) -> None:
    """Concurrently poll for the job's real pid and dismiss any modal dialog it raises --
    this workflow reproduced a blocking Qt dialog 4-for-4 times in prior testing on this
    machine (see rigid_flex_stackup_tools.py's docstring); without this, the job hangs.
    """
    while not stop_event.is_set():
        pid = pid_holder.get("pid")
        if pid:
            result = auto_dismiss_dialogs(pid, timeout=2.0)
            if result["dismissed"]:
                print("AUTO-DISMISSED:", result["dismissed"])
        await asyncio.sleep(1.0)


async def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_BOARD, BOARD)  # never mutate the shipped sample directly

    layers = [
        {
            "name": l["name"],
            "layer_type": l["type"],
            "material": l["material"],
            "thickness_mil": l["thickness_mil"],
            "zone": l["zone"],
            "ref_plane": l.get("ref_plane"),
            "hatched_plane": l.get("hatched_plane"),
        }
        for l in build_18layer_rigid_flex_stackup_definition()
    ]

    session = await start_allegro_session()
    sid = session["session_id"]
    result = await generate_multilayer_stackup(sid, layers=layers)
    print(f"queued {result['layer_count']} layers into session {sid}")

    await allegro_save_design(sid)
    run = await allegro_run_session(sid, board_file=str(BOARD))
    print("command:", run["command"])

    pid_holder: dict = {"pid": None}
    stop_event = asyncio.Event()

    async def find_pid() -> None:
        for _ in range(60):
            record = job_manager.get(run["job_id"])
            if record and record.pid:
                pid_holder["pid"] = record.pid
                return
            await asyncio.sleep(0.5)

    watcher_task = asyncio.create_task(dismiss_watcher(pid_holder, stop_event))
    await find_pid()
    print("pid:", pid_holder["pid"])

    status = await job_manager.wait(run["job_id"], timeout=120)
    print("allegro run state:", status.state, "returncode:", status.returncode)
    stop_event.set()
    await watcher_task

    rep = await run_allegro_report(board_file=str(BOARD), report_code="x-section", output_file=str(REPORT_OUT))
    rep_status = await job_manager.wait(rep["job_id"], timeout=60)
    print("report state:", rep_status.state, rep_status.returncode)
    print("--- x-section report ---")
    print(REPORT_OUT.read_text(errors="replace") if REPORT_OUT.exists() else "MISSING")


if __name__ == "__main__":
    asyncio.run(main())
