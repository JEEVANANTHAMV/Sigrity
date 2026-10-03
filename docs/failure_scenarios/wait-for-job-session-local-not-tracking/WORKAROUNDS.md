# Workarounds: wait-for-job-session-local-not-tracking

**Verified workaround: YES** — when `wait_for_job` raises the "not tracking" error, fall back to
`get_job_status` polling and do NOT resubmit the job.

## What works (verified)

1. **On `JobStillRunningError` ("running in a process this server instance is not tracking
   (likely a previous server run) — poll status()/tail_log() instead", `core/jobs.py:288-293`),
   switch to `get_job_status(job_id)` polling instead of `wait_for_job`.** This works because
   `get_job_status` routes to `JobManager.get()` (`core/jobs.py:65-71` → `275-283`), which does
   NOT require an entry in `_procs` — it falls back to reading `job.json` off disk. Caveat (see
   sibling scenario `job-state-running-lies-forever`): for a genuinely still-running orphaned job
   from a previous server process, `get_job_status` will keep returning the stale
   `state: "running"` from `job.json` (nothing updates it in the new process) — so pair it with
   `tail_job_log(job_id)` (reads `run.log` directly off disk, `core/jobs.py:318-329`) and an
   artifact check in the input file's directory (SKILL.md Rule 3) to learn the job's ACTUAL state,
   not just the stale persisted one.
2. **If you've completely lost the `job_id`**, use `list_all_jobs(state="running")`
   (`domains/platform/job_tools.py:141-148`) — but note this is in-memory-only ("List every job
   this server instance has launched since it started"), so after a server restart it will NOT
   show the orphaned job either; this is genuinely useful only for the "I lost track of the id
   mid-session, same process" case, not the cross-restart case.
3. **Prevent the condition entirely: keep the whole submit→wait flow inside one
   `run_tool_pipeline` call, or one uninterrupted server session.** SKILL.md Rule 1: "or
   re-issue the whole flow inside one `run_tool_pipeline`, where the wait always resolves" — the
   pipeline keeps `job_id` creation and the `wait_for_job` step in ONE server-process lifetime, so
   `_procs` will always contain the handle when the wait step runs, and `JobStillRunningError`
   cannot occur for that job.
4. **Do NOT resubmit** the same job after seeing this error — SKILL.md Rule 1, verbatim: "Do not
   resubmit the same job (you may now have two running against the same files)." Recover the real
   state via `get_job_status`/`tail_job_log`/artifact check first; only start a fresh
   launch if you have positive evidence the original job actually failed/died (e.g. `tail_job_log`
   shows a crash, or the artifact never appears after a reasonable wait and `check_design_lock`
   shows no live lock/PID).

## What does NOT work / is out of scope

- No in-suite mechanism re-adopts an orphaned PID into the current `JobManager` (no
   `reattach(job_id)`/`adopt(pid)` API anywhere in `core/jobs.py` or `core/process.py`); the
  `proc is None` → `JobStillRunningError` path in `wait()` is the terminal, by-design answer
  for that case, not a bug to work around with more waiting.
- `cancel_job` on such an orphaned job is a no-op (see sibling scenario
  `cancel-cannot-kill-detached-workers`) — do not treat "I called `cancel_job` and it returned a
   record" as evidence the orphaned process is actually dead; verify at the OS level by PID if
  you truly need to kill it.
