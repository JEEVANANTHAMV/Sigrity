# capture-succeeded-but-empty-log-fast-exit

Capture's batch run reports `state: "succeeded"` in ~0.1s with a completely empty `run.log` — far too fast for a real open+script+close+exit cycle. The job "succeeded" but no real work happened. status_category: `silent_noop`.

## What went wrong

Of the 3 clean re-test runs recorded in `core/tool_status.py`'s `capture` note (fresh project-directory copy per run), "runs 2 and 3 both reported 'succeeded' but in a **suspicious 0.1s** with a completely empty run.log, which is far too fast for a real open+script+close+exit cycle and matches this module's previously-documented 'exits immediately with no output' failure mode rather than confirming real work happened."

This is the silent-no-op face of the same underlying Capture batch-invocation defect documented in capture-batch-open-hang: sometimes the process genuinely hangs (100% CPU, zero windows, 0-byte log — the "hang" mode), and sometimes it reports success almost instantly while doing nothing (this mode). Both share the symptom of an **empty `run.log`**; the only difference is the return code/state.

The module explicitly warns about exactly this failure-shape at the suite-wide level too: `README.md` documents the general principle that "a fast 'succeeded' state alone" is not evidence the script ran — this is the same class of state lie as `job-state-succeeded-lies` at the platform level (success return code does not imply work happened), but here it is specific to Capture's batch invocation.

## Evidence

- `core/tool_status.py` `capture` note, lines ~470-479: "runs 2 and 3 both reported 'succeeded' but in a suspicious 0.1s with a completely empty run.log... do not treat a fast 'succeeded' state alone as evidence the script's actual content (place parts, save, etc.) ran — check for real output/log content, not just the return code."
- `capture_tools.py` docstring (lines 21-35): the run mechanics "themselves are unverified... treat every tool below as `built_untested` until `capture_run_session`'s batch invocation is independently confirmed working on this machine."
- `README.md` lines 137-143 (Capture retest): even the 60s-wait run that didn't immediately hang was "still running with an empty log" — the empty log is common to both the hang mode and this fast-exit mode.

## Affected code

- `sigrity_mcp/domains/cad/capture_tools.py` — `capture_run_session` (and anything that composes it, e.g. `generate_schematic_from_spec`).
- The empty-`run.log` / fast-state signal itself, detectable via the suite's own `get_job_status` + `tail_job_log`/`list_job_files`.
