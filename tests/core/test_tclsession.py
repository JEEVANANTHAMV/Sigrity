import sys
from pathlib import Path

import pytest

from sigrity_mcp.core.errors import JobNotFoundError
from sigrity_mcp.core.tclsession import (
    ScriptSession,
    ScriptSessionManager,
    TclSessionManager,
    SessionNotFoundError,
    clear_stale_design_lock,
    run_session,
)
from sigrity_mcp.core.jobs import JobManager


def test_create_and_get_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    session = mgr.create("powersi")
    assert session.session_id.startswith("powersi-session-")
    assert mgr.get(session.session_id) is session


def test_unknown_session_raises():
    mgr = TclSessionManager()
    with pytest.raises(SessionNotFoundError):
        mgr.get("does-not-exist")


def test_add_line_accumulates_and_previews(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    session = mgr.create("powerdc")
    mgr.add_line(session.session_id, "sigrity::open document {!}")
    mgr.add_line(session.session_id, "sigrity::save -w {test.pdcx} {!}")
    text = mgr.preview(session.session_id)
    assert "sigrity::open document {!}" in text
    assert "sigrity::save -w {test.pdcx} {!}" in text
    assert mgr.get(session.session_id).step_count == 2


def test_close_removes_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    session = mgr.create("xcitepi")
    mgr.close(session.session_id)
    with pytest.raises(SessionNotFoundError):
        mgr.get(session.session_id)


def test_list_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    a = mgr.create("powersi")
    b = mgr.create("powerdc")
    ids = {s.session_id for s in mgr.list_sessions()}
    assert ids == {a.session_id, b.session_id}


def test_get_distinguishes_closed_from_never_created(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    session = mgr.create("powersi")
    mgr.close(session.session_id)
    with pytest.raises(SessionNotFoundError, match="already run/closed"):
        mgr.get(session.session_id)
    with pytest.raises(SessionNotFoundError, match="was ever created"):
        mgr.get("totally-made-up-id")


def test_restore_reconstructs_session_after_simulated_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    session = mgr.create("powerdc")
    mgr.add_line(session.session_id, "sigrity::open document {!}")
    mgr.add_line(session.session_id, "sigrity::save -w {test.pdcx} {!}")

    # Simulate a server restart: fresh manager, same on-disk workdir.
    fresh_mgr = TclSessionManager()
    with pytest.raises(SessionNotFoundError):
        fresh_mgr.get(session.session_id)

    restored = fresh_mgr.restore(session.session_id)
    assert restored.session_id == session.session_id
    assert restored.tool == "powerdc"
    assert restored.step_count == 2
    text = restored.script.render()
    assert "sigrity::open document {!}" in text
    assert "sigrity::save -w {test.pdcx} {!}" in text
    # Now in memory — a second restore()/get() call just returns the same object.
    assert fresh_mgr.get(session.session_id) is restored


def test_restore_raises_when_no_snapshot_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    with pytest.raises(SessionNotFoundError):
        mgr.restore("never-existed")


def test_restore_unavailable_after_close_cleans_up_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mgr = TclSessionManager()
    session = mgr.create("xcitepi")
    mgr.add_line(session.session_id, "xpi_start")
    mgr.close(session.session_id)

    fresh_mgr = TclSessionManager()
    with pytest.raises(SessionNotFoundError):
        fresh_mgr.restore(session.session_id)


@pytest.mark.asyncio
async def test_run_session_writes_script_and_launches_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import sigrity_mcp.core.tclsession as tclsession_module

    fresh_jobs = JobManager()
    monkeypatch.setattr("sigrity_mcp.core.jobs.job_manager", fresh_jobs)
    monkeypatch.setattr("sigrity_mcp.core.process.job_manager", fresh_jobs)

    mgr = TclSessionManager()
    monkeypatch.setattr(tclsession_module, "tcl_sessions", mgr)

    session = mgr.create("fake_tool")
    mgr.add_line(session.session_id, "puts hello")

    # Patch executables.resolve so we don't need a real Sigrity install for this test.
    import sigrity_mcp.core.executables as executables_module

    monkeypatch.setattr(executables_module, "resolve", lambda name: sys.executable)

    record = await run_session(session.session_id, tool="fake_tool", build_args=["-c", "pass"])
    finished = await fresh_jobs.wait(record.job_id, timeout=10)
    assert finished.state in ("succeeded", "failed")  # python.exe won't understand -tcl, but it must run

    with pytest.raises(SessionNotFoundError):
        mgr.get(session.session_id)


@pytest.mark.asyncio
async def test_run_session_unknown_id_raises():
    with pytest.raises(SessionNotFoundError):
        await run_session("nope", tool="powersi")


def test_clear_stale_design_lock_removes_existing_lock(tmp_path):
    board = tmp_path / "board.brd"
    board.write_text("fake")
    lock = tmp_path / "board.brd.lck"
    lock.write_text("locked by pid 1234")

    removed = clear_stale_design_lock(str(board))

    assert removed is True
    assert not lock.exists()


def test_clear_stale_design_lock_noop_when_absent(tmp_path):
    board = tmp_path / "board.brd"
    board.write_text("fake")

    removed = clear_stale_design_lock(str(board))

    assert removed is False


def test_tcl_session_is_alias_for_script_session():
    assert TclSessionManager is ScriptSessionManager
    mgr = TclSessionManager()
    session = mgr.create("allegro")
    assert isinstance(session, ScriptSession)


@pytest.mark.asyncio
async def test_run_session_supports_positional_arg_and_custom_filename(fake_exe):
    from sigrity_mcp.core.tclsession import tcl_sessions

    session = tcl_sessions.create("capture")
    tcl_sessions.add_line(session.session_id, "puts hello")

    record = await run_session(
        session.session_id,
        tool="fake_tool",
        tcl_arg_flag=None,
        build_args=["-product=OrCAD Capture"],
        script_filename="macro.tcl",
    )
    script_path = str(Path(record.job_dir) / "macro.tcl")
    assert record.command[1:] == ["-product=OrCAD Capture", script_path]


@pytest.mark.asyncio
async def test_run_session_auto_enables_dismiss_dialogs_only_for_allegro_and_capture(
    fake_exe, monkeypatch
):
    """`tool="allegro"` via run_session is ALWAYS a real `allegro.exe -s <script> <board>`
    interactive-GUI launch (every Allegro batch exe goes through submit_job directly
    under its own distinct tool name instead -- see core.tclsession.run_session's
    docstring). This locks down that run_session sets dismiss_dialogs=True for it
    automatically -- with no call site (allegro_tools.allegro_run_session,
    aurora.scope_tools, allegro_placement_tools's zrouter run, spif_specctra_tools) or
    LLM agent needing to remember to do anything. `tool="capture"` (capture_tools.py's
    capture_run_session) gets the same treatment for the same class of bug -- Capture is
    explicitly named alongside Allegro in win32gui_helper's own module docstring as a
    Cadence exe that pops modal dialogs even from the command line, and core.tool_status's
    "capture" note documents three distinct real dialogs seen on this exact install.
    Every other tool is left alone.

    Also locks down the same `tool in ("allegro", "capture")` check applying a short
    (300s) `stall_timeout_seconds` override in place of the global 2-hour default -- a
    real, repeated failure mode (ripping up and re-routing a multi-branch net) hangs
    these sessions indefinitely with the log gone silent, and the global default would
    leave that running for two hours before anything noticed.
    """
    import sigrity_mcp.core.process as process_module
    from sigrity_mcp.core.config import settings
    from sigrity_mcp.core.tclsession import tcl_sessions

    seen = {}
    real_submit_job = process_module.submit_job

    async def _spy_submit_job(*args, **kwargs):
        seen["dismiss_dialogs"] = kwargs.get("dismiss_dialogs", False)
        seen["stall_timeout_seconds"] = kwargs.get("stall_timeout_seconds")
        return await real_submit_job(*args, **kwargs)

    monkeypatch.setattr(process_module, "submit_job", _spy_submit_job)

    allegro_session = tcl_sessions.create("allegro")
    tcl_sessions.add_line(allegro_session.session_id, "skill (something)")
    await run_session(allegro_session.session_id, tool="allegro", tcl_arg_flag="-s",
                       extra_args=["board.brd"], script_filename="macro.scr")
    assert seen["dismiss_dialogs"] is True
    assert seen["stall_timeout_seconds"] == settings.allegro_session_stall_timeout_seconds

    seen.clear()
    capture_session = tcl_sessions.create("capture")
    tcl_sessions.add_line(capture_session.session_id, "Open project.opj")
    await run_session(capture_session.session_id, tool="capture", tcl_arg_flag=None,
                       build_args=["-product=OrCAD Capture"], script_filename="macro.tcl")
    assert seen["dismiss_dialogs"] is True
    assert seen["stall_timeout_seconds"] == settings.allegro_session_stall_timeout_seconds

    seen.clear()
    other_session = tcl_sessions.create("powersi")
    tcl_sessions.add_line(other_session.session_id, "puts hello")
    await run_session(other_session.session_id, tool="powersi")
    assert seen["dismiss_dialogs"] is False
    assert seen["stall_timeout_seconds"] is None
