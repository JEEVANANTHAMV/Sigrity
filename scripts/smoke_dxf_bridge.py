"""One-off live smoke test for allegro_import_tools.py: creating a brand-new Allegro
.brd from a DXF outline (dxf2a), exporting an existing board's mechanical data back to
DXF (a2dxf), and staging a blank board from Cadence's own shipped template — all through
the actual MCP tool wrappers, not raw CLI. Then independently re-opens the dxf2a output
with report.exe (bypassing dxf2a/SKILL entirely) to prove the produced .brd is real and
readable, not just a stub file with a plausible-looking exit code.
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.core.process import run_quick
from sigrity_mcp.domains.cad.allegro_import_tools import (
    allegro_export_dxf,
    allegro_import_dxf,
    allegro_new_blank_board,
)

WORKDIR = Path("runs/dxf_smoke")
DXF_SAMPLE = Path("C:/Cadence/SPB_22.1/doc/wb_tut/examples/Module_1/flag.dxf")
CNV_SAMPLE = Path("C:/Cadence/SPB_22.1/doc/wb_tut/examples/Module_1/flag_l.cnv")
ROUTED_BOARD = Path(
    "C:/Cadence/SPB_22.1/tools/capture/samples/PCB-Layout/Fault-Detector/allegro/"
    "fault-detector_allegro_routed.brd"
)


async def run_and_report(name, coro_result):
    result = await coro_result
    job_id = result["job_id"]
    status = await job_manager.wait(job_id, timeout=60)
    print(f"\n=== {name} ===")
    print(f"command: {result['command']}")
    print(f"final state: {status.state}  returncode: {status.returncode}")
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        text = log_path.read_text(errors="replace")
        print("log tail:\n" + "\n".join(text.splitlines()[-15:]))
    else:
        print("(no run.log found)")
    return status


async def main():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    dxf_copy = WORKDIR / "flag.dxf"
    cnv_copy = WORKDIR / "flag_l.cnv"
    shutil.copy2(DXF_SAMPLE, dxf_copy)
    shutil.copy2(CNV_SAMPLE, cnv_copy)
    new_board = WORKDIR / "new_from_dxf.brd"
    if new_board.exists():
        new_board.unlink()

    status = await run_and_report(
        "allegro_import_dxf (new design)",
        allegro_import_dxf(str(cnv_copy), str(dxf_copy), str(new_board), output_units="MILS", accuracy=2),
    )
    produced_board = new_board.resolve()
    if produced_board.exists():
        print(f"\nIndependently re-reading {produced_board} with report.exe ...")
        report_result = await run_quick(
            "allegro_report", ["-v", "sum", str(produced_board), str(WORKDIR / "report_out.txt")]
        )
        print(f"report.exe returncode: {report_result['returncode']}")
        report_txt = WORKDIR / "report_out.txt"
        if report_txt.exists():
            print(report_txt.read_text(errors="replace")[:800])
    else:
        print(f"(expected output board not found at {produced_board} -- check job_dir contents)")

    blank = await allegro_new_blank_board(str(WORKDIR / "blank_template_copy.brd"), overwrite=True)
    print("\n=== allegro_new_blank_board ===")
    print(blank)

    export_cnv = WORKDIR / "export.cnv"
    shutil.copy2(CNV_SAMPLE, export_cnv)
    await run_and_report(
        "allegro_export_dxf",
        allegro_export_dxf(str(export_cnv), str(WORKDIR / "exported.dxf"), str(ROUTED_BOARD)),
    )


if __name__ == "__main__":
    asyncio.run(main())
