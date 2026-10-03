# celsius3d-rerun-in-place-hang — Workarounds

## What works (confirmed)

- **Always use a fresh copy of the project per run.** Copy `.3dth` + `.tcl` into a
  brand-new directory (the SKILL playbook's `runs\c3d_<n>\` convention) and run there.
  A clean target directory has no prior `_SS_W/` to trigger the overwrite prompt.
  This is the canonical, confirmed workaround prescribed by both `core/tool_status.py`
  and `celsius3d_tools.py`.
- **Pre-clean the result folder** before the run. `celsius3d_run_session` already calls
  `_clear_prior_celsius_results(project_file)` by default (`clean_prior_results=True`),
  which does a `glob("<stem>_*")` and `shutil.rmtree` of any dir ending in
  `_SS_W / _Result / _CFD / _EC / _Results`. This is what makes the in-suite path safe
  for re-runs — but it only protects the *specific* project file passed in; if a caller
  re-runs against a directory that still holds the prior folder and relies on an external
  cleanup, that must be done too.
- **Treat "result files exist at real size" as the completion signal, not "process
  exited."** Even with a fresh copy, Celsius3D can idle after it finishes (see
  `celsius3d-post-completion-idle-stall`). Poll for `SR3d.dat` +
  `case_Result_Summary.dat`/`.json` to be present at reasonable size, then
  `Stop-Process -Force <pid>` the now-idle process. The work is already on disk.

## What was tried / ruled out

- Re-running in place (relying on the solver to overwrite an existing `_SS_W/`):
  ruled out — hangs indefinitely with an empty log (the failure itself).
- Trusting `state: "running"` then waiting longer: ruled out — the process does not
  advance; it is the post-completion exit stall, not a slow solve.
- `cancel_job(job_id)`: does not reliably force-kill the idle Celsius3D process;
  a manual `Stop-Process -Force <pid>` was required (SKILL playbook Task 2b).

## Prevention

1. Stage each signoff into a fresh `runs\c3d_<n>\` before submitting.
2. Keep `clean_prior_results=True` (the default) so `_clear_prior_celsius_results`
   strips any stale result folder in the target.
3. Never point a second run at the same directory that a first run already populated.
4. Combine with the idle-stall detection (artifact-exists → kill) so the
   "completed but process won't exit" case is also handled.

## Notes

- This scenario is about the **re-run-in-place** trigger specifically. The broader
  "process idles after a successful solve even on a fresh dir" behavior is tracked
  separately as `celsius3d-post-completion-idle-stall`; the two workarounds compose.
- A fresh copy is **necessary but not sufficient** to guarantee a clean exit —
  see the idle-stall scenario and SKILL.md Task 2c for the evidence that a
  completely fresh, never-run directory still idled at the 120 s check.
