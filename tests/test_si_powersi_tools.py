import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session
from sigrity_mcp.domains.si.powersi_tools import (
    powersi_add_edge_port,
    powersi_add_excitation,
    powersi_add_ports_auto,
    powersi_export_network,
    powersi_export_rlgc,
    powersi_generate_html_report,
    powersi_run_session,
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
    session = await start_powersi_session(spd_file="board.spd")
    sid = session["session_id"]

    await powersi_set_mode(sid, "extraction")
    await powersi_set_frequency_sweep(sid, "1MHz", "20GHz", use_afs=True)
    await powersi_add_ports_auto(sid, ref_des="U1", signal_ref_impedance=50)
    await powersi_add_edge_port(sid, "P1", "node_a", "node_b", width=0.1)
    await powersi_add_excitation(sid, "NET_P", "NET_N", amplitude=1.0)
    await powersi_export_network(sid, "SParam1", "out.s4p")
    await powersi_export_rlgc(sid, "SParam1", "out_rlgc.csv")
    await powersi_generate_html_report(sid)

    script = tcl_sessions.preview(sid)
    assert "sigrity::update option -mode {extraction} {!}" in script
    assert "-start{1MHz} -end{20GHz} -AFS {!}" in script
    assert "sigrity::add port -all -circuit {U1} -SignalRefZ{50} {!}" in script
    assert "sigrity::add EdgePort -positiveNode{node_a} -negativeNode{node_b} -Width{0.1} -RefZ{50.0}" in script
    assert "sigrity::excitation add -posnet{NET_P} -negnet{NET_N} -ampa{1.0} {!}" in script
    assert "sigrity::export network -network{SParam1} -fileName{out.s4p} -type {S} {!}" in script
    assert "sigrity::export NetworkRLGC -network{SParam1} -FileName{out_rlgc.csv} -R -L -G -C" in script
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

    # The stand-in process is python.exe, not PowerSI, so it won't understand these
    # flags — we only care that a real process was launched and reached a terminal state.
    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    # session should be auto-closed after running
    with pytest.raises(Exception):
        tcl_sessions.get(sid)
