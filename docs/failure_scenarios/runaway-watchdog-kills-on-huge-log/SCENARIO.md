# Scenario: runaway-watchdog-kills-on-huge-log

**Manifest entry:** #95 — "Runaway log > 200MB → kill"
**Status category:** `known_blocked`
**Verified workaround: NO** — guard against the underlying bad input (e.g. a nonexistent file
path); if it still happens, inspect the log for the unbounded-loop pattern

## What goes wrong

`JobManager` runs a "size watchdog" per job (`core/jobs.py:184-202`, `size_watchdog()` inside
`_watch()`):

```python
while True:
    await asyncio.sleep(settings.log_watchdog_poll_seconds)   # default 2.0s
    if _safe_stat_size(log_path) > settings.max_log_bytes:    # default 200MB
        runaway_flag["killed"] = True
        proc.kill()
        return
```

That is: if `run.log` grows past `settings.max_log_bytes` (default
`200 * 1024 * 1024` = 200MB, `core/config.py:54`), **unconditionally** call `proc.kill()` and
mark the job `state="failed"`, `runaway_log_killed=True`.

This exists for a real, documented, confirmed incident (`core/config.py`'s own `max_log_bytes`
docstring, verbatim):

> "Added after a real incident on this machine: `report.exe`/`step_out.exe`/`ipc356_out.exe`,
> given a **nonexistent board-file path**, entered an unbounded output loop instead of failing
> fast — one such job's log reached **~150GB** before being caught and killed by hand. 200MB is
> already far beyond any legitimate Sigrity/Allegro log this suite has seen in real testing."

The design is a blunt, unconditional byte-cap with NO content inspection — same shape of
"weak signal, no domain knowledge" trade-off as the stall watchdog (sibling scenario
`stall-watchdog-kills-genuine-finishers`), but inverted: too MUCH output instead of too little.
`core/config.py:55-61`'s justification for picking 200MB is explicitly "far beyond any
*legitimate* log this suite has seen in real testing" — i.e. it's a best-effort threshold chosen
against the suite's own observed distribution of real, working jobs, not a per-tool or
per-command knowledge of "what is this specific tool's legitimate maximum log size under
legitimate-but-stressful inputs."

The failure shape this scenario documents is the *false-positive* side of that threshold:
**a job whose log legitimately grows past 200MB without being in an unbounded-error-loop gets
killed exactly the same way, for exactly the same undiagnosable reason, as a genuinely runaway
job.** Nothing in the kill path inspects the log's content for the specific
"unbounded output loop" signature (the same line repeated unboundedly, an error message
re-emitted, etc.) — the decision is purely `size > 200MB`. The only content-based analysis the
suite does automatically, on ANY finished job, is `license_issue_suspected` (scanning the last
1MB of the log for license-marker strings, `core/jobs.py:268-272`) and `crash_signature`
(`core/jobs.py:343-376`, NT-status-code exit detection) — neither of which distinguishes
"genuine long-but-legitimate output" from "unbounded error loop"; and neither runs as a
*pre*-kill check (they run after `_watch()`'s `proc.wait()` returns, i.e. after the kill has
already been decided and executed, if the runaway flag was set).

The suite is explicit that this kill is a *safety net*, not a diagnosis
(`JobRecord.runaway_log_killed` docstring, `core/jobs.py:76-79`: "the tool entered an unbounded
output loop **rather than genuinely running long**" — but this is asserted, not verified, by the
kill path itself; the docstring is telling the caller what the *intended* meaning is, while the
actual code is content-blind). The caller-facing `note` on a `runaway_log_killed` result
(`domains/platform/job_tools.py:42-47`) similarly just restates the intent — "a
runaway/unbounded output loop, not a genuine long-running result -- see core.config's
max_log_bytes docstring" — without offering any in-suite mechanism to check whether, *in this
specific run*, the "unbounded loop" characterization is actually true or whether 200MB was just
the wrong threshold for this particular tool/input.

## Consequence for the caller

When you see `state: "failed"` + `runaway_log_killed: true`, the *actual* cause is ambiguous in a
way the suite cannot itself resolve: it could be (a) the exact documented incident (bad input →
unbounded output loop — e.g. a nonexistent file path, or any other input that puts that tool
into its known-bad-output behavior) or (b) a genuinely long, legitimate run whose log just grew
past the suite-wide, tool-agnostic 200MB threshold. The only way to tell them apart is to
**inspect the actual log content** — which, given the log is (by definition of this failure mode)
>200MB and potentially many GB, must itself be done carefully: `tail_job_log` already does this
safely (`core/jobs.py:45-59` `_read_tail_text` explicitly exists to never load a multi-GB file
whole, and `core/jobs.py:318-329` `tail_log()` uses it before line-splitting) — so a caller
checking "did this really look like an unbounded loop, or was it a long-but-fine log?" should
`tail_job_log(job_id, max_lines=...)` and look at the LAST lines of a file that big: an
unbounded loop's tail will show the same error/line repeating; a genuine long run's tail will
show varied, ending-looking progress.

## Evidence

- `core/jobs.py:184-202` — full `size_watchdog()` source: poll every `log_watchdog_poll_seconds`
  (2.0s), compare `_safe_stat_size(log_path)` to `settings.max_log_bytes`, kill on exceed, no
  content check, no per-tool carve-out.
- `core/config.py:54-63` — `max_log_bytes` (200MB) + `log_watchdog_poll_seconds` (2.0s) defaults,
  including the full real-incident docstring (nonexistent board-file path → `report.exe` /
  `step_out.exe` / `ipc356_out.exe` unbounded output loop → ~150GB log before manual kill).
- `core/jobs.py:76-79` — `runaway_log_killed` field docstring: asserted intent ("unbounded output
  loop rather than genuinely running long") that the kill path itself does not actually verify.
- `domains/platform/job_tools.py:42-47` — the caller-facing `note` for a `runaway_log_killed`
  result, restating the same asserted intent, with no in-suite diagnostic offered at read time.
- `core/jobs.py:45-59,318-329` — `_read_tail_text`'s existence and `tail_log()`'s use of it: the
  suite IS aware that a log past this threshold can be multi-GB-scale and provides a safe way to
  read its tail — consistent with the "inspect the tail" mitigation in the workaround doc for
  this scenario, and evidence the authors contemplated the "legitimately huge log" case even as
  the kill itself stays content-blind.
- `core/jobs.py:268-272, 343-376` — the only two automatic, content-based post-exit analyses
  (`license_issue_suspected`, `crash_signature`), both running as post-hoc labels on the
  finished record rather than as pre-kill decision inputs.
