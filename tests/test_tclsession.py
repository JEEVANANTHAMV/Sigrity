import sys
from pathlib import Path

import pytest

from sigrity_mcp.core.errors import JobNotFoundError
from sigrity_mcp.core.tclsession import (
    ScriptSession,
    ScriptSessionManager,
    TclSessionManager,
    SessionNotFoundError,
    run_session,
)
from sigrity_mcp.core.jobs import JobManager


def test_create_and_get_session():
    mgr = TclSessionManager()
    session = mgr.create("powersi")
    assert session.session_id.startswith("powersi-session-")
    assert mgr.get(session.session_id) is session


def test_unknown_session_raises():
    mgr = TclSessionManager()
    with pytest.raises(SessionNotFoundError):
        mgr.get("does-not-exist")


def test_add_line_accumulates_and_previews():
    mgr = TclSessionManager()
    session = mgr.create("powerdc")
    mgr.add_line(session.session_id, "sigrity::open document {!}")
    mgr.add_line(session.session_id, "sigrity::save -w {test.pdcx} {!}")
    text = mgr.preview(session.session_id)
    assert "sigrity::open document {!}" in text
    assert "sigrity::save -w {test.pdcx} {!}" in text
    assert mgr.get(session.session_id).step_count == 2


def test_close_removes_session():
    mgr = TclSessionManager()
    session = mgr.create("xcitepi")
    mgr.close(session.session_id)
    with pytest.raises(SessionNotFoundError):
        mgr.get(session.session_id)


def test_list_sessions():
    mgr = TclSessionManager()
    a = mgr.create("powersi")
    b = mgr.create("powerdc")
    ids = {s.session_id for s in mgr.list_sessions()}
    assert ids == {a.session_id, b.session_id}


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
