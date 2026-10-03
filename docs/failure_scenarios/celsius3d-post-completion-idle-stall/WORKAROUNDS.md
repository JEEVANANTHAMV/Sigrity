# celsius3d-post-completion-idle-stall — Workarounds

## What works (confirmed)

- **Declare completion by artifact, not by process exit.** Poll the *project*
  directory (NOT `list_job_files`, which only shows the near-empty `job_dir`) for
  `case_SS_W\SR3d.dat` and `case_Result_Summary.dat`/`.json` to be present at a real,
  non-trivial size (e.g. `SR3d.dat` ~21 MB on the sample). Their appearance at real
  size **is** the completion signal. This is the documented "completion signal" in
  `celsius3d_tools.py` and SKILL.md Task 2b.
- **Kill the idle process once results are confirmed.** After the artifact check
  passes, `Stop-Process -Force <pid>` the now-idle `Celsius3D.exe`. The work is
  already on disk; killing loses nothing. Confirmed live (SKILL.md Task 2b:
  `Stop-Process -Id <pid> -Force → killed`, work already on disk).
- **Read the real result set out of the project dir**, not `job_dir`. For Celsius3D
  the solver writes `<name>_SS_W/` next to the `.3dth`, not into the job directory;
  `run.log` is near-empty (just the "legacy command line syntax" banner). Inspect the
  project directory on disk for results.

## What was tried / ruled out

- Waiting for the process to exit on its own (`wait_for_job` indefinitely): ruled out
  — it never exits; the "Unsaved Project" window has no dismissable button.
- `cancel_job(job_id)`: ruled out as the close mechanism — it "still reports
  'running'" and does not force-kill the idle process here; a manual
  `Stop-Process -Force` was required.
- Posting `WM_CLOSE` / `VK_RETURN` / `BN_CLICKED` to the "Unsaved Project" window or
  its children (via `core/win32gui_helper`): ruled out — zero visible/enabled
  children in `EnumWindows`; nothing to click; window does not close by message
  posting today. The helper confirms the diagnosis but cannot dismiss this
  particular window.
- Using a fresh, never-run dir to *avoid* the stall: ruled out as sufficient —
  SKILL.md Task 2c shows even a clean dir idled at the 120 s check. Fresh copies
  prevent the *re-run-in-place* variant (`celsius3d-rerun-in-place-hang`) but cannot
  guarantee a clean exit.

## Prevention

1. Never gate a Celsius3D signoff on `state == "succeeded"`.
2. Implement (caller or JobManager side-task) an artifact-poll: "SR3d.dat +
   case_Result_Summary.dat exist at real size" ⇒ done.
3. On done, `Stop-Process -Force <pid>` and record the artifact sizes.
4. Keep a fresh-copy dir per run (prevents the separate re-run-in-place hang) and
   combine both guards.

## Notes

- This is the harder of the two Celsius3D lifecycle failures: the re-run-in-place
  hang is avoided by a fresh copy, but this one *also* happens on a fresh copy, so
  the artifact-exists + kill guard is required regardless.
- The same artifact-not-in-job_dir gotcha applies to CelsiusCFD (its `<name>_EX_CFD/`
  tree is written next to the `.3dth` too — see SKILL.md Task 3), though on the
  tested CFD sample the process did exit cleanly (rc 0). The 3D idle-stall does not
  have a confirmed in-suite fix.
