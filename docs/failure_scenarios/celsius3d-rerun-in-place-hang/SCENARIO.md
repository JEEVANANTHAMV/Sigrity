# celsius3d-rerun-in-place-hang

- **tool**: `celsius3d` (`Celsius3D.exe`, wrapped as `start_celsius3d_session` / `celsius3d_run_session` in `sigrity_mcp/domains/thermal/celsius3d_tools.py`)
- **status_category**: `known_blocked` (genuine product hang, no confirmed in-suite fix; a fresh-copy workflow is the standard workaround, not a code fix)
- **verified_workaround**: YES — always run against a fresh copy of the project per run; never re-run in place (see WORKAROUNDS.md)

## What went wrong

Re-running `Celsius3D.exe -tcl <case>.tcl` against a project directory that
**already contains a prior run's result folder** (e.g. `case_SS_W/`) hangs the
process indefinitely with an empty log, even though the simulation itself has
actually completed. The job never advances past its startup banner and is either
reported "running" forever or killed on the JobManager's hard timeout.

This is a bug in **Celsius3D itself**, not in the suite's wrapper: the same
Tcl script that worked cleanly on a first run hangs when the result folder from
a previous run is already present. The likely mechanism is a GUI
overwrite-confirmation dialog (the same class of issue as Allegro/Capture's
"Product Choices" dialog): when the solver tries to write results into a
directory that is not empty, it is presumed to pop an interactive confirm.

It was first surfaced by the **multi-model eval harness** — the
`thermal_celsius3d_signoff` task on both endpoints (172.16.34.5 and 172.16.34.11)
independently reproduced it — and then reproduced standalone with a direct
`timeout 20 Celsius3D.exe -tcl case.tcl` (exit 124, kill on timeout, no output).

## Root cause

The solver, when its output target (`<case>_SS_W/`) is already occupied by a
prior run's artifacts, does not overwrite cleanly in batch/Tcl mode — it blocks
on an unsatisfied interactive confirmation, producing no further stdout. The
process stays alive (CPU idle, main window present) but never finishes. There is
no in-suite knob that makes Celsius3D skip or auto-accept that prompt.

## Evidence

- `core/tool_status.py:534-545` (the `celsius3d` note): first run succeeded
  ("Celsius3D.exe -tcl case.tcl exited 0, log showed 'Stress engine started and
  completed successfully!'"), then "IMPORTANT CAVEAT found via the multi-model
  eval harness (thermal_celsius3d_signoff task, both endpoints) and independently
  reproduced with a direct `timeout 20 Celsius3D.exe -tcl case.tcl` (exit 124):
  re-running against a project directory that already has a prior run's result
  folder (e.g. `<name>_SS_W/`) HANGS INDEFINITELY with an empty log — very
  likely a GUI overwrite-confirmation dialog, the same class of issue as
  Allegro/Capture's 'Product Choices' dialog. Always use a fresh copy of the
  project per run; never re-run in place."
- `domains/thermal/celsius3d_tools.py` module docstring (lines 13-32): confirms
  live and "re-tested multiple times on this machine (Sigrity 2024.0)"; notes
  that even the very FIRST run of a "fresh" project can exhibit the post-
  completion stall (see the companion scenario `celsius3d-post-completion-idle-stall`),
  but the re-run-in-place hang is the reliably-reproduced variant.
- `README.md:908-920`: "The two `thermal_celsius3d_signoff` runs caught a genuine,
  real, reproducible bug in Celsius3D itself, not a harness/prompt problem …
  both models independently ran the task, hit a job that never progressed past
  its startup banner … Investigating why turned up the real cause: re-running
  Celsius3D against a project directory that already contains a prior run's
  result folder hangs indefinitely — independently reproduced with a direct
  `timeout 20 Celsius3D.exe -tcl case.tcl` (exit 124, no output)."

## Symptoms a caller observes

- `celsius3d_run_session` returns `{job_id, state: "running"}` and the job is
  submitted normally (no error at submit time).
- `wait_for_job(job_id, timeout_seconds=…)` returns `"running"` repeatedly — the
  sim is done but the process has not exited.
- `tail_job_log` shows only the "legacy command line syntax" banner; no progress
  lines after it.
- The process is alive (a `get_job_status` shows a `pid`, `returncode: null`).
- In the project directory, the prior run's `case_SS_W/` is still present (the
  new run's results have not replaced it).

## Pipeline Impact

Blocks any Celsius3D signoff that reuses a project directory between runs (e.g. a
"parameter-sweep then re-run" loop, or a retry loop that points back at the same
staged copy). Both eval endpoints stalled for the task's full built-in retry
budget before the model correctly reported failure — so, left unhandled, this
burns an entire task's time budget and yields no result.
