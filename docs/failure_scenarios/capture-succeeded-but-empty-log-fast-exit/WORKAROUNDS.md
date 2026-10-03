# Workarounds — capture-succeeded-but-empty-log-fast-exit

## verified_workaround: None (per the manifest)

There is no in-suite fix that makes Capture's batch invocation genuinely work — the underlying defect is in Capture.exe's own `Open <project>` / batch code path on this machine, not in this suite's Python wrapper (see capture-batch-open-hang for the full root-cause evidence and list of confirmed-live alternative paths for the same goals).

## What you CAN do: never trust the state alone

The manifest's "NO" refers to a fix for the underlying defect. The one concrete, documented, *verified* guidance that does exist for *dealing with* this symptom is a verification discipline, not a workaround:

- `core/tool_status.py` `capture` note (explicit, quotable guidance): "**do not treat a fast 'succeeded' state alone as evidence** the script's actual content (place parts, save, etc.) ran — **check for real output/log content, not just the return code**."
- `capture_tools.py` docstring (HONEST LIMITATION, schematic_generation_tools.py lines 26-29, repeated in `generate_schematic_from_spec`'s own docstring): "Treat a `succeeded` result from this tool the same way `capture_run_session` itself warns to: check the job's actual log content (via `tail_job_log`/`list_job_files`), not just the returncode, before trusting that the parts/wires described below actually landed in the saved design."

## Practical rule for any Capture job

1. `wait_for_job` / `get_job_status` → get the job's `state` and `job_dir`.
2. **Always** read the actual log before believing the state: `list_job_files(job_id)` + `read_job_output_file`/`tail_job_log(job_id)`.
3. If `run.log` is empty (0 bytes) — regardless of whether `state` says `succeeded` or the returncode is 0 — treat the run as having done **no real work**, even if the return code is clean. Do not proceed on the assumption parts/wires/nets were placed or a design was saved.
4. If the log is non-empty but the state is a fast (~0.1s) success, still read it: an Open+Save+Close+Exit cycle against a real project should not complete in a fraction of a second — treat sub-second success times on this tool as suspicious and re-check the underlying design file on disk (e.g. independently, via a non-Capture path such as a report/extract tool against whatever output you expected) rather than trusting Capture's own claim.

## What does NOT help here

- Clicking dialogs: this mode has no distinct named dialog documented (the "Capture Custom Launch" recovery dialog is a separate, crash-dump-driven prompt — see capture-custom-launch-recovery-dialog); the empty-log/fast-exit mode is not documented as having any dismissable window at all.
- Retrying the exact same `capture_run_session` call: the module's own evidence shows retrying is *inconsistent* (sometimes the clean 3.2s run, sometimes the hang, sometimes this fast no-op) — retry is not a reliable remedy for any of the three modes.
