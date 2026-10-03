# Scenario: cancel-cannot-kill-detached-workers

**Manifest entry:** #93 — "cancel_job: detached zombies survive"
**Status category:** `known_blocked`
**Verified workaround: NO** — manual OS-level PID check/kill + `clear_stale_design_lock` if it was
a GUI-session job

## What goes wrong

`JobManager.cancel(job_id)` (`core/jobs.py:307-316`):

```python
def cancel(self, job_id: str) -> JobRecord:
    record = self.get(job_id)
    proc = self._procs.get(job_id)
    if proc is not None and record.state == "running":
        proc.kill()
        record.state = "cancelled"
        record.ended_at = time.time()
        record.save()
        self._stop_dismiss_watcher(job_id)
    return record
```

Three distinct failure shapes hide in these ~10 lines:

1. **No `taskkill /T` — only the direct child's PID is killed.** `proc.kill()` on an
   `asyncio.subprocess.Process` on Windows is just `TerminateProcess` on the *immediate* child's
   PID (`record.pid`, set in `submit()` at `core/jobs.py:149`). Sigrity/Allegro batch tools are
   known to SPAWN their own subprocesses — the suite's own docs name this as a real, observed
   fact: `core/tool_status.py:769-770` documents that `SPDSIM.exe` "is designed to run only as a
   genuine child process spawned by a live PowerSI Tcl session (inheriting some
   license/IPC context...)" — i.e. some tools' documented, real execution model is "parent
   process launches child worker process(es) that do the actual work." `SPDSIM` is the canonical
   documented example, but the shape is generic: `core/process.py:submit_job` /
   `core/jobs.py:submit()` launch the top-level exe with nothing like `CREATE_NO_NEW_PROCESS_GROUP`
   awareness or any child-tree bookkeeping — there is NO code anywhere in `core/jobs.py` or
   `core/process.py` that tracks, enumerates, or kills the child *tree* (no "kill the process
   group", no `taskkill /T <pid>`, no snapshot of "PIDs descended from mine"). So when `cancel()`
   fires, only the top-level PID dies; any worker/child process the tool spawned before or during
   its run keeps running — as far as this suite is concerned, invisibly, forever (until someone
   kills it at the OS level, or it naturally exhausts whatever it was doing).

2. **`proc is None` → silent no-op.** If the calling `cancel_job` MCP call happens in a DIFFERENT
   server process lifetime than the one that called `submit()` (see sibling scenarios
   `job-state-running-lies-forever` / `wait-for-job-session-local-not-tracking` — the same
   cross-restart boundary), `self._procs.get(job_id)` is `None`, and `cancel()` falls *through*
   the `if proc is not None and record.state == "running"` block entirely and just
   `return record` — **without raising an error, without setting `state="cancelled"`, without
   logging anything the caller can distinguish from "successfully cancelled."** The `JobRecord`
   returned by `cancel_job` in this case is literally unchanged from before the call — if
   `job.json` said `state: "running"` (the stale-across-restart shape), it STILL says
   `state: "running"` after `cancel_job` "returns successfully." A caller that checks
   "did `cancel_job` throw?" or "did the returned dict say `state: cancelled`?" will conclude,
   wrongly, that the cancellation took effect. There is no distinct error type, no
   `cancelled: false` flag, nothing in the returned `_record_to_dict` output
   (`domains/platform/job_tools.py:20-61`) that says "I didn't actually hold a live handle to
   this PID, so I couldn't have killed it."

3. **`record.state` not `"running"` → also a silent no-op, same return shape.** The same `if`
   condition means a job the suite already believes is terminal (e.g. a job whose `job.json` was
   somehow already marked `failed`/`succeeded`, or even a genuinely-already-dead process whose
   `_watch()` already ran) also just falls through and returns the record unchanged
   unmodified — indistinguishable, from the caller's side, from a successful cancellation, since
   neither path raises and neither is flagged as "did nothing."

## What this means for "detached zombies"

Put together: a job that (a) spawned child worker processes, and/or (b) is being cancelled from a
different server process lifetime than its `submit()`, is exactly the case where `cancel_job` is
**most** likely to return looking successful while doing NOTHING to the actual, still-running OS
process(es). There is no in-suite facility — no tool, no log field, no returned flag — to
*verify* the OS-level process actually died. The suite's own `JobRecord` has a `pid` field
(persisted to `job.json`) — this is the only handle a caller has to confirm, at the OS level,
whether that process (let alone its children) is actually gone.

This is consistent with the manifest marking it `known_blocked` with `verified_workaround: NO`
("manual PID check + clear_stale_design_lock" is listed as the *caller's* manual escape hatch, not
as an in-suite feature), and with the `stall_timeout_killed` / `runaway_log_killed` kill paths in
`_watch()` (`core/jobs.py:184-231`) having the EXACT same shape — `size_watchdog`/`stall_watchdog`
also just call `proc.kill()` on the immediate child, not a process tree — i.e. this is not
`cancel()`-specific; it's how *every* force-kill path in this suite works, and the manifest
scenario is scoped to `cancel_job` specifically because that's the one a *caller* invokes, as
opposed to the watchdogs firing automatically.

## Evidence

- `core/jobs.py:307-316` — full `cancel()` source, including the exact `if proc is not None and
  record.state == "running":` guard and the bare `return record` that is executed (with no state
  change) when that guard is false.
- `core/jobs.py:143-150` — `submit()`: `asyncio.create_subprocess_exec(*command, ...)` with no
  process-group creation flags, `record.pid = proc.pid` — a single-PID, immediate-child-only
  tracking model.
- `core/jobs.py:184-231` — `size_watchdog()`/`stall_watchdog()`: both "only ever calls
  `proc.kill()`" — the same immediate-PID-only kill semantics, confirming this is the suite-wide
  force-kill shape, not a `cancel()`-alone quirk.
- `core/tool_status.py:769-770` — the suite's own documentation, for `SPDSIM`, that at least one
  real tool in this suite's supported set "is designed to run only as a genuine child process
  spawned by a live PowerSI Tcl session (inheriting some license/IPC context a standalone
  invocation can't)" — direct, in-repo confirmation that parent-exe-spawns-child-worker is a real,
  documented execution pattern for at least one tool this suite wraps, i.e. that "kill only the
  immediate PID" is a genuinely insufficient kill for at least some wrapped tools.
- `domains/platform/job_tools.py:131-138` — `cancel_job` MCP tool: `try: record =
  job_manager.cancel(job_id); return _record_to_dict(record)` with no additional check that a
  kill actually happened, and no distinct error path for the `proc is None` case (only
  `JobNotFoundError` is caught, for a genuinely-unknown id — a known-but-not-live-handle id
  passes right through `cancel()` unmodified).
- Sibling scenarios `job-state-running-lies-forever` (stale `job.json` `state=running` across a
  restart) and `wait-for-job-session-local-not-tracking` (the `_procs`-is-None boundary)
  establish the precondition under which `cancel()`'s silent no-op path is actually reachable in
  practice, not just theoretically.
