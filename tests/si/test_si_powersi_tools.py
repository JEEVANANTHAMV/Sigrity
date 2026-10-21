import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session
from sigrity_mcp.domains.si.powersi_tools import (
    powersi_add_edge_port,
    powersi_add_excitation,
    powersi_add_port_component_pins,
    powersi_add_port_inject,
    powersi_add_port_manual,
    powersi_add_port_vrn,
    powersi_add_ports_auto,
    powersi_export_network,
    powersi_export_rlgc,
    powersi_generate_html_report,
    powersi_run_session,
    powersi_save_document,
    powersi_set_frequency_sweep,
    powersi_set_mode,
    start_powersi_session,
)


@pytest.mark.asyncio
async def test_start_session_opens_document():
    result = await start_powersi_session(spd_file=r"C:\design\board.spd")
    preview = await preview_tcl_session(result["session_id"])
    assert "sigrity::open document {C:/design/board.spd} {!}" in preview["script"]
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl():
    session = await start_powersi_session(spd_file="board.brd")
    sid = session["session_id"]

    await powersi_save_document(sid, "board.spd")
    await powersi_set_mode(sid, "extraction")
    await powersi_set_frequency_sweep(sid, "1MHz", "20GHz", use_afs=True)
    await powersi_add_ports_auto(sid, ref_des="U1", signal_ref_impedance=50)
    await powersi_add_port_component_pins(sid, "PortTest", "cap1", [0], [1], port_type=0)
    await powersi_add_port_manual(
        sid,
        "Redge",
        ["Node559::GND", "Node579::GND"],
        [-0.00498, -0.00518],
        [0.060225, 0.095985],
        row=1,
        col=1,
    )
    await powersi_add_port_vrn(sid, "MF_1")
    await powersi_add_edge_port(sid, "P1", positive_ckt_node="PCN1::PCN2", negative_ckt_node="NCN1::NCN2", width=0.002, reference_impedance=55)
    await powersi_add_excitation(sid, "NET_P", "NET_N", amplitude=1.0)
    await powersi_export_network(sid, "SParam1", "out.s4p")
    await powersi_export_rlgc(sid, "SParam1", "out_rlgc.csv")
    await powersi_generate_html_report(sid)

    script = tcl_sessions.preview(sid)
    assert "sigrity::save {board.spd} {!}" in script
    assert "sigrity::update option -mode {extraction} {!}" in script
    # "1MHz"/"20GHz" are normalized to plain Hz before being emitted -- PowerSI
    # mis-parses unit-suffixed strings (see powersi-frequency-suffix-parsing-error).
    assert "-start {1000000} -end {2e+10} -AFS {!}" in script
    assert "sigrity::add port -all -circuit {U1} -SignalRefZ {50} {!}" in script
    # doc-verified concrete example, printed p. 413 (package port, -type 0)
    assert "sigrity::add port -name {PortTest} -type {0} -circuit {cap1} -posPins {0} -negPins {1} {!}" in script
    # doc-verified concrete example, printed p. 412 (manual coordinate-based port)
    assert (
        "sigrity::add port -circuit {Redge} -select {manual} -row {1} -col {1} "
        "-RefNode {Node559::GND Node579::GND} -HCoord {-0.00498,-0.00518} "
        "-VCoord {0.060225,0.095985} -OnPin {!}"
    ) in script
    # doc-verified concrete example, printed p. 412 (VRN form)
    assert "sigrity::add port -circuit {MF_1} -VRN {!}" in script
    # doc-verified concrete example, printed p. 418-419 (EdgePort circuit-node form,
    # corrected flag casing -PositiveCktNode/-NegativeCktNode; name is a comment only)
    assert (
        "sigrity::add EdgePort -PositiveCktNode {PCN1::PCN2} -NegativeCktNode {NCN1::NCN2} "
        "-Width {0.002} -RefZ {55} {!} ; # port {P1}"
    ) in script
    assert "sigrity::excitation add -posnet {NET_P} -negnet {NET_N} -ampa {1.0} {!}" in script
    assert "sigrity::export network -network {SParam1} -fileName {out.s4p} -type {S} {!}" in script
    assert "sigrity::export NetworkRLGC -network {SParam1} -FileName {out_rlgc.csv} -R -L -G -C" in script
    assert "sigrity::do GenReport {!}" in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_correct_argv(fake_exe):
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    await powersi_set_mode(sid, "extraction")

    result = await powersi_run_session(sid, output_format="touchstone")
    assert result["command"][1:3] == ["-b", "-ft"]
    assert "-tcl" in result["command"]
    assert "warning" not in result  # .spd source, no save needed
    assert "artifact_dir" in result
    assert "artifact_dir" in result["note"]

    # The stand-in process is python.exe, not PowerSI, so it won't understand these
    # flags — we only care that a real process was launched and reached a terminal state.
    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    # session should be auto-closed after running
    with pytest.raises(Exception):
        tcl_sessions.get(sid)


