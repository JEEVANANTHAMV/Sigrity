# Workarounds: job-wait-second-concurrent-wait-hangs

**Status: `tool_bug_fixed`** — the underlying concurrency bug is already fixed in this codebase
(`core/jobs.py`). The remaining caller-side "workaround" is simply: don't reintroduce the failure
by calling something that would await the same subprocess a second time.

## What works (verified)

1. **Always wait via `wait_for_job(job_id, timeout_seconds=...)`** (which routes to
   `JobManager.wait()`, `core/jobs.py:285-305`) — never via any other mechanism that would await
   the underlying `asyncio.subprocess.Process.wait()` a second time. `JobManager.wait()` is
   specifically implemented to AVOID this: it polls `self._jobs[job_id].state` every 50ms
   (`core/jobs.py:302-305`) and never calls `proc.wait()` itself, so it cannot be "the second
   concurrent wait" that breaks `_watch()`'s completion notification.
2. **If `wait_for_job` returns still-`running` because the caller-side `timeout_seconds` elapsed,
   call it AGAIN** — SKILL.md Rule 1, verbatim: "If `wait_for_job` times out still `"running"`,
   call it again." Re-calling `wait_for_job` is safe (it's still just record-polling, not a new
   `proc.wait()`); what is unsafe is a second *independent* awaiter of the process object itself,
   which no exposed MCP tool performs.
3. **Chain the waiting inside `run_tool_pipeline`** when composing multi-step flows — SKILL.md:
   "PREFER pipelines when the sequence is known: they keep `session_id`/`job_id` in one server
   lifetime (where `wait_for_job` resolves) and collapse N round-trips into one call." A pipeline
   step `{"tool": "wait_for_job", "args": {"job_id": "${run.job_id}", "timeout_seconds": 180}}`
   is the canonical pattern in SKILL.md's PowerSI example.

## What does NOT work / is out of scope

- There is no MCP tool that directly exposes the raw `asyncio.subprocess.Process` to a caller, so
  this bug cannot be accidentally reintroduced *through the normal tool surface* — it was a
  code-level (in-`core/jobs.py`) bug in the old watchdog implementation, and the code itself now
  documents the fix and the reason (`core/jobs.py:184-202, 295-305`). Nothing further is required
  of the caller beyond point 1 (use `wait_for_job`), which is already `tool_bug_fixed` territory:
  the "workaround" is really just "the correct code, already merged."
- Do NOT "wait" on a job by repeatedly calling `get_job_status` in a tight external loop as a
  substitute for `wait_for_job` — it works, but it's strictly worse (no built-in deadline
  handling, more round trips) and offers no benefit; `wait_for_job` exists precisely to be the
  single correct blocking primitive.
