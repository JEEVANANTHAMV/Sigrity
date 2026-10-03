import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.allegro_tools import (
    allegro_create_board_outline,
    allegro_create_component,
    allegro_create_net,
    allegro_create_stackup,
    allegro_run_drc,
    allegro_run_session,
    allegro_save_design,
    start_allegro_session,
)
from sigrity_mcp.domains.platform.session_tools import close_tcl_session


@pytest.mark.asyncio
async def test_start_session_has_no_lines_yet():
    result = await start_allegro_session()
    preview = tcl_sessions.preview(result["session_id"])
    assert preview.strip() == ""
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_skill():
    session = await start_allegro_session()
    sid = session["session_id"]

    await allegro_create_net(sid, "GND")
    await allegro_create_component(sid, "U1", "MyDevice", package="SOIC8")
    await allegro_create_board_outline(sid, [[0, 0], [100, 0], [100, 50], [0, 50]])
    await allegro_create_stackup(sid, position="top")
    await allegro_run_drc(sid)
    await allegro_save_design(sid)

    script = tcl_sessions.preview(sid)
    assert 'skill (axlDBCreateNet "GND")' in script
    assert 'skill (axlDBCreateComponent "U1" "MyDevice" "SOIC8")' in script
    assert "axlDBCreateShape" in script and "BOARD GEOMETRY/OUTLINE" in script
    assert "skill (axlXSectionCreate nil 'top (make_axlXSection))" in script
    assert "skill (axlDRCUpdate nil)" in script
    assert "skill (axlSaveDesign)" in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_allegro_create_stackup_real_attributes_and_position_forms():
    """allegro_create_stackup used to only ever emit a bare, attribute-less
    (axlXSectionCreate nil 'position) call -- confirmed real name/layerType/material/
    thickness authoring (via make_axlXSection) live against a real board (see
    generate_multilayer_stackup's docstring / core/tool_status.py's "allegro" note for the
    live evidence); this test locks down the SKILL it composes for each position form.
    """
    session = await start_allegro_session()
    sid = session["session_id"]

    await allegro_create_stackup(sid, position="bottom", name="L2_GND", layer_type="PLANE",
                                  material="COPPER", thickness_mil=1.4)
    await allegro_create_stackup(sid, position="ANCHOR_LAYER")  # insert above a named layer
    await allegro_create_stackup(sid, position=3)  # numeric x_position

    script = tcl_sessions.preview(sid)
    lines = [ln for ln in script.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert (
        "skill (axlXSectionCreate nil 'bottom (make_axlXSection ?name \"L2_GND\" "
        '?layerType "PLANE" ?material "COPPER" ?thickness 1.4))' in lines[0]
    )
    assert 'skill (axlXSectionCreate nil "ANCHOR_LAYER" (make_axlXSection))' in lines[1]
    assert "skill (axlXSectionCreate nil 3 (make_axlXSection))" in lines[2]

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_correct_argv_and_appends_quit(fake_exe):
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_net(sid, "VCC")

    result = await allegro_run_session(sid, board_file="board.brd")
    assert result["command"][1] == "-s"
    assert result["command"][2].endswith("macro.scr")
    assert result["command"][3] == "board.brd"
    assert len(result["command"]) == 4
    # No axlSaveDesign in this session -- no .jrl-journal warning expected.
    assert "note" not in result

    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_run_session_warns_about_jrl_journal_when_session_saves_design(fake_exe):
    # Regression: SKILL-level save errors (e.g. the ?noCheck keyword bug) are logged
    # only to Allegro's own .jrl journal, never to run.log -- a state="succeeded"
    # result is not proof the save actually executed. Surface that at the call site
    # whenever the session's own script queues an axlSaveDesign call.
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_save_design(sid)

    result = await allegro_run_session(sid, board_file="board.brd")
    assert "axlSaveDesign" in result["note"]
    assert ".jrl" in result["note"]
