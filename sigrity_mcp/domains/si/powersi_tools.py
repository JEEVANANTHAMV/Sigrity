"""PowerSI automation — S-parameter / signal-integrity extraction.

CONSOLIDATED (compact-tool-surface pass): the 9 individual "compose" functions below
(`powersi_save_document`, `powersi_set_mode`, `powersi_set_frequency_sweep`,
`powersi_add_ports_auto`, `powersi_add_edge_port`, `powersi_add_excitation`,
`powersi_export_network`, `powersi_export_rlgc`, `powersi_generate_html_report` — same
Tcl-line-building logic as before, kept as plain importable Python functions with their
original names so existing direct-call test code is unaffected, just no longer each its
own top-level MCP tool) are now driven through ONE dispatcher tool,
`powersi_configure(session_id, operations)`, where `operations` is a list of
`{"op": "<short-name>", **kwargs}` dicts (`short-name` = the function name with the
`powersi_` prefix stripped, e.g. `{"op": "set_mode", "mode": "extraction"}` calls
`powersi_set_mode`). This cuts a full PowerSI flow from ~10 MCP round trips (one per
compose call) down to 3: `start_powersi_session` -> `powersi_configure([...])` ->
`powersi_run_session`. Every operation's underlying validation/Tcl-quoting is UNCHANGED.

IMPORTANT ORDERING CAVEAT (unchanged from before consolidation, just now expressed
through the dispatcher): for a non-`.spd` design, `save_document` MUST be the FIRST
operation in the `operations` list passed to `powersi_configure`, and that
`powersi_configure` call must itself be the very first thing done after
`start_powersi_session` (before any other `powersi_configure` call) — PowerSI silently
fails later (rc 0, empty Options.xml only, no .sNp produced) if the design isn't saved to
native SPD form as its very first follow-up step. See `powersi_run_session`'s own
ordering check (which still fires regardless of whether `save_document` was called
directly or via `powersi_configure`) and `powersi_configure`'s own docstring for details.

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

import re
from typing import Literal, Optional

from sigrity_mcp.core.config import settings
from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import tcl_sessions, run_session
from sigrity_mcp.mcp_app import mcp

_FREQ_SUFFIX_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)\s*([kKmMgG]?)\s*([Hh][Zz])?\s*$"
)
_FREQ_SUFFIX_FACTOR = {"": 1.0, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6, "g": 1e9, "G": 1e9}


def _to_plain_hz(value: str, param: str) -> str:
    """PowerSI's `-start`/`-end` take plain Hz numbers; a unit-suffixed string like
    '1MHz' is mis-parsed and produces the misleading error 'The ending frequency
    should not be smaller than the starting frequency' regardless of the real values.
    Converts k/M/G-suffixed input to plain Hz; rejects anything unparseable up front
    instead of letting a confusing failure surface after a job launch."""
    m = _FREQ_SUFFIX_RE.match(value)
    if not m:
        raise ValueError(
            f"{param}={value!r} is not a plain Hz number or a k/M/G-suffixed number "
            "(e.g. '1e6' or '1GHz'). PowerSI requires plain Hz."
        )
    number, suffix, _hz_literal = m.groups()
    factor = _FREQ_SUFFIX_FACTOR[suffix]
    if factor == 1.0:
        return number
    return f"{float(number) * factor:.10g}"

_MODES = Literal[
    "extraction", "resonance", "spatial", "layout",
    "3DFEMExtraction", "3DFEMSpa", "3DEMCap", "3DFEMRFIC", "3DEMInd", "s_assess",
]


@mcp.tool
async def start_powersi_session(spd_file: str) -> dict:
    """Begin a new PowerSI automation session by opening a layout design.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.create("powersi")
    tcl_sessions.add_line(session.session_id, f"sigrity::open document {tcl_path(spd_file)} {{!}}")
    return {"session_id": session.session_id, "spd_file": spd_file}


