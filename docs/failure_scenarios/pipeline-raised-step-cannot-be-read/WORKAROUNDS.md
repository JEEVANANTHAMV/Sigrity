# Workarounds: Reading a Pipeline's Raised-Step vs Normal-Step Results Correctly

## Verified Workaround (in-suite)

**Read each step entry in a fixed order: the entry's top-level `error` first, then (only if `result` exists) `result["error"]`.** This is exactly the playbook in SKILL.md:88-93:

> "to diagnose where a pipeline stopped, read each entry's `error` then `result` individually."

Concretely, for each entry in `results`:
1. If `"error" in entry` → this step **RAISED**. It has no `result`. This is the step that (with `stop_on_error=True`) halted the pipeline. Fix the *cause* (bad/missing arg name, unknown/closed session id) — it is a real step failure, not just an in-band message.
2. Else if `"result" in entry` and `entry["result"]` is a dict containing `"error"` → the tool call **succeeded at the MCP level** but returned an in-band error object (e.g. `get_job_status`/`preview_tcl_session` on a stale id). The pipeline did *not* halt here; the next step still ran. Inspect `result` to see what the tool reported.
3. Else → a clean success; use `entry["result"]` normally.

Manifest row 98 marks this `verified_workaround: YES (read error then result per step)`.

## Why it is still "known_blocked"

There is **no code fix that changes the encoding**: a raised step genuinely cannot have a `result` (the tool never ran / threw), and a normal step genuinely returns its payload (which may itself be an error object). The distinction is *semantic* and the current `run_tool_pipeline` output **does not provide a single discriminator field** (no `ok`/`state: "raised"|"ok-with-error"`). So the "workaround" is a mandated **reading protocol**, not a change that removes the two-shape ambiguity at the source. The API shape is fixed in `pipeline_tools.py:44-78`; callers must adapt. (A cleaner shape — e.g. always emitting `{"ok": bool, "kind": "raised"|"ok", "error": ..., "result": ...}` — is not implemented and would be a source change.)

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Read `entry.get("error")` first, then `entry.get("result", {}).get("error")` | **works** — correct attribution of the halt step vs a harmless in-band error | pipeline_tools.py:44-78, 83; SKILL.md:88-93 |
| 2 | Treat any step with a top-level `error` as the halt point (with `stop_on_error=True`) | **works** — a raiser is exactly where `break` fires | pipeline_tools.py:73-74, 62-64 |
| 3 | Look only at `result["error"]` to find "the" problem step | **misleading** — misses raised steps (no `result`) and mis-flags in-band error payloads as step failures | pipeline_tools.py:76-78 |
| 4 | Look only at top-level `error` to trust the pipeline | **misleading** — an in-band `result` error that is *not* a halt is invisible to it | pipeline_tools.py:77-78 |

## Prevention

1. **Standardize all pipeline-result reading to the `error`-then-`result` order** and document it wherever `run_tool_pipeline` results are consumed (the SKILL.md playbook already does).
2. When a pipeline halts, the **first entry with a top-level `error` is the raiser** — go to its `args` (which `run_tool_pipeline` records, lines 60/71) and fix the argument, rather than assuming the pipeline failed for an environmental reason.
3. For in-band `result` errors (stale session id, "No open script session …"), **re-issue the affected step correctly** (or inside one pipeline lifetime per SKILL.md:94) rather than resubmitting a different job.
4. When writing a new tool that can fail *without* raising (returning `{"error": ...}`), be aware that inside a pipeline it will surface as a `result`-bearing, *non-failing* step — call that out in the tool doc so callers don't mistake it for a raiser.

## Remaining Gaps

The two-shape result encoding (raised ⇒ `error` only; normal ⇒ `result` possibly containing an error object) is **not disambiguated by a single field**, so any consumer that does not implement the `error`-then-`result` protocol will misread outcomes. There is no in-suite flag on a step entry indicating "raised" vs "ok-with-error-payload", and `run_tool_pipeline` does not provide a convenience "first raiser" pointer — the caller must scan `results` in order.