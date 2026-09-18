import asyncio
import json

from sigrity_mcp.domains.pi.powerdc_tools import (
    powerdc_set_simulation_mode,
    powerdc_run_session,
    start_powerdc_session,
)
from sigrity_mcp.domains.platform.job_tools import get_job_status, tail_job_log


async def main():
    spd = r"C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\PowerDC\Electrical_Analysis\IR_Package.spd"
    session = await start_powerdc_session(spd_file=spd)
    sid = session["session_id"]
    await powerdc_set_simulation_mode(sid, ir_drop_analysis=True)
    run = await powerdc_run_session(sid)
    print("RUN:", json.dumps(run, indent=2))

    job_id = run["job_id"]
    for _ in range(30):
        status = await get_job_status(job_id)
        if status["state"] != "running":
            break
        await asyncio.sleep(2)
    print("STATUS:", json.dumps(status, indent=2))
    print("LOG:", json.dumps(await tail_job_log(job_id, max_lines=40), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
