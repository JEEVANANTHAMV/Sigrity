# Workarounds: 50-Step Cap and No Nesting

## Verified Workaround (in-suite)

**Split the sequence into multiple back-to-back `run_tool_pipeline` calls (or individual tool calls), chained by carrying ids out of one call and into the next.** Manifest row 100 marks this `verified_workaround: YES (split >50 into sequential calls)`. The pattern:

- Run pipeline A for steps 1..N (each ≤ 50), `save_as`-ing the ids you need at the end.
- Read the returned `results` (each succeeded step has a `result` key; see sibling `pipeline-raised-step-cannot-be-read` for how to read it correctly).
- Seed pipeline B (or a single tool call) with those carried values — now they are literal values, not `${...}` placeholders, so there is no re-substitution concern.

This keeps the benefit the pipeline is meant to provide — **one server lifetime, where `wait_for_job` resolves** (SKILL.md:94) — while staying under the 50-step cap. For nesting, the only supported decomposition is **sequential pipelines / sequential tool calls**, never a pipeline-inside-a-pipeline.

## Why there is no deeper fix (no in-suite change)

- **The 50-step cap is a deliberate, fixed guard** (`MAX_STEPS = 50`, pipeline_tools.py:28,35-36). It is not configurable and not chunked. Lifting/parameterizing it would be a source change; the intended mitigation is caller-side splitting.
- **No nesting / self-reference is a deliberate design boundary** (pipeline_tools.py:49-53; SKILL.md:87 "no nesting"). The single `async with Client(mcp)` loop (line 41) calls one tool per step and has no recursive path. Adding nested pipelines would require a new execution model (sub-client, nested `context`), which is not implemented.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Split a >50-step flow into sequential `run_tool_pipeline` calls, carrying ids between them | **works** — each call is ≤50 steps; values are literal (no `${…}`) across the boundary | pipeline_tools.py:28,35-36,80-81; SKILL.md:87,94 |
| 2 | Submit a single >50-step pipeline | **refused before executing** — returns the step-limit error, zero steps run | pipeline_tools.py:35-36 |
| 3 | Include a `run_tool_pipeline` step to nest | **refused** — step recorded with `error: "pipelines cannot call themselves"`; halts under `stop_on_error` | pipeline_tools.py:49-53 |
| 4 | Omit a step's `tool` key to "skip" it | **refused** — recorded as an error ("step is missing the required 'tool' key"); it does not silently no-op | pipeline_tools.py:44-48 |

## Prevention

1. **Count steps before calling.** If a planned flow is near 50, pre-split it at a natural boundary (a job is awaited, a new session opens, a file is staged) and chain the pipelines with carried literal values.
2. **Treat "no nesting" as absolute.** If a flow feels like it needs a sub-pipeline, restructure into a sequential pipeline / tool call instead; do not submit a `run_tool_pipeline` step.
3. **Carry values as literals across pipeline boundaries** (read `result` from the previous call, pass the concrete value in) — this simultaneously respects the no-nesting rule and avoids the placeholder re-substitution trap (see `pipeline-placeholder-double-substitution-trap`).
4. Keep every step's `tool` name present and exact — a missing key is another pre-execution refusal, not a no-op.

## Remaining Gaps

There is **no chunking/continuation, no configurable cap, and no nested/sub-pipeline mechanism** in `run_tool_pipeline`. A >50-step or self-referential flow has no single-call expression; the only in-suite path is caller-side sequential splitting. This is a structural constraint (not a defect to "fix"), but it means very long or hierarchical flows must be engineered out of one pipeline by hand.