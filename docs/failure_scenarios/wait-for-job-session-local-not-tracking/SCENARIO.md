# Scenario: wait-for-job-session-local-not-tracking

**Manifest entry:** #91 — "wait_for_job session-local; 'not tracking'"
**Status category:** `known_blocked`
**Verified workaround:** YES — fall back to `get_job_status` polling; never resubmit the job

## What goes wrong

`wait_for_job` (MCP tool, `domains/platform/job_tools.py:74-83`) delegates to
`JobManager.wait(job_id, timeout)` (`core/jobs.py:285-305`). The first thing that method does:

```python
record = self.get(job_id)
proc = self._procs.get(job_id)
if proc is None:
    if record.state == "running":
        raise JobStillRunningError(
            f"Job '{job_id}' is running in a process this server instance is not "
            "tracking (likely a previous server run) — poll status()/tail_log() instead."
        )
    return record
```

`self._procs` is the in-memory
`dict[str, asyncio.subprocess.Process]` (`core/jobs.py:99`) populated only in `submit()`
(line 150) for the duration of ONE server process's lifetime. There is no persistence, no
re-adoption of PIDs, nothing else that ever adds an entry to `_procs`. So:

- The `job_id` can be perfectly valid and the job perfectly alive — but if the `wait_for_job`
  call happens in a **different server process instance** than the one that called
  `submit()` (a restart, a client reconnecting to a freshly-spawned stdio server, a transport
  switch that respawns `main.py`), `self._procs.get(job_id)` is `None`, and (if the on-disk
  `job.json` still says `"running"`, per sibling scenario `job-state-running-lies-forever`) the
  method RAISES `JobStillRunningError` with the literal message above.
- Note the subtlety: `JobManager.wait()` catching this and *returning* a stale-but-not-running
  record is fine; the dangerous case is specifically `proc is None` **and** `record.state ==
  "running"` — which is exactly the cross-restart orphaned-job case. There is no PID liveness
  check anywhere in this path; nothing in the suite asks the OS "is `record.pid` actually still a
  running process?" — it simply refuses to wait on something it has no live handle for, and says
  so explicitly in the error text.

`JobNotFoundError` (id genuinely unknown — never submitted, or `job_dir` doesn't even exist) is a
DIFFERENT, already-handled path: `wait_for_job`'s own `try/except` (`job_tools.py:81-82`) catches
`JobNotFoundError` and returns it as a `{"error": "No job found with id '...'}` payload
(`core/jobs.py:283` raises it). `JobStillRunningError` is NOT caught there — it propagates to the
MCP client as a raised tool error. These two are easy to conflate ("job_id I don't recognize" vs.
"job_id I do recognize but this process isn't the one running it") and the suite treats them
deliberately differently: the first is a normal returned-dict error, the second is a hard raised
error that interrupts the calling tool flow.

SKILL.md documents the caller-facing resolution directly, in Rule 1: "`wait_for_job` is
session-local to the server process that launched the job — if it errors 'not tracking', fall
back to `get_job_status` polling" — and reinforces it in the Rule 1 paragraph about the MCP
client's 30s cap (sibling scenario `mcp-client-30s-roundtrip-cap`): "the `job_id` from the
original submission still works; recover with `get_job_status(job_id)` (or `list_all_jobs(state=
"running")` if you've lost track of the id) to read the real state."

## The "Do NOT resubmit" hazard, spelled out

The danger that makes this scenario a `known_blocked` caller-trap (rather than a purely harmless
"I'll just poll differently" situation) is the temptation to interpret `JobStillRunningError` as
"the job died / is gone / I should launch it again." SKILL.md Rule 1 is explicit about the
consequence of doing that, in the context of the 30s-cap sibling failure but the same "job_id
still valid while the call you made to check on it failed" pattern applies by extension: "Do not
resubmit the same job (you may now have two running against the same files)." A Sigrity batch
tool run against the same design file twice concurrently is not idempotent — it isn't a
queue-based or lock-checked launch; two `allegro.exe`/`report.exe`/PowerSI-Tcl processes opened
on the same `.brd`/`.spd` at once will contend for the design lock (see
`allegro-stale-lck-file-lock-dialog-hang` and `clear_stale_design_lock`'s docstring,
`core/tclsession.py:35-57`) or otherwise corrupt each other's run. The correct move is: the
original `job_id` is still the authoritative handle for that one launch; `get_job_status` (which
uses `JobManager.get()` → in-memory dict, else `job.json` on disk, `core/jobs.py:275-283`) does
NOT require a live `_procs` handle — it happily reads the (possibly stale, see sibling scenario)
record — so switch to `get_job_status` + `tail_job_log` + artifact checks instead of guessing
whether to relaunch.

## Evidence

- `core/jobs.py:99` — `self._procs: dict[str, asyncio.subprocess.Process] = {}`: the
  session-scoped handle table.
- `core/jobs.py:149-150` — `record.pid = proc.pid; self._procs[job_id] = proc`: populated only in
  `submit()`, only for the current `JobManager` instance's lifetime.
- `core/jobs.py:285-305` — full `JobManager.wait()` source, including the `proc is None` branch
  and the verbatim `JobStillRunningError` message ("likely a previous server run — poll
  status()/tail_log() instead").
- `core/jobs.py:26` — `from sigrity_mcp.core.errors import JobNotFoundError, JobStillRunningError`
  — two distinct, intentional error types.
- `domains/platform/job_tools.py:74-83` — `wait_for_job` only catches `JobNotFoundError`;
  `JobStillRunningError` propagates uncaught to the client.
- `.forjinn/skills/sigrity/SKILL.md`, Rule 1 (first paragraph) — verbatim: "`wait_for_job` is
  session-local to the server process that launched the job — if it errors 'not tracking', fall
  back to `get_job_status` polling (or re-issue the whole flow inside one `run_tool_pipeline`,
  where the wait always resolves)."
- `.forjinn/skills/sigrity/SKILL.md`, Rule 1 (30s-cap paragraph) — verbatim, for the
  "recover without resubmitting" pattern: "the `job_id` from the original submission still works;
  recover with `get_job_status(job_id)` (or `list_all_jobs(state="running")` if you've lost track
  of the id) to read the real state, then go back to polling/waiting normally." and "Do not
  resubmit the same job (you may now have two running against the same files)."
- Sibling scenario `job-state-running-lies-forever` — the on-disk `job.json` state that makes
  `record.state == "running"` true in the new process (no code path updates it after a restart).
