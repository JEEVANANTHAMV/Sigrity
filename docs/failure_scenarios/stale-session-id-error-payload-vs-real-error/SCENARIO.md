# Scenario: stale-session-id-error-payload-vs-real-error

**Manifest entry:** #87 — "Stale session → error payload, not raised"
**Status category:** `known_blocked`
**Verified workaround:** YES — inspect every step's `result['error']`, not just its `error` key

## What goes wrong

A stale (already run or closed) `session_id` does NOT produce a clean, distinct, easily-grep-able
raised error in the way a missing argument does. The two distinct failure shapes:

1. **Direct tool call** (`*_set_*`/`*_add_*`/`preview_tcl_session` etc. with a dead id): the
   domain tool catches `SessionNotFoundError` and returns a **dictionary payload**
   `{"error": "No open script session "<id>". It may have already been run/closed, or never
   created — start one with the matching *_start_session tool."}` (`core/tclsession.py:84-88` is
   the raise site; platform tools like `session_tools.py:27-28,36-38` catch it and return the
   dict). The caller (an LLM) must read and interpret that payload — there is no crash, no
   non-zero exit, nothing the harness flags.

   The error text deliberately does NOT tell you which of the two causes it is: "It may have
   already been run/closed, **or** never created" — a genuinely-typo'd id and a legitimately
   already-consumed id produce the *identical* message, so the caller cannot distinguish "I'll
   retry after re-running" from "this id was valid and the session was simply consumed" without
   remembering the flow.

2. **Inside `run_tool_pipeline`:** a step whose tool call **raised** is recorded with an `error`
   key and **no** `result` key, counts toward `failed_count`, and with `stop_on_error=True` halts
   the pipeline (SKILL.md, pipeline rules). BUT a step that returns **normally** still carries the
   stale-session failure — because these tools *return* `{"error": ...}` rather than raising — so
   that step is recorded as a *succeeded* step whose `result` is `{"error": "No open script
   session ..."}`. SKILL.md states this explicitly:

   > "a step that returns normally has a `result` key — but `result` may itself be an `{"error":
   > ...}` payload (e.g. `get_job_status` on a stale id), which is a *succeeded* step; inspect
   > `result` before trusting it. So: to diagnose where a pipeline stopped, read each entry's
   > `error` then `result` individually."

   So the *real* failure of a stale session can be hidden in a step that `run_tool_pipeline`
   reports as not-failed (it is a successful tool call that returned an error-shaped dict), while a
   superficially-identical-looking raised step (e.g. a different validation error that does raise)
   halts the pipeline loudly. Two different underlying causes (a consumed session id vs. a bad
   argument name) look completely different in the pipeline's output: one is a silent in-`result`
   dict, the other is an `error`-key step that stops the run.

Why it's `known_blocked`: the suite deliberately chose *return-an-error-dict* semantics for
`SessionNotFoundError` (so a single bad id doesn't 500 the MCP transport), and there is no
in-suite mechanism that distinguishes "closed" from "never existed", or that re-hydrates a session
(see `session-per-process-no-persistence`). No confirmed fix; the documented mitigation is purely
caller-side discipline.

## Evidence

- `core/tclsession.py:31-34,83-88` — `SessionNotFoundError` raised by `get()`; the message text
  covers both closed and never-created causes indistinguishably.
- `core/tclsession.py:100-101,199-200` — `close()` on `run` (`close_after=True` default) is what
  most commonly makes an id stale; after that the id is dead for this server process.
- `domains/platform/session_tools.py:21-28,34-38,44-52` — `preview_tcl_session` and
  `close_tcl_session` both `except SessionNotFoundError as exc: return {"error": str(exc)}` —
  returned, not raised, to the MCP client.
- `.forjinn/skills/sigrity/SKILL.md` (pipeline rules paragraph) — verbatim distinction between a
  step that RAISED (`error` key, no `result` key, halts with `stop_on_error=True`) and a step that
  returned normally but with `result == {"error": ...}` ("e.g. `get_job_status` on a stale id",
  which is a *succeeded* step); and the diagnosis recipe "read each entry's `error` then `result`
  individually".
- `.forjinn/skills/sigrity/SKILL.md` (Model B paragraph) — "reuse of a closed id →
  `{"error": "No open script session ..."}`" — confirming the payload-shaped (not raised) semantics
  for the direct-call path as well.
- `domains/platform/job_tools.py:65-71,75-83` — the same *return-not-raise* pattern for
  `JobNotFoundError` in `get_job_status`/`wait_for_job` (the SKILL.md pipeline note's "e.g.
  `get_job_status` on a stale id" is this exact code path: `try: ... except JobNotFoundError as
  exc: return {"error": str(exc)}`).
