"""BroadbandSPICE — converts an S-parameter network (Touchstone/.bnp) into a broadband
SPICE/HSPICE/Spectre circuit model, or checks one for passivity/causality.

Confirmed (doc/bbs_ug): no Tcl API — pure CLI switches, input is a network file
(Touchstone .sNp or Sigrity .bnp), not a layout `.spd`.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_broadbandspice_extraction(
    network_file: str,
    mode: Literal["Passivity", "Passivity2", "Passivity3", "Precision"] = "Passivity",
    netlist_format: Literal["HSPICE", "SPICE", "Spectre"] = "HSPICE",
    output_circuit_file: Optional[str] = None,
    max_iterations: int = 200,
    upper_frequency_ghz: float = 125.0,
    ignore_threshold: Optional[float] = None,
) -> dict:
    """Fit a broadband SPICE-compatible circuit model to a network file's S-parameters, as a background job.
See `.forjinn/skills/sigrity-si/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-b", f"-{mode}", f"-{netlist_format}", f"-i{max_iterations}", f"-uf{upper_frequency_ghz}"]
    if output_circuit_file:
        args.append(f"-cf:{output_circuit_file}")
    if ignore_threshold is not None:
        args.append(f"-ign{ignore_threshold}")
    args.append(network_file)

    record = await submit_job(tool="broadbandspice", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_broadbandspice_check(network_file: str) -> dict:
    """Check a network file for passivity/causality violations without fitting a circuit model, as a background job.
See `.forjinn/skills/sigrity-si/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    record = await submit_job(tool="broadbandspice", build_args=["-b", "-Checking", network_file])
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
