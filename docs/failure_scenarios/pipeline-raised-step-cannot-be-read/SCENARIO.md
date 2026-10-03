# Pipeline: A Step That RAISED Is Recorded With `error` Only, No `result` — and a Step That Returned Normally May Still Carry an `error` Payload

**Slug**: `pipeline-raised-step-cannot-be-read`
**Tool(s) affected**: `run_tool_pipeline` result reading/diagnosis (any step whose tool call raised, e.g. bad/missing arg name, unknown session id)
**Status category**: `known_blocked` (per manifest row 98)
**Pipeline stage**: platform (declarative multi-step execution — reading/diagnosing results)

## Symptom

When trying to **diagnose where a pipeline stopped**, two distinct kinds of step outcome exist and they have **different shapes**, which is easy to get wrong:

1. **A step whose tool call RAISED** (bad/missing argument name, unknown session id, an exception in the tool body, etc.) is recorded with an **`error` key and NO `result` key** at all. It counts toward `failed_count`, and with `stop_on_error=True` it **halts the pipeline**.
2. **A step that returned normally** has a **`result` key** — but that `result` may *itself* be an `{"error": ...}` payload (a *successful* MCP call that returned an error object, e.g. `get_job_status` on a stale id, or `preview_tcl_session` on a closed id). Such a step is **not** a failure of the pipeline step; it has a `result` key, no top-level `error` key.

The confusion: a naive reader looks for `result["error"]` (case 2) and misses case 1, or looks for `step["error"]` (case 1) and misses case 2. The two must be read **separately, per step**: first the step-level `error`, then the step-level `result["error"]` if `result` exists.

In practice this means: a pipeline that "stopped" may have stopped because step N *raised* (entry has `error`, no `result`) — but a *later-looking* step that returned `{"error": "No open script session ..."}` still has `result` present and is not the raiser. Reading them in the wrong order misattributes the halt.

## Root Cause

`run_tool_pipeline` builds each step's result entry in one of **two structurally different ways** (pipeline_tools.py:44-78):

- **Raised path** (line 66-75): `except Exception` → `results.append({"index": index, "tool": tool_name, "args": resolved_args, "error": str(exc)})`. **No `result` key is set.** `succeeded` is then counted as `sum(1 for r in results if "error" not in r)` (line 83), so a raised step is excluded from `succeeded_count` and counted in `failed_count`.
- **Normal path** (line 77-78): `entry = {"index": index, "tool": tool_name, "args": resolved_args, "result": payload}`. `payload` is `json.loads(call_result.content[0].text)` (line 68) — and that payload can itself be `{"error": ...}` if the tool *returned* (rather than raised) an error object.

So the **presence of an `error` key is ambiguous**: top-level `error` ⇒ raised (step failed); `result.error` ⇒ the tool ran fine and reported an in-band error. The two are **not encoded in a single field or a single `ok` flag**, so a reader must branch on key *presence*, not on a uniform field. There is no `state: "raised" | "ok-with-error-payload"` discriminator in the entry.

## Evidence

- `sigrity_mcp/domains/platform/pipeline_tools.py:66-75` — the `try/except Exception` around `client.call_tool`; on exception it appends `{"index","tool","args","error": str(exc)}` (line 70-72) with **no `result` key**, then `if stop_on_error: break` (73-74).
- `sigrity_mcp/domains/platform/pipeline_tools.py:77-78` — the normal path appends `{"index","tool","args","result": payload}`; `payload` is the parsed JSON (line 68) and may be `{"error": ...}`.
- `sigrity_mcp/domains/platform/pipeline_tools.py:83` — `succeeded = sum(1 for r in results if "error" not in r)` — success is defined purely by *absence* of a top-level `error` key.
- `.forjinn/skills/sigrity/SKILL.md:88-93` — the canonical description: "A step whose tool call RAISED (bad/missing arg name, unknown session id, …) is recorded with an `error` key and NO `result` key, counts toward `failed_count`, and with `stop_on_error=True` HALTS the pipeline. A step that returns normally has a `result` key — but `result` may itself be an `{"error": ...}` payload (e.g. `get_job_status` on a stale id), which is a *succeeded* step; inspect `result` before trusting it. So: to diagnose where a pipeline stopped, read each entry's `error` then `result` individually."
- `.forjinn/skills/sigrity/SKILL.md:21` (rule B) — a reuse of a closed session id returns `{"error": "No open script session ..."}` — i.e. an *in-band* error payload (case 2), not a raise.
- Live example of case 2 in `eval_results_summary.json` (turn 4, brd_to_powersi_signoff): `preview_tcl_session` returned `{"error":"No open script session 'powersi-session-da37289a'. It may have already been run/closed..."}` with `ok: true` — a normal step whose payload is an error object.

## Pipeline Impact

Misreading the two shapes **misattributes where a pipeline stopped** (blaming the later in-band-error step instead of the earlier raiser, or vice versa) and can cause a caller to either (a) resubmit when the real problem was a raised step (e.g. a bad arg name) that should be fixed, or (b) treat a harmless in-band error payload (stale session id) as a pipeline failure when the next step should just be re-issued correctly. Correct diagnosis requires reading **each entry's `error` first, then its `result`**.