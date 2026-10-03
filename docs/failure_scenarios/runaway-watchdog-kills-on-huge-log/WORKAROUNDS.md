# Workarounds: runaway-watchdog-kills-on-huge-log

**Verified workaround: NO** in-suite fix changes the kill decision. Confirmed caller-side
mitigations: (1) guard the *input* that triggers the known unbounded-loop failure mode in the
first place, and (2) on a `runaway_log_killed` result, `tail_job_log` the actual file to
determine whether it was a real loop or just a legitimately huge log.

## What works (verified)

1. **Prevent the documented trigger.** The ONLY confirmed, real-incident cause of an
   unbounded-output loop, per `core/config.py`'s own docstring, is a **nonexistent board-file
   path** given to `report.exe`/`step_out.exe`/`ipc356_out.exe`. The directly actionable
   prevention is: verify the input file actually exists (e.g. a `copy_file`
   (`domains/platform/file_tools.py:21-33`) into a scratch dir first, or at minimum check
   the path exists) BEFORE submitting a job against `report`/`step_out`/`ipc356_out`-family
   tools — the suite gives you `copy_file` precisely so you have a verified-good working copy
   to point the tool at, rather than passing through a possibly-stale/typos/absent source path.
   (This is also the general pattern in SKILL.md's "REAL file assets" guidance: "Copy
   read-only sources into the job scratch or a `runs/` target first ... `copy_file(src,dst,
   overwrite)` to stage.")
2. **On an actual `runaway_log_killed: true` result, inspect the log tail before deciding
   what actually happened.** `tail_job_log(job_id, max_lines=...)` is explicitly safe even for
   a multi-GB log (`core/jobs.py:45-59`'s `_read_tail_text` reads only the last N bytes, never
   the whole file — this was added for EXACTLY this "log can be hundreds of GB" incident class,
   not just the 200MB threshold). Read the returned last lines: repeated identical error text
   at the tail is the unbounded-loop signature (treat as a genuinely-bad run, go fix the input —
   usually the same nonexistent-file-path class of error the incident was about); varied,
   ending-looking progress at the tail is the "log was just legitimately over 200MB and the
   kill was a false-positive threshold miss" signature — in that case, check
   (`list_job_files` / the input file's own directory, SKILL.md Rule 3) whether the tool
   actually produced the expected output artifact before the kill; if it did, treat the run's
   *work product* as valid even though `state` says `failed` (analogous discipline to sibling
   scenario `stall-watchdog-kills-genuine-finishers`, same "check the artifact, don't trust the
   flag" principle, applied to the opposite end of the output-volume spectrum).
3. **Check the `crash` field** (surfaced by `crash_signature`, `core/jobs.py:58-60` in
   `_record_to_dict`) alongside the note — a genuine crash-shaped exit (NT status code) is a
   different animal entirely from either failure mode and is worth ruling out first, since
   `crash_signature`'s comment notes it exists "so callers can stop confusing 'the route
   finished with warnings' with 'the process crashed'" — a genuinely-crashing process that
   ALSO happened to log a lot before dying is a third, distinct shape the `runaway_log_killed`
   flag alone does not disambiguate.

## What does NOT work / is out of scope

- No in-suite mechanism inspects a log's CONTENT at kill-decision time (no "is this the same
  line repeating?" check, no per-tool "legitimate max log size" table) — the kill is
  deliberately, by design, a plain byte cap, per `core/config.py`'s own framing of it as "a
  safety net" rather than a diagnostic. There is no tool to "explain why this specific log
  exceeded the cap" beyond the caller reading it themselves (point 2).
- You cannot "raise the threshold for this one job" per-run via the public tool surface —
  `max_log_bytes` has no per-job `run_*`/`*_run_session` parameter (unlike
  `stall_timeout_seconds`, which every `submit()` call does accept, `core/jobs.py:115`); the
  only way to change it is the `SIGRITY_MAX_LOG_BYTES` env var (`core/config.py:22-23`,
  pydantic-settings env prefix `SIGRITY_`), i.e. a process-wide, server-restart-level change,
  not something an in-flow tool caller can tune for a single suspected-legitimate-long run.
- Do NOT just re-run a `runaway_log_killed` job on the assumption "maybe 200MB was a fluke
  this time" without first applying point 2 — if the tail shows a genuine unbounded loop, the
  re-run will produce another multi-GB log and get killed again, wasting the same disk-space
  and time; fix the underlying input first.
