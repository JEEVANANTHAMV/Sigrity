"""OptimizePI automation — decap/VRM placement optimization and PDN target-impedance analysis.

Confirmed real batch invocation: `OptimizePI.exe -b -export_report -tcl <script.tcl>`.
The `sigrity::` Tcl vocabulary below (namespace-style like PowerDC/PowerSI) is
transcribed from the confirmed reference, not guessed.

Usage pattern: start_optimizepi_session -> one or more optimizepi_* "compose" tools
(each just appends a Tcl line, no process launched) -> optimizepi_run_session (writes
the accumulated script and actually launches OptimizePI once). Use
preview_tcl_session/close_tcl_session (sigrity_mcp.domains.platform.session_tools) to
inspect or discard a session, and the job-control tools (get_job_status, tail_job_log,
list_job_files, read_job_output_file) to track/retrieve the run started by
optimizepi_run_session.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_WORKFLOW_KEYS = Literal[
    "postLayout", "preLayout", "DeviceImpedanceChecking",
    "LoopInductancesAnalysis", "PinInductancesAnalysis", "BestCapatitorLocationEstimation",
]
_DECAP_TYPES = Literal["Device", "EMI"]
_PLOT_FILE_TYPES = Literal["CSV", "BNP", "touchstone"]


@mcp.tool
async def start_optimizepi_session(workflow_key: _WORKFLOW_KEYS) -> dict:
    """Begin a new OptimizePI automation session by selecting its workflow.

    `workflow_key` picks which OptimizePI workflow this macro runs: 'postLayout',
    'preLayout', 'DeviceImpedanceChecking', 'LoopInductancesAnalysis',
    'PinInductancesAnalysis', or 'BestCapatitorLocationEstimation' (spelling of
    "Capatitor" kept exactly as Cadence's own Tcl API has it). Returns a session_id —
    pass it to every other optimizepi_* tool below, then finish with
    optimizepi_run_session. Nothing is executed yet; this records
    `sigrity::update workflow -product {OptimizePI} -workflowkey {<workflow_key>} {!}`.
    """
    session = tcl_sessions.create("optimizepi")
    tcl_sessions.add_line(
        session.session_id,
        f"sigrity::update workflow -product {{OptimizePI}} -workflowkey {tcl_str(workflow_key)} {{!}}",
    )
    return {"session_id": session.session_id, "workflow_key": workflow_key}


@mcp.tool
async def optimizepi_attach_layout(session_id: str, spd_file: str) -> dict:
    """Attach a layout (.spd) design to the current OptimizePI session.

    Appends `sigrity::open document -attach {<spd_file>} {!}`.
    """
    tcl_sessions.add_line(session_id, f"sigrity::open document -attach {tcl_path(spd_file)} {{!}}")
    return {"session_id": session_id, "spd_file": spd_file}


@mcp.tool
async def optimizepi_add_vrm(session_id: str, power_net: str, ground_net: str, ref_des: str) -> dict:
    """Add a VRM (voltage regulator module) reference on a power/ground net pair, by component.

    Appends
    `sigrity::add VRM -byNet -powerName {<power_net>} -groundName {<ground_net>} -component {<ref_des>} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add VRM -byNet -powerName {tcl_str(power_net)} "
            f"-groundName {tcl_str(ground_net)} -component {tcl_str(ref_des)} {{!}}"
        ),
    )
    return {"session_id": session_id, "power_net": power_net, "ground_net": ground_net, "ref_des": ref_des}


@mcp.tool
async def optimizepi_add_decap_candidate(
    session_id: str,
    power_net: str,
    ground_net: str,
    decap_type: _DECAP_TYPES,
    ref_des: str,
) -> dict:
    """Add a decoupling-capacitor placement candidate on a power/ground net pair for the optimizer to consider.

    `decap_type` is 'Device' (an actual mounted decap component) or 'EMI' (an EMI
    filter/decap candidate). Appends
    `sigrity::add deCap -byNet -powerName {<power_net>} -groundName {<ground_net>} -portGeneration {} -type {<decap_type>} -component {<ref_des>} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add deCap -byNet -powerName {tcl_str(power_net)} "
            f"-groundName {tcl_str(ground_net)} -portGeneration {{}} "
            f"-type {tcl_str(decap_type)} -component {tcl_str(ref_des)} {{!}}"
        ),
    )
    return {
        "session_id": session_id,
        "power_net": power_net,
        "ground_net": ground_net,
        "decap_type": decap_type,
        "ref_des": ref_des,
    }


