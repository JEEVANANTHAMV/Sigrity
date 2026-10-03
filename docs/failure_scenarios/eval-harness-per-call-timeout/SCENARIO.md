# Eval Harness Per-Call Timeout Fired on a Legitimate Pipeline

**Slug**: `eval-harness-per-call-timeout`
**Tool(s) affected**: the evaluation harness itself — `scripts/eval_e2e.py` (specifically the per-tool-call `asyncio.wait_for(..., timeout=TOOL_TIMEOUT_SECONDS)` wrapper); the model endpoints under eval (qwen3-max via the two vLLM nodes)
**Status category**: `tool_bug_fixed` (per manifest row 105) — the *harness* bug, fixed in the harness, not a Sigrity tool bug
**Pipeline stage**: eval / multi-model end-to-end harness (outside the live Sigrity job path, but it gates how the suite's tools are judged)

## Symptom

In the **first** end-to-end evaluation run, the harness's own **90-second per-call timeout** was firing on legitimate multi-step `run_tool_pipeline` calls (and long-running jobs like a real Celsius3D solve) that were *not* actually failing. The model was doing the right thing — submitting a correct 6-step PowerSI pipeline, or waiting on a genuine ~10-minute Celsius3D run — but the harness cut the call off at 90 s and recorded a tool-call **error**. Result: **4 of 6 task+endpoint combinations failed to reach a final answer**, with the "error" being the harness's timeout, not a tool defect.

The concrete live symptom in the saved run (`eval_results_summary.json`, `thermal_celsius3d_signoff`): the model called `wait_for_job(job_id, timeout_seconds=<large>)`, and the harness wrapped that in `asyncio.wait_for(..., timeout=TOOL_TIMEOUT_SECONDS)`. When the legitimate wait exceeded the harness cap, the harness produced:

```
"error": "TimeoutError", "result_preview": "{\"error\": \"TimeoutError\"}"
```

with `ok: false` — a **false error** on a call that would have succeeded if allowed to run. The model then correctly fell back to `get_job_status`/`tail_job_log` and continued (see the turns below it in that run).

## Root Cause

The harness has a **single flat per-call timeout** applied to *every* tool call: `TOOL_TIMEOUT_SECONDS = 180` in the current file, but the bug was that it was **90 s** in the first run (README:875 "the harness's own 90s per-call timeout was firing"). The wrapper is in `scripts/eval_e2e.py`:

```python
call_result = await asyncio.wait_for(
    client.call_tool(name, args), timeout=TOOL_TIMEOUT_SECONDS
)
```

A **legitimate** `run_tool_pipeline` (or `wait_for_job` on a real multi-minute solve) can take far longer than 90 s, so `asyncio.wait_for` raises `asyncio.TimeoutError`, which the harness caught and recorded as a tool error. Two compounding problems:

1. **The cap was too short** for real Sigrity operations (pipeline calls bundle 5-6 tool rounds + a job wait that can run minutes).
2. **The timeout was indistinguishable from a real tool error** at a glance — `str(asyncio.TimeoutError())` is empty, so the recorded `error` text was just the bare type name (or nothing useful). This is what later motivated type-tagging the error.

## Evidence

- `scripts/eval_e2e.py:39` — `TOOL_TIMEOUT_SECONDS = 180` (the **current, fixed** value; the bug was the prior 90 s value noted in README:875).
- `scripts/eval_e2e.py:129-140` — the per-call wrapper: `call_result = await asyncio.wait_for(client.call_tool(name, args), timeout=TOOL_TIMEOUT_SECONDS)` inside `try/except Exception`; on exception, `error_text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__` and `payload = json.dumps({"error": error_text}); call_record["ok"] = False; call_record["error"] = error_text`. **This block is the fix for the "indistinguishable from a real error" half**: the comment (lines 134-136) explicitly says `str(exc)` is empty for e.g. `asyncio.TimeoutError` and that the type is forced in "so a timeout is distinguishable from a real tool error at a glance."
- `eval_results_summary.json` — live evidence of the symptom in `thermal_celsius3d_signoff`: `wait_for_job` calls with `timeout_seconds` 180/300/600 all return `"ok": false, "error": "TimeoutError"` while `get_job_status` right after them shows the Celsius3D job still genuinely `state:"running"` (pid 18284, `returncode":null`) — i.e. a real long solve, not a tool defect.
- `README.md:873-881` — "First run (prior pass): 4 of 6 task+endpoint combinations failed to reach a final answer within 14 turns, with one silent tool-call error. Both root causes were in the eval harness/task prompts, not the tools: the harness's own 90s per-call timeout was firing on a legitimate multi-step `run_tool_pipeline` call... After raising the timeout, making timeout errors self-identifying, fixing the prompts, and tightening the system prompt: **6/6 succeeded**."
- `README.md:903` (this pass table) — `thermal_celsius3d_signoff` shows `3 errors` per endpoint, which are the harness `TimeoutError` on the genuine ~10-min Celsius3D wait (see the `TimeoutError` rows in the summary), *not* real tool failures — the models still reached correct final answers.

## Pipeline Impact

While the 90 s cap was active, the eval **falsely scored correct model/tool behavior as failed** (4/6 in run one), and even in the fixed run the 3 per-endpoint `timeout_celsius` `TimeoutError`s are *artifact* errors, not tool regressions — they reflect that a legitimate multi-minute job outgrew the per-call wrapper. Any harness/CI that reuses a **flat, short per-call timeout on a model that legitimately blocks on a long pipeline** will over-report failures. The current 180 s + type-tagged error is the mitigation; very long jobs can still outgrow even 180 s per-call (as the Celsius3D `wait_for_job(timeout_seconds=300/600)` rows show the model raising the *tool's* own timeout to compensate).