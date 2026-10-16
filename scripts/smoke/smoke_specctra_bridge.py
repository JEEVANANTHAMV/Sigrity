"""Live smoke test for the confirmed SPECCTRA autorouting bridge, exercised through the
actual MCP tool functions (not just raw CLI) to validate submit_job wiring.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.spif_specctra_tools import run_specctra_autoroute, run_spif_export_to_specctra

BOARD = "C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd"
WORKDIR = Path("C:/Users/aicoe/Desktop/Sigrity/runs/specctra_bridge_smoke")


async def run_and_report(name, coro_result, timeout=90):
    result = await coro_result
    job_id = result["job_id"]
    status = await job_manager.wait(job_id, timeout=timeout)
    print(f"\n=== {name} ===")
    print(f"command: {result['command']}")
    print(f"final state: {status.state}  returncode: {status.returncode}")
    log_path = Path(status.job_dir) / "run.log"
    if log_path.exists():
        text = log_path.read_text(errors="replace")
        print("log tail:\n" + "\n".join(text.splitlines()[-15:]))
    return status


async def main():
    WORKDIR.mkdir(parents=True, exist_ok=True)
    dsn_path = str(WORKDIR / "board.dsn")
    await run_and_report("run_spif_export_to_specctra", run_spif_export_to_specctra(BOARD, dsn_path))

    do_path = WORKDIR / "route.do"
    do_path.write_text(
        f"bestsave on {WORKDIR}\\best.wir\n"
        f"status_file {WORKDIR}\\route.sts\n"
        "smart_route\n"
        f"write session {WORKDIR}\\routed.ses\n"
        f"report status {WORKDIR}\\final.sts\n",
        encoding="utf-8",
    )
    await run_and_report("run_specctra_autoroute", run_specctra_autoroute(dsn_path, str(do_path)), timeout=120)

    final_sts = WORKDIR / "final.sts"
    if final_sts.exists():
        print("\n=== final.sts (routing statistics) ===")
        print(final_sts.read_text(errors="replace")[-1500:])


if __name__ == "__main__":
    asyncio.run(main())
