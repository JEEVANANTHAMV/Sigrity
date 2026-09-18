"""PowerDC automation — DC IR-drop analysis, electro-thermal (E-T) co-simulation, and
thermal power-integrity analysis.

IMPORTANT CAVEAT: PowerDC's own user guide never documents a raw `-tcl <script.tcl>`
batch switch the way PowerSI's does — the documented model there is "configure via Tcl
in the GUI, `sigrity::save -w {file.pdcx}`, then run PowerDC in batch against that
`.pdcx`". `powerdc_run_session` (below) follows the same shared-launcher-family
convention as PowerSI/OptimizePI/XcitePI anyway (`-b -tcl <script> [spd]`) since that's
the most defensible inference (all four share the same launcher binary family) — but
this has NOT been empirically verified against a live license on this machine, so treat
it as best-effort until confirmed. The `sigrity::` Tcl vocabulary itself (open/set/add/
update/save/do) and the `-Report` CLI sign-off mode are transcribed from real sample
scripts and the CLI reference, not guessed.

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

    Returns a session_id — pass it to every other powerdc_* tool below to keep adding
    steps (simulation mode, VRMs, sinks, thermal setup, ...) to the same macro, then
    finish with powerdc_run_session. Nothing is executed yet; this records
    `sigrity::open document {!}` followed by `sigrity::open document -attach {<spd_file>} {!}`,
    matching the real sample scripts (e.g. share/SpeedXP/Samples/PowerDC/Electrical_Analysis/MB.tcl).
    """
    session = tcl_sessions.create("powerdc")
    tcl_sessions.add_line(session.session_id, "sigrity::open document {!}")
    tcl_sessions.add_line(
        session.session_id, f"sigrity::open document -attach {tcl_path(spd_file)} {{!}}"
    )
    return {"session_id": session.session_id, "spd_file": spd_file}


@mcp.tool
async def powerdc_set_simulation_mode(
    session_id: str,
    ir_drop_analysis: bool = False,
    e_t_co_simulation: bool = False,
    thermal_only: bool = False,
) -> dict:
    """Select which PowerDC analysis mode(s) this session runs: DC IR-drop, electro-thermal co-simulation, or thermal-only.

    Appends `sigrity::set pdcSimMode -irDropAnalysis {0|1} -eTcoSimulation{0|1} -thermalOnly{0|1} {!}`.
    These are independent toggles per PowerDC's own Tcl option — pass True for whichever
    mode(s) this run needs (real sample scripts typically set just one, e.g.
    `-IRDropAnalysis {1}` for a pure DC IR-drop study).
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::set pdcSimMode -irDropAnalysis {{{int(ir_drop_analysis)}}} "
            f"-eTcoSimulation{{{int(e_t_co_simulation)}}} "
            f"-thermalOnly{{{int(thermal_only)}}} {{!}}"
        ),
    )
    return {
        "session_id": session_id,
        "ir_drop_analysis": ir_drop_analysis,
        "e_t_co_simulation": e_t_co_simulation,
        "thermal_only": thermal_only,
    }


@mcp.tool
async def powerdc_add_vrm(
    session_id: str,
    power_net: str,
    ground_net: str,
    ref_des: Union[str, list[str]],
    voltage: float,
) -> dict:
    """Add a voltage-regulator-module (VRM) source on a power/ground net pair for one or more components.

    `ref_des` may be a single RefDes string or a list — a list is joined as
    `{RD1}{RD2}...` per the real sample scripts. Appends
    `sigrity::add pdcVRM -auto -net {power,ground} -ckt {RefDes} -voltage {v} {!}`.
    """
    ckt = _ckt_arg(ref_des)
    tcl_sessions.add_line(
        session_id,
        f"sigrity::add pdcVRM -auto {_net_arg(power_net, ground_net)} {ckt} -voltage {{{voltage}}} {{!}}",
    )
    return {"session_id": session_id, "power_net": power_net, "ground_net": ground_net, "ref_des": ref_des}


@mcp.tool
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

    `model` selects PowerDC's sink behavior: 'Equal Voltage', 'Equal Current' (default),
    or 'Unequal Current'. `upper_tolerance`/`lower_tolerance` are passed through verbatim
    as PowerDC expects them (a value and a percent, e.g. "0.05,5%") since the exact
    internal comma convention isn't validated here. Appends
    `sigrity::add pdcSink -auto -net {power,ground} -ckt {RefDes} -model {model} [-voltage {v}] [-current {i}] [-upperTolerance {..}] [-lowerTolerance {..}] {!}`.
    """
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


