import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, restore_tcl_session


@pytest.mark.asyncio
async def test_restore_tcl_session_reconstructs_after_simulated_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = tcl_sessions.create("powerdc")
    tcl_sessions.add_line(session.session_id, "sigrity::open document {!}")

    # Simulate a server restart by dropping this session from the shared in-memory
    # manager directly, leaving only its on-disk snapshot behind.
    tcl_sessions._sessions.pop(session.session_id)

    result = await restore_tcl_session(session.session_id)
    assert result["restored"] is True
    assert result["session_id"] == session.session_id
    assert result["tool"] == "powerdc"
    assert "sigrity::open document {!}" in result["script"]

    await close_tcl_session(session.session_id)


@pytest.mark.asyncio
async def test_restore_tcl_session_returns_error_dict_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = await restore_tcl_session("totally-made-up-id")
    assert "error" in result
