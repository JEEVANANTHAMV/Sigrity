"""PowerDC automation — DC IR-drop analysis, electro-thermal (E-T) co-simulation, and
thermal power-integrity analysis.

CONSOLIDATED (compact-tool-surface pass): the 11 individual "compose" functions below
(`powerdc_set_simulation_mode`, `powerdc_add_vrm`, etc. — same Tcl-line-building logic
as before, kept as plain importable Python functions with their original names so
existing direct-call test code is unaffected, just no longer each its own top-level MCP
tool) are now driven through ONE dispatcher tool, `powerdc_configure(session_id,
operations)`, where `operations` is a list of `{"op": "<short-name>", **kwargs}` dicts
(`short-name` = the function name with the `powerdc_` prefix stripped, e.g.
`{"op": "add_vrm", "power_net": ...}` calls `powerdc_add_vrm`). This cuts a full
PowerDC flow from ~13 MCP round trips (one per compose call) to 3:
`start_powerdc_session` -> `powerdc_configure([...])` -> `powerdc_run_session`. Every
operation's underlying validation/Tcl-quoting is UNCHANGED — this only changes how many
separate tool calls an agent needs, not what each operation does or how safely it's
built. See `powerdc_configure`'s own docstring for the full op list.

NOTE: PowerDC's own user guide never documents a raw `-tcl <script.tcl>` batch switch
the way PowerSI's does. `powerdc_run_session` (below) uses it anyway (`-b -tcl <script>
[spd]`), following the same shared-launcher-family convention as PowerSI/OptimizePI/
XcitePI — and this has now been CONFIRMED empirically against a real
sample design on this no-license-required machine (see powerdc_run_session's docstring). What's still
genuinely unconfirmed is the exact spelling of every individual `sigrity::` flag —
e.g. PowerDC rejected `-eTcoSimulation` outright when tested (see
powerdc_set_simulation_mode's docstring). The `sigrity::` Tcl vocabulary itself
(open/set/add/update/save/do) and the `-Report` CLI sign-off mode are transcribed from
real sample scripts and the CLI reference, not guessed, but individual flag names
should still be treated as "best transcription, not guaranteed" until exercised.

Usage pattern: start_powerdc_session -> one or more powerdc_* "compose" tools (each just
appends a Tcl line, no process launched) -> powerdc_run_session (writes the accumulated
script, appends `sigrity::begin simulation {!}`, and actually launches PowerDC once).
Use preview_tcl_session/close_tcl_session (sigrity_mcp.domains.platform.session_tools)
to inspect or discard a session, and the job-control tools (get_job_status,
tail_job_log, list_job_files, read_job_output_file) to track/retrieve the run started by
powerdc_run_session. powerdc_export_signoff_report is a separate, CLI-only tool (no Tcl
session involved) for PowerDC's `-Report` batch mode against an already-simulated case.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_SINK_MODELS = Literal["Equal Voltage", "Equal Current", "Unequal Current"]
_DISSIPATION_SOURCE = Literal["Volume", "Top Surface", "Bottom Surface"]
_BOARD_TYPE = Literal["tbLead2s2p27", "tbBGA1s40"]
_REPORT_TYPE = Literal[
    "all", "VoltageDistribution", "ViaCurrent", "PinIRdrop", "PowerLoss",
    "PlanePowerDensity", "PlaneCurrentDensity", "Temperature", "PinResistance",
    "HeatFlux", "Conductivity", "FusionCurrentDensity", "MeanTimeToFailure",
]


def _net_arg(power_net: str, ground_net: str) -> str:
    return f"-net {tcl_str(f'{power_net},{ground_net}')}"


def _ckt_arg(ref_des: Union[str, list[str]]) -> str:
    """Format a `-ckt` value: a single RefDes, or a list joined as `{RD1}{RD2}...`
    (matching the real sample scripts, e.g. `-ckt {Vrm3}{Vrm2}{Vrm1}`)."""
    if isinstance(ref_des, (list, tuple)):
        return "-ckt " + "".join(tcl_str(r) for r in ref_des)
    return f"-ckt {tcl_str(ref_des)}"


@mcp.tool
async def start_powerdc_session(spd_file: str) -> dict:
    """Begin a new PowerDC automation session by opening an empty document, then attaching a layout (.spd) design.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.create("powerdc")
    tcl_sessions.add_line(session.session_id, "sigrity::open document {!}")
    tcl_sessions.add_line(
        session.session_id, f"sigrity::open document -attach {tcl_path(spd_file)} {{!}}"
    )
    return {"session_id": session.session_id, "spd_file": spd_file}