@mcp.tool
async def optimizepi_add_impedance_observation(
    session_id: str,
    positive_pin: str,
    negative_pin: str,
    ref_des: str,
) -> dict:
    """Add an impedance-observation point (a pin pair to track PDN impedance at) for the optimizer's target-impedance analysis.

    Appends
    `sigrity::add impedanceObservation -byPin -positivePinName {<positive_pin>} -negativePinName {<negative_pin>} -component {<ref_des>} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add impedanceObservation -byPin -positivePinName {tcl_str(positive_pin)} "
            f"-negativePinName {tcl_str(negative_pin)} -component {tcl_str(ref_des)} {{!}}"
        ),
    )
    return {"session_id": session_id, "positive_pin": positive_pin, "negative_pin": negative_pin, "ref_des": ref_des}


@mcp.tool
async def optimizepi_set_frequency_range(session_id: str, start_freq: str, end_freq: str) -> dict:
    """Set the frequency range OptimizePI analyzes over.

    `start_freq`/`end_freq` must include a unit suffix exactly as OptimizePI's Tcl
    expects (e.g. "10kHz", "1GHz") — passed through verbatim, not parsed, matching the
    same convention as PowerSI's frequency tools. Appends
    `sigrity::update simu -startFreq {<start_freq>} -endFreq {<end_freq>} {!}`.
    """
    tcl_sessions.add_line(
        session_id, f"sigrity::update simu -startFreq {tcl_str(start_freq)} -endFreq {tcl_str(end_freq)} {{!}}"
    )
    return {"session_id": session_id, "start_freq": start_freq, "end_freq": end_freq}


@mcp.tool
async def optimizepi_configure_optimization(
    session_id: str,
    name: str,
    ref_des: str,
    objective: str = "Best Performance vs. Cost",
    min_caps: Optional[int] = None,
    max_caps: Optional[int] = None,
    max_cost: Optional[float] = None,
    max_area: Optional[float] = None,
) -> dict:
    """Configure the decap-optimization goal and constraints for one device/optimization target.

    `objective` is passed through verbatim (OptimizePI's default is "Best Performance
    vs. Cost"); `min_caps`/`max_caps` bound the candidate decap count, `max_cost`/
    `max_area` bound cost/board-area budgets — omit any constraint you don't want to
    apply. Appends
    `sigrity::update deviceOPTI -name {<name>} -refDes {<ref_des>} -opiObjective {<objective>} [-min {n}] [-max {n}] [-maxCost {v}] [-maxArea {v}] {!}`.
    """
    parts = [
        "sigrity::update deviceOPTI",
        f"-name {tcl_str(name)}",
        f"-refDes {tcl_str(ref_des)}",
        f"-opiObjective {tcl_str(objective)}",
    ]
    if min_caps is not None:
        parts.append(f"-min {{{min_caps}}}")
    if max_caps is not None:
        parts.append(f"-max {{{max_caps}}}")
    if max_cost is not None:
        parts.append(f"-maxCost {{{max_cost}}}")
    if max_area is not None:
        parts.append(f"-maxArea {{{max_area}}}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "name": name, "ref_des": ref_des, "objective": objective}


@mcp.tool
async def optimizepi_generate_report(session_id: str) -> dict:
    """Queue OptimizePI's standard optimization report. Appends `sigrity::do genReport {!}`."""
    tcl_sessions.add_line(session_id, "sigrity::do genReport {!}")
    return {"session_id": session_id}


@mcp.tool
async def optimizepi_export_impedance_plot(
    session_id: str,
    output_file: str,
    port_name: str,
    file_type: _PLOT_FILE_TYPES = "CSV",
) -> dict:
    """Queue an export of an impedance-vs-frequency plot for a named port once the run finishes.

    `file_type` selects the on-disk format: 'CSV' (default), 'BNP' (Sigrity binary), or
    'touchstone'. Appends
    `sigrity::export impedanceplot -pathname {<output_file>} -filetype {<file_type>} -portname {<port_name>} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::export impedanceplot -pathname {tcl_path(output_file)} "
            f"-filetype {tcl_str(file_type)} -portname {tcl_str(port_name)} {{!}}"
        ),
    )
    return {"session_id": session_id, "output_file": output_file, "port_name": port_name, "file_type": file_type}


@mcp.tool
async def optimizepi_run_session(session_id: str) -> dict:
    """Write out the session's accumulated Tcl macro and launch OptimizePI against it as a background job.

    Runs `OptimizePI.exe -b -export_report -tcl <macro.tcl>`. Returns a job_id
    immediately; poll it with get_job_status/wait_for_job.
    """
    record = await run_session(
        session_id, tool="optimizepi", tcl_arg_flag="-tcl", build_args=["-b", "-export_report"]
    )
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
    }
