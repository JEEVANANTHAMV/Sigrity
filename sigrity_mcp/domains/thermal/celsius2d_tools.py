"""Celsius2D automation — 2D/board-level thermal & thermal-stress simulation, CLI-only (no Tcl session).

CONFIRMED LIVE on this machine against a real Cadence sample workspace
(`share/PostInstallationCheck/celsius2d/demo_sim.pdcx`): `Celsius2D.exe -b -XIMSAVE -r
demo_sim.pdcx` exited 0 with "Simulation succeed" and full thermal+stress engine logs
(mesh generation, matrix solve, real memory/timing statistics). This is the same
`-b -XIMSAVE -r <workspace>.pdcx` invocation convention already confirmed for PowerDC's
CLI (Domain 1) — transcribed from Cadence's own installer self-test script
(`share/PostInstallationCheck/bin/postInstallCheck.pl`), which drives Celsius2D exactly
this way with no separate `.tcl` macro involved (unlike Celsius3D/CelsiusCFD).

A second sample (`chip.pdcx`) failed with a domain-content error ("The CFD File
Specified in the Use Defined CFD File is invalid") rather than a launch/license/syntax
failure — confirming the CLI invocation itself is solid and errors surface as real,
readable diagnostics in the job log, not silent failure.
"""

from __future__ import annotations

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_celsius2d_workspace(pdcx_file: str, save_excel_result: bool = True) -> dict:
    """Run an already-configured Celsius2D thermal/thermal-stress workspace, as a background job.

    Runs `Celsius2D.exe -b -XIMSAVE -r <pdcx_file>` — confirmed live via a real Cadence
    sample workspace on this machine (see module docstring). `save_excel_result` maps to
    the `-XIMSAVE` flag (auto-save the results workbook); it's included unconditionally
    here since that's how the confirmed-working invocation was actually run — pass
    `save_excel_result=False` only if you've independently confirmed Celsius2D accepts
    running without it.
    `pdcx_file` must already be a fully-configured Celsius2D/PowerDC-style workspace
    (materials, thermal boundary conditions, and — for CFD-linked cases — a valid
    referenced CFD file) — this tool runs an existing setup, it does not build one from
    bare geometry (no additional Celsius2D-specific authoring Tcl/CLI surface was found
    documented anywhere in the shipped doc tree).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log,
    then read the engine's own log (`<name>_ThermalEngine.log` /
    `<name>_ResourceProfile.log`) via list_job_files/read_job_output_file for full detail
    beyond this job's own stdout capture.
    """
    args = ["-b"]
    if save_excel_result:
        args.append("-XIMSAVE")
    args += ["-r", pdcx_file]
    record = await submit_job(tool="celsius2d", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
