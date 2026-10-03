"""In-memory macro sessions shared by every domain that automates a scriptable Cadence
tool — originally just Sigrity's `sigrity::`-style Tcl (Clarity3D, XtractIM, PowerSI,
PowerDC, ...), now also OrCAD Capture's own (differently-flavored) Tcl and Allegro PCB
Editor's SKILL. Despite the historical name, `TclSession`/`ScriptSession` has nothing
Tcl-specific in its mechanics — it's just a uuid, a step counter, and a list of raw text
lines — so the same class serves any of these languages; only the *content* of the lines
(and the quoting helper used to build them: `core.tclscript` for Tcl, `core.skillscript`
for SKILL) differs per tool.

Why sessions instead of one process-launch per command: Sigrity's own automation model
is "compose one script describing the whole flow, then run it once" — each
`--NoUI -tcl script.tcl` invocation is a fresh process with no state carried from a
previous invocation, and the same is true of Capture's and Allegro's batch/script-replay
modes. If every MCP tool call (open design, add a net, set the mesh, place a part, run)
launched its own process, most of those calls would do nothing useful and be enormously
slower than the real workflow. So instead, "add X" tools just append a line to an
in-memory script; a single "run" tool finally writes it out and launches the one process
that matters.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sigrity_mcp.core.errors import SigrityError
from sigrity_mcp.core.tclscript import TclScript


class SessionNotFoundError(SigrityError):
    """Raised when a session_id does not correspond to a known open script session."""


def clear_stale_design_lock(design_path: str) -> bool:
    """Remove a stale `<design_path>.lck` sibling file, if one exists, before opening a design.

    ROOT CAUSE FIX for a real, reproducible failure mode caught live: Allegro/Capture
    both write a `.lck` file next to a design while it's open; if the process that
    created it is killed (a hung batch job, a forcibly-terminated session — this
    happens routinely with headless automation, unlike normal interactive use) rather
    than exiting cleanly, that `.lck` file is orphaned. The NEXT batch launch against
    that same design path then hits a real modal "this design appears to be open/
    locked, override?" dialog — which blocks forever with no console output at all
    (previously misdiagnosed as a license-fetch hang or generic timeout, since a
    headless batch job has no way to click through it). Since every caller here always
    owns a private, already-copied working file (never a design another live process
    could legitimately still have open), removing a stale lock before launch is safe
    and prevents the dialog outright rather than requiring a human to click past it.
    Returns True if a lock file was found and removed (worth logging/surfacing to the
    caller), False if there was nothing to clean up.
    """
    lock_path = Path(f"{design_path}.lck")
    if lock_path.is_file():
        lock_path.unlink()
        return True
    return False


@dataclass
class ScriptSession:
    session_id: str
    tool: str
    script: TclScript = field(default_factory=TclScript)
    step_count: int = 0


# Backward-compat alias: every Sigrity-domain module imports this name specifically
# (`from sigrity_mcp.core.tclsession import TclSession`) — keep it working unchanged.
TclSession = ScriptSession


class ScriptSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ScriptSession] = {}

    def create(self, tool: str) -> ScriptSession:
        session_id = f"{tool}-session-{uuid.uuid4().hex[:8]}"
        session = ScriptSession(session_id=session_id, tool=tool)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ScriptSession:
        if session_id not in self._sessions:
            raise SessionNotFoundError(
                f"No open script session '{session_id}'. It may have already been run/closed, "
                "or never created — start one with the matching *_start_session tool."
            )
        return self._sessions[session_id]

    def add_line(self, session_id: str, line: str) -> ScriptSession:
        session = self.get(session_id)
        session.script.raw(line)
        session.step_count += 1
        return session

    def preview(self, session_id: str) -> str:
        return self.get(session_id).script.render()

    def close(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[ScriptSession]:
        return list(self._sessions.values())


# Backward-compat alias, same reasoning as TclSession above.
TclSessionManager = ScriptSessionManager

tcl_sessions = ScriptSessionManager()

# Interactive Allegro/Capture GUI session jobs normally complete in ~5-20s (confirmed
# live: axlDBCreateNet ~5.6s, load+query+exit ~20s; even the most complex documented
# stackup/routing session finished in ~1-3 minutes). The global `job_stall_timeout_seconds`
# default (2 hours) is tuned for long batch simulations (XcitePI, PowerSI, PowerDC) and is
# far too long for this class of job: a real, repeatedly-confirmed failure mode (ripping
# up and re-routing a multi-branch/multi-pin net) hangs the session indefinitely with the
# log gone completely silent, and nothing catches it for two hours. 300s gives every
# documented legitimate session several times its normal runtime margin while still
# surfacing this specific hang in minutes instead of hours.
ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS = 300


async def run_session(
    session_id: str,
    tool: str,
    tcl_arg_flag: str | None = "-tcl",
    build_args: list[str] | None = None,
    extra_args: list[str] | None = None,
    close_after: bool = True,
    script_filename: str = "macro.tcl",
):
    """Write out an open session's accumulated script and launch `tool` against it as a background job.

    `tcl_arg_flag=None` and a non-default `script_filename` exist for non-Tcl-flag tools
    like OrCAD Capture (bare positional script path, still a `.tcl` file) and Allegro
    (SKILL command-replay via `-s`, written as `.scr`) — see `core.process.submit_job`'s
    docstring for the exact semantics.

    `tool in ("allegro", "capture")` always launches as `dismiss_dialogs=True` -- every
    `run_session` caller that passes `tool="allegro"` is a real
    `allegro.exe -s <script> <board>` interactive-GUI launch (confirmed by grep across
    the domain modules: every other Allegro-family batch exe -- report.exe,
    batch_drc.exe, designextractor.exe, ... -- goes through `core.process.submit_job`
    directly under its own distinct tool name, not through a script session at all), and
    this is CONFIRMED LIVE to be able to raise a modal startup dialog with nothing
    present to click it -- see `core.win32gui_helper.DismissWatcher`'s docstring for the
    live repro evidence. Setting this here, once, means every current and future
    `tool="allegro"` call site (`allegro_tools.allegro_run_session`,
    `aurora.scope_tools`'s in-design-analysis workflow, `allegro_placement_tools`'s
    zrouter run, `spif_specctra_tools`'s SPECCTRA import) gets the fix automatically,
    with nothing for any of those call sites (or the LLM agent calling them) to remember
    to do.

    The same `tool in ("allegro", "capture")` check also applies
    `ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS` (300s) in place of the global 2-hour stall
    watchdog default -- a real, repeatable failure mode (ripping up and re-routing a
    multi-branch/multi-pin net) hangs these sessions indefinitely with the log gone
    completely silent, and the 2-hour default would leave that running for hours before
    anything noticed. No working chat-level fix for the hang itself was found (per-branch
    rip-up, shorter-timeout polling, and per-object delete-and-recreate were all tried and
    still hit the same hang); this at least bounds the damage and reports it clearly
    (`stall_timeout_killed=True` on the job record) instead of relying on a caller to
    notice zero log growth on their own.

    `capture_run_session` (`tool="capture"`) gets the same treatment for the same class
    of bug: `win32gui_helper`'s own module docstring explicitly names orCAD Capture
    alongside Allegro as a Cadence exe that "initialise[s] a Qt or classic-Win32 GUI even
    when driven from the command line, and block[s] on a modal dialog" -- and
    `core.tool_status`'s "capture" note documents three distinct real dialogs seen on
    this exact install (a 'Product Choices' license-tier chooser, a 'Capture Custom
    Launch' crash-recovery prompt, and a stale-.lck-file 'already open/locked, override?'
    prompt). Capture's batch invocation is separately still `known_blocked` for an
    unrelated reason (the `Open <project>` step itself hangs with zero windows at all,
    which DismissWatcher correctly can't help with -- see capture_tools.py's module
    docstring), so this does not make `capture_run_session` reliable end-to-end, but it
    closes the same dialog-hang gap for it that Allegro already has, at zero cost (a
    dialog-watching thread that finds nothing to click is a harmless no-op).

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
        script_filename=script_filename,
        dismiss_dialogs=(tool in ("allegro", "capture")),
        stall_timeout_seconds=(
            ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS if tool in ("allegro", "capture") else None
        ),
    )
    if close_after:
        tcl_sessions.close(session_id)
    return record
