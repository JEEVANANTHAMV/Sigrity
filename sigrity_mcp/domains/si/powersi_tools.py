"""PowerSI automation — S-parameter / signal-integrity extraction.

Confirmed real batch invocation (doc/psi_ug/ch5_run_simulation_re_Command_Line_and_Parameters.html):
    powersi.exe -b -tcl <script.tcl> <layout_file.spd>
and the `sigrity::` Tcl command vocabulary below is transcribed from doc/psi_ug's Tcl
chapters and confirmed sample usage, not guessed.

Usage pattern: start_powersi_session -> one or more powersi_* "compose" tools (each just
appends a Tcl line, no process launched) -> powersi_run_session (writes the accumulated
script and actually launches PowerSI once). Use preview_tcl_session/close_tcl_session
(sigrity_mcp.domains.platform.session_tools) to inspect or discard a session, and the
job-control tools (get_job_status, tail_job_log, list_job_files, read_job_output_file)
to track/retrieve the run started by powersi_run_session.

Confirmed live: this is also the real CAD-to-analysis bridge for this whole suite — a
real Allegro/OrCAD 22.1 `.brd` file (e.g. one written by the cad domain's Allegro tools)
opens directly via start_powersi_session, auto-translated by PowerSI's built-in
"BRDExtractor". Call powersi_save_document right after opening a non-`.spd` design and
before adding any other steps — PowerSI refuses to simulate a design that hasn't been
saved to native SPD form first.

This bridge is NOT limited to `.brd` — PowerSI's `sigrity::open document` goes through
Sigrity's built-in "SPDIF Translator" (documented in
doc/Translators_UG/Introduction_to_Sigrity_Translators.html as available inside every
Layout Workbench tool via Tools > Options > Edit Options > Translator, keyed off file
extension, not a separate standalone exe), which covers far more than the six dedicated
`*2Spd.exe` translators wrapped in `sigrity_mcp/domains/extraction/translators.py`:
Altium (`.pcbdoc`), IPC-2581 (`.xml`), DXF (`.dxf`), ODB++ (`.tgz`/`.tar`/`.gz`/`.zip`/
`.7z`), and IEEE 2401 M-Format, in addition to Allegro. CONFIRMED LIVE this pass against
two of these, both through this exact tool pair (`start_powersi_session` +
`powersi_save_document`), no other code involved: a real 130KB DXF sample
(share/Translators/Samples/dxf2spd/demo.dxf) produced a genuine 640KB `.spd` (log:
"File [...demo.dxf] is loaded." / "File [demo_out.spd] is saved."), and a real 55MB
Altium `.PcbDoc` sample (share/Translators/Samples/altium/demo1.PcbDoc) produced a
genuine ~19MB `.spd` the same way. IPC-2581 (tried against a real 229MB sample) is
plausible but unconfirmed — the process was genuinely still parsing (1.6GB RAM, not a
stalled dialog) when the test was cut off at 90s rather than let run unbounded; expect
this format to need a longer `powersi_run_session` timeout on a real file this size,
not necessarily to be broken. So: for "import a foreign PCB/schematic layout for
Sigrity analysis," this pair of tools IS the general answer — reach for a dedicated
`translate_*_to_spd` tool in `translators.py` only for the formats it doesn't cover
(GDSII, OASIS, NDD, PADS, RIF, Cadvance, Zuken).
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import tcl_sessions, run_session
from sigrity_mcp.mcp_app import mcp

_MODES = Literal[
    "extraction", "resonance", "spatial", "layout",
    "3DFEMExtraction", "3DFEMSpa", "3DEMCap", "3DFEMRFIC", "3DEMInd", "s_assess",
]


@mcp.tool
async def start_powersi_session(spd_file: str) -> dict:
    """Begin a new PowerSI automation session by opening a layout design.

    Confirmed live: PowerSI's `sigrity::open document` accepts more than native `.spd`
    files — it also directly opened a real Allegro/OrCAD 22.1 `.brd` file (via its
    built-in "BRDExtractor" translator, invoked automatically, no separate translate
    step needed) and made it available to the rest of the session. This is the real,
    confirmed CAD-to-analysis bridge: create/export a board in Allegro, hand its `.brd`
    straight to `spd_file` here.
    One consequence, also confirmed live: a design opened from a non-`.spd` format is
    NOT yet in native SPD form — PowerSI refuses to simulate it ("Cannot run the
    simulation because the loaded design file is not in SPD format") until you call
    powersi_save_document to save it as `.spd` first. Call that before
    powersi_run_session whenever `spd_file` isn't already a `.spd` path.
    Returns a session_id — pass it to every other powersi_* tool below to keep adding
    steps (save, ports, frequency sweep, exports, ...) to the same macro, then finish
    with powersi_run_session. Nothing is executed yet; this only records
    `sigrity::open document {<spd_file>} {!}` in the session's script.
    """
    session = tcl_sessions.create("powersi")
    tcl_sessions.add_line(session.session_id, f"sigrity::open document {tcl_path(spd_file)} {{!}}")
    return {"session_id": session.session_id, "spd_file": spd_file}


@mcp.tool
async def powersi_save_document(session_id: str, spd_file: str) -> dict:
    """Save the currently-open design to a native `.spd` file.

    Confirmed live: required after opening a non-`.spd` design (e.g. a real Allegro
    `.brd`, translated automatically on open by PowerSI's built-in BRDExtractor) before
    powersi_run_session can actually simulate it — PowerSI errors on `begin simulation`
    otherwise ("the loaded design file is not in SPD format"). Appends
    `sigrity::save {<spd_file>} {!}`.
    """
    tcl_sessions.add_line(session_id, f"sigrity::save {tcl_path(spd_file)} {{!}}")
    return {"session_id": session_id, "spd_file": spd_file}


@mcp.tool
async def powersi_set_mode(session_id: str, mode: _MODES) -> dict:
    """Set the PowerSI analysis mode for this session (e.g. 'extraction' for S-parameter extraction, 'resonance' for resonance analysis).

    Appends `sigrity::update option -mode {<mode>} {!}`.
    """
    tcl_sessions.add_line(session_id, f"sigrity::update option -mode {tcl_str(mode)} {{!}}")
    return {"session_id": session_id, "mode": mode}


@mcp.tool
async def powersi_set_frequency_sweep(
    session_id: str,
    start: str,
    end: str,
    use_afs: bool = True,
) -> dict:
    """Define the frequency sweep range for the simulation.

    `start`/`end` must be plain numeric values in Hz, e.g. "1e6" (1 MHz), "1e9" (1 GHz),
    "0" — NOT unit-suffixed strings. Confirmed empirically on this machine: PowerSI
    accepted "-start 1e6 -end 1e9" but rejected "-start 1MHz -end 1GHz" with "The ending
    frequency should not be smaller than the starting frequency" (it doesn't parse the
    unit suffix the way you'd expect). Values are passed through verbatim, not
    validated, so always use scientific/plain notation. `use_afs=True` (default)
    enables PowerSI's Adaptive Frequency Sweep, which picks intermediate points
    automatically instead of a fixed linear/log step; set False for a plain swept range
    if you intend to control point spacing another way.
    Appends `sigrity::update freq -start {<start>} -end {<end>} [-AFS] {!}`. Note the
    space between each flag and its brace-quoted value is required — PowerSI's Tcl
    parser rejects a concatenated `-start{1e6}` token as one unrecognized parameter
    (also confirmed empirically against a real design on this machine).
    """
    afs_flag = " -AFS" if use_afs else ""
    tcl_sessions.add_line(
        session_id,
        f"sigrity::update freq -start {tcl_str(start)} -end {tcl_str(end)}{afs_flag} {{!}}",
    )
    return {"session_id": session_id, "start": start, "end": end, "use_afs": use_afs}


@mcp.tool
async def powersi_add_ports_auto(
    session_id: str,
    ref_des: Optional[str] = None,
    signal_ref_impedance: Optional[float] = None,
    power_ref_impedance: Optional[float] = None,
) -> dict:
    """Auto-generate ports for every pin of a component (or every component if ref_des is omitted).

    This is PowerSI's fast path for port creation — appropriate when you want a port on
    every signal/power pin rather than hand-picking specific nets. Appends
    `sigrity::add port -all [-circuit {ref_des}] [-SignalRefZ {v}] [-PowerRefZ {v}] {!}`.
    """
    parts = ["sigrity::add port -all"]
    if ref_des:
        parts.append(f"-circuit {tcl_str(ref_des)}")
    if signal_ref_impedance is not None:
        parts.append(f"-SignalRefZ {{{signal_ref_impedance}}}")
    if power_ref_impedance is not None:
        parts.append(f"-PowerRefZ {{{power_ref_impedance}}}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "ref_des": ref_des}


@mcp.tool
async def powersi_add_edge_port(
    session_id: str,
    name: str,
    positive_node: str,
    negative_node: str,
    width: float,
    reference_impedance: float = 50.0,
) -> dict:
    """Add one explicit edge port between a positive and negative node (e.g. a trace edge to a ground edge).

    Use this instead of powersi_add_ports_auto when you need precise control over a
    specific port's location/impedance rather than blanket per-pin ports. Appends
    `sigrity::add EdgePort -positiveNode {} -negativeNode {} -Width {} -RefZ {} {!}`.
    """
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add EdgePort -positiveNode {tcl_str(positive_node)} "
            f"-negativeNode {tcl_str(negative_node)} -Width {{{width}}} "
            f"-RefZ {{{reference_impedance}}} {{!}} ; # port {tcl_str(name)}"
        ),
    )
    return {"session_id": session_id, "name": name}


@mcp.tool
async def powersi_add_excitation(
    session_id: str,
    positive_net: str,
    negative_net: str,
    source_circuit: Optional[str] = None,
    amplitude: Optional[float] = None,
) -> dict:
    """Add a signal excitation source between two nets, for time/frequency-domain response analysis.

    Appends `sigrity::excitation add -posnet {} -negnet {} [-cktfromsrc {}] [-ampa {}] {!}`.
    """
    parts = [
        "sigrity::excitation add",
        f"-posnet {tcl_str(positive_net)}",
        f"-negnet {tcl_str(negative_net)}",
    ]
    if source_circuit:
        parts.append(f"-cktfromsrc {tcl_str(source_circuit)}")
    if amplitude is not None:
        parts.append(f"-ampa {{{amplitude}}}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "positive_net": positive_net, "negative_net": negative_net}


@mcp.tool
async def powersi_export_network(
    session_id: str,
    network_name: str,
    output_file: str,
    matrix_type: Literal["S", "Z", "Y"] = "S",
    frequency: Optional[str] = None,
) -> dict:
    """Queue an export of the simulated network's S/Z/Y matrix to a file once the run finishes.

    `output_file`'s extension determines the on-disk format PowerSI writes (e.g. `.s4p`
    for a 4-port Touchstone file). Appends
    `sigrity::export network -network {} -fileName {} [-freq {}] -type {S|Z|Y} {!}`.
    """
    parts = [
        "sigrity::export network",
        f"-network {tcl_str(network_name)}",
        f"-fileName {tcl_path(output_file)}",
    ]
    if frequency:
        parts.append(f"-freq {tcl_str(frequency)}")
    parts.append(f"-type {tcl_str(matrix_type)}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "output_file": output_file}


@mcp.tool
async def powersi_export_rlgc(
    session_id: str,
    network_name: str,
    output_file: str,
    resistance: bool = True,
    inductance: bool = True,
    conductance: bool = True,
    capacitance: bool = True,
    frequency: Optional[str] = None,
) -> dict:
    """Queue an export of the network's per-unit-length RLGC parameters to a file.

    Appends `sigrity::export NetworkRLGC -network {} -FileName {} [-R][-L][-G][-C] [-Frequency {}]`.
    """
    parts = [
        "sigrity::export NetworkRLGC",
        f"-network {tcl_str(network_name)}",
        f"-FileName {tcl_path(output_file)}",
    ]
    if resistance:
        parts.append("-R")
    if inductance:
        parts.append("-L")
    if conductance:
        parts.append("-G")
    if capacitance:
        parts.append("-C")
    if frequency:
        parts.append(f"-Frequency {tcl_str(frequency)}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "output_file": output_file}


@mcp.tool
async def powersi_generate_html_report(session_id: str) -> dict:
    """Queue generation of PowerSI's standard HTML simulation report. Appends `sigrity::do GenReport {!}`."""
    tcl_sessions.add_line(session_id, "sigrity::do GenReport {!}")
    return {"session_id": session_id}


@mcp.tool
async def powersi_run_session(
    session_id: str,
    spd_file: Optional[str] = None,
    output_format: Literal["touchstone", "bnp", "both"] = "touchstone",
) -> dict:
    """Write out the session's accumulated Tcl macro and launch PowerSI against it as a background job.

    Before running, this appends `sigrity::begin simulation {!}` as the macro's final
    line. This is required, not optional: PowerSI's batch CLI only auto-starts the
    simulation if the script actually contains a simulation-trigger command — confirmed
    empirically (a session without it opens the design, applies settings, and exits
    with returncode 0 having done nothing else at all; adding this line is what makes it
    actually simulate and produce exportable results).
    Runs `powersi.exe -b <-ft|-fb|-fbt> -tcl <macro.tcl> [spd_file]`. Only pass
    `spd_file` if the design isn't already the one opened by start_powersi_session (e.g.
    to run the same macro against a different layout) — most callers should omit it.
    `output_format` selects PowerSI's native result format: 'touchstone' (-ft, .sNp
    files), 'bnp' (-fb, Sigrity's binary format, the CLI default), or 'both' (-fbt).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    tcl_sessions.add_line(session_id, "sigrity::begin simulation {!}")
    fmt_flag = {"touchstone": "-ft", "bnp": "-fb", "both": "-fbt"}[output_format]
    record = await run_session(
        session_id,
        tool="powersi",
        tcl_arg_flag="-tcl",
        build_args=["-b", fmt_flag],
        extra_args=[spd_file] if spd_file else None,
    )
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
    }
