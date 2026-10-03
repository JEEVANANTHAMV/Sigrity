# Pipeline `${...}` Placeholder Double-Substitution Trap

**Slug**: `pipeline-placeholder-double-substitution-trap`
**Tool(s) affected**: `run_tool_pipeline` (any step args), and the substitution engine `sigrity_mcp/core/pipeline.py` (`resolve`, `_lookup`)
**Status category**: `known_blocked` (per manifest row 97)
**Pipeline stage**: platform (declarative multi-step execution)

## Symptom

When a step's saved result **already contains a literal `${...}` sequence** in one of its string values, and a *later* step references that value, the placeholder text is **re-substituted a second time** against the current pipeline `context`. The result is either a wrong value or a hard `unresolved placeholder` error, *and in practice* the step then hangs or silently produces the wrong call.

Two distinct re-substitution mechanisms both live in `pipeline.py` and are real:

1. **Inline stringification of a *whole* referenced value**: `resolve` (pipeline.py:39-45) resolves a *whole* placeholder (`^\$\{path\}$`) to the raw looked-up value (pipeline.py:40-42), but it only does that for the *string being resolved now*. When a later step embeds a value that itself was **stored** as a string containing `${...}` (because the producing tool returned that literal), that inner `${...}` is treated as a new placeholder.
2. **Inline embedding**: a placeholder embedded in a larger string (`"job-${job.job_id}-final"`, pipeline.py:36-37) is substituted **in place** with `_INLINE.sub(...)` (pipeline.py:44). If a *stored* value is a big string that happens to contain `${...}`-shaped text, it will be parsed out and overwritten on the next `resolve` pass.

In other words: **the substitution is not idempotent.** A value that was correct when first written to `context` can be silently rewritten by a subsequent `resolve(...)` pass over a step that references it (directly or as part of a larger string). This is exactly the "double-substitution trap": the same `${...}` token is evaluated more than once, the second time against a different (later) context, producing a corrupted argument.

The practical, observed consequence recorded for this scenario is a **~20-minute silent hang with no clean error** (see sibling scenario `pipeline-argument-name-traps-silent-hang`): rather than failing loudly, a mangled/corrupted arg causes the launched tool to wait for interactive input that never comes.

## Root Cause

`resolve` is a **single recursive pass per step** (pipeline.py:32-50) — it does not distinguish between (a) the *caller's intended* `${name.field}` reference and (b) **data that happens to contain `${...}`** as literal content. There is no escape/quote mechanism in the substitution grammar (`_WHOLE` / `_INLINE` regexes, pipeline.py:14-15), so any string value that contains a `${` sequence is indistinguishable from a placeholder and is always re-parsed. The `context` dict (`pipeline_tools.py:38,80-81`) holds the *raw produced payload* and re-resolves it from scratch on every later step, so a value is re-substituted each time it flows into a later arg.

`pipeline_tools.py` resolves `resolved_args = resolve(raw_args, context)` (line 57) **per step**, against the same shared `context`. Because the stored `context[name]` value is the *already-resolved/produced* payload, and later `resolve` calls re-walk strings including any embedded `${...}`, a value that contained a literal `${...}` gets a second evaluation. There is no "already resolved, do not re-walk" marker on context values.

## Evidence

- `sigrity_mcp/core/pipeline.py:14-15` — the two regexes: `_WHOLE = re.compile(r"^\$\{([\w.]+)\}$")` and `_INLINE = re.compile(r"\$\{([\w.]+)\}")`. No escape syntax exists.
- `sigrity_mcp/core/pipeline.py:32-45` — `resolve`: a whole-placeholder resolves to the raw looked-up value (`return _lookup(context, whole.group(1))`, lines 40-42); a value with `${` anywhere is rewritten in place via `_INLINE.sub(lambda m: str(_lookup(...)), value)` (line 44). `_lookup` (lines 22-29) raises `PlaceholderError` on any missing key.
- `sigrity_mcp/domains/platform/pipeline_tools.py:56-64` — per-step `resolved_args = resolve(raw_args, context)`; on `PlaceholderError` the step is recorded with `error: "unresolved placeholder: '${...}'"` (line 60) and, with `stop_on_error=True`, HALTS (lines 62-64). So the *loud* failure mode (unresolved placeholder) is real and is the first signal of the trap.
- `.forjinn/skills/sigrity/SKILL.md:87-88` — "Rules: `save_as` stores a step's result so later steps read `${name.field}` (typed) or embed it in a bigger string." — documents the intended use; the trap is the un-escaped opposite case.
- `.forjinn/skills/sigrity/SKILL.md:74-85` — the verified example uses **whole-placeholder** references (`"${s.session_id}"`, `"${run.job_id}"`), which is the safe form (see WORKAROUNDS).
- Sibling: `docs/failure_scenarios/pipeline-argument-name-traps-silent-hang/SCENARIO.md` — the same "silent ~20 min hang" symptom class, the other face of malformed pipeline step args.

## Pipeline Impact

Any pipeline in which **an earlier tool's produced string value contains literal `${...}`** (a generated command line, a path, a Tcl/SKILL snippet, a log excerpt echoed back, etc.) and a later step reads that value is at risk of **silent corruption** (wrong arg → tool hangs waiting on interactive input) or a **hard `unresolved placeholder` halt**. The danger is worse than a normal bug because the *producing* step looks fine (it has a `result` key) and the corruption only becomes visible one or more steps later as a hang or a failed call, making the root cause hard to trace.