import asyncio
import json
import shutil
from pathlib import Path

from sigrity_mcp.domains.cad.allegro_batch_tools import run_allegro_dbdoctor, run_allegro_report
from sigrity_mcp.domains.platform.job_tools import get_job_status, read_job_output_file, wait_for_job


async def main():
    src = Path(
        r"C:\Cadence\SPB_22.1\tools\capture\samples\PCB-Layout\Fault-Detector\allegro"
        r"\fault-detector_allegro_routed.brd"
    )
    scratch = Path.cwd() / "runs" / "allegro_smoke"
    scratch.mkdir(parents=True, exist_ok=True)
    board = scratch / "board.brd"
    shutil.copy(src, board)

    report_run = await run_allegro_report(str(board), "sum")
    print("REPORT RUN:", json.dumps(report_run, indent=2))
    report_status = await wait_for_job(report_run["job_id"], timeout_seconds=60)
    print("REPORT STATUS:", json.dumps(report_status, indent=2))

    dbdoctor_run = await run_allegro_dbdoctor(str(board), check_only=True)
    print("DBDOCTOR RUN:", json.dumps(dbdoctor_run, indent=2))
    dbdoctor_status = await wait_for_job(dbdoctor_run["job_id"], timeout_seconds=60)
    print("DBDOCTOR STATUS:", json.dumps(dbdoctor_status, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
