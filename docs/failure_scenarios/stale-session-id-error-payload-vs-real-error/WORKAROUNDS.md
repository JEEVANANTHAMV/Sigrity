# Workarounds: stale-session-id-error-payload-vs-real-error

**Verified workaround: YES** — inspect `result['error']` on every pipeline step, not just the
step-level `error` key; don't trust a "succeeded" step unconditionally.

## What works (verified)

1. **Diagnose pipeline stalls step-by-step, reading BOTH keys.** SKILL.md's own recipe:
   "to diagnose where a pipeline stopped, read each entry's `error` then `result` individually."
   Concretely: for each step in `run_tool_pipeline`'s output, if it has an `error` key the tool
   call raised (pipeline halts under `stop_on_error=True`). If it has a `result` key, still check
   whether `result` *itself* starts with `{"error": ...}` — that is the stale-session / stale-job
   signature and it does NOT count toward `failed_count`.

2. **Re-issue the compose→run flow instead of retrying with the old id.** Since a consumed
   `session_id` cannot be resurrected (no persistence — see sibling scenario
   `session-per-process-no-persistence`), the fix is a fresh `start_*_session` + re-queue all lines
   + `*_run_session`, ideally inside a single `run_tool_pipeline` so the whole lifecycle stays in
   one server-process lifetime (SKILL.md: "PREFER pipelines when the sequence is known").

3. **Prevent the failure at the source: never thread a `session_id` across more tool calls than
   the model (or pipeline) can keep in one continuous lifetime.** The SKILL.md Model B section and
   pipeline section exist precisely to avoid manual `session_id` threading across turns.

## What was tried / doesn't work

- There is no in-suite API to distinguish *why* a `session_id` is stale ("already run/closed" vs.
  "never created" — the `SessionNotFoundError` message in `core/tclsession.py:84-88` deliberately
  doesn't) and no API to recover a closed session. Confirmed by reading `core/tclsession.py` and
  `domains/platform/session_tools.py` in full: `_sessions` is a plain `dict`, `close()` is a bare
  `pop`, and `list_tcl_sessions` only reflects the current live process. Stays `known_blocked`;
  the only confirmed mitigation is caller-side (points 1–3 above).
- `list_tcl_sessions` (in `session_tools.py`) is a useful *check* before assuming an id is stale:
  if it doesn't appear there (and it's not one you just created seconds ago in the same process),
  it's either closed or from a different/restarted server — don't send it to another `*_set_*`
  call, you just get the same `{"error": ...}` payload back.
