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

ROOT CAUSE, CONFIRMED (previously mislabeled "pre-existing launcher issue", resolved
2026-10-21): the "no S-param, no window, silent rc=0 in ~3-5s" failure on every
historical `PowerSI.exe -b -tcl` launch (5/5 reproducible, see jobs
runs/powersi-0b32fd1b56, -59cbfee8aa7a1, -fb19b3d25f, -119b8aa7a1, and the original
-d2bc1e3cc8, plus scripts/smoke/smoke_powersi_port_fix.py for the port-command probes
themselves) is a "Choose License Suites" modal PowerSI raises at startup that the
previous auto-dismiss machinery could never advance: it is a MULTI-CHECKBOX
feature-selection dialog (Clarity 3D / Clarity 3D V8 / Clarity PCB/IC/Advanced IC
Package Extraction Suite / Clarity 3D Cloud NG / Clarity 3D Premier / Clarity 3D Cloud /
Clarity 3D V8 Token / Multiphysics GUI Pool, with a "Choose all" button and a "Save the
chosen suites and do not prompt again" checkbox), not a plain confirm/OK button — so the
`win32gui_helper.DismissWatcher`'s confirm-word ladder (OK/Next/Continue) had nothing in
it to click, and the process simply exited with no feature license checked out.
Consequently `sigrity::begin simulation` (and every downstream command in the macro)
runs against an empty, never-opened layout — PowerSI's own side-log for this case says
exactly that: "Failed to run the command because the layout is empty. First load an SPD
layout file" — which is indistinguishable from, and was previously misdiagnosed as, the
"component-free stub geometry" port-creation problem this module's other docstrings
address (an orthogonal, already-correct issue: the emitted Tcl lines were always
byte-correct per psi_ug.pdf; the tool was never far enough through startup to even
reach them). Fixed by adding the "license" entry to
`core.executables.SELECTOR_DIALOG_PATTERNS` (auto-answers "Choose all" — the dialog's
own select-every-suite button, the correct universal answer on this no-license-
restriction/PREMIUM install, matching the "default/continue" answer convention already
used for every other selector dialog there — plus the "Save the chosen suites and do
not prompt again" persistence checkbox where available), so future PowerSI/PowerDC/
other-Sigrity-analysis-tool launches through `powersi_run_session` and its siblings get
this dialog answered before any real Tcl runs. Re-verify with
`scripts/smoke/smoke_powersi_port_fix.py` (probes A and B should now produce real
`*S<N>p` files) if this dialog ever starts reappearing (e.g. a new Sigrity patch that
changes the dialog title or control layout).

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
    """Auto-generate ports by component, using `sigrity::add port -all`.

    DOC-VERIFIED LIMITATION (psi_ug.pdf "PowerSI Tcl Commands", printed pp. 410-412):
    this command family is component-centric. `-all` is documented as "Auto Generate
    Ports by Components" and every documented example is scoped to a real 2-terminal
    (or multi-pin) component: `sigrity::add port -all -circuit {die} {!}`,
    `sigrity::add port -circuit {die} -SignalRefZ {2} -PowerRefZ {1} {!}`. It works by
    pairing each component's own positive/negative pins on enabled nets. A design
    (or a test geometry) whose nets have NO component at either end -- e.g. a bare
    2-point trace stub drawn by hand with no part at its tips -- is an input shape none
    of the `add port` forms are designed for: there is no component/pin to pair, so
    `add port -all` generates nothing and the later `begin simulation` silently yields
    no S-parameters (rc 0, empty result, which looks exactly like a "syntax" failure
    but is not). For component-free nets use `powersi_add_port_manual` (explicit
    coordinates + reference nodes on a named -circuit scope) instead, or terminate the
    trace at a real component and use `powersi_add_port_component_pins`.

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


async def powersi_add_port_component_pins(
    session_id: str,
    name: str,
    ref_des: str,
    pos_pins: list,
    neg_pins: list,
    port_type: int = 0,
) -> dict:
    """Create ONE port from a real component's pins: `sigrity::add port -name ... -type
    {0|1} -circuit {RefDes} -posPins {...} -negPins {...}`.

    DOC-VERIFIED (psi_ug.pdf "PowerSI Tcl Commands", printed p. 413, "Create Port Based
    on Existing Component Pins") -- the only `add port` form with a complete, concrete,
    unambiguous worked example:
        -type {0}  create package port   sigrity::add port -name {PortTest} -type {0} -circuit {cap1} -posPins {0} -negPins {1}
        -type {1}  create circuit port   sigrity::add port -name {PortTest1} -type {1} -circuit {cap1} -posPins {0} -negPins {1}

    PIN NUMBERING CORRECTION (2026-10-21, CONFIRMED LIVE against the real Fault-Detector
    sample board, `.spd` of `runs/innosynth_imx8mp/powersi_verify/board.brd`): the doc's
    own example (`-posPins {0} -negPins {1}`) is misleading for an ordinary 2-pin part.
    `pos_pins`/`neg_pins` are the component's REAL, 1-based pin NUMBERS (the same
    numbers printed on the part's own datasheet/footprint), not a 0-based index into
    the pin list. `posPins {0} -negPins {1}` against a real resistor `R14` fails hard:
    `"The circuit node {0} is not connected to any package node."` — pin `0` does not
    exist on a part whose real pins are `1`/`2`. Re-run with `posPins {1} -negPins {2}`
    completed a REAL, full PowerSI simulation end to end (FEM mesh, 18-point 1-50MHz
    AFS sweep, `[Number of Ports] 1`) and produced a genuine Touchstone `.s1p` file with
    real S11 data — independently re-read from disk, not inferred from a clean exit
    code. This is the first fully-confirmed PowerSI field-solver run in this project.
    `pos_pins`/`neg_pins` accept pin NAMES too (not just numbers) per the doc's own
    `-posPins`/`-negPins` grammar — prefer a part's real pin name when one exists and is
    known, falling back to the real (1-based) pin number otherwise.

    This is the recommended way to port a physical board net: terminate the net at a
    real 2-pin component (small resistor, pad/via pair, the actual IC under test) and
    reference that component's real refdes + real pin numbers/names here.
    Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    if not (isinstance(port_type, int) and port_type in (0, 1)):
        raise ValueError(f"port_type must be 0 (package port) or 1 (circuit port); got {port_type!r}")
    if not pos_pins or not neg_pins:
        raise ValueError("pos_pins and neg_pins must both be non-empty")
    if len(pos_pins) != len(neg_pins):
        raise ValueError(f"pos_pins ({len(pos_pins)}) and neg_pins ({len(neg_pins)}) must be the same length")
    parts = [
        "sigrity::add port",
        f"-name {tcl_str(name)}",
        f"-type {{{port_type}}}",
        f"-circuit {tcl_str(ref_des)}",
        f"-posPins {{{' '.join(str(p) for p in pos_pins)}}}",
        f"-negPins {{{' '.join(str(n) for n in neg_pins)}}}",
        "{!}",
    ]
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "name": name, "ref_des": ref_des, "port_type": port_type}


async def powersi_add_port_manual(
    session_id: str,
    ref_des: str,
    ref_nodes: list,
    h_coords: list,
    v_coords: list,
    row: int = 1,
    col: int = 1,
    on_pin: bool = True,
) -> dict:
    """Create ONE coordinate-based port: `sigrity::add port -circuit {RefDes} -select
    {manual} -row {n} -col {n} -RefNode {...} -HCoord {x1,x2} -VCoord {y1,y2} -OnPin {!}`.

    DOC-VERIFIED (psi_ug.pdf "PowerSI Tcl Commands", printed p. 412, "Auto Generate
    Ports on Pins", select="manual") -- the closest documented mechanism to "port at an
    arbitrary board location". Still circuit-scoped (requires -circuit {RefDes} to
    scope it, it is NOT purely net-based). `ref_nodes` are `{node <net>}`-style node
    name strings (doc example: `-RefNode {Node559::GND Node579::GND}`); `h_coords` and
    `v_coords` are the matching X/Y coordinate pairs (doc example:
    `-HCoord {-0.00498,-0.00518} -VCoord {0.060225,0.095985}`). Use this when the
    component-pin form doesn't fit (e.g. the net has no 2-pin component, but does have
    a named structure to scope it to, and known coordinates).
    Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    if len(ref_nodes) < 2:
        raise ValueError(f"-RefNode needs at least 2 node names (positive + negative); got {len(ref_nodes)}")
    if len(h_coords) != len(ref_nodes) or len(v_coords) != len(ref_nodes):
        raise ValueError(
            f"h_coords ({len(h_coords)}), v_coords ({len(v_coords)}) and ref_nodes ({len(ref_nodes)})"
            " must all be the same length"
        )
    parts = [
        "sigrity::add port",
        f"-circuit {tcl_str(ref_des)}",
        "-select {manual}",
        f"-row {{{row}}}",
        f"-col {{{col}}}",
        f"-RefNode {{{' '.join(str(n) for n in ref_nodes)}}}",
        f"-HCoord {{{','.join(str(x) for x in h_coords)}}}",
        f"-VCoord {{{','.join(str(y) for y in v_coords)}}}",
    ]
    if on_pin:
        parts.append("-OnPin")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "ref_des": ref_des, "ref_nodes": list(ref_nodes)}


async def powersi_add_port_vrn(
    session_id: str,
    ref_des: str,
) -> dict:
    """Add all ports of one component by its VRN: `sigrity::add port -circuit {RefDes}
    -VRN {!}`.

    DOC-VERIFIED (psi_ug.pdf "PowerSI Tcl Commands", printed p. 412, "Add Port by
    Component"): `sigrity::add port -circuit {MF_1} -VRN {!}`. Use for a component
    whose port topology is already defined in its VRN (pin net / reference net)
    definition rather than derived from pin pairing.
    Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, f"sigrity::add port -circuit {tcl_str(ref_des)} -VRN {{!}}")
    return {"session_id": session_id, "ref_des": ref_des}


async def powersi_add_edge_port(
    session_id: str,
    name: str,
    positive_node: Optional[str] = None,
    negative_node: Optional[str] = None,
    positive_ckt_node: Optional[str] = None,
    negative_ckt_node: Optional[str] = None,
    width: float = 0.002,
    reference_impedance: float = 50.0,
) -> dict:
    """Add one explicit edge port: `sigrity::add EdgePort -PositiveNode/-PositiveCktNode
    {-NegativeNode/-NegativeCktNode} -Width {v} -RefZ {v} {!}`.

    DOC-VERIFIED FLAG NAMES + EXAMPLE (psi_ug.pdf "PowerSI Tcl Commands", printed
    p. 418-419): the documented example is
        sigrity::add EdgePort -PositiveCktNode {PCN1::PCN2} -NegativeCktNode {NCN1::NCN2} -Width {.002} -RefZ {55} {!}
    i.e. the real flags are `-PositiveNode|-pn`, `-NegativeNode|-nn` (package nodes) and
    `-PositiveCktNode|-pn`, `-NegativeCktNode|-nn` (circuit nodes), with node strings in
    `<RefDes>::<Net>` double-colon notation. The earlier implementation's
    `-positiveNode`/`-negativeNode` (lower-case) was NOT the documented flag casing;
    the package-node form `-PositiveNode/-NegativeNode` is accepted but the doc shows
    NO worked example for a plain package node on a component-free net (only the
    circuit-node example exists), so a bare-net edge port has no documented node-string
    grammar -- treat that path as the least certain and prefer a component-scoped port
    (`powersi_add_port_component_pins` / `powersi_add_port_manual`) when in doubt.
    At least one of (positive_node, negative_node) must be given together with the
    matching circuit-node pair or package-node pair; `name` is informational only --
    PowerSI names edge ports on its own.
    Call load_skill('sigrity-si') for the full verified playbook, pitfalls, and a live example."""
    has_pkg = positive_node is not None or negative_node is not None
    has_ckt = positive_ckt_node is not None or negative_ckt_node is not None
    if not has_pkg and not has_ckt:
        raise ValueError("at least one of positive_node/negative_node (package) or positive_ckt_node/negative_ckt_node (circuit) is required")
    parts = ["sigrity::add EdgePort"]
    if positive_node is not None:
        parts.append(f"-PositiveNode {tcl_str(positive_node)}")
    if positive_ckt_node is not None:
        parts.append(f"-PositiveCktNode {tcl_str(positive_ckt_node)}")
    if negative_node is not None:
        parts.append(f"-NegativeNode {tcl_str(negative_node)}")
    if negative_ckt_node is not None:
        parts.append(f"-NegativeCktNode {tcl_str(negative_ckt_node)}")
    parts.append(f"-Width {{{width}}}")
    parts.append(f"-RefZ {{{reference_impedance}}}")
    parts.append("{!}")
    tcl_sessions.add_line(session_id, " ".join(parts) + f" ; # port {tcl_str(name)}")
    return {
        "session_id": session_id,
        "name": name,
        "positive_node": positive_node,
        "negative_node": negative_node,
        "positive_ckt_node": positive_ckt_node,
        "negative_ckt_node": negative_ckt_node,
    }


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
    "add_port_component_pins": powersi_add_port_component_pins,
    "add_port_manual": powersi_add_port_manual,
    "add_port_vrn": powersi_add_port_vrn,
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
    `save_document, set_mode, set_frequency_sweep, add_ports_auto,
    add_port_component_pins, add_port_manual, add_port_vrn, add_edge_port,
    add_excitation, export_network, export_rlgc, generate_html_report` and `kwargs` are
    that operation's own parameters (everything except `session_id`, which is threaded
    through automatically) — see each corresponding `powersi_*` function's own docstring
    (still present in this module, just no longer individually exposed as a top-level
    tool) for its exact kwargs. PORT-CHOOSING GUIDANCE (all doc-verified against
    psi_ug.pdf "PowerSI Tcl Commands", printed pp. 410-413): a real net must carry a
    port before `begin simulation` produces S-parameters; choose the narrowest
    component-scoped form that fits the actual geometry — `add_port_component_pins`
    (net terminates in a real 2-pin component; preferred, has the only complete worked
    example), `add_port_manual` (net has known coordinates + reference nodes),
    `add_port_vrn` (component's VRN already defines its pins), or `add_ports_auto`
    (bulk-generate ports for every component in scope). None of these work on a net
    with no component at either end (a bare hand-drawn trace stub) — that is a test-
    geometry problem, not a flag problem; terminate the trace at a real part first.
    Operations are applied in list order, since later ones
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
