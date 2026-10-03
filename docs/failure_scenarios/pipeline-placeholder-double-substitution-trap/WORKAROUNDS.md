# Workarounds: Pipeline `${...}` Placeholder Double-Substitution

## Verified Workaround (in-suite)

**Reference a saved step's value as a *whole placeholder*, not inline — and never pass a produced value that contains `${...}` through as a string that a later step will re-walk.** This is the documented, live-verified pattern in the SKILL.md example:

- Use `"session_id": "${s.session_id}"` (a value that is **entirely** one placeholder, `^\$\{path\}$`), which `resolve` returns *as-is* with its original type (pipeline.py:40-42). This keeps the value opaque to any later string re-walk — a whole-placeholder that resolves to a plain string id is safe as long as that string does not itself contain `${`.
- Do **not** embed a value that may contain `${...}` into a larger template string (`"job-${x.out}-final"`), because `_INLINE.sub` (pipeline.py:44) will re-parse any `${...}` inside the produced content. Build those composed strings *after* the pipeline (post-step), not inside it.

Manifest row 97 marks this `verified_workaround: YES (whole-placeholder refs, not inline)`.

## What makes it "blocked" / not a real in-suite fix

There is **no escape/quote syntax** in the substitution grammar (pipeline.py:14-15) and **no "already-resolved" marker** on `context` values (pipeline_tools.py:38,80-81). So there is no way, *inside `run_tool_pipeline` alone*, to safely round-trip a produced value that genuinely contains a literal `${...}` and have a later step consume it verbatim. The only reliable avoidance is to **not create the situation**: keep placeholder payloads `${...}`-free at the source, or do the string composition outside the pipeline. That is a caller discipline, not a code fix, which is why the manifest keeps it `known_blocked`.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Whole-placeholder reference (`"${name.field}"`) for every forwarded value | **works** — the value passes through whole, typed, and is not re-walked as a bigger string | pipeline.py:40-42; SKILL.md:74-85 (live 6-step PowerSI pipeline) |
| 2 | Inline-embedding a produced value into a template string (`"…$${x.y}…"`) | **unsafe** — any `${...}` inside the produced string is re-substituted in place, corrupting the arg or raising `unresolved placeholder` | pipeline.py:36-44 (`_INLINE.sub`) |
| 3 | Adding an escape/quote token to the grammar | **not implemented** (would require source change; out of scope) | pipeline.py:14-15 (no escape path) |
| 4 | Compose the post-step string *after* `run_tool_pipeline` returns (outside the substitution engine) | **works** — avoids feeding `${...}` back into `resolve` entirely | inference from pipeline.py single-pass design |

## Prevention

1. **Audit each `save_as` payload for `${` before reusing it in a later step.** If the producing tool returns any string containing `${...}` (command lines, generated Tcl/SKILL, echoed logs), do not reference it by placeholder in a later step.
2. **Keep placeholders whole-value, never inline**, for any field you forward. The inline form (`"…${x.y}…"`) is only safe when the *produced* value cannot contain `${`.
3. **Move template-string composition outside the pipeline.** `run_tool_pipeline` is for *threading ids*, not for building strings that the produced data will flow into.
4. When the pipeline halts with `error: "unresolved placeholder: '${…}'"` (pipeline_tools.py:60), treat it as the **first symptom** of a produced value leaking a `${...}` — read the earlier step's `result` to find the offending value.

## Remaining Gaps

No in-suite escape/quote mechanism or idempotency guard exists. A genuinely `${...}`-containing produced value cannot be safely threaded through `run_tool_pipeline` for a later step to consume verbatim. The workaround is purely caller discipline (whole references + compose outside), not a code change, so the risk persists for any caller who embeds produced data inline.