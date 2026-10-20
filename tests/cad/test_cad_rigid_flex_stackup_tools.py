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
    the tool's docstring's FULL-SCALE LIVE TEST note and load_skill("sigrity-cad")).
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
async def test_reference_plane_assigned_only_via_adjacency_not_a_skill_field():
    """Proves the reported caveat is both (a) real and (b) handled with confidence.

    The tool has NO SKILL-callable "reference plane" field on an xsection layer (checked
    against this install's vendored SKILL docs -- axlXSectionGet.txt has no such
    attribute; no axlCNS* constraint-manager function offers one). Allegro's impedance
    calculator infers a signal layer's reference plane purely from STACKUP ADJACENCY to a
    PLANE layer -- so the ONLY thing a design flow can actually set, to hit the
    50/90/100 Ohm targets, is which named plane physically sits above/below the signal
    layer. That is exactly what the input `layers` list's order encodes.

    This deterministic unit test locks in that property: two stackups that differ ONLY in
    which named GND plane is adjacent to the signal layer must (1) queue a SKILL script
    whose physical layer order encodes exactly that adjacency, and (2) carry no
    ref_plane/zone/hatched_plane content in any queued SKILL line -- i.e. those inputs are
    echoed in the return value for bookkeeping only and never become a SKILL call, which
    is why the live proof (scripts/smoke/smoke_ref_plane_adjacency.py, run 2026-10-18
    against a real board copy) showed the reference plane actually switching to whichever
    plane we placed adjacent.

    top-to-bottom queued:  <above>  /  L_SIG_DIFF  /  <below>  /  L_SIG_SE50
    """
    signal_above, signal_below = "L_GND_A", "L_GND_B"
    layers = [
        {"name": signal_above, "layer_type": "PLANE", "material": "COPPER", "thickness_mil": 1.4,
         "ref_plane": None, "zone": "RIGID"},
        # The 90 Ohm differential-pair signal conductor -- its electrical reference plane(s)
        # are whatever PLANE layers are physically adjacent to it, i.e. L_GND_A here.
        {"name": "L_SIG_DIFF", "layer_type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7,
         "ref_plane": "L_GND_A", "zone": "RIGID"},
        {"name": signal_below, "layer_type": "PLANE", "material": "COPPER", "thickness_mil": 1.4,
         "ref_plane": None, "zone": "RIGID"},
        {"name": "L_SIG_SE50", "layer_type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7,
         "ref_plane": "L_SIG_DIFF", "zone": "FLEX", "hatched_plane": True},
    ]

    session = await start_allegro_session()
    sid = session["session_id"]
    result = await generate_multilayer_stackup(sid, layers=layers)

    # 1) The queued SKILL encodes adjacency as PHYSICAL ORDER: the two named GND planes
    #    must bracket the signal conductor, in exactly the order given -- this is the
    #    reference-plane assignment, and it is real.
    queued_names = [l["name"] for l in result["queued_layers"]]
    assert queued_names == [signal_above, "L_SIG_DIFF", signal_below, "L_SIG_SE50"]
    sig_idx = queued_names.index("L_SIG_DIFF")
    assert queued_names[sig_idx - 1] == signal_above
    assert queued_names[sig_idx + 1] == signal_below

    script = tcl_sessions.preview(sid)
    lines = [ln for ln in script.splitlines() if ln.strip()]
    assert len(lines) == 4
    # The signal conductor's SKILL line references ONLY real, settable xsection
    # attributes (name/layerType/material/thickness) -- no reference-plane field.
    sig_line = next(ln for ln in lines if "L_SIG_DIFF" in ln)
    assert 'skill (axlXSectionCreate nil \'bottom (make_axlXSection ?name "L_SIG_DIFF" ' in sig_line
    assert "?layerType \"CONDUCTOR\"" in sig_line
    assert "?material \"COPPER\"" in sig_line
    assert "?thickness 0.7" in sig_line

    # 2) ref_plane / zone / hatched_plane are echoed in the return value for
    #    bookkeeping, but carry NO SKILL field: none of that content appears anywhere
    #    in the queued SKILL script, and the signal line's attribute list closes
    #    immediately after ?thickness (no ref_plane/zone/hatch field appended). This
    #    is precisely why the impedance target is controlled (with confidence) via
    #    adjacency -- there is no alternative field to fight us.
    sig_entry = next(l for l in result["queued_layers"] if l["name"] == "L_SIG_DIFF")
    assert sig_entry["ref_plane"] == "L_GND_A"  # echoed back for docs/bookkeeping
    assert "RIGID" not in script and "FLEX" not in script      # zone -> no SKILL call
    assert "hatch" not in script.lower() and "ref_plane" not in script  # neither do these
    assert sig_line.rstrip().endswith("?thickness 0.7))")       # signal line closes after ?thickness (no ref-plane attr)

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_high_speed_constraint_preset():
    result = await get_high_speed_constraint_preset("DDR5")
    assert result["status"] == "success"
    assert result["constraints"]["diff_impedance_ohms"] == 80.0
    assert result["constraints"]["intra_pair_length_match_mils"] == 2.0

    pcie_res = await get_high_speed_constraint_preset("PCIE_GEN5")
    assert pcie_res["constraints"]["diff_impedance_ohms"] == 85.0