async def powersi_save_document(session_id: str, spd_file: str) -> dict:
    """Save the currently-open design to a native `.spd` file.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, f"sigrity::save {tcl_path(spd_file)} {{!}}")
    return {"session_id": session_id, "spd_file": spd_file}


async def powersi_set_mode(session_id: str, mode: _MODES) -> dict:
    """Set the PowerSI analysis mode for this session (e.g. 'extraction' for S-parameter extraction, 'resonance' for resonance analysis).
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, f"sigrity::update option -mode {tcl_str(mode)} {{!}}")
    return {"session_id": session_id, "mode": mode}


async def powersi_set_frequency_sweep(
    session_id: str,
    start: str,
    end: str,
    use_afs: bool = True,
) -> dict:
    """Define the frequency sweep range for the simulation.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    start = _to_plain_hz(start, "start")
    end = _to_plain_hz(end, "end")
    if float(end) < float(start):
        raise ValueError(f"end ({end}) is smaller than start ({start}) -- PowerSI would reject this.")
    afs_flag = " -AFS" if use_afs else ""
    tcl_sessions.add_line(
        session_id,
        f"sigrity::update freq -start {tcl_str(start)} -end {tcl_str(end)}{afs_flag} {{!}}",
    )
    return {"session_id": session_id, "start": start, "end": end, "use_afs": use_afs}


async def powersi_add_ports_auto(
    session_id: str,
    ref_des: Optional[str] = None,
    signal_ref_impedance: Optional[float] = None,
    power_ref_impedance: Optional[float] = None,
) -> dict:
    """Auto-generate ports for every pin of a component (or every component if ref_des is omitted).
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
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


async def powersi_add_edge_port(
    session_id: str,
    name: str,
    positive_node: str,
    negative_node: str,
    width: float,
    reference_impedance: float = 50.0,
) -> dict:
    """Add one explicit edge port between a positive and negative node (e.g. a trace edge to a ground edge).
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::add EdgePort -positiveNode {tcl_str(positive_node)} "
            f"-negativeNode {tcl_str(negative_node)} -Width {{{width}}} "
            f"-RefZ {{{reference_impedance}}} {{!}} ; # port {tcl_str(name)}"
        ),
    )
    return {"session_id": session_id, "name": name}


async def powersi_add_excitation(
    session_id: str,
    positive_net: str,
    negative_net: str,
    source_circuit: Optional[str] = None,
    amplitude: Optional[float] = None,
) -> dict:
    """Add a signal excitation source between two nets, for time/frequency-domain response analysis.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
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


async def powersi_export_network(
    session_id: str,
    network_name: str,
    output_file: str,
    matrix_type: Literal["S", "Z", "Y"] = "S",
    frequency: Optional[str] = None,
) -> dict:
    """Queue an export of the simulated network's S/Z/Y matrix to a file once the run finishes.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
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
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
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


async def powersi_generate_html_report(session_id: str) -> dict:
    """Queue generation of PowerSI's standard HTML simulation report. Appends `sigrity::do GenReport {!}`.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, "sigrity::do GenReport {!}")
    return {"session_id": session_id}


_CONFIGURE_OPS = {
    "save_document": powersi_save_document,
    "set_mode": powersi_set_mode,
    "set_frequency_sweep": powersi_set_frequency_sweep,
    "add_ports_auto": powersi_add_ports_auto,
    "add_edge_port": powersi_add_edge_port,
    "add_excitation": powersi_add_excitation,
    "export_network": powersi_export_network,
    "export_rlgc": powersi_export_rlgc,
    "generate_html_report": powersi_generate_html_report,
}


