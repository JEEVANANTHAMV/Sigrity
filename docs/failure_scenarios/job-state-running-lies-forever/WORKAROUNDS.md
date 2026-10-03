# Workarounds: job-state-running-lies-forever

**Verified workaround: NO** in-suite fix changes the stale `state` itself. Confirmed mitigation is
to stop trusting the state field for cross-restart jobs and check artifacts/logs directly.

## What works (verified)

1. **When you see `state: "running"` on a job you're already suspicious about (submitted before a
   server restart, or stuck far past its normal runtime), check the actual log and files on disk
   instead of polling `get_job_status`/`wait_for_job`:**
   - `tail_job_log(job_id, max_lines=200)` — reads `run.log` off disk
     (`core/jobs.py:318-329`), which works whether or not the job is in the current server's
     memory; a genuinely finished process wrote its final lines there.
   - `list_job_files(job_id)` + `list`/check the *input file's own directory* for a new, non-empty
     artifact newer than the job started (SKILL.md Rule 3: "list the *input file's* directory ...
     for a new non-empty artifact newer than the job start — that is the real success check").
   - SKILL.md Rule 2, directly: "The log file is the only source of truth: `tail_job_log(job_id)`
     for the real completion/error line, and confirm a real non-empty artifact."
2. **If `wait_for_job` raises `JobStillRunningError`** ("running in a process this server instance
   is not tracking (likely a previous server run) — poll status()/tail_log() instead",
   `core/jobs.py:288-293`), take it at face value: this is the suite telling you it has no handle
   on that PID. Do NOT call `wait_for_job` again expecting it to resolve — apply point 1 instead.
3. **Check for an orphaned design lock** if the job was an Allegro/Capture session job:
   `check_design_lock(design_path)` (`domains/platform/file_tools.py:67-71`) — a job that was
   killed/died abnormally leaves `<design>.lck` behind, which is a separate (but related)
   "looks like it's still running" signal; `clear_stale_design_lock`
   (`core/tclsession.py:35-57`) is the paired fix before relaunching.

## What does NOT work / is out of scope

- Nothing in this suite re-adopts an orphaned PID, re-parents the running child, or rewrites a
  stale `job.json`'s `state` to its true post-crash value. `JobManager.get()`'s disk fallback
  (`core/jobs.py:278-282`) is read-only; no code path in `core/jobs.py` or `core/process.py`
  checks "is `record.pid` still a live OS process" and updates state accordingly. This is why the
  manifest lists this as `known_blocked` with `verified_workaround: NO` (the "artifact check"
  listed in the manifest INDEX is the caller-side mitigation above, not a state-field fix).
- Do NOT just `cancel_job(job_id)` on a stale-`running` job to "clear it": `cancel()`
  (`core/jobs.py:307-316`) does `self._procs.get(job_id)` → `None` post-restart → skips the
  `proc.kill()` entirely and returns the record unchanged — it does NOT touch the orphaned process
  (and it also does NOT rewrite `state` when there's no live handle). A truly-orphaned process can
  only be killed at the OS level (Task Manager / `taskkill` by the PID in the stale `job.json`),
  which is outside this suite — see sibling scenario `cancel-cannot-kill-detached-workers`.

## Practical rule

- Treat any `state: "running"` that survives a server restart (or a `wait_for_job` that raises
  `JobStillRunningError`) as **uninformative** — immediately fall back to `tail_job_log` +
  artifact check per SKILL.md Rule 2/3, and check for `.lck` orphans for GUI-session tools.
