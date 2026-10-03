# Scenario: session-per-process-no-persistence

**Manifest entry:** #86 — "Sessions in-memory; lost on restart"
**Status category:** `known_blocked`
**Verified workaround:** YES — chain the whole compose→run flow in one server/pipeline lifetime

## What goes wrong

Model B (the session model, see parent SKILL.md) works like this: `start_<x>_session(...)` returns a
`session_id`; a series of `<x>_set_*` / `<x>_add_*` / `<x>_create_*` calls each take that
`session_id` and queue exactly one line of Tcl/SKILL — nothing executes, no process launches; then
one `<x>_run_session(session_id, ...)` writes the accumulated macro to disk and launches a single
background process.

The entire composed-but-unrun session lives in the `ScriptSessionManager`'s
`self._sessions: dict[str, ScriptSession]` — a plain in-memory dict
(`sigrity_mcp/core/tclsession.py:74-81`). There is no serialization, no disk snapshot, no recovery
path. `tcl_sessions` is a module-level singleton (`core/tclsession.py:110`) that lives exactly for
the lifetime of the MCP server process.

Consequence: if the server process restarts (crash, user restart, transport switch, or simply a
different server instance the client now talks to), **every open `session_id` is gone**. A `get()`
on such an id raises `SessionNotFoundError`:

> "No open script session '<id>'. It may have already been run/closed, or never created — start
> one with the matching *_start_session tool." (`core/tclsession.py:84-88`)

The accumulated script is discarded with it — lines that had been queued are never written to
`macro.tcl` because the run tool was never called, and even if it had been called, the *new*
process cannot see the old session's lines. This mirrors the deeper Cadence constraint documented
in the `tclsession.py` module docstring: each batch invocation (`--NoUI -tcl script.tcl`,
`allegro.exe -s`) is a fresh process with no state carried from a previous invocation — so there is
no alternative Cadence-side object that could host the composition across two server lives; the
only place the composition exists anywhere is that in-memory dict.

Additionally: `*_run_session` calls `tcl_sessions.close(session_id)` by default
(`close_after=True`, `core/tclsession.py:199-200`), so session ids are single-use even within one
server lifetime — reusing a run/closed id gives the same `SessionNotFoundError`, which the SKILL.md
summarizes: "reuse of a closed id → `{"error": "No open script session ..."}`".

Note the asymmetry with jobs: `JobManager.get()` *can* recover a finished job from its
`job.json` on disk (`core/jobs.py:275-283`), but sessions have no equivalent — there is no
`session.json` and no recovery path.

## Evidence

- `core/tclsession.py:73-81` — `ScriptSessionManager.__init__` holds `self._sessions: dict[str, ScriptSession] = {}`; module-level singleton at line 110.
- `core/tclsession.py:83-88` — `get()` raises `SessionNotFoundError` for any id not in the dict, for either cause (run/closed or never-created) — the message deliberately does not distinguish them.
- `core/tclsession.py:100-101` — `close()` is a bare `pop`; no state persisted before or after the run.
- `core/tclsession.py:199-200` — `run_session(..., close_after=True)` closes the session right after `submit_job` returns the record.
- `core/tclsession.py:10-18` (module docstring) — the Cadence-side reason: every batch tool invocation is a stateless fresh process; the in-memory session is the only carrier of the composed script.
- `.forjinn/skills/sigrity/SKILL.md`, Model B paragraph — "The session auto-closes; reuse of a closed id → `{"error": "No open script session ..."}`".
- `domains/platform/session_tools.py` — `preview_tcl_session`/`close_tcl_session`/`list_tcl_sessions` all read the same in-memory dict; `list_tcl_sessions` can only ever show sessions open in the *current* server process ("currently open ... on this server").
- Contrast: `core/jobs.py:9-11` (module docstring) — "Job state lives both in memory (for the life of this server process) and as a small `job.json` file ... so `status()` still works after a server restart for jobs that already finished" — sessions get no such dual storage.
