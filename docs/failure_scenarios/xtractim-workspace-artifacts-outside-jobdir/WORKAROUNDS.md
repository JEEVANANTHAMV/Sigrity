# Workarounds: XtractIM Artifacts Outside the Job Dir

## Verified Workaround

**Harvest results from the input `.ximx`'s directory (and the `.spd`'s directory if `spd_override` re-points the layout), not from the job dir.** After `run_xtractim_workspace` + `wait_for_job` reports `succeeded`, `list_job_files` will show only `job.json` + a 0-byte `run.log`. The real, verified artifacts live next to the `.ximx`:
- `EPAResult_<name>_<ts>_<pid>.eparesult`
- `<name>_<ts>_PinInductanceAll_LB.csv` (~672 KB) and `_LC.csv`
- `<name>_<ts>_PinRLofEachNet_LB.csv` / `_LC.csv`
- `<name>_<ts>_NetLoopInd.csv` (the L/C/R per loop, e.g. `VDD_1,VSS,0.442200,44.981500,12.417300`)
- `<name>_XtractIM.err`
- `EPAResult_.../Ref_Files/` (IC / LB / LC matrix files)
- XtractIM's own solver log `<layout-name>_<ts>_<pid>.log` (in the same dir; this is where the real timeline `Fetch License` → `[Matrix File Name List]` → `Ending time` lives, since the job's `run.log` is 0 bytes).

This is the documented, live-verified harvest pattern (SKILL.md Task 1, job `xtractim-91f66f4d36`).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Read results from the job dir (`list_job_files`) | **mis-harvest — job dir is empty** (only `job.json` + 0-byte `run.log`) even on a clean rc 0 run. | `SKILL.md:43-44`, `:72-74` |
| 2 | Read results from the `.ximx` input's directory | **worked — the reliable path.** Real RLC matrices + `.eparesult` + `Ref_Files/` + solver log found there. | `SKILL.md:46-56` (Task 1 artifact listing); `:290` |
| 3 | Read XtractIM's own `<layout>_<ts>_<pid>.log` in the input dir (job `run.log` is 0 bytes) | **worked — real solver timeline captured** (`Fetch License` → `[Matrix File Name List]` → `Ending time`). | `SKILL.md:66-70` |

## Prevention

1. **Stage the `.ximx` in a known, dedicated input directory** and harvest from that exact directory. If you pass `spd_override` to re-point the layout, account for outputs potentially following the overridden layout's location.
2. **Never use the job dir / job `run.log` as the success signal for XtractIM workspace mode.** Use `succeeded` + rc 0 *plus* the presence of the expected `.eparesult` / `NetLoopInd.csv` in the input dir.
3. **Glob for the artifacts** (they are timestamped: `EPAResult_*`, `*NetLoopInd.csv`, `*PinInductanceAll_*.csv`, `*_XtractIM.err`) in the input dir — match on the newest run, since repeated runs accumulate time-stamped files in the same directory (mirrors the platform-domain "check CWD, not job dir" pattern also seen for BroadbandSPICE in this suite).
4. **For the real log, look for `<layout>_<ts>_<pid>.log` next to the `.ximx`**, not the 0-byte job `run.log`.

## Remaining Gaps

This is a **behavioral property of `XtractIM.exe -b`** (it resolves outputs relative to the input file, not the caller's CWD), not a bug in the wrapper — there is no output-directory argument to `run_xtractim_workspace` to redirect it. The workaround is purely a **caller-side harvest-location discipline**, and it is not automated in-suite: nothing in `xtractim_tools.py` writes the "where results landed" path into the job record, so every caller must independently remember to look next to the `.ximx`. That manual convention is the remaining gap — an in-suite helper that (a) stages the `.ximx`, (b) harvests the input-dir artifacts, and (c) records their path in the job metadata would make this self-contained.