# --- powersi_set_frequency_sweep: unit-suffix normalization -------------------------


@pytest.mark.asyncio
async def test_frequency_sweep_converts_unit_suffixes():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    result = await powersi_set_frequency_sweep(sid, "1MHz", "1GHz")
    assert result["start"] == "1000000"
    assert result["end"] == "1000000000"
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_frequency_sweep_passes_through_plain_hz_unchanged():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    result = await powersi_set_frequency_sweep(sid, "1e6", "1e9")
    assert result["start"] == "1e6"
    assert result["end"] == "1e9"
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_frequency_sweep_rejects_unparseable_value():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="not a plain Hz number"):
        await powersi_set_frequency_sweep(sid, "fast", "1e9")
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_frequency_sweep_rejects_end_smaller_than_start():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="smaller than start"):
        await powersi_set_frequency_sweep(sid, "1GHz", "1MHz")
    await close_tcl_session(sid)


# --- powersi_add_port_component_pins: doc-verified -type {0|1} form -----------------


@pytest.mark.asyncio
async def test_add_port_component_pins_package_port():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    result = await powersi_add_port_component_pins(sid, "PortTest", "cap1", [0], [1], port_type=0)
    assert result["port_type"] == 0
    script = tcl_sessions.preview(sid)
    assert "sigrity::add port -name {PortTest} -type {0} -circuit {cap1} -posPins {0} -negPins {1} {!}" in script
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_port_component_pins_circuit_port():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    await powersi_add_port_component_pins(sid, "PortTest1", "cap1", [0], [1], port_type=1)
    script = tcl_sessions.preview(sid)
    assert "-type {1}" in script
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_port_component_pins_rejects_bad_port_type():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="port_type must be 0|1"):
        await powersi_add_port_component_pins(sid, "P", "cap1", [0], [1], port_type=2)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_port_component_pins_rejects_mismatched_pin_counts():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="same length"):
        await powersi_add_port_component_pins(sid, "P", "cap1", [0, 1], [1], port_type=0)
    await close_tcl_session(sid)


# --- powersi_add_port_manual: doc-verified coordinate-based form ---------------------


@pytest.mark.asyncio
async def test_add_port_manual_requires_two_nodes():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="at least 2 node names"):
        await powersi_add_port_manual(sid, "Redge", ["Node1::GND"], [-0.005], [0.06])
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_port_manual_rejects_mismatched_coord_counts():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="same length"):
        await powersi_add_port_manual(sid, "Redge", ["A::GND", "B::GND"], [-0.005], [0.06])
    await close_tcl_session(sid)


# --- powersi_add_edge_port: doc-verified flag casing ---------------------------------


@pytest.mark.asyncio
async def test_add_edge_port_package_node_form():
    # -PositiveNode/-NegativeNode (package-node family) -- the corrected casing.
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    await powersi_add_edge_port(sid, "P1", positive_node="PN1::PN2", negative_node="NN1::NN2", width=0.002, reference_impedance=55)
    script = tcl_sessions.preview(sid)
    assert "-PositiveNode {PN1::PN2} -NegativeNode {NN1::NN2}" in script
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_edge_port_rejects_no_nodes():
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="at least one of"):
        await powersi_add_edge_port(sid, "P1", width=0.002)
    await close_tcl_session(sid)


