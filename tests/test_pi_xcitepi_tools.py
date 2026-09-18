import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session
from sigrity_mcp.domains.pi.xcitepi_tools import (
    start_xcitepi_session,
    xcitepi_generate_report,
    xcitepi_open_layout,
    xcitepi_run_session,
    xcitepi_save_design,
    xcitepi_save_iome_result,
    xcitepi_set_spice_output,
)


@pytest.mark.asyncio
async def test_start_session_sets_feature_and_tech_file():
    result = await start_xcitepi_session(feature="IOME", tech_file=r"C:\tech\demo1_pme_ckt.tech")
    preview = await preview_tcl_session(result["session_id"])
    assert "xpi_set_feature {IOME}" in preview["script"]
    assert "xpi_set_tech_file {C:/tech/demo1_pme_ckt.tech}" in preview["script"]
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl_matching_sample_decap_flow():
    session = await start_xcitepi_session(feature="IOME", tech_file="demo1_pme_ckt.tech")
    sid = session["session_id"]

    await xcitepi_open_layout(sid, "demo_decap.gds", map_file="demo1.map")
    await xcitepi_save_design(sid, "demo_decap.xpi")
    await xcitepi_set_spice_output(sid, "demo_decap.sp", style="pin", extraction="rc")
    await xcitepi_generate_report(sid, "report.htm", scope="decap")
    await xcitepi_save_iome_result(sid, "demo_decap")

    script = tcl_sessions.preview(sid)
    assert "xpi_open_file {demo_decap.gds} {demo1.map}" in script
    assert "xpi_save_design {demo_decap.xpi}" in script
    assert "xpi_set_spice_output_path {demo_decap.sp}" in script
    assert "xpi_set_spice_option -pin -rc" in script
    assert "xpi_report -decap -output {report.htm}" in script
    assert "xpi_save_iome_result {demo_decap}" in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_open_layout_without_map_file_omits_second_word():
    session = await start_xcitepi_session(feature="PME", tech_file="tech.tech")
    sid = session["session_id"]
    await xcitepi_open_layout(sid, "layout.gds")
    script = tcl_sessions.preview(sid)
    lines = script.splitlines()
    assert "xpi_open_file {layout.gds}" in lines  # exact line, no trailing map-file word
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_correct_argv_and_appends_start_close_exit(fake_exe):
    session = await start_xcitepi_session(feature="IOME", tech_file="demo1_pme_ckt.tech")
    sid = session["session_id"]
    await xcitepi_open_layout(sid, "demo_decap.gds", map_file="demo1.map")

    result = await xcitepi_run_session(sid)
    assert result["command"][1:3] == ["-b", "-tcl"]

    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    macro_path = result["command"][3]
    macro_text = open(macro_path, encoding="utf-8").read()
    assert "xpi_start" in macro_text
    assert "xpi_close_design" in macro_text
    assert "xpi_exit" in macro_text

    # session should be auto-closed after running
    with pytest.raises(Exception):
        tcl_sessions.get(sid)
