"""Generic Tcl-session inspection tools, shared by every domain that builds a macro
incrementally (PowerSI, PowerDC, XcitePI, OptimizePI, Clarity3D, XtractIM, ...).

Each of those domains has its own `start_*_session` tool (because what "opening" means
differs per tool), but once a session exists, previewing or discarding it is identical
everywhere — so that part lives here once instead of six times.
"""

from __future__ import annotations

from sigrity_mcp.core.tclsession import SessionNotFoundError, tcl_sessions
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def preview_tcl_session(session_id: str) -> dict:
    """Show the Tcl macro accumulated so far in an open automation session, without running anything.

    Use this to sanity-check the exact commands a run_*_session tool is about to execute
    before committing to a potentially long simulation — every `*_add_*`/`*_set_*` tool
    for this session_id appends one more line to what you'll see here.
    """
    try:
        session = tcl_sessions.get(session_id)
        return {
            "session_id": session_id,
            "tool": session.tool,
            "step_count": session.step_count,
            "script": session.script.render(),
        }
    except SessionNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool
async def close_tcl_session(session_id: str) -> dict:
    """Discard an open automation session without running it.

    Use this to abandon a session you started composing but decided not to run (e.g. you
    realized you need different inputs) — otherwise it just stays open, harmlessly, until
    the server restarts.
    """
    try:
        tcl_sessions.get(session_id)  # raise if unknown before reporting success
    except SessionNotFoundError as exc:
        return {"error": str(exc)}
    tcl_sessions.close(session_id)
    return {"session_id": session_id, "closed": True}


@mcp.tool
async def list_tcl_sessions() -> dict:
    """List every Tcl automation session currently open (composed but not yet run, or run but not closed) on this server."""
    sessions = tcl_sessions.list_sessions()
    return {
        "count": len(sessions),
        "sessions": [
            {"session_id": s.session_id, "tool": s.tool, "step_count": s.step_count} for s in sessions
        ],
    }