@mcp.tool
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

    Appends
    `sigrity::add pdcInter -auto -net {power,ground} -ckt {RefDes} [-positivePin{pin}] [-negativePin{pin}] -resistance {v} {!}`.
    """
    parts = ["sigrity::add pdcInter -auto", _net_arg(power_net, ground_net), _ckt_arg(ref_des)]
    if positive_pin is not None:
        parts.append(f"-positivePin{tcl_str(positive_pin)}")
    if negative_pin is not None:
        parts.append(f"-negativePin{tcl_str(negative_pin)}")
    parts.append(f"-resistance {{{resistance}}}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "ref_des": ref_des, "resistance": resistance}


@mcp.tool
async def powerdc_mark_thermal_component(session_id: str, ref_des: str) -> dict:
    """Flag a component as a thermal component so PowerDC includes it in thermal/electro-thermal analysis.

    Appends `sigrity::update circuit {<ref_des>} -setAsThermalComponent {1} {!}`.
    """
    tcl_sessions.add_line(
        session_id, f"sigrity::update circuit {tcl_str(ref_des)} -setAsThermalComponent {{1}} {{!}}"
    )
    return {"session_id": session_id, "ref_des": ref_des}


@mcp.tool
async def powerdc_set_power_dissipation(
    session_id: str,
    ref_des: str,
    watts: Optional[float] = None,
    power_map_file: Optional[str] = None,
    source: _DISSIPATION_SOURCE = "Volume",
    output_temperature_map: Optional[str] = None,
) -> dict:
    """Set a thermal component's power dissipation, either as a fixed wattage or from a power-map file.

    Pass exactly one of `watts` (a single dissipation value) or `power_map_file` (a
    spatial power-map text file) — this raises ValueError if both or neither are given.
    `source` picks which surface/volume the dissipation is applied to. If
    `output_temperature_map` is given, PowerDC writes the resulting per-cell temperature
    map to that file. Note: the Tcl option name `outputTemmperatureMap` is genuinely
    misspelled in Cadence's own API (extra 'm') — it is kept exactly as-is here, not
    "fixed". Appends one of:
    `sigrity::update circuit {RefDes} -dissipation {-type {Power} -value {watts} -source {src} -outputTemmperatureMap {file}} {!}`
    or
    `sigrity::update circuit {RefDes} -dissipation {-type {Power} -filename {file} -powerMap {0} -source {src} -outputTemmperatureMap {file}} {!}`.
    """
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


@mcp.tool
async def powerdc_set_thermal_test_board(
    session_id: str,
    board_type: _BOARD_TYPE,
    stackup: str,
    dimension: str,
    enhance_pkg_area: bool = False,
) -> dict:
    """Configure PowerDC's standard JEDEC-style thermal test board (used for package-level thermal characterization).

    `stackup`/`dimension` are passed through verbatim as pre-formatted, comma-separated
    strings per PowerDC's own convention (e.g. `"0.0762,0.1143,0.0096,0.0096,40,0,0,0"`)
    — this tool does not parse or validate their internal structure, the caller is
    responsible for formatting them correctly for the chosen `board_type`. Appends
    `sigrity::update pdcTestBoard -type {board_type} -stackup {stackup} -dimension {dimension} -enhancePKGArea {0|1} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::update pdcTestBoard -type {tcl_str(board_type)} "
            f"-stackup {tcl_str(stackup)} -dimension {tcl_str(dimension)} "
            f"-enhancePKGArea {{{int(enhance_pkg_area)}}} {{!}}"
        ),
    )
    return {"session_id": session_id, "board_type": board_type}


@mcp.tool
async def powerdc_enable_autosave_results(session_id: str, save_excel: bool = True) -> dict:
    """Enable PowerDC's auto-save of simulation results (and optionally the Excel results workbook) once the run finishes.

    Appends `sigrity::update option -AutoSaveSimulationResult {1} -AutoSaveExcelResult {0|1} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        f"sigrity::update option -AutoSaveSimulationResult {{1}} -AutoSaveExcelResult {{{int(save_excel)}}} {{!}}",
    )
    return {"session_id": session_id, "save_excel": save_excel}


