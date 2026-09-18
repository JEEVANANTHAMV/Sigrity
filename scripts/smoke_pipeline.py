import asyncio
import json

import sigrity_mcp.server  # noqa: F401 - triggers registration of every domain's tools
from sigrity_mcp.domains.platform.pipeline_tools import run_tool_pipeline


async def main():
    spd = r"C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\PowerSI\3D-EM\one_trace.spd"
    steps = [
        {"tool": "start_powersi_session", "args": {"spd_file": spd}, "save_as": "s"},
        {"tool": "powersi_set_mode", "args": {"session_id": "${s.session_id}", "mode": "extraction"}},
        {
            "tool": "powersi_set_frequency_sweep",
            "args": {"session_id": "${s.session_id}", "start": "1e6", "end": "1e9"},
        },
        {"tool": "powersi_add_ports_auto", "args": {"session_id": "${s.session_id}"}},
        {"tool": "powersi_run_session", "args": {"session_id": "${s.session_id}"}, "save_as": "run"},
        {"tool": "wait_for_job", "args": {"job_id": "${run.job_id}", "timeout_seconds": 60}, "save_as": "final"},
    ]
    result = await run_tool_pipeline(steps)
    print(json.dumps(result, indent=2, default=str)[:3000])


if __name__ == "__main__":
    asyncio.run(main())
