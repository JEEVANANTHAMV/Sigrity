"""In-memory Tcl macro sessions shared by every domain that automates a `sigrity::`-style
Sigrity tool (Clarity3D, XtractIM, PowerSI, PowerDC, ...).

Why sessions instead of one process-launch per Tcl command: Sigrity's own automation
model is "compose one script describing the whole flow, then run it once" — each
`--NoUI -tcl script.tcl` invocation is a fresh process with no state carried from a
previous invocation. If every MCP tool call (open design, add a net, set the mesh, set
the frequency sweep, run) launched its own solver process, most of those calls would do
nothing useful and be enormously slower than the real workflow. So instead, "add X" tools
just append a line to an in-memory script; a single "run" tool finally writes it out and
launches the one process that matters.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sigrity_mcp.core.errors import SigrityError
from sigrity_mcp.core.tclscript import TclScript


class SessionNotFoundError(SigrityError):
    """Raised when a session_id does not correspond to a known open Tcl session."""


@dataclass
class TclSession:
    session_id: str
    tool: str
    script: TclScript = field(default_factory=TclScript)
    step_count: int = 0


class TclSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TclSession] = {}

    def create(self, tool: str) -> TclSession:
        session_id = f"{tool}-session-{uuid.uuid4().hex[:8]}"
        session = TclSession(session_id=session_id, tool=tool)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> TclSession:
        if session_id not in self._sessions:
            raise SessionNotFoundError(
                f"No open Tcl session '{session_id}'. It may have already been run/closed, "
                "or never created — start one with the matching *_start_session tool."
            )
        return self._sessions[session_id]

    def add_line(self, session_id: str, line: str) -> TclSession:
        session = self.get(session_id)
        session.script.raw(line)
        session.step_count += 1
        return session

    def preview(self, session_id: str) -> str:
        return self.get(session_id).script.render()

    def close(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[TclSession]:
        return list(self._sessions.values())


tcl_sessions = TclSessionManager()


async def run_session(
    session_id: str,
    tool: str,
    tcl_arg_flag: str = "-tcl",
    build_args: list[str] | None = None,
    extra_args: list[str] | None = None,
    close_after: bool = True,
):
    """Write out an open session's accumulated Tcl script and launch `tool` against it as a background job.

    Thin bridge to `core.process.submit_job` kept here (rather than there) so
    `core.process` doesn't need to import session state — imported lazily to avoid a
    module-load cycle (process.py has no reason to know about sessions at import time).
    """
    from sigrity_mcp.core.process import submit_job

    session = tcl_sessions.get(session_id)
    record = await submit_job(
        tool=tool,
        build_args=build_args,
        tcl_script=session.script,
        tcl_arg_flag=tcl_arg_flag,
        extra_args=extra_args,
    )
    if close_after:
        tcl_sessions.close(session_id)
    return record