@mcp.tool
async def powerdc_save_workspace(session_id: str, pdcx_file: str) -> dict:
    """Save the current PowerDC workspace/setup to a `.pdcx` file within the session's macro.

    This is the step the PowerDC user guide actually documents for batch runs: configure
    via Tcl, save to `.pdcx`, then run PowerDC in batch against that file. Appends
    `sigrity::save -w {<pdcx_file>} {!}`.
    """
    tcl_sessions.add_line(session_id, f"sigrity::save -w {tcl_path(pdcx_file)} {{!}}")
    return {"session_id": session_id, "pdcx_file": pdcx_file}


@mcp.tool
async def powerdc_run_one_step_powertree(
    session_id: str,
    vrm_sink_csv: str,
    extract_rules_xml: str,
    amm_library: str,
) -> dict:
    """Queue PowerDC's "One-Step PowerTree" automated VRM/sink extraction from a spreadsheet, inside the current session's macro.

    PowerTree has no standalone documented batch executable of its own — it is driven
    from inside PowerDC (or OptimizePI) via this Tcl command. Appends
    `sigrity::do OneStepPowerTree -VrmSink{<vrm_sink_csv>} -ExtractRules{<extract_rules_xml>} -ammLibrary{<amm_library>} {!}`.
    This only records the step; call powerdc_run_session afterwards to actually execute it.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::do OneStepPowerTree -VrmSink{tcl_path(vrm_sink_csv)} "
            f"-ExtractRules{tcl_path(extract_rules_xml)} -ammLibrary{tcl_path(amm_library)} {{!}}"
        ),
    )
    return {
        "session_id": session_id,
        "vrm_sink_csv": vrm_sink_csv,
        "extract_rules_xml": extract_rules_xml,
        "amm_library": amm_library,
    }


@mcp.tool
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

    This is the `sigrity::do pdcReport` Tcl command, distinct from the CLI-only
    `powerdc_export_signoff_report` tool below (which drives PowerDC's `-Report` batch
    switch against an already-simulated case file, outside any Tcl session). Appends
    `sigrity::do pdcReport [-resultTable] [-diagramPlot] [-sinkIRDropSummaryCsv] [-boardStackup] [-layoutView] [-allPlots] [-allOptions] -fileName {<output_file>} {!}`.
    """
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


@mcp.tool
async def powerdc_run_session(session_id: str, spd_file: Optional[str] = None) -> dict:
    """Write out the session's accumulated Tcl macro and launch PowerDC against it as a background job.

    UNVERIFIED SYNTAX CAVEAT: PowerDC's official docs do not confirm a `-tcl` batch
    switch the way PowerSI's do; this follows the same shared-launcher convention as the
    other `sigrity::`-scripted tools (PowerSI/OptimizePI/XcitePI) but has not been
    empirically verified against a live license on this machine — treat it as
    best-effort until confirmed. The documented, confirmed alternative is: use the
    compose tools above to build up a setup, call powerdc_save_workspace to write a
    `.pdcx`, then invoke PowerDC's batch mode directly against that file
    (`PowerDC.exe -b [switches] setup.pdcx [layout.spd]`) yourself if this run mode turns
    out not to work on your license.

    Before running, this appends `sigrity::begin simulation {!}` as the final macro line
    (confirmed via real sample scripts, e.g. MB.tcl, even though it isn't documented on
    the official Tcl reference pages — it's the actual run trigger). Only pass
    `spd_file` if the design isn't already the one opened by start_powerdc_session.
    Runs `PowerDC.exe -b -tcl <macro.tcl> [spd_file]`. Returns a job_id immediately; poll
    it with get_job_status/wait_for_job.
    """
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

    Runs `PowerDC.exe -b <case_file> -Report -<report_type>` as a background job.
    `case_file` should be a `.pdcx` (or equivalent saved case) that already holds
    simulation results — this mode post-processes an existing case rather than running a
    new simulation. `report_type` selects one section (PowerDC also accepts short
    aliases like `-V`/`-VC`/`-PI`/etc. for these, not used here for clarity):
    'all', 'VoltageDistribution', 'ViaCurrent', 'PinIRdrop', 'PowerLoss',
    'PlanePowerDensity', 'PlaneCurrentDensity', 'Temperature', 'PinResistance',
    'HeatFlux', 'Conductivity', 'FusionCurrentDensity', or 'MeanTimeToFailure'.
    This is a distinct capability from powerdc_generate_signoff_report (which queues
    `sigrity::do pdcReport` inside a Tcl session) — use this one when you already have a
    saved case and just want its sign-off report regenerated without reopening a session.
    """
    args = ["-b", case_file, "-Report", f"-{report_type}"]
    record = await submit_job(tool="powerdc", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
