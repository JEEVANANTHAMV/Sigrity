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

    Runs `BroadbandSPICE.exe -b -<mode> -<netlist_format> -i<max_iterations> -uf<upper_frequency_ghz> [-cf:<output_circuit_file>] [-ign<ignore_threshold>] <network_file>`.
    `mode` picks the fitting algorithm: 'Passivity' (default, enforces passivity),
    'Passivity2'/'Passivity3' (alternate passivity-enforcement variants), or
    'Precision' (prioritizes fit accuracy — `ignore_threshold` only applies in this mode,
    as an off-diagonal-term ignore cutoff).
    `network_file` is a Touchstone (.sNp) or Sigrity `.bnp` file — this tool does not take
    a layout `.spd` directly; extract S-parameters with PowerSI/Clarity3D/XtractIM first.
    Returns a job_id; the fitted netlist and `.bds` project land in the job directory.
    """
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

    Runs `BroadbandSPICE.exe -b -Checking <network_file>` (mutually exclusive with the
    fitting options in run_broadbandspice_extraction). Results land in a `BBSResult`
    subdirectory of the job's working directory — inspect it with list_job_files.
    """
    record = await submit_job(tool="broadbandspice", build_args=["-b", "-Checking", network_file])
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
