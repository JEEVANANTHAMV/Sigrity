"""SPDSIM — legacy SPEED2000 transmission-line field solver.

Confirmed (doc/spd2k_ug, doc/speedem_ug, zero Tcl hits in either): SPDSIM has no Tcl
API at all — it's driven entirely by CLI switches against a `.spd` project file
authored in SPDGEN (SPDGEN itself is GUI-only; no batch/Tcl automation is documented
for it, so it isn't wrapped here).

CONFIRMED BLOCKED live, root cause narrowed (see `core.tool_status`): both this
module's `-b` flag AND the alternate `-as`/`-spice -run` flags documented in
`doc/psi_ug/ch10_tcl_re_Calling_SPDSIM_in_PowerSI_Commands.html` (a page titled
"Invoke Subprocesses") fail identically — `"Skip license fetch ...."` followed by
`"Failed to open the file"` — against two different real sample `.spd` files (one
legacy, one modern). That doc page's own framing strongly suggests SPDSIM.exe is
designed to run only as a genuine child process of a live PowerSI Tcl session (via
`sigrity::do exec "...spdsim.exe" -as "file.spd" &`), not as an independently launched
standalone process — this module's direct `submit_job` invocation may be
structurally the wrong approach, not just missing a flag.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_spdsim_simulation(
    spd_file: str,
    save_interval_steps: Optional[int] = None,
    minimized_window: bool = False,
    logs: Optional[str] = None,
) -> dict:
    """Run a SPDSIM transmission-line field simulation against a `.spd` project (built beforehand in SPDGEN) as a background job.

    Runs `SPDSIM.exe -b [-s] [-n<save_interval_steps>] [-r[:logs]] <spd_file>`.
    `save_interval_steps` sets how often (in simulation steps) results are checkpointed
    to disk (SPDSIM's default is every 100 steps if omitted).
    `logs` selects which auxiliary logs to write, using SPDSIM's letter codes
    concatenated together — e, x, r, p, t, m for execution_time/reading_time/
    profile_spd/trace_extraction/memory_time respectively (e.g. "ept"); omit for
    SPDSIM's default set, or pass "" for none.
    Returns a job_id immediately — poll it with get_job_status/wait_for_job, then
    inspect the `.cur` curve files and `*.log` files it writes via list_job_files/
    read_job_output_file.
    """
    args = ["-b"]
    if minimized_window:
        args.append("-s")
    if save_interval_steps is not None:
        args.append(f"-n{save_interval_steps}")
    if logs is not None:
        args.append(f"-r:{logs}" if logs else "-r")
    args.append(spd_file)

    record = await submit_job(tool="spdsim", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
