# celsius2d-invalid-cfd-reference-domain-error — Workarounds

## What works (confirmed)

- **Use a valid, self-contained workspace.** The Cadence `demo_sim.pdcx` sample runs
  end-to-end with the identical invocation (`Celsius2D.exe -b -XIMSAVE -r …`) → rc 0,
  "Simulation succeed", full artifacts. This is the confirmed-good reference input.
- **For a real project, make the referenced CFD file valid/present.** If a workspace's
  "Use Defined CFD File" points at a missing or mismatched file, either (a) ensure the
  file the workspace references actually exists at the expected path, or (b) edit the
  workspace's content so it no longer references the invalid/absent file. This is a
  content fix in the `.pdcx`, which is exactly the GUI-authoring step this suite does
  not perform (see `celsius-studio-gui-only-no-batch-authoring`).
- **Confirm success by the real success line + artifacts, not just rc.** Success line
  (engine log): `--Simulation succeed` (e.g. `demo_sim_092626_192639_9952.log`), plus
  `demo_sim_ResourceProfile.log` `[Total Simulation Time] …`. Artifacts are written
  **next to the `.pdcx`**, not in the `job_dir` (e.g. `demo_sim.results`,
  `demo_sim_ThermalResult.tem`, `demo_sim_ThermalEngine.log`).

## What was tried / ruled out

- Retrying `chip.pdcx` with the same command: ruled out (not a transient) — the failure
  is a deterministic content precondition (invalid referenced CFD file), so the same
  input fails the same way.
- Treating the failure as a license or CLI problem: ruled out — the log line is a
  specific domain-content diagnostic ("The CFD File Specified in the Use Defined CFD
  File is invalid"), and the identical invocation succeeds for `demo_sim.pdcx`.

## Prevention

1. Before running a Celsius2D workspace, confirm it is self-contained: the workspace
   references no external/missing CFD file, or the referenced file is co-located and
   valid.
2. Use the shipped `demo_sim.pdcx` as the known-good reference input for tests and
   smoke runs (it is the sample that is actually runnable).
3. On this specific error, read the job log and act on the named precondition (the
   referenced CFD file) rather than retrying the same input.
4. If a content fix is needed, it is done by authoring/editing the workspace in the
   CelsiusStudio GUI (this suite runs pre-built `.pdcx` workspaces; it does not author
   them — see the companion scenario).

## Notes

- Unlike the 3D/CFD lifecycle failures, Celsius2D's confirmed behavior is clean: valid
  input → `state: "succeeded"` (rc 0), invalid reference → a clean, readable failure.
  There is no hang/stall reported for Celsius2D; the only failure in the evidence is
  this content precondition.
- This is the canonical example in the suite of a **readable domain-content diagnostic
  surfacing** (the wrapper + CLI are proven sound; the input is the problem).
