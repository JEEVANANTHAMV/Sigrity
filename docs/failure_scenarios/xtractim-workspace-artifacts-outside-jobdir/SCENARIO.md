# XtractIM Workspace-Mode Artifacts Are Written Next to the .ximx, Not in the Job Dir

**Slug**: `xtractim-workspace-artifacts-outside-jobdir`
**Tool(s) affected**: `run_xtractim_workspace` (`XtractIM.exe`, logical tool `xtractim`)
**Status category**: `unreliable_intermittent`
**Pipeline stage**: extraction (XtractIM 2.5D/3D package & PCB PG/EPA extraction)

## Symptom

A fully successful `run_xtractim_workspace` job reports `state: succeeded, returncode 0`, but `list_job_files(job_id)` shows the **job_dir is empty** — only `job.json` + `run.log` (and `run.log` is 0 bytes). A pipeline that checks the job dir for results will conclude "no output / failed" even though the extraction genuinely ran and produced real RLC matrices.

The real artifacts are written **next to the input `.ximx`** (in the input file's directory), **not** in the job's scratch directory. The job's own `run.log` is also 0 bytes because XtractIM writes its own run log as `<dir-of-ximx>\<layout-name>_<timestamp>_<pid>.log` — again in the input's directory, not the job dir.

## Root Cause

`XtractIM.exe -b <workspace-ximx>` resolves all its output paths (results, per-net CSVs, `.err`, `Ref_Files/`, and its own solver timeline log) **relative to the directory of the input `.ximx`**, regardless of the per-job scratch `cwd` that `submit_job` sets. So the job framework's "look in `job_dir` for outputs" contract does not hold for XtractIM workspace mode — the artifacts land wherever the `.ximx` lives. This is one of the extraction domain's two **inviolable rules**: some tools (XtractIM being the canonical example) write results **outside `job_dir`**, so you must also check the input file's directory.

Verified live (SKILL.md Task 1, job `xtractim-91f66f4d36`, ~40 s wall, rc 0):
```
t1_xtractim_ws\EPAResult_Wirebond_EPA_092626_192820_22996.eparesult
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinInductanceAll_LB.csv   (672 KB)
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinInductanceAll_LC.csv   (23 KB)
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinRLofEachNet_LB.csv
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinRLofEachNet_LC.csv
t1_xtractim_ws\Wirebond_EPA_20260926192820_NetLoopInd.csv
t1_xtractim_ws\Wirebond_EPA_XtractIM.err
t1_xtractim_ws\EPAResult_... \Ref_Files\  (IC / LB / LC matrix files)
```
`NetLoopInd.csv` first data rows (verified real L/C/R content): `VDD_1,VSS,0.442200,44.981500,12.417300` (L nH / C pF / R mOhm). XtractIM's own log `Wirebond_EPA_092626_192741_22996.log` (in the same dir) shows the full solver timeline: `Fetch License` → `[Matrix File Name List]` → `Ending time = 09/26/2026 19:28:20`.

## Evidence

- `.forjinn/skills/sigrity-extraction/SKILL.md:41-74` (Task 1) — "**Verification — job_dir is EMPTY.** `list_job_files` → only `job.json` + `run.log` (0 bytes). **XtractIM writes its results next to the `.ximx`, not in the job dir.** … **Mistake #1 for Task 1:** trusting `list_job_files` and stopping there. The job dir will be empty even for a fully successful run. **Check the directory of the `.ximx` input**, not the job dir, before declaring the run done or 'failed'."
- `.forjinn/skills/sigrity-extraction/SKILL.md:66-70` — "The job's own log file was 0 bytes … XtractIM writes **its** run log to `<dir-of-ximx>\<layout-name>_<timestamp>_<pid>.log` (same dir as the input, not the job dir)."
- `.forjinn/skills/sigrity-extraction/SKILL.md:18-20` (inviolable rule 1) — "`state:'succeeded'` + rc 0 ≠ artifacts exist. Verify with `list_job_files(job_id)` — and know that some tools (XtractIM below) write results **outside `job_dir`**, so you must also check the input file's directory."
- `.forjinn/skills/sigrity-extraction/SKILL.md:290` — one-line: "`run_xtractim_workspace(workspace_xml=…)` → rc 0 + artifacts **in the .ximx's directory, not job_dir**."
- `sigrity_mcp/domains/extraction/xtractim_tools.py:47-55` (`run_xtractim_workspace`) — args are `["-b", workspace_xml]` (+ optional `spd_override`); no output-dir argument exists, so outputs follow the `.ximx`.
- `sigrity_mcp/core/tool_status.py:742-745` — "Confirmed live end-to-end against a real Cadence sample (`share/PostInstallationCheck/xtractim/Wirebond_EPA.ximx`): `XtractIM.exe -b Wirebond_EPA.ximx` exited 0 and ran a genuine full-wave RLC extraction."

## Pipeline Impact

A pipeline that harvests XtractIM results from the job dir will **miss every artifact** on a successful run (empty job dir → false "no output"), and may mis-flag a clean run as failed. Conversely, the 0-byte job `run.log` gives no solver evidence either. The harvest step must look in **the input `.ximx`'s directory** (and/or honor the optional `spd_override` location) for the `.eparesult`, `*NetLoopInd.csv`, `*PinInductanceAll_{LC,LB}.csv`, `*_XtractIM.err`, and `Ref_Files/`, and for the real solver log `<layout>_<ts>_<pid>.log`. Because a successful run's job dir is indistinguishable from a failed one at the job level, this is a silent, systematic mis-harvest risk, not an intermittent one in effect — categorized here as `unreliable_intermittent` in the manifest because the *symptom of checking the wrong place* is the trap.
