"""OptimizePI automation — decap/VRM placement optimization and PDN target-impedance analysis.

CONSOLIDATED (compact-tool-surface pass): the 8 individual "compose" functions below
(`optimizepi_attach_layout`, `optimizepi_add_vrm`, etc. — same Tcl-line-building logic
as before, kept as plain importable Python functions with their original names so
existing direct-call test code is unaffected, just no longer each its own top-level MCP
tool) are now driven through ONE dispatcher tool, `optimizepi_configure(session_id,
operations)`, where `operations` is a list of `{"op": "<short-name>", **kwargs}` dicts
(`short-name` = the function name with the `optimizepi_` prefix stripped, e.g.
`{"op": "add_vrm", "power_net": ...}` calls `optimizepi_add_vrm`). This cuts a full
OptimizePI flow from ~10 MCP round trips (one per compose call) to 3:
`start_optimizepi_session` -> `optimizepi_configure([...])` -> `optimizepi_run_session`.
Every operation's underlying validation/Tcl-quoting is UNCHANGED — this only changes how
many separate tool calls an agent needs, not what each operation does or how safely it's
built. See `optimizepi_configure`'s own docstring for the full op list.

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
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.create("optimizepi")
    tcl_sessions.add_line(
        session.session_id,
        f"sigrity::update workflow -product {{OptimizePI}} -workflowkey {tcl_str(workflow_key)} {{!}}",
    )
    return {"session_id": session.session_id, "workflow_key": workflow_key}


async def optimizepi_attach_layout(session_id: str, spd_file: str) -> dict:
    """Attach a layout (.spd) design to the current OptimizePI session.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, f"sigrity::open document -attach {tcl_path(spd_file)} {{!}}")
    return {"session_id": session_id, "spd_file": spd_file}


async def optimizepi_add_vrm(session_id: str, power_net: str, ground_net: str, ref_des: str) -> dict:
    """Add a VRM (voltage regulator module) reference on a power/ground net pair, by component.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add VRM -byNet -powerName {tcl_str(power_net)} "
            f"-groundName {tcl_str(ground_net)} -component {tcl_str(ref_des)} {{!}}"
        ),
    )
    return {"session_id": session_id, "power_net": power_net, "ground_net": ground_net, "ref_des": ref_des}


async def optimizepi_add_decap_candidate(
    session_id: str,
    power_net: str,
    ground_net: str,
    decap_type: _DECAP_TYPES,
    ref_des: str,
) -> dict:
    """Add a decoupling-capacitor placement candidate on a power/ground net pair for the optimizer to consider.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
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


async def optimizepi_add_impedance_observation(
    session_id: str,
    positive_pin: str,
    negative_pin: str,
    ref_des: str,
) -> dict:
    """Add an impedance-observation point (a pin pair to track PDN impedance at) for the optimizer's target-impedance analysis.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add impedanceObservation -byPin -positivePinName {tcl_str(positive_pin)} "
            f"-negativePinName {tcl_str(negative_pin)} -component {tcl_str(ref_des)} {{!}}"
        ),
    )
    return {"session_id": session_id, "positive_pin": positive_pin, "negative_pin": negative_pin, "ref_des": ref_des}


async def optimizepi_set_frequency_range(session_id: str, start_freq: str, end_freq: str) -> dict:
    """Set the frequency range OptimizePI analyzes over.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id, f"sigrity::update simu -startFreq {tcl_str(start_freq)} -endFreq {tcl_str(end_freq)} {{!}}"
    )
    return {"session_id": session_id, "start_freq": start_freq, "end_freq": end_freq}


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
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
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


async def optimizepi_generate_report(session_id: str) -> dict:
    """Queue OptimizePI's standard optimization report. Appends `sigrity::do genReport {!}`.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, "sigrity::do genReport {!}")
    return {"session_id": session_id}


async def optimizepi_export_impedance_plot(
    session_id: str,
    output_file: str,
    port_name: str,
    file_type: _PLOT_FILE_TYPES = "CSV",
) -> dict:
    """Queue an export of an impedance-vs-frequency plot for a named port once the run finishes.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::export impedanceplot -pathname {tcl_path(output_file)} "
            f"-filetype {tcl_str(file_type)} -portname {tcl_str(port_name)} {{!}}"
        ),
    )
    return {"session_id": session_id, "output_file": output_file, "port_name": port_name, "file_type": file_type}


_CONFIGURE_OPS = {
    "attach_layout": optimizepi_attach_layout,
    "add_vrm": optimizepi_add_vrm,
    "add_decap_candidate": optimizepi_add_decap_candidate,
    "add_impedance_observation": optimizepi_add_impedance_observation,
    "set_frequency_range": optimizepi_set_frequency_range,
    "configure_optimization": optimizepi_configure_optimization,
    "generate_report": optimizepi_generate_report,
    "export_impedance_plot": optimizepi_export_impedance_plot,
}


@mcp.tool
async def optimizepi_configure(session_id: str, operations: list[dict]) -> dict:
    """Apply a list of OptimizePI session-configuration operations in one call (replaces calling the 8 individual compose tools one at a time).

    Each item in `operations` is `{"op": "<name>", **kwargs}` where `<name>` is one of:
    `attach_layout, add_vrm, add_decap_candidate, add_impedance_observation,
    set_frequency_range, configure_optimization, generate_report,
    export_impedance_plot` and `kwargs` are that operation's own parameters (everything
    except `session_id`, which is threaded through automatically) — see each
    corresponding `optimizepi_*` function's own docstring (still present in this module,
    just no longer individually exposed as a top-level tool) for its exact kwargs.
    Operations are applied in list order, since later ones (e.g. an impedance-plot
    export) can depend on earlier ones (e.g. the observation point existing). Raises
    `ValueError` naming the exact index and op on an unknown `op` or a bad/missing
    kwarg, rather than silently skipping it.

    Example: `operations=[{"op": "attach_layout", "spd_file": "board.spd"},
    {"op": "add_vrm", "power_net": "+3V3", "ground_net": "GND", "ref_des": "U1"},
    {"op": "set_frequency_range", "start_freq": "1MHz", "end_freq": "100MHz"}]`.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    results = []
    for i, raw_op in enumerate(operations):
        op = dict(raw_op)
        name = op.pop("op", None)
        fn = _CONFIGURE_OPS.get(name)
        if fn is None:
            raise ValueError(
                f"operations[{i}]: unknown op {name!r}. Valid ops: {sorted(_CONFIGURE_OPS)}"
            )
        try:
            result = await fn(session_id, **op)
        except TypeError as e:
            raise ValueError(f"operations[{i}] (op={name!r}): {e}") from e
        results.append({"op": name, **result})
    return {"session_id": session_id, "operations_applied": len(results), "results": results}


@mcp.tool
async def optimizepi_run_session(session_id: str) -> dict:
    """Write out the session's accumulated Tcl macro and launch OptimizePI against it as a background job.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    record = await run_session(
        session_id, tool="optimizepi", tcl_arg_flag="-tcl", build_args=["-b", "-export_report"]
    )
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
    }
