import json
import os
import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.allegro_tools import start_allegro_session
from sigrity_mcp.domains.cad.rigid_flex_stackup_tools import (
    build_18layer_rigid_flex_stackup_definition,
    generate_18layer_rigid_flex_stackup,
    generate_multilayer_stackup,
    get_high_speed_constraint_preset,
)
from sigrity_mcp.domains.platform.session_tools import close_tcl_session
from sigrity_mcp.server import mcp


@pytest.mark.asyncio
async def test_generate_18layer_rigid_flex_stackup(tmp_path):
    scr_file = str(tmp_path / "stackup.scr")
    result = await generate_18layer_rigid_flex_stackup(output_script_path=scr_file)
    assert result["status"] == "success"
    assert result["layer_count"] == 18
    assert "L9_FLEX_SIG1" in result["flex_layers"]
    assert os.path.exists(scr_file)
    # Preview-only, not executable SKILL -- see the tool's own docstring/note.
    assert "generate_multilayer_stackup" in result["note"]


@pytest.mark.asyncio
async def test_generate_multilayer_stackup_composes_in_given_order_not_reversed():
    """The real, live-verified finding (see the tool's docstring): axlXSectionCreate(nil
    'bottom ...) must be queued IN THE GIVEN top-to-bottom order to land correctly -- an
    earlier reverse-queued implementation was proven wrong via a live report.exe read-back.
    So the session script must show the layers in the SAME order they were passed in.
    """
    session = await start_allegro_session()
    sid = session["session_id"]

    layers = [
        {"name": "TOPTEST", "layer_type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 1.4},
        {"name": "PLANETEST", "layer_type": "PLANE", "material": "COPPER", "thickness_mil": 1.4},
        {"name": "BOTTOMTEST", "layer_type": "CONDUCTOR", "material": "RA_COPPER", "thickness_mil": 0.7},
    ]
    result = await generate_multilayer_stackup(sid, layers=layers)
    assert result["layer_count"] == 3
    assert [l["name"] for l in result["queued_layers"]] == ["TOPTEST", "PLANETEST", "BOTTOMTEST"]

    script = tcl_sessions.preview(sid)
    lines = [ln for ln in script.splitlines() if ln.strip()]
    assert len(lines) == 3
    # Order in the script must match input order (NOT reversed).
    assert "TOPTEST" in lines[0]
    assert "PLANETEST" in lines[1]
    assert "BOTTOMTEST" in lines[2]
    # Each line is a real axlXSectionCreate call with a real defstruct, not a bare/no-op call.
    assert 'skill (axlXSectionCreate nil \'bottom (make_axlXSection ?name "TOPTEST" ' in lines[0]
    assert "?layerType \"CONDUCTOR\"" in lines[0]
    assert "?material \"COPPER\"" in lines[0]
    assert "?thickness 1.4" in lines[0]

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_generate_multilayer_stackup_warns_on_top_bottom_name_collision():
    # Regression: a layer named "TOP"/"BOTTOM" (case-insensitive) collides with the
    # board's own pre-existing outer layers and is silently skipped by Allegro -- no
    # duplicate, no error, no attribute change. Must surface a warning instead of
    # reporting it as queued with no caveat.
    session = await start_allegro_session()
    sid = session["session_id"]
    layers = [
        {"name": "top", "layer_type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 1.4},
        {"name": "INNER1", "layer_type": "PLANE", "material": "COPPER", "thickness_mil": 1.4},
        {"name": "BOTTOM", "layer_type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 1.4},
    ]
    result = await generate_multilayer_stackup(sid, layers=layers)
    assert "SILENTLY SKIPPED" in result["warning"]
    assert "top" in result["warning"] and "BOTTOM" in result["warning"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_generate_multilayer_stackup_no_warning_for_normal_layer_names():
    session = await start_allegro_session()
    sid = session["session_id"]
    layers = [{"name": "L2_GND", "layer_type": "PLANE", "material": "COPPER", "thickness_mil": 1.4}]
    result = await generate_multilayer_stackup(sid, layers=layers)
    assert "warning" not in result
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_generate_multilayer_stackup_rejects_empty_or_unnamed_layers():
    session = await start_allegro_session()
    sid = session["session_id"]

    with pytest.raises(ValueError):
        await generate_multilayer_stackup(sid, layers=[])

    with pytest.raises(ValueError):
        await generate_multilayer_stackup(sid, layers=[{"layer_type": "CONDUCTOR"}])

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_generate_multilayer_stackup_accepts_the_real_18layer_definition():
    """Confirms the actual production 18-layer definition (same shape used by
    generate_18layer_rigid_flex_stackup) round-trips through generate_multilayer_stackup's
    input contract -- this exact list was also run live against a real board (see
    the tool's docstring's FULL-SCALE LIVE TEST note and .forjinn/skills/sigrity-cad/SKILL.md).
    """
    raw_layers = build_18layer_rigid_flex_stackup_definition()
    mapped = [
        {
            "name": l["name"],
            "layer_type": l["type"],
            "material": l["material"],
            "thickness_mil": l["thickness_mil"],
            "zone": l["zone"],
            "ref_plane": l.get("ref_plane"),
            "hatched_plane": l.get("hatched_plane"),
        }
        for l in raw_layers
    ]

    session = await start_allegro_session()
    sid = session["session_id"]
    result = await generate_multilayer_stackup(sid, layers=mapped)
    assert result["layer_count"] == 18
    assert [l["name"] for l in result["queued_layers"]] == [l["name"] for l in mapped]
    # zone/ref_plane/hatched_plane are informational only -- echoed back, not SKILL calls.
    flex_entry = next(l for l in result["queued_layers"] if l["name"] == "L9_FLEX_SIG1")
    assert flex_entry["zone"] == "FLEX"
    assert flex_entry["hatched_plane"] is True

    script = tcl_sessions.preview(sid)
    assert script.count("axlXSectionCreate") == 18

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_generate_multilayer_stackup_accepts_layers_as_json_string_through_mcp():
    """Reproduces the real failure: a calling model (observed live: qwen3-max via vLLM,
    through the real forji-desk app) serialized the `layers` list argument as a JSON
    STRING rather than a native JSON array. FastMCP's pydantic argument validation in
    `FunctionTool.run()` rejects that outright (confirmed directly against the installed
    fastmcp==4.0.4 package: `tool.run({"session_id": ..., "layers": json.dumps([...])})`
    raises `pydantic.ValidationError: ... Input should be a valid list [type=list_type...]`
    with no fix applied).

    This calls the tool through `mcp.call_tool(...)` -- the real dispatch path a live
    `tools/call` request takes (middleware chain -> FunctionTool.run() -> the tool body),
    NOT the raw Python function directly -- so it actually exercises
    `JsonStringArgumentCoercionMiddleware` (sigrity_mcp/core/argument_coercion_middleware.py),
    which is where the fix lives.
    """
    session = await start_allegro_session()
    sid = session["session_id"]

    layers = [
        {"name": "TOPTEST", "layer_type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 1.4},
        {"name": "BOTTOMTEST", "layer_type": "PLANE", "material": "COPPER", "thickness_mil": 1.4},
    ]
    # The exact failure mode: layers arrives JSON-encoded as a string, not a list.
    args = {"session_id": sid, "layers": json.dumps(layers)}

    result = await mcp.call_tool("generate_multilayer_stackup", args)

    assert result.is_error is False
    assert result.structured_content["layer_count"] == 2
    assert [l["name"] for l in result.structured_content["queued_layers"]] == [
        "TOPTEST",
        "BOTTOMTEST",
    ]

    script = tcl_sessions.preview(sid)
    assert script.count("axlXSectionCreate") == 2

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_high_speed_constraint_preset():
    result = await get_high_speed_constraint_preset("DDR5")
    assert result["status"] == "success"
    assert result["constraints"]["diff_impedance_ohms"] == 80.0
    assert result["constraints"]["intra_pair_length_match_mils"] == 2.0

    pcie_res = await get_high_speed_constraint_preset("PCIE_GEN5")
    assert pcie_res["constraints"]["diff_impedance_ohms"] == 85.0
