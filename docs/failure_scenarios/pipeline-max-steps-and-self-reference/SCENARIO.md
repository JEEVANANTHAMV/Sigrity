# Pipeline: 50-Step Hard Cap and No Nesting (Self-Reference Refused)

**Slug**: `pipeline-max-steps-and-self-reference`
**Tool(s) affected**: `run_tool_pipeline` itself
**Status category**: `known_blocked` (per manifest row 100)
**Pipeline stage**: platform (declarative multi-step execution)

## Symptom

`run_tool_pipeline` refuses to run when the submitted step list **exceeds 50 steps**, and it **refuses a pipeline that calls itself** (a step whose `tool` is `run_tool_pipeline`). Both are hard refusals that return an error *before* any step executes, so a caller with a long or self-referential flow cannot express it as a single pipeline and must restructure.

Two separate refusals, both in the first lines of the function:

1. **Step-count cap** — `if len(steps) > MAX_STEPS: return {"error": f"Pipeline has {len(steps)} steps, exceeding the {MAX_STEPS}-step limit."}` with `MAX_STEPS = 50`. No step runs.
2. **Self-reference / no nesting** — inside the per-step loop, `if tool_name == "run_tool_pipeline": results.append({"index": index, "tool": tool_name, "error": "pipelines cannot call themselves"})`. A step whose tool is the pipeline tool is rejected (and, with `stop_on_error=True`, halts). There is also no general sub-pipeline mechanism: `resolve` only substitutes placeholders and `client.call_tool` is called with a single tool name per step, so a "pipeline inside a pipeline" is not expressible.

## Root Cause

These are **deliberate design limits** in `pipeline_tools.py`, not bugs:

- `MAX_STEPS = 50` (pipeline_tools.py:28) is a fixed guard. The function checks `len(steps) > MAX_STEPS` at the top (line 35-36) and returns an error immediately — it does not chunk, stream, or recurse.
- The self-reference check (line 49-53) exists because `run_tool_pipeline` opens a single in-process `Client(mcp)` (line 41) and calls tools against that same server; letting a pipeline call itself would recurse into a new client/loop with shared `context`, which the design explicitly does not support ("no nesting" — SKILL.md:87).
- There is no recursion: `pipeline.py:resolve` only substitutes `${...}` placeholders; the step body (pipeline_tools.py:66-78) calls exactly one tool per step and stores its result in `context` — there is no second level of pipeline execution.

The manifest frames the *workaround* as a caller behavior ("split >50 into sequential calls"), i.e. the cap is meant to push long flows out of a single pipeline, not to be lifted.

## Evidence

- `sigrity_mcp/domains/platform/pipeline_tools.py:28` — `MAX_STEPS = 50`.
- `sigrity_mcp/domains/platform/pipeline_tools.py:35-36` — `if len(steps) > MAX_STEPS: return {"error": f"Pipeline has {len(steps)} steps, exceeding the {MAX_STEPS}-step limit."}`.
- `sigrity_mcp/domains/platform/pipeline_tools.py:49-53` — `if tool_name == "run_tool_pipeline": results.append({"index": index, "tool": tool_name, "error": "pipelines cannot call themselves"})` (+ `break` under `stop_on_error`).
- `sigrity_mcp/domains/platform/pipeline_tools.py:41-78` — a single `async with Client(mcp) as client:` loop; one `client.call_tool(tool_name, resolved_args)` per step; no recursive/nested pipeline call path.
- `sigrity_mcp/domains/platform/pipeline_tools.py:44-48` — a step missing the required `tool` key is also rejected up front (recorded as an error, halting under `stop_on_error`), a third "refuse before executing" path in the same family.
- `.forjinn/skills/sigrity/SKILL.md:87` — "Max 50 steps; no nesting." (the canonical one-line statement of both limits).
- `.forjinn/skills/sigrity/SKILL.md:69-85` — the intended use case (a 6-step PowerSI flow in one call), i.e. the pipeline is sized for *known, moderately short* sequences, not unlimited ones.

## Pipeline Impact

A flow longer than 50 steps, or one that wants to express a sub-sequence as a nested pipeline, **cannot be expressed as `run_tool_pipeline`** and is refused at submission. The caller must split the work: run multiple `run_tool_pipeline` calls back-to-back (chaining ids between them by hand / via saved values), or fall back to individual tool calls for the tail. This is a hard structural limit, so it is not intermittent — it is deterministic given the step count / self-reference.