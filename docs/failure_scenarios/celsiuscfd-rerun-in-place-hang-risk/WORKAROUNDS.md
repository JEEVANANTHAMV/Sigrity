# celsiuscfd-rerun-in-place-hang-risk — Workarounds

## What works (confirmed / prevented proactively)

- **Always run against a fresh copy of the project directory per run** (SKILL
  playbook convention: `copy pcb_pkg_sav.3dth pcb_pkg_sav.tcl → runs\cfd_<n>\`).
  A clean target has no prior `_EX_CFD/` to trigger the assumed overwrite prompt.
  Prescribed by both `core/tool_status.py` and `celsiuscfd_tools.py`.
- **Keep the default pre-clean on.** `celsiuscfd_run_session(...,
  clean_prior_results=True)` (the default) invokes `_clear_prior_celsius_results`,
  which deletes any `<stem>_*` dir ending in `_SS_W / _Result / _CFD / _EC /
  _Results` in the project's parent directory before submitting. This is the same
  helper as celsius3d and directly targets this risk.
- **Verify by artifact on disk for the CFD result tree too.** As with Celsius3D,
  `list_job_files` only shows the near-empty `job_dir`; the real CFD artifacts are
  written **next to the `.3dth`** in `<name>_EX_CFD\` (`pcb_pkg_sav.cfd`,
  `pcb_pkg_sav.log`, `pcb_pkg_Simulation_Summary.dat`). Inspect that directory, not
  the job_dir, to confirm completion. On the tested sample the process exited
  cleanly (rc 0 → `state: "succeeded"`), so no kill was required there — but the
  artifact check is still the right confirmation signal.

## What was tried / ruled out

- Nothing CFD-specific was tried against an *occupied* directory (that re-run test
  was deliberately not performed), so there is no CFD-specific "tried & failed" log
  line analogous to Celsius3D's. The rule-out here is by *product-family
  inference* from the confirmed Celsius3D bug, which is exactly why the scenario is
  `built_untested`/risk rather than `known_blocked`.
- Re-running in place and relying on the solver to overwrite: not confirmed safe for
  CFD (no clean test), and confirmed to hang for the sibling 3D solver — so the
  conservative practice is to not do it.

## Prevention

1. Stage each CFD run into a fresh `runs\cfd_<n>\`.
2. Keep `clean_prior_results=True` (default) so `_clear_prior_celsius_results`
   clears any stale result folder in the target.
3. Never point a second CFD run at a directory the first run already populated.
4. Confirm completion by checking `<name>_EX_CFD\` for the `.cfd` + summary files
   on disk rather than trusting process exit alone (cheap insurance if a CFD idle-
   variant ever surfaces, mirroring the 3D case).

## Notes

- This is a **risk/prevention** scenario, not a confirmed repro. The only CFD
  failure mode confirmed with live evidence is the first-run success; the re-run-
  in-place hang is carried by inference from the identical, confirmed Celsius3D
  bug. If a future test intentionally re-runs into an occupied `_EX_CFD/` dir, this
  entry should be upgraded (or downgraded) to match the observed outcome.
- The `_clear_prior_celsius_results` helper is shared between the celsius3d and
  celsiuscfd modules (identical copy in each file), so the prevention is symmetric.
