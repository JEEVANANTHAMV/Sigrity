# Workarounds: session-per-process-no-persistence

**Verified workaround: YES** — keep the whole compose→run chain inside a single server lifetime,
ideally inside one `run_tool_pipeline` call.

## What works (verified)

1. **Do the whole session lifecycle in one `run_tool_pipeline` call.** This is the documented
   preferred pattern (SKILL.md, "The one-call shortcut" + SKILL.md Rule 1 guidance: "re-issue the
   whole flow inside one `run_tool_pipeline`, where the wait always resolves"). A pipeline step
   list like:

   ```
   run_tool_pipeline(stop_on_error=True, steps=[
     {"tool": "start_powersi_session", "args": {"spd_file": "<PATH>"}, "save_as": "s"},
     {"tool": "powersi_run_session", "args": {"session_id": "${s.session_id}"}},
   ])
   ```

   keeps `session_id` creation, all `*_set_*`/`*_add_*` queueing, and the `*_run_session` launch
   inside ONE server process lifetime — the session is guaranteed to still be in
   `ScriptSessionManager._sessions` when `run_session` calls `tcl_sessions.get(session_id)` and
   immediately closes it. SKILL.md: "PREFER pipelines when the sequence is known: they keep
   `session_id`/`job_id` in one server lifetime (where `wait_for_job` resolves) and collapse N
   round-trips into one call."

2. **If not using a pipeline: complete all `start_*` → `*_set_*` → `*_run_session` calls
   back-to-back without letting the server restart in between, and never rely on a `session_id`
   from an earlier session/conversation.** Treat any session id as valid only within the current
   server process. `get_job_status`/`list_all_jobs` (and `list_tcl_sessions`) reflect the current
   server process only ("this server instance ... since it started" per `job_tools.py:143-144`).

## What does NOT work / no confirmed fix

- There is **no in-suite mechanism to recover an open session after a server restart**: no
  `session.json`, no dump/reload of the accumulated script, no `restore_session` tool
  (`core/tclsession.py` has no persistence code path at all; `list_tcl_sessions` in
  `session_tools.py` reads only the live in-memory dict). This stays a `known_blocked` structural
  property, matching the manifest: no confirmed in-suite fix.
- Reusing a `session_id` after its `*_run_session` (or an explicit `close_tcl_session`) fails with
  `SessionNotFoundError` by design — the only options are to start a NEW session and re-queue all
  lines, or to do it in a pipeline as above.

## Practical rule

- Never hold a `session_id` longer than the current tool-calling turn group. If a long task spans
  multiple user turns and the server may restart in between, re-issue the full compose→run chain
  (fresh `start_*_session`) rather than reusing the old id.
