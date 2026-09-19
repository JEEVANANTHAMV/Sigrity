import pytest

from sigrity_mcp.domains.cad.allegro_constraint_tools import (
    allegro_create_ecset,
    allegro_get_net_constraint,
    allegro_set_physical_constraint,
    allegro_set_spacing_constraint,
)
from sigrity_mcp.domains.cad.allegro_tools import start_allegro_session
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session


@pytest.mark.asyncio
async def test_set_spacing_constraint_default_cset_and_layer():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_set_spacing_constraint(sid, "line_line", 5)
    preview = await preview_tcl_session(sid)
    assert "skill (axlCNSSetSpacing nil nil 'line_line 5)" in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_spacing_constraint_explicit_cset_and_layer():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_set_spacing_constraint(sid, "line_shape", "5mil", cset="", layer="TOP")
    preview = await preview_tcl_session(sid)
    assert 'skill (axlCNSSetSpacing "" "TOP" \'line_shape "5mil")' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_physical_constraint_boolean_value():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_set_physical_constraint(sid, "allow_etch", True, cset="")
    preview = await preview_tcl_session(sid)
    assert "skill (axlCNSSetPhysical \"\" nil 'allow_etch t)" in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_ecset_minimal():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_ecset(sid, "USB_DIFFPAIR")
    preview = await preview_tcl_session(sid)
    assert 'skill (axlCNSEcsetCreate "USB_DIFFPAIR")' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_ecset_copy_from():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_ecset(sid, "NEW_SET", copy_from="OLD_SET")
    preview = await preview_tcl_session(sid)
    assert 'skill (axlCNSEcsetCreate "NEW_SET" "OLD_SET")' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_net_constraint():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_get_net_constraint(sid, "NET1", "IMPEDANCE_RULE")
    preview = await preview_tcl_session(sid)
    assert 'skill (axlCnsNetFlattened "NET1" "IMPEDANCE_RULE")' in preview["script"]
    await close_tcl_session(sid)
