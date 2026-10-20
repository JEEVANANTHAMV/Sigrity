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

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sigrity_mcp.core.config import settings
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
    (previously misdiagnosed as a startup hang or generic timeout, since a
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
    # Accumulated SKILL defun sources for tools whose call is too large to ride a bare
    # `.scr` line. Allegro 22.1's `-s` command-replay parser (lineread) corrupts any
    # `skill <expr>` line whose form has more than one top-level whitespace-separated
    # token (it keeps only the first; e.g. `skill (axlCNSSetSpacing nil nil 'line_line
    # 5)` re-parses with the space before the symbol dropped -> "not a function" / silent
    # no-op; confirmed live 2026-10-18, see allegro_constraint_tools.py's docstring).
    # The documented error-proof pattern (SKILL Language Reference `load`/`lineread`
    # sections + Cadence's own dp_rep.il) is: put the multi-arg call in a `.il`, `load`
    # it, call a single-token function. `run_session` writes these to <board dir>/auto_il.il
    # and emits `skill (load "...")` + `skill <func>` per call.
    il_lines: list[str] = field(default_factory=list)
    il_func_names: list[str] = field(default_factory=list)


# Backward-compat alias: every Sigrity-domain module imports this name specifically
# (`from sigrity_mcp.core.tclsession import TclSession`) — keep it working unchanged.
TclSession = ScriptSession


def _session_snapshot_path(session_id: str) -> Path:
    return settings.resolve_workdir() / "sessions" / f"{session_id}.json"


class ScriptSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ScriptSession] = {}
        # Ids this server instance has itself closed (via run_session's close_after or an
        # explicit close()), so get()'s error can distinguish "you consumed this one
        # yourself" from "this id was never created / the server restarted" — the exact
        # ambiguity a caller otherwise has no way to tell apart from a bare
        # SessionNotFoundError. Capped so a long-lived server doesn't grow this
        # unboundedly; losing the oldest entries only degrades the message back to the
        # generic case, it never breaks correctness.
        self._closed: dict[str, float] = {}
        self._closed_cap = 1000

    def create(self, tool: str) -> ScriptSession:
        session_id = f"{tool}-session-{uuid.uuid4().hex[:8]}"
        session = ScriptSession(session_id=session_id, tool=tool)
        self._sessions[session_id] = session
        self._snapshot(session)
        return session

    def get(self, session_id: str) -> ScriptSession:
        if session_id not in self._sessions:
            if session_id in self._closed:
                raise SessionNotFoundError(
                    f"Script session '{session_id}' was already run/closed in this server "
                    "process — it is single-use. Start a NEW session with the matching "
                    "*_start_session tool and re-queue the script lines (or do the whole "
                    "flow in one run_tool_pipeline)."
                )
            raise SessionNotFoundError(
                f"No open script session '{session_id}' was ever created in this server "
                "process — check the id for a typo, or the server may have restarted "
                "(try restore_tcl_session if the session was created before a restart)."
            )
        return self._sessions[session_id]

    def add_line(self, session_id: str, line: str) -> ScriptSession:
        session = self.get(session_id)
        session.script.raw(line)
        session.step_count += 1
        self._snapshot(session)
        return session

    def add_il(self, session_id: str, source: str, func_name: str) -> ScriptSession:
        """Queue a multi-arg SKILL call to run via a loaded `.il` file (see
        `ScriptSession.il_lines` for why a bare `.scr` line cannot carry it). `source`
        is a complete SKILL `defun NAME () ...` body; `func_name` is the symbol it
        defines. `run_session` writes all queued sources to one `.il` and emits the
        documented `load` + single-token-call sequence for each, in queue order."""
        session = self.get(session_id)
        session.il_lines.append(source)
        session.il_func_names.append(func_name)
        self._snapshot(session)
        return session

    def preview(self, session_id: str) -> str:
        return self.get(session_id).script.render()

    def close(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._closed[session_id] = time.time()
        if len(self._closed) > self._closed_cap:
            oldest = sorted(self._closed, key=self._closed.get)[: len(self._closed) - self._closed_cap]
            for sid in oldest:
                del self._closed[sid]
        try:
            _session_snapshot_path(session_id).unlink(missing_ok=True)
        except OSError:
            pass

    def list_sessions(self) -> list[ScriptSession]:
        return list(self._sessions.values())

    def _snapshot(self, session: ScriptSession) -> None:
        """Persist this session's accumulated script to disk so `restore()` can
        reconstruct it after a server restart. Best-effort: a write failure here must
        never break the in-memory flow that's this manager's actual job — sessions
        already work fine without persistence, this only adds a recovery path."""
        try:
            path = _session_snapshot_path(session.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "session_id": session.session_id,
                        "tool": session.tool,
                        "step_count": session.step_count,
                        "lines": list(session.script._lines),
                        "il_lines": list(session.il_lines),
                        "il_func_names": list(session.il_func_names),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def restore(self, session_id: str) -> ScriptSession:
        """Reconstruct a session from its on-disk snapshot (written by every `create()`/
        `add_line()` call) when it's not in this server instance's memory — the normal
        case being a server restart between a `*_start_session` call and the matching
        `run_session`. Raises `SessionNotFoundError` (same type as `get()`) if no
        snapshot exists either; the composed script itself is NOT recoverable if this
        server instance never saw it (sessions are queued client-side call by call, so
        a session an earlier server process never received cannot be reconstructed from
        nothing)."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        path = _session_snapshot_path(session_id)
        if not path.is_file():
            raise SessionNotFoundError(
                f"No open script session '{session_id}' and no on-disk snapshot to restore "
                "— it was never created in any server process, or its snapshot was already "
                "cleaned up by a close()."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        session = ScriptSession(
            session_id=data["session_id"],
            tool=data["tool"],
            step_count=data["step_count"],
            il_lines=list(data.get("il_lines", [])),
            il_func_names=list(data.get("il_func_names", [])),
        )
        for line in data["lines"]:
            session.script.raw(line)
        self._sessions[session_id] = session
        return session


# Backward-compat alias, same reasoning as TclSession above.
TclSessionManager = ScriptSessionManager

tcl_sessions = ScriptSessionManager()


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

    `tool in ("allegro", "apd", "capture")` always launches as `dismiss_dialogs=True` --
    every `run_session` caller that passes `tool="allegro"` is a real
    `allegro.exe -s <script> <board>` launch (confirmed by grep across the domain modules:
    every other Allegro-family batch exe -- report.exe, batch_drc.exe,
    designextractor.exe, ... -- goes through `core.process.submit_job` directly under its
    own distinct tool name, not through a script session at all), and this is CONFIRMED
    LIVE to be able to raise a modal startup dialog with nothing present to click it -- see
    `core.win32gui_helper.DismissWatcher`'s docstring for the live repro evidence.
    `tool="apd"` is the same class of launch (the `apd.exe` launcher stub spawns
    `allegro.exe -product <APD tier> -nograph ...`; even with `-nograph`, a one-time
    Product Choices or similar modal can still appear on an unexpected state), so it is
    covered by the same watcher. Setting this here, once, means every current and future
    `allegro`/`apd` call site (`allegro_tools.allegro_run_session`, `aurora/scope_tools.py`'s
    in-design-analysis workflow, `apd_package_tools`'s zrouter/apd-batch/apr runs,
    `spif_specctra_tools`'s SPECCTRA import) gets the fix automatically, with nothing for
    any of those call sites (or the LLM agent calling them) to remember to do.

    The same `tool in ("allegro", "apd", "capture")` check also applies
    `settings.allegro_session_stall_timeout_seconds` (300s by default) in place of the
    global 2-hour stall watchdog default -- a real, repeatable failure mode (ripping up
    and re-routing a
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
    this exact install (a 'Product Choices' product-chooser, a 'Capture Custom
    Launch' crash-recovery prompt, and a stale-.lck-file 'already open/locked, override?'
    prompt). This is ALSO where `tool="capture"` gets `ENABLE_CAPTURE_AUTOMATION=TRUE`
    injected into its process environment (via `submit_job`'s `extra_env` -- see
    `JobManager.submit`'s docstring for the full root-cause writeup): confirmed live to
    be the actual fix for what was previously misdiagnosed purely as an `Open`-step
    hang -- Capture's embedded Start Page widget makes a *synchronous* network call at
    startup that this env var skips entirely, closing off an unanswerable native "Proxy
    Server Credential" dialog that otherwise blocks the whole process forever (zero log,
    zero visible windows of its own, ~100% CPU on one core) on any machine whose system
    proxy demands authentication. What this does NOT yet fix: making a *supplied Tcl
    script* actually execute unattended once Capture is open. Multiple invocation forms
    were tried live and confirmed NOT to work (`Capture.exe script.tcl` and
    `Capture.exe -product=... script.tcl` both just open an idle interactive 'Capture>'
    console in the Command Window without ever sourcing the file; piping the script via
    redirected stdin does nothing because that console is a GUI widget, not a real
    process stdin reader; a per-user `capinit.tcl` at the documented
    `%HOME%\\cdssetup\\capture\\capinit.tcl` path, and at the launch CWD, both went
    unloaded). So `capture_run_session`'s batch invocation remains `known_blocked` for
    genuine unattended schematic EDITING -- see `core.tool_status.TOOL_STATUS_NOTES
    ["capture"]` for the full evidence trail, the real `Capture.Application` COM
    automation interface found as a promising next lead (`OpenDesign`/`Save`/`Close`/
    `Exit` all confirmed callable), and `capture_headless_tools.py` for a working,
    Capture.exe-free alternative for the specific case of extracting a netlist from an
    EXISTING `.dsn` (not authoring a new one).

    If `session_id` is not in this server instance's memory but has an on-disk snapshot
    (written by every `*_start_session`/`add_*` call — see `ScriptSessionManager._snapshot`),
    it is transparently restored before raising `SessionNotFoundError` — the common
    "server restarted between composing the macro and running it" case becomes
    self-healing with zero caller changes, instead of losing the whole queued script.

    Thin bridge to `core.process.submit_job` kept here (rather than there) so
    `core.process` doesn't need to import session state — imported lazily to avoid a
    module-load cycle (process.py has no reason to know about sessions at import time).
    """
    from sigrity_mcp.core.process import submit_job

    try:
        session = tcl_sessions.get(session_id)
    except SessionNotFoundError:
        session = tcl_sessions.restore(session_id)
    record = await submit_job(
        tool=tool,
        build_args=build_args,
        tcl_script=session.script,
        tcl_arg_flag=tcl_arg_flag,
        extra_args=extra_args,
        script_filename=script_filename,
        dismiss_dialogs=(tool in ("allegro", "apd", "capture")),
        stall_timeout_seconds=(
            settings.allegro_session_stall_timeout_seconds if tool in ("allegro", "apd", "capture") else None
        ),
        extra_env=({"ENABLE_CAPTURE_AUTOMATION": "TRUE"} if tool == "capture" else None),
    )
    if close_after:
        tcl_sessions.close(session_id)
    return record
