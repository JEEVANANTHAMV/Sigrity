"""One-off live smoke test for the newly-added project-creation, symbol-authoring, and
mechanical-exchange tools (copyproject, xcon2project, generate_sim_variant, create_sym,
ipc2581_in, idf_out, idx_out, brd2dml, pdf_out) against real Cadence sample files, through
the actual MCP tool wrappers. Prints each job's final state and a tail of its log.
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_library_tools import allegro_create_symbol
from sigrity_mcp.domains.cad.allegro_manufacturing_tools import (
    run_dml_export,
    run_idf_export,
    run_idx_export,
    run_ipc2581_import,
    run_pdf_export,
)
from sigrity_mcp.domains.cad.allegro_project_tools import (
    allegro_copy_project,
    allegro_generate_sim_variant,
    allegro_package_xcon_project,
)

WORKDIR = Path("runs/project_mfg_smoke")
ROUTED_BOARD = Path(
    "C:/Cadence/SPB_22.1/tools/capture/samples/PCB-Layout/Fault-Detector/allegro/"
    "fault-detector_allegro_routed.brd"
)
ALTIUM_TEMPLATE_CPM = Path("C:/Cadence/SPB_22.1/share/pcb/translators/altium_proj_template/altium_proj_template.cpm")
ALTIUM_TEMPLATE_XCON = Path(
    "C:/Cadence/SPB_22.1/share/pcb/translators/altium_proj_template/worklib/top/sch_1/top.xcon"
)
IPC2581_SAMPLE = Path("C:/Cadence/Sigrity2024.0/share/Translators/Samples/ipc2581/demo2.xml")
DRA_SAMPLE = Path("C:/Cadence/SPB_22.1/doc/lc_tut/tutorial_examples/Master_Library/Symbols/asp-134488-01.dra")


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
        print("log tail:\n" + "\n".join(text.splitlines()[-8:]))
    print(f"job_dir contents: {[p.name for p in Path(status.job_dir).iterdir()]}")
    return status


async def main():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    board_copy = WORKDIR / "sample.brd"
    shutil.copy2(ROUTED_BOARD, board_copy)

    await run_and_report("run_idf_export", run_idf_export(str(board_copy.resolve())))
    await run_and_report("run_idx_export", run_idx_export(str(board_copy.resolve())))
    await run_and_report("run_dml_export", run_dml_export(str(board_copy.resolve())))
    await run_and_report("run_pdf_export", run_pdf_export(str(board_copy.resolve())))

    if IPC2581_SAMPLE.exists():
        await run_and_report(
            "run_ipc2581_import",
            run_ipc2581_import(str(IPC2581_SAMPLE), output_board_file=str((WORKDIR / "from_ipc2581.brd").resolve())),
        )
    else:
        print(f"\n(skipping ipc2581_in -- sample not found at {IPC2581_SAMPLE})")

    await run_and_report(
        "allegro_generate_sim_variant",
        allegro_generate_sim_variant(
            str(board_copy.resolve()),
            output_board_file=str((WORKDIR / "variant.brd").resolve()),
            cline_oversize_percent=1.0,
            dielectric_oversize_percent=1.0,
        ),
    )

    if DRA_SAMPLE.exists():
        await run_and_report(
            "allegro_create_symbol",
            allegro_create_symbol(str(DRA_SAMPLE), output_symbol_file=str((WORKDIR / "mysym.psm").resolve()), symbol_type="package"),
        )
    else:
        print(f"\n(skipping create_sym -- sample not found at {DRA_SAMPLE})")

    if ALTIUM_TEMPLATE_CPM.exists():
        copy_dest = (WORKDIR / "copyproj_out").resolve()
        copy_dest.mkdir(parents=True, exist_ok=True)
        await run_and_report(
            "allegro_copy_project",
            allegro_copy_project(str(ALTIUM_TEMPLATE_CPM), str(copy_dest), "smokeproj", "smokelib", "smokedesign"),
        )
    else:
        print(f"\n(skipping copyproject -- sample not found at {ALTIUM_TEMPLATE_CPM})")

    if ALTIUM_TEMPLATE_XCON.exists():
        xcon_dest = (WORKDIR / "xcon2proj_out").resolve()
        xcon_dest.mkdir(parents=True, exist_ok=True)
        await run_and_report(
            "allegro_package_xcon_project",
            allegro_package_xcon_project(
                str(ALTIUM_TEMPLATE_XCON), "top", "worklib", str(ALTIUM_TEMPLATE_CPM), output_folder=str(xcon_dest)
            ),
        )
    else:
        print(f"\n(skipping xcon2project -- sample not found at {ALTIUM_TEMPLATE_XCON})")


if __name__ == "__main__":
    asyncio.run(main())
