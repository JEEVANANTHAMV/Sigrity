from dataclasses import dataclass

import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.capture_tools import (
    auto_dismiss_recovery_dialog_if_stuck,
    capture_annotate,
    capture_check_design_rules,
    capture_create_netlist,
    capture_place_part,
    capture_place_pin,
    capture_place_wire,
    capture_run_session,
    capture_save,
    capture_set_property,
    start_capture_session,
)
from sigrity_mcp.domains.platform.session_tools import close_tcl_session


@pytest.mark.asyncio
async def test_start_session_opens_project():
    result = await start_capture_session(project_file=r"C:\designs\board.opj")
    preview = tcl_sessions.preview(result["session_id"])
    assert preview.strip() == "Open C:/designs/board.opj"
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl():
    session = await start_capture_session(project_file="board.opj")
    sid = session["session_id"]

    await capture_place_part(sid, 100, 200, "mylib.olb", "R", package="RES")
    await capture_place_wire(sid, 0, 0, 100, 0)
    await capture_place_pin(sid, 10, 10, "IN1")
    await capture_set_property(sid, "Value", "10k")
    await capture_annotate(sid)
    await capture_check_design_rules(sid)
    await capture_create_netlist(sid)
    await capture_save(sid)

    script = tcl_sessions.preview(sid)
    assert "PlacePart 100 200 {mylib.olb} {R} {RES} FALSE" in script
    assert "PlaceWire 0 0 100 0" in script
    assert 'PlacePin 10 10 {IN1} {Passive} FALSE' in script
    assert "SetProperty {Value} {10k}" in script
    assert 'Menu "Tools::Annotate"' in script
    assert 'Menu "PCB::Design Rules Check"' in script
    assert 'Menu "Tools::Create Netlist"' in script
    assert 'Menu "File::Save"' in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_positional_argv_and_appends_close_exit(fake_exe):
    session = await start_capture_session(project_file="board.opj")
    sid = session["session_id"]

    result = await capture_run_session(sid, product="OrCAD Capture")
    assert result["command"][1] == "-product=OrCAD Capture"
    assert result["command"][2].endswith("macro.tcl")
    assert len(result["command"]) == 3

    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


# auto_dismiss_recovery_dialog_if_stuck — regression coverage for a real gap: a job
# that reaches a TERMINAL state with run.log still empty is a known Capture fast-exit
# silent-no-op mode (job "succeeded" having done no real work). capture_run_session
# itself can never observe this (it returns immediately after launch, long before the
# process can reach a terminal state) -- this function is the first point that
# actually waits long enough to see it, so the warning belongs here.


@dataclass
class _FakeJobRecord:
    state: str
    job_dir: str


class _FakeJobManager:
    def __init__(self, record):
        self._record = record

    async def wait(self, job_id, timeout):
        return self._record


@pytest.mark.asyncio
async def test_auto_dismiss_warns_on_succeeded_with_empty_log(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module

    (tmp_path / "run.log").write_bytes(b"")
    record = _FakeJobRecord(state="succeeded", job_dir=str(tmp_path))
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManager(record))

    note = await auto_dismiss_recovery_dialog_if_stuck("fake-job", check_after_seconds=1.0)
    assert note is not None
    assert "fast-exit" in note
    assert "succeeded" in note


@pytest.mark.asyncio
async def test_auto_dismiss_no_warning_when_succeeded_with_real_log_content(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module

    (tmp_path / "run.log").write_text("real output here")
    record = _FakeJobRecord(state="succeeded", job_dir=str(tmp_path))
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManager(record))

    note = await auto_dismiss_recovery_dialog_if_stuck("fake-job", check_after_seconds=1.0)
    assert note is None


@pytest.mark.asyncio
async def test_auto_dismiss_no_warning_for_failed_state(tmp_path, monkeypatch):
    # Scope is deliberately limited to the misleading "succeeded" case -- a "failed"
    # state is already an honest negative signal, nothing misleading to flag.
    import sigrity_mcp.core.jobs as jobs_module

    (tmp_path / "run.log").write_bytes(b"")
    record = _FakeJobRecord(state="failed", job_dir=str(tmp_path))
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManager(record))

    note = await auto_dismiss_recovery_dialog_if_stuck("fake-job", check_after_seconds=1.0)
    assert note is None