async def powerdc_set_simulation_mode(
    session_id: str,
    ir_drop_analysis: bool = False,
    e_t_co_simulation: bool = False,
    thermal_only: bool = False,
) -> dict:
    """Select which PowerDC analysis mode(s) this session runs: DC IR-drop, electro-thermal co-simulation, or thermal-only.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    parts = ["sigrity::set pdcSimMode"]
    if ir_drop_analysis:
        parts.append("-irDropAnalysis {1}")
    if e_t_co_simulation:
        parts.append("-eTcoSimulation {1}")
    if thermal_only:
        parts.append("-thermalOnly {1}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {
        "session_id": session_id,
        "ir_drop_analysis": ir_drop_analysis,
        "e_t_co_simulation": e_t_co_simulation,
        "thermal_only": thermal_only,
    }


async def powerdc_add_vrm(
    session_id: str,
    power_net: str,
    ground_net: str,
    ref_des: Union[str, list[str]],
    voltage: float,
) -> dict:
    """Add a voltage-regulator-module (VRM) source on a power/ground net pair for one or more components.

    LIVE-TESTED 2026-10-02 and NOT YET WORKING on a plain SPDIF-translated board: `sigrity::add pdcVRM
    -auto -net {power,ground} ...` consistently fails with `The net pair '-net {power net name, ground
    net name}' is not specified.` even with real net names from the attached design and real copper
    present on the referenced layer (the suspected missing-copper cause was tested and ruled out -- see
    `core.tool_status`'s `powerdc`/`allegro` notes for the full 4-variation investigation). Leading
    hypothesis: `-auto -net {X,Y}` resolves against pre-defined PowerDC Net Classes (as seen in this
    suite's own `IR_Package.pdcx`, and in every real Cadence sample script, which always uses the
    literal class name `PowerNets` rather than any board-specific net), not raw net-name strings -- a
    bare SPDIF-translated `.spd` with no Net Class/AMM setup may not satisfy this regardless of net
    names. Treat this tool as unconfirmed until a Net-Class-defined design is tried.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    ckt = _ckt_arg(ref_des)
    tcl_sessions.add_line(
        session_id,
        f"sigrity::add pdcVRM -auto {_net_arg(power_net, ground_net)} {ckt} -voltage {{{voltage}}} {{!}}",
    )
    return {"session_id": session_id, "power_net": power_net, "ground_net": ground_net, "ref_des": ref_des}


async def powerdc_add_sink(
    session_id: str,
    power_net: str,
    ground_net: str,
    ref_des: Union[str, list[str]],
    model: _SINK_MODELS = "Equal Current",
    voltage: Optional[float] = None,
    current: Optional[float] = None,
    upper_tolerance: Optional[str] = None,
    lower_tolerance: Optional[str] = None,
) -> dict:
    """Add a current-sink (load device) on a power/ground net pair for one or more components.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    parts = [
        "sigrity::add pdcSink -auto",
        _net_arg(power_net, ground_net),
        _ckt_arg(ref_des),
        f"-model {tcl_str(model)}",
    ]
    if voltage is not None:
        parts.append(f"-voltage {{{voltage}}}")
    if current is not None:
        parts.append(f"-current {{{current}}}")
    if upper_tolerance is not None:
        parts.append(f"-upperTolerance {tcl_str(upper_tolerance)}")
    if lower_tolerance is not None:
        parts.append(f"-lowerTolerance {tcl_str(lower_tolerance)}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "power_net": power_net, "ground_net": ground_net, "ref_des": ref_des}


async def powerdc_add_interconnect(
    session_id: str,
    power_net: str,
    ground_net: str,
    ref_des: Union[str, list[str]],
    resistance: float,
    positive_pin: Optional[str] = None,
    negative_pin: Optional[str] = None,
) -> dict:
    """Add a fixed-resistance interconnect element (e.g. a jumper or fuse) on a power/ground net pair.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    parts = ["sigrity::add pdcInter -auto", _net_arg(power_net, ground_net), _ckt_arg(ref_des)]
    if positive_pin is not None:
        parts.append(f"-positivePin {tcl_str(positive_pin)}")
    if negative_pin is not None:
        parts.append(f"-negativePin {tcl_str(negative_pin)}")
    parts.append(f"-resistance {{{resistance}}}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "ref_des": ref_des, "resistance": resistance}


async def powerdc_mark_thermal_component(session_id: str, ref_des: str) -> dict:
    """Flag a component as a thermal component so PowerDC includes it in thermal/electro-thermal analysis.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id, f"sigrity::update circuit {tcl_str(ref_des)} -setAsThermalComponent {{1}} {{!}}"
    )
    return {"session_id": session_id, "ref_des": ref_des}


async def powerdc_set_power_dissipation(
    session_id: str,
    ref_des: str,
    watts: Optional[float] = None,
    power_map_file: Optional[str] = None,
    source: _DISSIPATION_SOURCE = "Volume",
    output_temperature_map: Optional[str] = None,
) -> dict:
    """Set a thermal component's power dissipation, either as a fixed wattage or from a power-map file.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    if (watts is None) == (power_map_file is None):
        raise ValueError("Provide exactly one of watts or power_map_file, not both/neither.")

    if watts is not None:
        inner = f"-type {{Power}} -value {{{watts}}} -source {tcl_str(source)}"
    else:
        inner = f"-type {{Power}} -filename {tcl_path(power_map_file)} -powerMap {{0}} -source {tcl_str(source)}"
    if output_temperature_map is not None:
        inner += f" -outputTemmperatureMap {tcl_path(output_temperature_map)}"

    tcl_sessions.add_line(session_id, f"sigrity::update circuit {tcl_str(ref_des)} -dissipation {{{inner}}} {{!}}")
    return {"session_id": session_id, "ref_des": ref_des, "watts": watts, "power_map_file": power_map_file}


async def powerdc_set_thermal_test_board(
    session_id: str,
    board_type: _BOARD_TYPE,
    stackup: str,
    dimension: str,
    enhance_pkg_area: bool = False,
) -> dict:
    """Configure PowerDC's standard JEDEC-style thermal test board (used for package-level thermal characterization).
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::update pdcTestBoard -type {tcl_str(board_type)} "
            f"-stackup {tcl_str(stackup)} -dimension {tcl_str(dimension)} "
            f"-enhancePKGArea {{{int(enhance_pkg_area)}}} {{!}}"
        ),
    )
    return {"session_id": session_id, "board_type": board_type}


async def powerdc_enable_autosave_results(session_id: str, save_excel: bool = True) -> dict:
    """Enable PowerDC's auto-save of simulation results (and optionally the Excel results workbook) once the run finishes.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        f"sigrity::update option -AutoSaveSimulationResult {{1}} -AutoSaveExcelResult {{{int(save_excel)}}} {{!}}",
    )
    return {"session_id": session_id, "save_excel": save_excel}


async def powerdc_save_workspace(session_id: str, pdcx_file: str) -> dict:
    """Save the current PowerDC workspace/setup to a `.pdcx` file within the session's macro.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, f"sigrity::save -w {tcl_path(pdcx_file)} {{!}}")
    return {"session_id": session_id, "pdcx_file": pdcx_file}


async def powerdc_run_one_step_powertree(
    session_id: str,
    vrm_sink_csv: str,
    extract_rules_xml: str,
    amm_library: str,
) -> dict:
    """Queue PowerDC's \"One-Step PowerTree\" automated VRM/sink extraction from a spreadsheet, inside the current session's macro.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::do OneStepPowerTree -VrmSink {tcl_path(vrm_sink_csv)} "
            f"-ExtractRules {tcl_path(extract_rules_xml)} -ammLibrary {tcl_path(amm_library)} {{!}}"
        ),
    )
    return {
        "session_id": session_id,
        "vrm_sink_csv": vrm_sink_csv,
        "extract_rules_xml": extract_rules_xml,
        "amm_library": amm_library,
    }


