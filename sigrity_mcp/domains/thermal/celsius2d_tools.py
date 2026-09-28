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
See `.forjinn/skills/sigrity-celsius/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-b"]
    if save_excel_result:
        args.append("-XIMSAVE")
    args += ["-r", pdcx_file]
    record = await submit_job(tool="celsius2d", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
