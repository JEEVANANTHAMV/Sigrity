# Workarounds: Clarity3D Has No .3dem Input; Feeding .spd Segfaults

## Verified Workaround (to run Clarity3D)

**None in-suite — a real `.3dem` input is required and none exists on this machine.** The manifest marks this `verified_workaround: NO (no .3dem on machine)`. The only path to actually run Clarity3D is to **obtain a real `.3dem` (or `spdb`) design file** and pass it as `design_file` to `start_clarity3d_session`/`clarity3d_run_session`. Until then, Clarity3D is a hard block with no in-suite substitute.

There is **no workaround that lets a `.spd`/`.dsn` stand in for a `.3dem`** — the tool rejects those formats (`ERROR: File format is not supported.`) and then dies.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Search the install + `runs/` for a usable `.3dem`/`.spdb` | **failed — none exist** (recursive `*.3dem` and `*.spdb` searches under `share` and `runs/` returned nothing). | `SKILL.md:203-207` |
| 2 | Feed the only Clarity3D-labeled file, `43micro.spd`, as `design_file` | **failed — tool rejects the format and the process segfaults** with `ERROR: File format is not supported.`; job state stuck `"running"`, PID dead, returncode unset. | `SKILL.md:214-232` |
| 3 | Feed `.dsp`/`.dsn` as `design_file` (earlier eval run) | **failed — identical signature:** state `"cancelled"`, 119-byte `run.log` (banner only), no result. | `SKILL.md:228-232` (job `clarity3d_workbench-7076037627`) |

## Prevention

1. **Record Clarity3D as known-blocked on this machine and don't burn time retrying.** Per `SKILL.md:236-237`: "If you don't have a `.3dem` on hand, you can't run Clarity3D — this is a file-format limitation, not a license or HPC issue." A retry cannot change the outcome until a `.3dem` is present.
2. **Gate on input format before launching.** Only call `start_clarity3d_session`/`clarity3d_run_session` when `design_file` actually ends in `.3dem` (or is a confirmed `spdb`). Never pass a `.spd`/`.dsn`/`.dsp` as `design_file` — it doesn't fail cleanly, it segfaults.
3. **Handle the stuck `"running"` state on wrong-format runs.** If a Clarity3D job is fed a non-`.3dem` and `wait_for_job` times out with state still `"running"`: `cancel_job`, then `kill /F` the PID if it sticks — the dead process does not clean up its own exit code. Check the **macro log** (`macro_<ts>_<pid>.log`) for the real `ERROR: File format is not supported.` line; `run.log` only has the 119-byte legacy-syntax banner.
4. **Remind callers that `design_file` is required** for `clarity3d_run_session` (unlike `celsius3d_run_session`), and that both `begin` and `end simulation -fileName` are emitted and required.

## Remaining Gaps

Clarity3D is **genuinely blocked on this machine**: no valid input format is available (no `.3dem`), and the tool's behavior on an invalid input is a hard, uncleaned process death that leaves job state `"running"`. This is not a bug in this suite's wrapper — the wrapper's Tcl composition matches the confirmed `test2.3dem` sample shape and the documented `--NoUI -tcl` batch invocation. Closing this requires **a real `.3dem` design to be obtained**; without one, no flag, retry, or in-suite alternative unlocks full-wave 3D EM extraction.
