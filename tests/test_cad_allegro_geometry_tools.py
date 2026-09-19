import pytest

from sigrity_mcp.domains.cad.allegro_geometry_tools import (
    allegro_assign_net,
    allegro_create_film,
    allegro_create_simple_padstack,
    allegro_create_trace,
    allegro_create_via,
    allegro_get_module_instance_location,
    allegro_place_module_instance,
)
from sigrity_mcp.domains.cad.allegro_tools import start_allegro_session
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session


@pytest.mark.asyncio
async def test_create_trace_appends_path_and_start():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_trace(sid, [[0, 0], [100, 0], [100, 100]], "TOP", "GND")
    preview = await preview_tcl_session(sid)
    assert "axlPathStart" in preview["script"]
    assert '"TOP"' in preview["script"] and '"GND"' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_trace_requires_two_points():
    session = await start_allegro_session()
    sid = session["session_id"]
    with pytest.raises(ValueError):
        await allegro_create_trace(sid, [[0, 0]], "TOP", "GND")
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_via_with_net():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_via(sid, "via_pad", 100.0, 200.0, net_name="VCC", rotation=45.0)
    preview = await preview_tcl_session(sid)
    assert 'skill (axlDBCreateVia "via_pad" (list 100.0 200.0) "VCC" nil 45.0)' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_via_standalone_no_net():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_via(sid, "via_pad", 0, 0)
    preview = await preview_tcl_session(sid)
    assert 'skill (axlDBCreateVia "via_pad" (list 0 0) nil nil 0.0)' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_simple_padstack_smt_no_drill():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_simple_padstack(sid, "smt_pad", "TOP", 25, 60)
    preview = await preview_tcl_session(sid)
    assert "axlDBCreatePadStack" in preview["script"]
    assert "make_axlPadStackPad" in preview["script"]
    assert "?figureSize 25:60" in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_place_module_instance():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_place_module_instance(sid, "U1_inst", "SOIC8_MOD", 500, 1500, rotation=90)
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlDBCreateModuleInstance "U1_inst" "SOIC8_MOD" (list 500 1500) 90 0 nil nil)'
        in preview["script"]
    )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_assign_net():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_assign_net(sid, "PIN", "U1.1", "GND", ripup=True)
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlDBAssignNet (car (axlSelectByName "PIN" "U1.1")) "GND" t nil)' in preview["script"]
    )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_film_basic():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_film(sid, "TOP", ["ETCH/TOP"])
    preview = await preview_tcl_session(sid)
    assert 'skill (axlFilmCreate "TOP" ?layers (list "ETCH/TOP"))' in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_film_negative_and_mirrored():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_film(sid, "BOTTOM", ["ETCH/BOTTOM"], negative=True, mirrored=True)
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlFilmCreate "BOTTOM" ?layers (list "ETCH/BOTTOM") ?negative t ?mirrored t)'
        in preview["script"]
    )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_module_instance_location():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_get_module_instance_location(sid, "U1_inst")
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlGetModuleInstanceLocation (car (axlSelectByName "GROUP" "U1_inst")))'
        in preview["script"]
    )
    await close_tcl_session(sid)
