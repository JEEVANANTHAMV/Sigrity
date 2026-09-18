import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.extraction.xtractim_tools import (
    run_xtractim_workspace,
    start_xtractim_session,
    xtractim_process_and_save,
    xtractim_run_session,
    xtractim_select_net,
    xtractim_set_circuits,
    xtractim_set_mode,
    xtractim_set_package_type,
    xtractim_set_pg_analysis_options,
)
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session


@pytest.mark.asyncio
async def test_run_workspace_builds_correct_argv(fake_exe):
    result = await run_xtractim_workspace("workspace.xml")
    assert result["command"][1:] == ["-b", "workspace.xml"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_run_workspace_with_spd_override(fake_exe):
    result = await run_xtractim_workspace("workspace.xml", spd_override="new.spd")
    assert result["command"][1:] == ["-b", "workspace.xml", "new.spd"]


@pytest.mark.asyncio
async def test_start_session_opens_document():
    result = await start_xtractim_session(spd_file=r"C:\design\board.spd")
    preview = await preview_tcl_session(result["session_id"])
    script = preview["script"]
    assert "sigrity::open document {!}" in script
    assert "sigrity::open document -attach {C:/design/board.spd} {!}" in script
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl():
    session = await start_xtractim_session(spd_file="board.spd")
    sid = session["session_id"]

    await xtractim_select_net(sid, net_name=None, selected=False)
    await xtractim_select_net(sid, net_name="GND", selected=True)
    await xtractim_set_mode(sid, "EPA")
    await xtractim_set_package_type(sid, die=0, board=0, assembly=1)
    await xtractim_set_circuits(sid, die_ref_des="U1", board_ref_des="BGA1", component_ref_des_list=["C1", "C2"])
    await xtractim_set_pg_analysis_options(sid)
    await xtractim_process_and_save(sid, "workspace.xml")

    script = tcl_sessions.preview(sid)
    assert "sigrity::update net selected 0 -all {!}" in script
    assert "sigrity::update net selected 1 {GND} {!}" in script
    assert "sigrity::update Mode {EPA} {!}" in script
    assert "sigrity::update PackageType -d {0} -b {0} -a {1} {!}" in script
    assert "sigrity::update Circuits -d {U1} -b {BGA1} -c {C1} {C2} {!}" in script
    assert "sigrity::update PGAnalysis -i {1} -d {1} -l {1} -p {2} -freq {2} -all {!}" in script
    assert "sigrity::process shape {!}" in script
    assert "sigrity::save -workspace {workspace.xml} {!}" in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_correct_argv(fake_exe):
    session = await start_xtractim_session(spd_file="board.spd")
    sid = session["session_id"]
    await xtractim_set_mode(sid, "EPA")

    result = await xtractim_run_session(sid)
    assert result["command"][1] == "-b"
    assert "-tcl" in result["command"]

    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    with pytest.raises(Exception):
        tcl_sessions.get(sid)
