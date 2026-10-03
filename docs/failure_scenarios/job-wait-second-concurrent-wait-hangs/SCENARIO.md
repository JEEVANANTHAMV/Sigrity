# Scenario: job-wait-second-concurrent-wait-hangs

**Manifest entry:** #90 — "2nd concurrent wait → Windows Proactor bug"
**Status category:** `tool_bug_fixed`
**Verified workaround:** YES — route all waiting through `wait_for_job` (never a second raw
`proc.wait()` on the same subprocess)

## What goes wrong (root cause, now fixed in code)

`JobManager` launches every job with a dedicated `_watch()` task per job
(`core/jobs.py:158`, started in `submit()`): `asyncio.create_task(self._watch(job_id, proc,
log_file, ...))`. `_watch()`'s completion logic is a single, bare
`returncode = await proc.wait()` (`core/jobs.py:235`) — this is deliberately the SOLE caller of
`proc.wait()` for that process.

The earlier implementation of the log-size watchdog (`size_watchdog` inside the same `_watch()`)
itself co-owned the completion signal: it wrapped `proc.wait()` in a reusable `asyncio.Task` and
polled it via `asyncio.wait(..., timeout=...)`. The in-code comment documents the two
reproducible, confirmed-live consequences of that design on **this machine's Windows/Proactor
event loop** (`core/jobs.py:184-196`:

> "An earlier version had this watchdog itself co-own the completion signal (wrapping
> `proc.wait()` in a reusable Task, polled via `asyncio.wait(..., timeout=...)`), which
> reproducibly caused two distinct real problems on this machine's (Windows/Proactor) event loop:
> every single job took a full extra `log_watchdog_poll_seconds` to be detected as complete
> (185 tests x ~2s each turned an ~12s test suite into 5+ minutes), and it was still
> intermittently unreliable (a job occasionally never got marked complete at all). Keeping this
> watchdog fully separate from the one proven-reliable completion path below (a bare, single
> `await proc.wait()`) avoids both."

The general, confirmed principle this encodes (restated in `JobManager.wait()`'s own comment,
`core/jobs.py:295-301`):

> "`_watch()` (started once per job in `submit()`) is the sole owner of `proc.wait()` for a given
> process — confirmed via direct testing that a second concurrent caller awaiting the same asyncio
> subprocess's `.wait()` (even via `asyncio.wait_for`) causes `_watch`'s own completion
> notification to never fire on this machine's (Windows/Proactor) event loop, leaving the job
> stuck reporting 'running' forever even after the real process has exited."

So the failure shape is: **any second concurrent awaiter of the SAME asyncio subprocess's
`wait()` breaks the first awaiter's (the canonical `_watch()`'s) completion notification** — the
OS knows the process exited, but the JobManager's `_watch` task never wakes, never writes the
terminal `state`/`returncode` to the `JobRecord`, and `get_job_status` keeps reporting
`running` forever for that job (a real-process-exited-but-state-stuck shape, distinct from the
across-restart `job-state-running-lies-forever` scenario, which is about the server process dying,
not about two coroutines racing on one `proc.wait()`).

The current, fixed design in `core/jobs.py`:
- `size_watchdog()` and `stall_watchdog()` are "fully independent" — "never touches `proc.wait()`
  itself, only `proc.kill()` if the log grows too large" / "Same 'fully independent, only ever
  calls proc.kill(), never touches proc.wait()' shape" (`core/jobs.py:184-231`).
- `JobManager.wait()` (`core/jobs.py:295-305`) does NOT call `proc.wait()` at all, for exactly
  this reason — it polls its OWN `JobRecord.state` in a tight loop instead:
  `while self._jobs[job_id].state == "running" and time.monotonic() < deadline:
  await asyncio.sleep(0.05)` — i.e. it waits for the *record* to be updated by the
  sole-`proc.wait()`-owner (`_watch`), rather than independently awaiting the process.

## Evidence

- `core/jobs.py:158` — `asyncio.create_task(self._watch(job_id, proc, log_file, stall_timeout_seconds))`: one `_watch` task per job, created at submit time.
- `core/jobs.py:235` — `returncode = await proc.wait()`: the single authoritative completion site.
- `core/jobs.py:184-196` — full in-code history of the buggy double-`proc.wait()` design and the two observed failure modes on Windows/Proactor (extra-poll-delay completion detection + intermittent never-completes), including the concrete regression measurement ("185 tests x ~2s ... ~12s test suite into 5+ minutes").
- `core/jobs.py:295-301` — `JobManager.wait()`'s docstring/comment restating the confirmed general rule (a second concurrent `.wait()` caller on the same asyncio subprocess breaks `_watch`'s completion notification on this machine's event loop) and the chosen fix (poll the record, don't call `proc.wait()`).
- `core/jobs.py:302-305` — the actual polling implementation (`asyncio.sleep(0.05)` loop over `self._jobs[job_id].state`), which is what `wait_for_job` (`domains/platform/job_tools.py:74-83`, `await job_manager.wait(job_id, timeout=timeout_seconds)`) relies on.
- Manifest status is `tool_bug_fixed` — matching the "now fixed in code" framing above: the fix is the current single-owner `proc.wait()` + record-polling design, not merely a caller-side avoidance.
