# celsiuscfd-rerun-in-place-hang-risk

- **tool**: `celsiuscfd` (`CelsiusCFD.exe`, wrapped as `start_celsiuscfd_session` / `celsiuscfd_set_solver_cpu_percentage` / `celsiuscfd_run_session` in `sigrity_mcp/domains/thermal/celsiuscfd_tools.py`)
- **status_category**: `built_untested` (the exact re-run-in-place failure was NOT independently re-tested for CelsiusCFD; it is classified as a *risk* inherited from the confirmed Celsius3D bug in the same product family)
- **verified_workaround**: YES (prevented proactively) — always run against a fresh project copy per run; `_clear_prior_celsius_results` pre-cleans the target dir (see WORKAROUNDS.md)

## What went wrong (as a risk, not a confirmed repro)

CelsiusCFD is **not independently confirmed** to hang on re-run-in-place the way
Celsius3D does. What IS confirmed: a first run of the Cadence sample
(`share/PostInstallationCheck/celsiuscfd/pcb_pkg_sav.3dth` + `pcb_pkg_sav.tcl`)
succeeded cleanly — `CelsiusCFD.exe -tcl pcb_pkg_sav.tcl` exited 0, log showed
"CelsiusECSolver is completed", "CFD network file (.cfd) is generated!", and a real
`.cfd` network file was produced (~18 s in the live SKILL run). No stall was observed
**on that sample's first run**.

The scenario here is a **documented risk carried over from the confirmed
Celsius3D re-run-in-place hang** (see `celsius3d-rerun-in-place-hang`): both solvers
are the same Cadence `sigrity::` Tcl-scripted product family, both take
`<exe> -tcl <script>.tcl`, and both write a result subfolder next to the `.3dth`
(`<name>_EX_CFD/` for CFD, `<name>_SS_W/` for 3D). Because Celsius3D reliably hangs
when its prior result folder is still present, the suite conservatively treats
CelsiusCFD as **subject to the same risk until proven otherwise** and prescribes the
identical fresh-copy workflow.

## Root cause (assumed, from the sibling tool)

Same as the confirmed Celsius3D mechanism: when the output target (`<name>_EX_CFD/`
for CelsiusCFD, `<name>_SS_W/` for Celsius3D) is already occupied by a prior run's
artifacts, the Tcl/batch path is presumed to block on an interactive
overwrite-confirmation that a headless run cannot satisfy — leaving the process
hung with an empty log. Not independently observed for CFD; assumed by product
family.

## Evidence

- `core/tool_status.py:546-553` (the `celsiuscfd` note): "Confirmed live end-to-end
  against a real Cadence sample project on its FIRST run … `CelsiusCFD.exe -tcl
  pcb_pkg_sav.tcl` exited 0, log showed 'CelsiusECSolver is completed' and a real
  .cfd network file was generated. **Not independently re-tested against an
  already-simulated project directory, but given Celsius3D's confirmed same-family
  hang in that scenario (see celsius3d's note), treat CelsiusCFD as likely subject to
  the same re-run-in-place risk until proven otherwise — use a fresh project copy per
  run.**"
- `domains/thermal/celsiuscfd_tools.py` module docstring (lines 14-20): "Celsius3D
  (the sibling structural/thermal-stress solver, same product family) was confirmed
  via both direct testing and the multi-model eval harness to hang indefinitely when
  re-run against a project directory that already has a prior run's result folder …
  CelsiusCFD was **not independently re-tested this exact way**, but treat it as
  likely subject to the same risk until proven otherwise: always run against a fresh
  copy of the project directory, never re-run in place."
- `domains/thermal/celsiuscfd_tools.py:39-49` — `_clear_prior_celsius_results`
  (identical to the celsius3d one), called from `celsiuscfd_run_session` when
  `clean_prior_results=True` (default), deleting any `<stem>_*` dir ending in
  `_SS_W / _Result / _CFD / _EC / _Results` before run. This is the in-suite
  prevention for exactly this risk.
- `.forjinn/skills/sigrity-celsius/SKILL.md` Task 3: first-run success on a fresh
  copy (`runs\cfd_1`), no stall observed on that sample; result tree
  `pcb_pkg_sav_EX_CFD\` next to the `.3dth`.

## Symptoms a caller would observe (IF the risk materializes)

- Same as the confirmed Celsius3D re-run hang: `state: "running"` stuck, `tail_job_log`
  shows only the startup banner, process alive with `returncode: null`, result folder
  from the prior run still present and not replaced. This is the *inherited*
  expectation; there is no CFD-specific log line confirming it was actually observed.

## Pipeline Impact

Unverified but treated as a real risk: a CFD signoff loop that re-runs against the
same populated directory could hang indefinitely, exactly as the confirmed Celsius3D
case does. The in-suite default (`clean_prior_results=True` + the caller's own fresh
copy per run) is the mitigation; the residual gap is that a clean confirmation
test (intentionally re-running into an occupied dir) was never performed.