# --- powersi_add_port_inject: the confirmed-working port-creation path --------------


_FAKE_BASE_SPD = """* Port description lines

* Extraction Setting description lines

* Linkage description line
.Connect C12 C_CAP300_C_c
2 $Package.Node506!!2::N09032
1 $Package.Node367!!1::N09000
.EndC
.Connect R14 R_RES400_R_r
1 $Package.Node933!!1::+15V
2 $Package.Node653!!2::N049980
.EndC
"""


@pytest.mark.asyncio
async def test_add_port_inject_builds_complete_port_from_real_connect_block(tmp_path):
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    spd_file = tmp_path / "board.spd"
    spd_file.write_text(_FAKE_BASE_SPD, encoding="utf-8")
    result = await powersi_add_port_inject(sid, "C12", pos_pin=1, neg_pin=2, saved_spd=str(spd_file))
    assert result["positive_node"] == "$Package.Node367!!1::N09000"
    assert result["negative_node"] == "$Package.Node506!!2::N09032"
    saved = spd_file.read_text(encoding="utf-8")
    assert ".Port" in saved and ".EndPort" in saved
    assert "+            PositiveTerminal $Package.Node367!!1::N09000" in saved
    assert "+            NegativeTerminal $Package.Node506!!2::N09032" in saved
    # RefZ must be written as a BARE INTEGER (PowerSI's .spd parser silently rejects a
    # float-flavored "50.0" here, proven live 2026-10-21).
    assert "RefZ = 50\n" in saved and "RefZ = 50.0" not in saved
    # the injected block must sit BEFORE the original extraction-setting marker, replacing
    # the previously-empty port section, and the rest of the file (incl. the .Connect block
    # used to source the node refs) must survive intact
    assert saved.index("* Port description lines") < saved.index("* Extraction Setting description lines")
    assert ".Connect C12 C_CAP300_C_c" in saved
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_port_inject_rejects_unknown_refdes(tmp_path):
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    spd_file = tmp_path / "board.spd"
    spd_file.write_text(_FAKE_BASE_SPD, encoding="utf-8")
    with pytest.raises(ValueError, match=r"no `\.Connect U99` block"):
        await powersi_add_port_inject(sid, "U99", pos_pin=1, neg_pin=2, saved_spd=str(spd_file))
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_add_port_inject_rejects_bad_pin_number(tmp_path):
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]
    spd_file = tmp_path / "board.spd"
    spd_file.write_text(_FAKE_BASE_SPD, encoding="utf-8")
    with pytest.raises(ValueError, match="pins 1/99 not found"):
        await powersi_add_port_inject(sid, "C12", pos_pin=1, neg_pin=99, saved_spd=str(spd_file))
    await close_tcl_session(sid)


# --- powersi_run_session: missing-save-document silent failure guard ---------------


@pytest.mark.asyncio
async def test_run_session_raises_when_non_spd_source_never_saved(fake_exe):
    # Regression: opening a non-.spd design and never saving produces a SILENT
    # failure (rc 0, empty Options.xml, no .sNp) with no error anywhere -- catch it
    # before launch instead.
    session = await start_powersi_session(spd_file="board.brd")
    sid = session["session_id"]
    with pytest.raises(ValueError, match="hasn't been saved to native SPD form"):
        await powersi_run_session(sid)


@pytest.mark.asyncio
async def test_run_session_warns_when_save_is_not_immediately_after_open(fake_exe):
    session = await start_powersi_session(spd_file="board.brd")
    sid = session["session_id"]
    await powersi_set_mode(sid, "extraction")  # a step BEFORE the save
    await powersi_save_document(sid, "board.spd")

    result = await powersi_run_session(sid)
    assert "warning" in result
    assert "immediately after" in result["warning"]


@pytest.mark.asyncio
async def test_run_session_no_warning_when_save_is_first_step(fake_exe):
    session = await start_powersi_session(spd_file="board.brd")
    sid = session["session_id"]
    await powersi_save_document(sid, "board.spd")  # immediately after open
    await powersi_set_mode(sid, "extraction")

    result = await powersi_run_session(sid)
    assert "warning" not in result