async def powerdc_generate_signoff_report(
    session_id: str,
    output_file: str,
    result_table: bool = True,
    diagram_plot: bool = True,
    sink_irdrop_summary_csv: bool = True,
    board_stackup: bool = False,
    layout_view: bool = False,
    all_plots: bool = False,
    all_options: bool = False,
) -> dict:
    """Queue generation of PowerDC's sign-off HTML report from *within* the current Tcl session (before/instead of running PowerDC's separate `-Report` CLI batch mode).
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    parts = ["sigrity::do pdcReport"]
    flag_map = {
        "-resultTable": result_table,
        "-diagramPlot": diagram_plot,
        "-sinkIRDropSummaryCsv": sink_irdrop_summary_csv,
        "-boardStackup": board_stackup,
        "-layoutView": layout_view,
        "-allPlots": all_plots,
        "-allOptions": all_options,
    }
    for flag, enabled in flag_map.items():
        if enabled:
            parts.append(flag)
    parts.append(f"-fileName {tcl_path(output_file)}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "output_file": output_file}


_CONFIGURE_OPS = {
    "set_simulation_mode": powerdc_set_simulation_mode,
    "add_vrm": powerdc_add_vrm,
    "add_sink": powerdc_add_sink,
    "add_interconnect": powerdc_add_interconnect,
    "mark_thermal_component": powerdc_mark_thermal_component,
    "set_power_dissipation": powerdc_set_power_dissipation,
    "set_thermal_test_board": powerdc_set_thermal_test_board,
    "enable_autosave_results": powerdc_enable_autosave_results,
    "save_workspace": powerdc_save_workspace,
    "run_one_step_powertree": powerdc_run_one_step_powertree,
    "generate_signoff_report": powerdc_generate_signoff_report,
}


@mcp.tool
async def powerdc_configure(session_id: str, operations: list[dict]) -> dict:
    """Apply a list of PowerDC session-configuration operations in one call (replaces calling the 11 individual compose tools one at a time).

    Each item in `operations` is `{"op": "<name>", **kwargs}` where `<name>` is one of:
    `set_simulation_mode, add_vrm, add_sink, add_interconnect,
    mark_thermal_component, set_power_dissipation, set_thermal_test_board,
    enable_autosave_results, save_workspace, run_one_step_powertree,
    generate_signoff_report` and `kwargs` are that operation's own parameters (everything
    except `session_id`, which is threaded through automatically) — see each
    corresponding `powerdc_*` function's own docstring (still present in this module,
    just no longer individually exposed as a top-level tool) for its exact kwargs and
    caveats (e.g. `add_vrm`'s unconfirmed Net-Class requirement). Operations are applied
    in list order, since later ones (e.g. a dissipation update) can depend on earlier
    ones (e.g. the component existing). Raises `ValueError` naming the exact index and
    op on an unknown `op` or a bad/missing kwarg, rather than silently skipping it.

    Example: `operations=[{"op": "set_simulation_mode", "ir_drop_analysis": True},
    {"op": "add_sink", "power_net": "+3V3", "ground_net": "GND", "ref_des": "U1",
    "current": 1.2}]`.
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
async def powerdc_run_session(session_id: str, spd_file: Optional[str] = None) -> dict:
    """Write out the session's accumulated Tcl macro and launch PowerDC against it as a background job.
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, "sigrity::begin simulation {!}")
    record = await run_session(
        session_id,
        tool="powerdc",
        tcl_arg_flag="-tcl",
        build_args=["-b"],
        extra_args=[spd_file] if spd_file else None,
    )
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
    }


@mcp.tool
async def powerdc_export_signoff_report(case_file: str, report_type: _REPORT_TYPE = "all") -> dict:
    """Generate a PowerDC sign-off report against an already-simulated case, via PowerDC's CLI-only `-Report` batch mode (no Tcl session involved).
Call load_skill('sigrity-pi') for the full verified playbook, pitfalls, and a live example."""
    args = ["-b", case_file, "-Report", f"-{report_type}"]
    record = await submit_job(tool="powerdc", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
