import asyncio
import json
from pathlib import Path

from sigrity_mcp.domains.si.powersi_tools import (
    powersi_add_ports_auto,
    powersi_export_network,
    powersi_run_session,
    powersi_set_frequency_sweep,
    powersi_set_mode,
    start_powersi_session,
)
from sigrity_mcp.domains.platform.job_tools import get_job_status, list_job_files, read_job_output_file, tail_job_log


async def main():
    # DOC-VERIFIED (psi_ug.pdf "PowerSI Tcl Commands", printed pp. 410-413): port
    # generation is component-centric -- the net under analysis must be terminated at a
    # real component for `add port` to produce a port. The bare 3D-EM `one_trace.spd`
    # stub has no such component, so the real bridge test is a component-bearing design:
    # the real Allegro `.brd` we translated to native `.spd` end-to-end in this workspace
    # (see runs/innosynth_imx8mp/powersi_verify/board.spd, 81 real components, real
    # translated nets). `add port -all -circuit {RefDes}` on a real component is the
    # documented "Auto Generate Ports" path, not a guessed flag.
    spd = r"C:\Users\aicoe\Desktop\Sigrity\runs\innosynth_imx8mp\powersi_verify\board.spd"
    session = await start_powersi_session(spd_file=spd)
    sid = session["session_id"]
    await powersi_set_mode(sid, "extraction")
    await powersi_set_frequency_sweep(sid, "1e6", "1e9", use_afs=True)
    await powersi_add_ports_auto(sid, ref_des="C12")
    await powersi_export_network(sid, "@ALL_NETS", "board.s2p", matrix_type="S")
    print("RUN:", json.dumps(run, indent=2))

    job_id = run["job_id"]
    for _ in range(30):
        status = await get_job_status(job_id)
        if status["state"] != "running":
            break
        await asyncio.sleep(2)
    print("STATUS:", json.dumps(status, indent=2))

    log = await tail_job_log(job_id, max_lines=40)
    print("LOG:", json.dumps(log, indent=2))

    files = await list_job_files(job_id)
    print("FILES:", json.dumps(files, indent=2))

    job_dir = Path(status["job_dir"])
    for f in job_dir.glob("*.log"):
        if f.name != "run.log":
            print(f"--- {f.name} ---")
            print(f.read_text(encoding="utf-8", errors="replace")[:2000])


if __name__ == "__main__":
    asyncio.run(main())
