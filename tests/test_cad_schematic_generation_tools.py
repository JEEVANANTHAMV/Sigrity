import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.schematic_generation_tools import generate_schematic_from_spec


@pytest.mark.asyncio
async def test_generate_schematic_from_spec_composes_expected_script(fake_exe, monkeypatch):
    captured_session_id = {}

    from sigrity_mcp.domains.cad import schematic_generation_tools as sgt

    original_run = sgt.capture_run_session

    async def spy_run(session_id, product="OrCAD Capture"):
        captured_session_id["id"] = session_id
        captured_session_id["script"] = tcl_sessions.preview(session_id)
        return await original_run(session_id, product=product)

    monkeypatch.setattr(sgt, "capture_run_session", spy_run)

    result = await generate_schematic_from_spec(
        project_file="board.opj",
        parts=[
            {"x": 0, "y": 0, "library_file": "mylib.olb", "part_name": "R", "package": "RES"},
            {"x": 100, "y": 0, "library_file": "mylib.olb", "part_name": "C", "package": "CAP"},
        ],
        wires=[{"x1": 0, "y1": 0, "x2": 100, "y2": 0}],
        pins=[{"x": 0, "y": 10, "pin_name": "IN1"}],
    )

    assert result["parts_placed"] == 2
    assert result["wires_placed"] == 1
    assert result["pins_placed"] == 1
    assert "job_id" in result

    script = captured_session_id["script"]
    assert script.count("PlacePart") == 2
    assert "PlaceWire 0 0 100 0" in script
    assert 'PlacePin 0 10 {IN1} {Passive} FALSE' in script
    assert 'Menu "Tools::Annotate"' in script
    assert 'Menu "Tools::Create Netlist"' in script
    assert 'Menu "File::Save"' in script

    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_generate_schematic_from_spec_can_skip_annotate_and_netlist(fake_exe, monkeypatch):
    from sigrity_mcp.domains.cad import schematic_generation_tools as sgt

    captured = {}
    original_run = sgt.capture_run_session

    async def spy_run(session_id, product="OrCAD Capture"):
        captured["script"] = tcl_sessions.preview(session_id)
        return await original_run(session_id, product=product)

    monkeypatch.setattr(sgt, "capture_run_session", spy_run)

    await generate_schematic_from_spec(
        project_file="board.opj",
        parts=[{"x": 0, "y": 0, "library_file": "mylib.olb", "part_name": "R"}],
        annotate=False,
        create_netlist=False,
    )

    assert 'Menu "Tools::Annotate"' not in captured["script"]
    assert 'Menu "Tools::Create Netlist"' not in captured["script"]
    assert 'Menu "File::Save"' in captured["script"]
