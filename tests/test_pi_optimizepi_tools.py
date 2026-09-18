import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session
from sigrity_mcp.domains.pi.optimizepi_tools import (
    optimizepi_add_decap_candidate,
    optimizepi_add_impedance_observation,
    optimizepi_add_vrm,
    optimizepi_attach_layout,
    optimizepi_configure_optimization,
    optimizepi_export_impedance_plot,
    optimizepi_generate_report,
    optimizepi_run_session,
    optimizepi_set_frequency_range,
    start_optimizepi_session,
)


@pytest.mark.asyncio
async def test_start_session_sets_workflow():
    result = await start_optimizepi_session(workflow_key="postLayout")
    preview = await preview_tcl_session(result["session_id"])
    assert "sigrity::update workflow -product {OptimizePI} -workflowkey {postLayout} {!}" in preview["script"]
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl():
    session = await start_optimizepi_session(workflow_key="postLayout")
    sid = session["session_id"]

    await optimizepi_attach_layout(sid, r"C:\design\board.spd")
    await optimizepi_add_vrm(sid, "VCC", "GND", "Vrm1")
    await optimizepi_add_decap_candidate(sid, "VCC", "GND", "Device", "C100")
    await optimizepi_add_impedance_observation(sid, "1", "2", "U1")
    await optimizepi_set_frequency_range(sid, "10kHz", "1GHz")
    await optimizepi_configure_optimization(sid, "opt1", "U1", min_caps=1, max_caps=20, max_cost=5.0, max_area=100.0)
    await optimizepi_generate_report(sid)
    await optimizepi_export_impedance_plot(sid, "impedance.csv", "PORT1", file_type="CSV")

    script = tcl_sessions.preview(sid)
    assert "sigrity::open document -attach {C:/design/board.spd} {!}" in script
    assert "sigrity::add VRM -byNet -powerName {VCC} -groundName {GND} -component {Vrm1} {!}" in script
    assert "sigrity::add deCap -byNet -powerName {VCC} -groundName {GND} -portGeneration {} -type {Device} -component {C100} {!}" in script
    assert "sigrity::add impedanceObservation -byPin -positivePinName {1} -negativePinName {2} -component {U1} {!}" in script
    assert "sigrity::update simu -startFreq {10kHz} -endFreq {1GHz} {!}" in script
    assert "sigrity::update deviceOPTI -name {opt1} -refDes {U1} -opiObjective {Best Performance vs. Cost} -min {1} -max {20} -maxCost {5.0} -maxArea {100.0} {!}" in script
    assert "sigrity::do genReport {!}" in script
    assert "sigrity::export impedanceplot -pathname {impedance.csv} -filetype {CSV} -portname {PORT1} {!}" in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_correct_argv(fake_exe):
    session = await start_optimizepi_session(workflow_key="DeviceImpedanceChecking")
    sid = session["session_id"]
    await optimizepi_attach_layout(sid, "board.spd")

    result = await optimizepi_run_session(sid)
    assert result["command"][1:4] == ["-b", "-export_report", "-tcl"]

    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    # session should be auto-closed after running
    with pytest.raises(Exception):
        tcl_sessions.get(sid)
