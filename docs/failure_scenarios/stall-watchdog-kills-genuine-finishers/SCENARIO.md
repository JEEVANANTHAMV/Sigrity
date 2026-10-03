# Scenario: stall-watchdog-kills-genuine-finishers

**Manifest entry:** #94 — "Stall watchdog kills completed-but-idle jobs"
**Status category:** `known_blocked`
**Verified workaround:** YES — on `stall_timeout_killed`, verify artifacts before assuming
nothing happened

## What goes wrong

`JobManager` runs a "stall watchdog" per job (`core/jobs.py:204-231`, `stall_watchdog()` inside
`_watch()`):

```python
limit = (settings.job_stall_timeout_seconds if stall_timeout_seconds is None else stall_timeout_seconds)
if limit <= 0: return  # disabled
last_size = -1
last_change = time.monotonic()
while True:
    await asyncio.sleep(settings.stall_watchdog_poll_seconds)
    size = _safe_stat_size(log_path)
    now = time.monotonic()
    if size != last_size:
        last_size = size; last_change = now; continue
    if now - last_change >= limit:
        stall_flag["killed"] = True
        proc.kill()
        return
```

That is, its ONLY signal is "has `run.log` grown by even one byte since the last sampled
moment?" — and if the log is byte-identical for `limit` consecutive seconds in a row, it calls
`proc.kill()`. The default `limit` is `settings.job_stall_timeout_seconds = 7200`
(2 hours, `core/config.py:66`), overridable per-job via `stall_timeout_seconds` (which
`core/tclsession.py:195-197` sets to 300s specifically for `tool="allegro"`/`tool="capture"`
interactive session jobs — `ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS = 300`,
`core/tclsession.py:121`).

The failure mode this is meant to catch is real and well-documented (`core/config.py:67-98`,
verbatim intent): (1) an undismissed modal dialog with no console output, (2) a silent
FlexNet-license-fetch wait with zero console output, (3) **Celsius3D's confirmed
post-completion idle-stall** — "the process finishes real work, writes a full result set, then
simply never exits on its own (frozen CPU, idle main window, no dialog of any kind) -- a real
2.5+ hour live incident, previously only recoverable by a human finding and killing it by hand."

THE BUG IN THIS DESIGN: for case (3) — and any other job that **legitimately finishes its real
work, writes its real output files, and then just idles/never-exits** — the watchdog is
indistinguishable, from its own vantage point (log-file byte growth only), from a *genuinely
hung* job that never did any work at all. In both cases `run.log` stops growing. The difference
— "I already wrote my complete, correct output to disk somewhere else before I stopped writing
to my console log" vs. "I've been stuck and never produced anything" — is invisible to a
watchdog whose entire sensing mechanism is `run.log` size. So when the 2-hour (or 300s, for
Allegro/Capture session jobs) window elapses on a *finished-but-idle* job, `proc.kill()` fires on
a process that had ALREADY done its job correctly.

The suite is explicitly aware of this exact false-positive risk — not as an afterthought, but as
a documented, intentional trade-off, in THREE places:

1. `core/config.py:93-97` — "This must never fire on a job that is genuinely still working, only
   one that has gone truly, completely silent for the full timeout window" — i.e. the authors
   acknowledge the *only* signal is silence, not "did the intended work finish."
2. `core/jobs.py:81-90` — the `JobRecord.stall_timeout_killed` field's own docstring: "A job
   killed this way **may still have genuinely completed real work and written real output files
   before going silent** (this is exactly what happens in the Celsius3D case) — check
   `list_job_files`/output content before assuming nothing happened, don't trust state="failed"
   alone."
3. `domains/platform/job_tools.py:48-57` — the `note` text attached to any
   `_record_to_dict` output where `stall_timeout_killed` is true, surfaced to every caller of
   `get_job_status`/`wait_for_job`: "not necessarily a clean failure. Check
   list_job_files/read_job_output_file before assuming no real work happened -- a stalled job can
   still have written complete, genuine results before going silent."

So `state="failed"` + `stall_timeout_killed=True` is, by design, an **ambiguous** result: it
genuinely could be (a) a real hang the watchdog correctly caught, or (b) a fully successful
run the watchdog correctly-for-the-wrong-reason killed at the "process won't exit on its own"
tail. The suite's answer is not to try to disambiguate inside the kill decision (it can't — it
only sees log growth) but to make the *consequence* of the false-positive safe: the caller is
told, at the moment of reading the result, to go verify actual output files before treating the
kill as a "the run failed" result. That's a real mitigation, but it's entirely on the caller, and
the kill itself (wasting a process that had already succeeded, and — since `proc.kill()` is the
same immediate-PID-only mechanism, see sibling scenario `cancel-cannot-kill-detached-workers` —
no more targeted than that) has already happened by the time the caller gets to check.

## Evidence

- `core/jobs.py:204-231` — full `stall_watchdog()` source: byte-growth-only signal, `proc.kill()`
  on timeout, no post-kill artifact check, no "did work already complete" branch.
- `core/config.py:66` — `job_stall_timeout_seconds: int = 7200`; `core/config.py:67-98` — the full
  docstring naming the three intended target failure modes, including the Celsius3D
  post-completion idle-stall by name, and the explicit "measured from 'last byte written', not
  'job start'" acknowledgment of how weak the signal is for tools that legitimately write 0 bytes
  of `run.log` for their whole run (PowerSI/OptimizePI, same docstring, lines 88-91).
- `core/tclsession.py:112-121,195-197` — `ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS = 300`, applied
  specifically (and only) to `tool in ("allegro", "capture")` via the `stall_timeout_seconds`
  override — i.e. this same byte-growth-only kill logic runs on a much tighter (5-minute) window
  for GUI session jobs, making the "kill a job that was actually fine" shape of false positive
  more likely to bite precisely the class of job (interactive Allegro/Capture session, SKILL.md
  confirmed-legitimate runs of "~5-20s" per `core/tclsession.py:112-114`) whose *normal* behavior
  includes a period of zero console output between the final real work line and process exit.
- `core/jobs.py:81-90` — `stall_timeout_killed` field docstring (quoted in full above).
- `domains/platform/job_tools.py:48-57` — the caller-facing `note` (quoted in full above).
- Sibling documented real incident: `celsius3d-post-completion-idle-stall` (manifest #81) and
  `core/tool_status.py`'s `celsius3d` note (referenced by `core/config.py:81` itself) — the
  concrete, confirmed-live example of "genuine finisher" that this watchdog is built to catch,
  and therefore the concrete, confirmed-live example of what happens when a *different*
  genuinely-fine, log-silent tail of a run hits the same kill path.
- Sibling scenario `cancel-cannot-kill-detached-workers` — confirms the `proc.kill()` used here
  is the same immediate-PID-only mechanism (no process-tree kill), in case the "genuine
  finisher" being killed here had already spawned child workers before finishing.
