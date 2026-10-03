import pytest

from sigrity_mcp.domains.cad.allegro_geometry_tools import (
    allegro_assign_net,
    allegro_create_copper_shape,
    allegro_create_film,
    allegro_create_simple_padstack,
    allegro_create_trace,
    allegro_create_via,
    allegro_delete_connect,
    allegro_get_module_instance_location,
    allegro_get_net_length,
    allegro_place_module_instance,
)
from sigrity_mcp.domains.cad.allegro_tools import start_allegro_session
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session


@pytest.mark.asyncio
async def test_create_trace_appends_path_and_start():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_create_trace(sid, [[0, 0], [100, 0], [100, 100]], "TOP", "GND", width=5.0)
    assert result["skill_layer"] == "ETCH/TOP"
    assert result["width"] == 5.0
    preview = await preview_tcl_session(sid)
    assert "axlPathStart" in preview["script"]
    assert '"ETCH/TOP"' in preview["script"] and '"GND"' in preview["script"]
    # width must be threaded into axlPathStart as its second argument, not omitted
    # (omitting it is the live-confirmed zero-width-copper bug this fix closes).
    assert "(list 100 100)) 5.0)" in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_trace_passes_full_class_subclass_string_as_is():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_create_trace(sid, [[0, 0], [100, 0]], "BOUNDARY/L2_GND", "GND", width=8.0)
    assert result["skill_layer"] == "BOUNDARY/L2_GND"
    preview = await preview_tcl_session(sid)
    assert '"BOUNDARY/L2_GND"' in preview["script"]
    assert "8.0)" in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_trace_requires_two_points():
    session = await start_allegro_session()
    sid = session["session_id"]
    with pytest.raises(ValueError):
        await allegro_create_trace(sid, [[0, 0]], "TOP", "GND", width=5.0)
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
async def test_create_copper_shape_dynamic_default_boundary_class():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_create_copper_shape(
        sid, "L2_GND", "GND", points=[[0, 0], [1000, 0], [1000, 1000], [0, 1000]]
    )
    assert result["dynamic"] is True
    assert result["skill_layer"] == "BOUNDARY/L2_GND"
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlDBCreateShape (axlPathStart (list (list 0 0) (list 1000 0) (list 1000 1000) '
        '(list 0 1000) (list 0 0))) t "BOUNDARY/L2_GND" "GND")' in preview["script"]
    )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_copper_shape_requires_points():
    session = await start_allegro_session()
    sid = session["session_id"]
    with pytest.raises(TypeError):
        await allegro_create_copper_shape(sid, "L2_GND", "GND")
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_copper_shape_static_etch_with_explicit_points():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_create_copper_shape(
        sid, "TOP", "VCC", points=[[0, 0], [100, 0], [100, 100], [0, 100]], dynamic=False
    )
    assert result["dynamic"] is False
    assert result["skill_layer"] == "ETCH/TOP"
    preview = await preview_tcl_session(sid)
    assert "axlPathStart" in preview["script"]
    assert '"ETCH/TOP"' in preview["script"] and '"VCC"' in preview["script"]
    # auto-closed: 4 input points -> 5 points in the rendered path (first repeated as last)
    assert preview["script"].count("(list ") == 6  # 5 point pairs + the outer list(...)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_copper_shape_points_already_closed_not_duplicated():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_create_copper_shape(
        sid, "L2_GND", "GND", points=[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]
    )
    preview = await preview_tcl_session(sid)
    # 5 input points already closed -> still 5 point pairs, not 6
    assert preview["script"].count("(list ") == 6
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_copper_shape_rejects_too_few_points():
    session = await start_allegro_session()
    sid = session["session_id"]
    with pytest.raises(ValueError):
        await allegro_create_copper_shape(sid, "TOP", "GND", points=[[0, 0], [1, 1]])
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_delete_connect_default_ripup():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_delete_connect(sid, "NET", "N00885")
    assert result["ripup"] is True
    assert "DESTRUCTIVE" in result["warning"]
    assert "allegro_assign_net" in result["warning"]
    preview = await preview_tcl_session(sid)
    assert (
        "skill (axlDeleteObject (car (axlSelectByName \"NET\" \"N00885\")) 'ripup)"
        in preview["script"]
    )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_delete_connect_no_ripup_logic_only():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_delete_connect(sid, "NET", "GND", ripup=False)
    assert result["ripup"] is False
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlDeleteObject (car (axlSelectByName "NET" "GND")))' in preview["script"]
    )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_net_length():
    session = await start_allegro_session()
    sid = session["session_id"]
    await allegro_get_net_length(sid, "N00885")
    preview = await preview_tcl_session(sid)
    assert (
        'skill (axlDBGetLength (car (axlSelectByName "NET" "N00885")))' in preview["script"]
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


@pytest.mark.asyncio
async def test_delete_connect_no_warning_for_non_net_object_type():
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_delete_connect(sid, "PIN", "U1.1")
    assert "warning" not in result
    await close_tcl_session(sid)


# --- allegro_create_trace: self-overlapping path pre-flight check ------------------
#
# Regression coverage for a real failure signature: axlDBCreatePath silently returns
# nil (0 segments, Missing Connections: 1) for a path that retraces part of its own
# prior extent -- same symptom as the bare-layer-name/zero-width bugs, different cause.


@pytest.mark.asyncio
async def test_create_trace_rejects_self_overlapping_horizontal_path():
    session = await start_allegro_session()
    sid = session["session_id"]
    # Two horizontal segments at y=0: [0,10]->[0,0] is really x 0..10, then x 5..15 --
    # these overlap in x-range [5,10].
    with pytest.raises(ValueError, match="self-overlaps"):
        await allegro_create_trace(
            sid, [[0, 0], [10, 0], [5, 0], [15, 0]], "TOP", "GND", width=5.0
        )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_trace_rejects_self_overlapping_vertical_path():
    session = await start_allegro_session()
    sid = session["session_id"]
    with pytest.raises(ValueError, match="self-overlaps"):
        await allegro_create_trace(
            sid, [[0, 0], [0, 10], [0, 5], [0, 15]], "TOP", "GND", width=5.0
        )
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_trace_allows_segments_touching_at_a_corner():
    # A valid L-shaped corner: segments share an endpoint but do not overlap in extent.
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_create_trace(
        sid, [[0, 0], [10, 0], [10, 10]], "TOP", "GND", width=5.0
    )
    assert result["point_count"] == 3
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_trace_allows_a_real_meander_with_no_overlap():
    # A genuine meander (back-and-forth) that does NOT retrace its own extent -- each
    # horizontal leg is at a different Y, so no two collinear segments overlap.
    session = await start_allegro_session()
    sid = session["session_id"]
    result = await allegro_create_trace(
        sid,
        [[0, 0], [10, 0], [10, 5], [0, 5], [0, 10], [10, 10]],
        "TOP", "GND", width=5.0,
    )
    assert result["point_count"] == 6
    await close_tcl_session(sid)
