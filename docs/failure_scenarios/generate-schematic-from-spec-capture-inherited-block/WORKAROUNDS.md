# Workarounds — generate-schematic-from-spec-capture-inherited-block

## verified_workaround: None (for actually authoring a populated schematic end-to-end, on this machine)

There is no in-suite fix: the blocker is inherited wholesale from Capture's own batch invocation (see capture-batch-open-hang for the underlying root cause, and its WORKAROUNDS.md for the list of what was tried and did NOT fix the underlying `Open <project>` defect). Composing the same failing primitives into a single call doesn't change their failure behavior.

## What the code already does defensively (no action needed from the caller)

- `generate_schematic_from_spec` already calls `auto_dismiss_recovery_dialog_if_stuck(run_result["job_id"])` right after `capture_run_session` (schematic_generation_tools.py lines 170-172) — this is the automatic guard against the *separate* "Capture Custom Launch" crash-recovery dialog (capture-custom-launch-recovery-dialog), and its result (if any) is surfaced on the returned dict as `stuck_check_note`. You do not need to wire this in yourself when using `generate_schematic_from_spec`; you would only need equivalent handling if you compose the `capture_*` primitives by hand instead.
- The returned dict names exactly what page was targeted (`page: "<design> -> <folder>/<page>"`), so a wrong/underived design address is visible in the result rather than silent — useful when diagnosing whether a failed run at least pointed at the right design.

## For the caller: same discipline as `capture_run_session`

Treat the returned `succeeded` state with the exact skepticism the module itself documents (verbatim, from schematic_generation_tools.py's own docstring and README.md lines 496-500):

> "check the job's actual log content (via `tail_job_log`/`list_job_files`), not just the returncode, before trusting that the parts/wires described below actually landed in the saved design."

Do not assume the `parts_placed`/`wires_placed`/`pins_placed` counts in the result reflect parts/wires/pins that actually landed — those counts reflect what was *queued into the Tcl macro*, not what Capture actually executed, for the same reason Capture's `state` can lie (see capture-succeeded-but-empty-log-fast-exit). Independently verify the underlying design file on disk if it exists, rather than trusting Capture's own claim.

## What actually works instead for the same overall goal (confirmed live, non-Capture paths)

Since end-to-end Capture schematic authoring is blocked here, the same *capability* (get a design into analysis/simulation, or create a new project) has confirmed-live alternative routes the suite itself documents:

- **Create/duplicate a new schematic project from scratch** (no Capture GUI): `allegro_copy_project` (`copyproject.exe`, confirmed live) or `allegro_package_xcon_project` (`xcon2project.exe`, confirmed live) — see copyproject-cpm-extension-not-appended / xcon2project-refproj-required-despite-brackets.
- **Run PSpice simulation** on a `.cir` netlist independent of Capture: `run_pspice_simulation` (`psp_cmd.exe`, confirmed live) — see pspice-gui-entrypoints-hang-on-help.
- **Translate a real `.brd` into simulation-ready `.spd` form** for SI/PI analysis, bypassing Capture entirely: PowerSI BRD-bridge (`start_powersi_session(spd_file=<brd>)` + `powersi_save_document`) — confirmed live, README.md lines 144-149.
- **Checklist-style design verification** without any Capture object model: `run_schematic_checklist` over real `report.exe -v net`/`-v bom` CSV output — see schematic-checklist-heuristic-precision-unverified for the caveats on that path too (coarse heuristics, unverified precision).
