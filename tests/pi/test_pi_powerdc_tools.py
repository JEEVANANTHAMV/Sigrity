import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session
from sigrity_mcp.domains.pi.powerdc_tools import (
    powerdc_add_interconnect,
    powerdc_add_sink,
    powerdc_add_vrm,
    powerdc_enable_autosave_results,
    powerdc_export_signoff_report,
    powerdc_generate_signoff_report,
    powerdc_mark_thermal_component,
    powerdc_run_one_step_powertree,
    powerdc_run_session,
    powerdc_save_workspace,
    powerdc_set_power_dissipation,
    powerdc_set_simulation_mode,
    powerdc_set_thermal_test_board,
    start_powerdc_session,
)


@pytest.mark.asyncio
async def test_start_session_opens_and_attaches_document():
    result = await start_powerdc_session(spd_file=r"C:\design\board.spd")
    preview = await preview_tcl_session(result["session_id"])
    assert "sigrity::open document {!}" in preview["script"]
    assert "sigrity::open document -attach {C:/design/board.spd} {!}" in preview["script"]
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl():
    session = await start_powerdc_session(spd_file="board.spd")
    sid = session["session_id"]

    await powerdc_set_simulation_mode(sid, ir_drop_analysis=True)
    await powerdc_add_vrm(sid, "PowerNets", "GND", ["Vrm3", "Vrm2", "Vrm1"], voltage=1.5)
    await powerdc_add_sink(
        sid, "VCC", "GND", "U1", model="Equal Current", current=2.0, upper_tolerance="5%", lower_tolerance="5%"
    )
    await powerdc_add_interconnect(sid, "VCC", "GND", "R1", resistance=0.01, positive_pin="1", negative_pin="2")
    await powerdc_mark_thermal_component(sid, "U1")
    await powerdc_set_power_dissipation(sid, "U1", watts=5.0, source="Volume", output_temperature_map="U1_temp.dat")
    await powerdc_set_thermal_test_board(sid, "tbLead2s2p27", "0.0762,0.1143,0.0096,0.0096", "10,10", enhance_pkg_area=True)
    await powerdc_enable_autosave_results(sid, save_excel=True)
    await powerdc_run_one_step_powertree(sid, "vrm_sink.csv", "rules.xml", "amm.lib")
    await powerdc_generate_signoff_report(sid, "report.htm")
    await powerdc_save_workspace(sid, "setup.pdcx")

    script = tcl_sessions.preview(sid)
    assert "sigrity::set pdcSimMode -irDropAnalysis {1} {!}" in script
    assert "sigrity::add pdcVRM -auto -net {PowerNets,GND} -ckt {Vrm3}{Vrm2}{Vrm1} -voltage {1.5} {!}" in script
    assert "sigrity::add pdcSink -auto -net {VCC,GND} -ckt {U1} -model {Equal Current} -current {2.0}" in script
    assert "-upperTolerance {5%} -lowerTolerance {5%} {!}" in script
    assert "sigrity::add pdcInter -auto -net {VCC,GND} -ckt {R1} -positivePin {1} -negativePin {2} -resistance {0.01} {!}" in script
    assert "sigrity::update circuit {U1} -setAsThermalComponent {1} {!}" in script
    assert "-dissipation {-type {Power} -value {5.0} -source {Volume} -outputTemmperatureMap {U1_temp.dat}} {!}" in script
    assert "sigrity::update pdcTestBoard -type {tbLead2s2p27} -stackup {0.0762,0.1143,0.0096,0.0096} -dimension {10,10} -enhancePKGArea {1} {!}" in script
    assert "sigrity::update option -AutoSaveSimulationResult {1} -AutoSaveExcelResult {1} {!}" in script
    assert "sigrity::do OneStepPowerTree -VrmSink {vrm_sink.csv} -ExtractRules {rules.xml} -ammLibrary {amm.lib} {!}" in script
    assert "sigrity::do pdcReport -resultTable -diagramPlot -sinkIRDropSummaryCsv -fileName {report.htm} {!}" in script
    assert "sigrity::save -w {setup.pdcx} {!}" in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_power_dissipation_requires_exactly_one_source():
    session = await start_powerdc_session(spd_file="board.spd")
    sid = session["session_id"]
    with pytest.raises(ValueError):
        await powerdc_set_power_dissipation(sid, "U1")
    with pytest.raises(ValueError):
        await powerdc_set_power_dissipation(sid, "U1", watts=5.0, power_map_file="map.txt")
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_power_dissipation_from_power_map_file():
    session = await start_powerdc_session(spd_file="board.spd")
    sid = session["session_id"]
    await powerdc_set_power_dissipation(sid, "D1", power_map_file="PowerMapD1.txt", output_temperature_map="D1_TemperatureMap.dat")
    script = tcl_sessions.preview(sid)
    assert "-dissipation {-type {Power} -filename {PowerMapD1.txt} -powerMap {0} -source {Volume} -outputTemmperatureMap {D1_TemperatureMap.dat}} {!}" in script
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_appends_begin_simulation_and_builds_correct_argv(fake_exe):
    session = await start_powerdc_session(spd_file="board.spd")
    sid = session["session_id"]
    await powerdc_set_simulation_mode(sid, ir_drop_analysis=True)

    result = await powerdc_run_session(sid)
    assert result["command"][1:3] == ["-b", "-tcl"]

    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    macro_path = result["command"][3]
    macro_text = open(macro_path, encoding="utf-8").read()
    assert "sigrity::begin simulation {!}" in macro_text

    # session should be auto-closed after running
    with pytest.raises(Exception):
        tcl_sessions.get(sid)


@pytest.mark.asyncio
async def test_export_signoff_report_argv(fake_exe):
    result = await powerdc_export_signoff_report("case.pdcx", report_type="PinIRdrop")
    assert result["command"][1:] == ["-b", "case.pdcx", "-Report", "-PinIRdrop"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")
