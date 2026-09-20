import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.schematic_generation_tools import _find_project_schematic_design, generate_schematic_from_spec


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


@pytest.mark.asyncio
async def test_generate_schematic_from_spec_rejects_partial_page_spec_before_any_session(monkeypatch):
    """A half-given page spec (say, only `design` of the three) must be rejected with an
    error dict BEFORE any session is created or any process launched — verified here by
    asserting the very next call (`start_capture_session`) never actually runs."""
    from sigrity_mcp.domains.cad import schematic_generation_tools as sgt

    async def explode_start(project_file):
        raise AssertionError("start_capture_session must not be called for a rejected arg combo")

    async def explode_select(session_id, design, schematic_folder, page):
        raise AssertionError("capture_select_page must not be called for a rejected arg combo")

    async def explode_auto(job_id):
        raise AssertionError("auto_dismiss_recovery_dialog_if_stuck must not run for a rejected arg combo")

    monkeypatch.setattr(sgt, "start_capture_session", explode_start)
    monkeypatch.setattr(sgt, "capture_select_page", explode_select)
    monkeypatch.setattr(sgt, "auto_dismiss_recovery_dialog_if_stuck", explode_auto)

    result = await generate_schematic_from_spec(
        project_file="any.opj",
        parts=[{"x": 0, "y": 0, "library_file": "lib.olb", "part_name": "R"}],
        design="./some.dsn",
    )

    assert "error" in result
    assert "design, schematic_folder, and page" in result["error"]


@pytest.mark.asyncio
async def test_generate_schematic_from_spec_uses_explicit_page_when_given(fake_exe, monkeypatch):
    from sigrity_mcp.domains.cad import schematic_generation_tools as sgt

    captured = {}
    original_run = sgt.capture_run_session

    async def spy_run(session_id, product="OrCAD Capture"):
        captured["script"] = tcl_sessions.preview(session_id)
        return await original_run(session_id, product=product)

    async def no_auto_check(job_id):
        return None

    monkeypatch.setattr(sgt, "capture_run_session", spy_run)
    monkeypatch.setattr(sgt, "auto_dismiss_recovery_dialog_if_stuck", no_auto_check)

    result = await generate_schematic_from_spec(
        project_file="board.opj",
        parts=[{"x": 0, "y": 0, "library_file": "mylib.olb", "part_name": "R"}],
        design="./board.dsn",
        schematic_folder="MyFolder",
        page="PAGE_3",
        annotate=False,
        create_netlist=False,
    )

    script = captured["script"]
    assert 'SelectPMItem {./board.dsn}' in script
    assert 'OPage {MyFolder} {PAGE_3}' in script
    assert result["page"] == "./board.dsn -> MyFolder/PAGE_3"


def _write_opj(tmp_path, name, body):
    opj = tmp_path / name
    opj.write_text(body, encoding="utf-8")
    return str(opj)


def test_find_project_schematic_design_parses_real_opj_shape(tmp_path):
    path = _write_opj(
        tmp_path,
        "Fault-Detector.opj",
        r"""(ExpressProject "test1"
  (ProjectVersion "19981106")
  (ProjectType "PCB")
  (Folder "Design Resources"
    (Folder "Library")
    (NoModify)
    (File ".\fault-detector.dsn"
      (Type "Schematic Design"))
    (BuildFileAddedOrDeleted "x")
  )
)""",
    )
    design, stem = _find_project_schematic_design(path)
    assert design == ".\\fault-detector.dsn"
    assert stem == "fault-detector"


def test_find_project_schematic_design_ignores_non_design_files(tmp_path):
    path = _write_opj(
        tmp_path,
        "lib.opj",
        r"""(ExpressProject "x"
  (Folder "Design Resources"
    (File ".\my.lib"
      (Type "Library"))
    (File ".\my.dsn"
      (Type "Schematic Design"))
  )
)""",
    )
    result = _find_project_schematic_design(path)
    assert result == (".\\my.dsn", "my")


def test_find_project_schematic_design_returns_none_for_missing_file(tmp_path):
    assert _find_project_schematic_design(str(tmp_path / "does_not_exist.opj")) is None


def test_find_project_schematic_design_returns_none_when_no_schematic_type(tmp_path):
    path = _write_opj(
        tmp_path,
        "lib.opj",
        r"""(ExpressProject "x"
  (Folder "Design Resources"
    (File ".\my.lib"
      (Type "Library"))
  )
)""",
    )
    assert _find_project_schematic_design(path) is None


@pytest.mark.asyncio
async def test_generate_schematic_from_spec_selects_page_before_placement(fake_exe, monkeypatch):
    """Regression test for the live root cause found this pass: after `Open <proj>`,
    Capture's active view is the project root, not a schematic page — Placement
    commands had *nowhere to act* — so the macro must select a real page first. We
    assert ordering (SelectPMItem/OPage before any PlacePart) rather than re-testing
    the (machine-level, see core/tool_status.py's `capture` note) question of whether
    Capture itself honors that correctly on this install."""
    from sigrity_mcp.domains.cad import schematic_generation_tools as sgt

    captured = {}
    original_run = sgt.capture_run_session

    async def spy_run(session_id, product="OrCAD Capture"):
        captured["script"] = tcl_sessions.preview(session_id)
        return await original_run(session_id, product=product)

    async def no_auto_check(job_id):
        return None

    monkeypatch.setattr(sgt, "capture_run_session", spy_run)
    monkeypatch.setattr(sgt, "auto_dismiss_recovery_dialog_if_stuck", no_auto_check)

    await generate_schematic_from_spec(
        project_file="board.opj",
        parts=[{"x": 0, "y": 0, "library_file": "mylib.olb", "part_name": "R"}],
        annotate=False,
        create_netlist=False,
    )

    script = captured["script"]
    select_idx = script.index("SelectPMItem")
    opage_idx = script.index("OPage")
    place_idx = script.index("PlacePart")
    open_idx = script.index("Open ")
    assert open_idx < select_idx < opage_idx < place_idx


def test_find_window_returns_none_when_no_matching_window(monkeypatch):
    """Unit test for the window-lookup helper behind capture_handle_custom_launch_dialog,
    faked at the ctypes boundary via _win32_user32 (no real Capture process involved) —
    confirms the tool path correctly reports 'no dialog present' rather than raising,
    the common case for a caller polling a healthy, non-dialog-blocked job."""
    import sigrity_mcp.domains.cad.capture_tools as ct

    class _CallableProperty:
        def __init__(self):
            self.argtypes = None
            self.restype = None

        def __call__(self, *args, **kwargs):
            return 1

    class _FakeUser32:
        def __init__(self):
            self.EnumWindows = _CallableProperty()
            self.GetWindowTextW = _CallableProperty()

    fake_user32 = _FakeUser32()
    # EnumWindows() is called with (callback, 0); no windows are registered, so the
    # callback is never invoked and GetWindowTextW is never reached.
    fake_user32.EnumWindows = _CallableProperty()

    monkeypatch.setattr(ct, "_win32_user32", lambda: fake_user32)

    found = ct._find_window("definitely_absent_dialog_title")
    assert found is None