@mcp.tool
async def powersi_configure(session_id: str, operations: list[dict]) -> dict:
    """Apply a list of PowerSI session-configuration operations in one call (replaces calling the 9 individual compose tools one at a time).

    Each item in `operations` is `{"op": "<name>", **kwargs}` where `<name>` is one of:
    `save_document, set_mode, set_frequency_sweep, add_ports_auto, add_edge_port,
    add_excitation, export_network, export_rlgc, generate_html_report` and `kwargs` are
    that operation's own parameters (everything except `session_id`, which is threaded
    through automatically) — see each corresponding `powersi_*` function's own docstring
    (still present in this module, just no longer individually exposed as a top-level
    tool) for its exact kwargs. Operations are applied in list order, since later ones
    (e.g. adding ports) typically depend on earlier ones (e.g. the mode being set).
    Raises `ValueError` naming the exact index and op on an unknown `op` or a bad/missing
    kwarg, rather than silently skipping it.

    ORDERING CAVEAT for `save_document`: if the session's design is a non-`.spd` file
    (opened via `start_powersi_session`), `save_document` MUST be the FIRST operation in
    THIS list, and this must be the first `powersi_configure` call made after
    `start_powersi_session` -- PowerSI silently fails later (rc 0, empty Options.xml
    only, no .sNp produced) if the design isn't saved to native SPD form as its very
    first follow-up step. `powersi_run_session` re-checks this ordering itself and will
    raise/warn if it's violated, but don't rely on that -- get the order right here.

    Example: `operations=[{"op": "save_document", "spd_file": "out.spd"},
    {"op": "set_mode", "mode": "extraction"},
    {"op": "set_frequency_sweep", "start": "1e6", "end": "1e9"},
    {"op": "add_ports_auto"}]`.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
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
async def powersi_run_session(
    session_id: str,
    spd_file: Optional[str] = None,
    output_format: Literal["touchstone", "bnp", "both"] = "touchstone",
) -> dict:
    """Write out the session's accumulated Tcl macro and launch PowerSI against it as a background job.
Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.add_line(session_id, "sigrity::begin simulation {!}")
    lines = session.script._lines
    open_idx = next((i for i, l in enumerate(lines) if l.startswith("sigrity::open document")), None)
    source_is_spd = False
    if open_idx is not None:
        m = re.search(r"\{([^}]*)\}", lines[open_idx])
        if m:
            source_is_spd = m.group(1).lower().endswith(".spd")
    save_idx = next((i for i, l in enumerate(lines) if l.startswith("sigrity::save ")), None)
    late_save_warning = None
    if not source_is_spd:
        if save_idx is None:
            raise ValueError(
                "This session opened a non-.spd design; PowerSI refuses to simulate a "
                "design that hasn't been saved to native SPD form first, and the "
                "failure is SILENT (rc 0, empty Options.xml only, no .sNp produced). "
                "Call powersi_save_document(session_id, <spd_path>) right after "
                "start_powersi_session and before any other step, then re-run."
            )
        if open_idx is not None and save_idx != open_idx + 1:
            late_save_warning = (
                "sigrity::save is not the line immediately after sigrity::open document "
                "in this session's composed macro; only save-as-the-very-next-step is "
                "verified to work -- a later save has been observed to also silently "
                "produce no output. Prefer calling powersi_save_document immediately "
                "after start_powersi_session."
            )

    fmt_flag = {"touchstone": "-ft", "bnp": "-fb", "both": "-fbt"}[output_format]
    record = await run_session(
        session_id,
        tool="powersi",
        tcl_arg_flag="-tcl",
        build_args=["-b", fmt_flag],
        extra_args=[spd_file] if spd_file else None,
    )
    result = {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
    }
    if late_save_warning:
        result["warning"] = late_save_warning

    # run_session (like submit_job) returns immediately after launch -- record.state is
    # "running" here almost every time, not a terminal state, so this cannot scan for
    # finished artifacts yet. artifact_dir itself IS knowable up front (PowerSI always
    # writes to the configured workdir root, never job_dir) -- report it unconditionally
    # so the caller knows where to look once they confirm completion separately via
    # wait_for_job/get_job_status.
    result["artifact_dir"] = str(settings.resolve_workdir())
    result["note"] = (
        "PowerSI writes its real artifacts (*_S.<N>p, *_S.ckt, *_Options.xml, "
        "*_PowerSI.err) to artifact_dir (the configured workdir root), NOT job_dir -- "
        "after confirming this job reached a terminal state (wait_for_job/"
        "get_job_status), judge success by a non-empty *_S.<N>p there, never by "
        "run.log or list_job_files (a perfect run and a missing-save failure both "
        "yield rc 0 and an empty log)."
    )
    return result
