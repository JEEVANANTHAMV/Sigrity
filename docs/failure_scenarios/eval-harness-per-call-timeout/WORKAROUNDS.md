# Workarounds: Eval Harness Per-Call Timeout

## Verified Fix (in-harness — `tool_bug_fixed`)

Both halves of the bug are **fixed in the harness**, and the fixes are in `scripts/eval_e2e.py`:

1. **Raise the per-call timeout to 180 s.** `TOOL_TIMEOUT_SECONDS = 180` (eval_e2e.py:39). This covers the legitimate multi-step `run_tool_pipeline` calls and most single tool round-trips. README:875→881 confirms raising it (among the four fixes) took the first run from **4/6 → 6/6**.
2. **Make timeout errors self-identifying (type-tagged).** The `except` block (eval_e2e.py:133-140) now records `error_text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__`, and the comment (lines 134-136) states the intent verbatim: `str(exc)` is empty for `asyncio.TimeoutError`, so the type is forced in "so a timeout is distinguishable from a real tool error at a glance." A harness timeout now reads `TimeoutError: ...` (or bare `TimeoutError`) rather than masquerading as a blank/mysterious tool error.

Together these are the manifest's `verified_workaround: YES (TOOL_TIMEOUT=180s; type-tagged errors)`.

## What this does / doesn't fix

- **Does fix**: the *false failures* on legitimate pipelines (run-one 4/6 → 6/6) and the *diagnostic ambiguity* (can't tell a timeout from a real error).
- **Does not fix**: a genuinely multi-minute job can still exceed even the per-call wrapper. See the live `thermal_celsius3d_signoff` rows: the model passes the *tool's own* `timeout_seconds` of 180/300/600 to `wait_for_job`, and the harness still records `TimeoutError` when the ~10-min solve exceeds the per-call cap. The models worked around this by **re-calling** `wait_for_job` with a larger `timeout_seconds` and cross-checking `get_job_status`/`tail_job_log` — and still reached correct final answers. So very long jobs are handled by the model's retry/poll discipline, with a few *harmless* artifact-timeout rows remaining in the report.

## Workarounds / mitigations (with outcomes)

| # | Change | Outcome | Evidence |
|---|--------|---------|----------|
| 1 | `TOOL_TIMEOUT_SECONDS = 90` (original) | **false failures** on legitimate pipelines — run-one 4/6 | README:873-875 |
| 2 | `TOOL_TIMEOUT_SECONDS = 180` (now) | **eliminates the run-one false failures** — 6/6, 12/12 this pass | eval_e2e.py:39; README:881, :892-894 |
| 3 | Bare `str(exc)` capture (original) | **ambiguous** — empty for `asyncio.TimeoutError`, indistinguishable from a real error | eval_e2e.py:134-136 (comment describes the old failure) |
| 4 | Type-tagged error `f"{type.__name__}: {exc}"` (now) | **timeout is visible at a glance** | eval_e2e.py:137-138 |
| 5 | (model-side) re-call `wait_for_job` with a larger `timeout_seconds`, cross-check `get_job_status` | **handles the few remaining >180 s single-call jobs** (e.g. Celsius3D ~10 min) without a wrong final answer | eval_results_summary.json `thermal_celsius3d_signoff` turns; README:903, 908-919 |

## Prevention

1. **Size the per-call timeout to the real p99 of the slowest legitimate tool the eval runs** (a `run_tool_pipeline` bundling a job wait can be minutes). 180 s is the current floor; if the eval adds longer tasks (real CFD/EM solves), raise it or make it task-aware.
2. **Always type-tag harness exceptions** so `asyncio.TimeoutError` (empty `str`) is distinguishable from a genuine tool exception — never record a bare `str(exc)` that may be empty.
3. **Count harness timeouts separately from tool errors in the report.** A `TimeoutError` on a job that `get_job_status` later shows as still-running/succeeded is a *harness artifact*, not a tool regression — keep the metric honest (the 3 `thermal_celsius3d_signoff` errors are this kind).
4. **Encourage the model to poll, not just wait once**: `wait_for_job` + `get_job_status`/`tail_job_log` recovery, already baked into the system prompt (eval_e2e.py:171-172, "pass a generously long timeout_seconds to wait_for_job").

## Remaining Gaps

Even at 180 s, a flat per-call cap can still out-run a single-call wait on a genuinely long job (e.g. the ~10-min Celsius3D signoff), leaving a small number of **artifact** `TimeoutError` rows in the report (3 per endpoint in the celsius3d task, README:903). The clean fix for those is a per-task or poll-based timeout (or making the wrapped call non-blocking), which the current harness does not do — it still uses one flat `asyncio.wait_for` per call. The false-failure class is fixed; the "long job vs flat cap" class is mitigated by model retry discipline, not eliminated.