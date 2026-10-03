---
name: sigrity-celsius
description: Sigrity Celsius (Thermal) - Celsius2D/3D/CFD verified sequences, the Celsius3D post-completion idle-stall and how to detect/kill it, exact success lines. Use for thermal, electrothermal, or thermal-stress analysis of a pre-built .pdcx/.3dth project.
---

# Sigrity Celsius (Thermal) MCP — Verified Playbook

Live-exercised end-to-end on this machine (Sigrity 2024.0) against the Cadence
`PostInstallationCheck` samples. Every call below was actually made; states,
timestamps, and artifact sizes are real.

## Sample projects (all pre-built — these tools RUN, they do not AUTHOR)
| Domain | Input | Also present |
|---|---|---|
| Celsius2D | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\celsius2d\demo_sim.pdcx` | â€” |
| Celsius3D | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\celsius3d\case.3dth` | `case.tcl` |
| CelsiusCFD | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\celsiuscfd\pcb_pkg_sav.3dth` | `pcb_pkg_sav.tcl` |

Scratch root (from `SIGRITY_WORKDIR`): `C:\Users\aicoe\Desktop\Sigrity\runs\`

---

## Ground rules (learned the hard way)
1. **Every `run_*` returns `{job_id, state:"running"}` immediately.** Follow with
   `wait_for_job(job_id, timeout_seconds=â€¦)`. If it comes back `"running"`, the timeout
   elapsed â€” call `wait_for_job` again (or `get_job_status`).
2. **`state:"succeeded"` â‰  verified.** Always confirm output artifacts on disk.
3. **`list_job_files` only shows the job_dir** (`job.json`, `macro.tcl`, `run.log`). It
   does **NOT** show the real result tree â€” for Celsius3D/CFD the solver writes
   `<name>_SS_W/` (3D) or `<name>_EX_CFD/` (CFD) **next to the `.3dth`**, not in the
   job_dir. `run.log` is near-empty (just a "legacy command line syntax" banner).
   â†’ Inspect the *project* directory on disk, not `list_job_files`, for results.
4. **Session state is in-memory per MCP-server process.** Tcl sessions and job records
   live in the FastMCP server's Python process. If that process dies, every
   `session_id` and `job_id` it held is gone. Start + compose + run a session in **one**
   server lifetime. (A `run_*` job keeps running even if the server is lost â€” you can
   still `get_job_status`/`wait_for_job` by `job_id` while that process lives.)
5. **Celsius3D post-completion idle-stall** (the big one, see Task 2). The sim finishes
   and writes the full result set (~20â€“30 s), then `Celsius3D.exe` idles forever. The job
   stays `state:"running"`. Fix = treat "result files exist with real size" as the
   completion signal, then kill the process.

---

## TASK 1 â€” EASY: Celsius2D (board 2D thermal + stress)
**Verified: succeeded, rc=0, ~14 s.**

```
1. run_celsius2d_workspace(pdcx_file="C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\celsius2d\demo_sim.pdcx")
   â†’ {job_id:"celsius2d-9feeda9ae5", state:"running",
      command:[Celsius2D.exe, -b, -XIMSAVE, -r, â€¦demo_sim.pdcx]}
2. wait_for_job(job_id, timeout_seconds=180)
   â†’ state:"succeeded", returncode:0   (started 19:26:39 â†’ ended ~19:26:52)
```

Result artifacts are written **next to the `.pdcx`** (in the celsius2d sample dir), e.g.:
`demo_sim_ThermalEngine.log`, `demo_sim_ResourceProfile.log`, `demo_sim.results` (1.36 MB),
`demo_sim_ThermalResult.tem` (12 MB), `demo_sim_SimulationResultFile.xml`.

**Success line** (engine log, exact text):
```
[2026/09/26-19:26:52]--Simulation succeed          â† demo_sim_092626_192639_9952.log (the per-run timestamped log)
[2026/09/26-19:26:52]--[Total Simulation Time] 10.899124 s   â† demo_sim_ResourceProfile.log
```
`demo_sim_ThermalEngine.log` tail confirms a real MUMPS in-core solve
(127,575 unknowns, 3,799,287 nonzeros, ~703 MB).

**Caveats:** there is no session â€” one call. A *different* sample (`chip.pdcx`) fails with
a domain-content error ("The CFD File Specified in the Use Defined CFD File is invalid")
â€” that's an input problem, not a launch/license failure.

---

## TASK 2 â€” MEDIUM: Celsius3D (3D electrothermal / thermal-stress)
**Verified: results are correct and complete. The process stalls after completion (expected).**

### 2a. First run in a FRESH copy dir
Because the result folder is written into the project dir, always give it a clean target:
```bash
mkdir runs\c3d_1
copy case.3dth case.tcl â†’ runs\c3d_1\
```
Then, in ONE server lifetime:
```
1. start_celsius3d_session(project_file="C:\Users\aicoe\Desktop\Sigrity\runs\c3d_1\case.3dth")
   â†’ session_id:"celsius3d-session-f3c63489"
2. celsius3d_run_session(session_id, project_file="â€¦\runs\c3d_1\case.3dth")
   â†’ job_id:"celsius3d-5b66113f06", state:"running",
     command:[Celsius3D.exe, -tcl, <job_dir>\macro.tcl]
3. wait_for_job(job_id, timeout_seconds=90)
   â†’ state:"running"  â† STILL RUNNING after 90 s = the stall (sim already done)
```

### 2b. The stall, demonstrated + the completion signal
While `get_job_status` still says `running` (pid 7552, returncode null), the results are
already fully on disk in `runs\c3d_1\case_SS_W\`:
```
SR3d.dat                       21,172,917 bytes   (full field result)
case_Result_Summary.dat            1,623 bytes
case_Result_Summary.json             2,284 bytes
case_Simulation_Summary.dat          368 bytes
ResultsInfo.dat                        990 bytes
case.log: "INFO:Stress engine started and completed successfully!"
```
**Completion signal = `SR3d.dat` + `case_Result_Summary.dat` present at real size.** The
process will never exit on its own. Fix: kill it.
```
cancel_job(job_id)            â†’ still reports "running" (cancel doesn't force-kill the idle proc here)
Stop-Process -Id <pid> -Force â†’ killed        (work is already on disk)
```

**Real numeric values** from `case_Result_Summary.json` (verified):
```
Displacement: u_max 5.174e-06 m, v_max 5.18622e-06 m, w_max 4.5411e-07 m
Strain:       Strain_zx_max 1.74753e-03, Strain_yz_max 1.61674e-03
Stress:       1stPrincipal_max 2.02918e+08 Pa (â‰ˆ203 MPa), vonMisesStress_max 1.14399e+08 Pa (â‰ˆ114 MPa)
```

### 2c. Key finding â€” the stall is NOT re-run-only
Reproduced on a **completely fresh, never-run** dir (`runs\c3d_2`, same sample): sim
completed in ~30 s, `SR3d.dat`/`case_Result_Summary.*` written, yet the process still idled
"running" at the 120 s check. So a fresh-copy dir is necessary but **not sufficient** to
avoid the stall â€” you must still use the file-exists completion signal + kill.

---

## TASK 3 â€” COMPLEX: CelsiusCFD (CFD thermal)
**Verified: succeeded, rc=0, ~18 s, no stall on this sample.** Fresh-copy dir first
(same rationale as 3D):
```bash
mkdir runs\cfd_1
copy pcb_pkg_sav.3dth pcb_pkg_sav.tcl â†’ runs\cfd_1\
```
In ONE server lifetime, thread `session_id` through every step:
```
1. start_celsiuscfd_session(project_file="C:\Users\aicoe\Desktop\Sigrity\runs\cfd_1\pcb_pkg_sav.3dth")
   â†’ session_id:"celsiuscfd-session-4a475690"
2. celsiuscfd_set_solver_cpu_percentage(session_id, cpu_percentage=100)
   â†’ {session_id:"celsiuscfd-session-4a475690", cpu_percentage:100}
3. celsiuscfd_run_session(session_id="celsiuscfd-session-4a475690",
                          project_file="â€¦\runs\cfd_1\pcb_pkg_sav.3dth")
   â†’ job_id:"celsiuscfd-e23594fc3c", state:"running",
     command:[CelsiusCFD.exe, -tcl, <job_dir>\macro.tcl]
4. wait_for_job(job_id, timeout_seconds=300)
   â†’ state:"succeeded", returncode:0   (started 19:30:16 â†’ ended 19:30:34, 8-CPU solver)
```

Result tree appears **next to the `.3dth`** in `runs\cfd_1\pcb_pkg_sav_EX_CFD\`:
- `pcb_pkg_sav.cfd` â€” **the .cfd file (present, 72 bytes, `<CFD_TERMINAL_DEFINITION â€¦>`)**
- `pcb_pkg_sav.log` engine log; `pcb_pkg_sav_full.log`; `pcb_pkg_sav_Simulation_Summary.dat`

**Success lines** (exact):
```
CelsiusECSolver is completed
Elaps time of CFD Engine Run: 12 seconds.
INFO:CFD network file (.cfd) is generated!
```
`Simulation_Summary.dat` confirms `CPU Usage: 100` (so the 100% override took effect).
Note: the sample's `.cfd` is tiny/empty `<CFD_TERMINAL_DEFINITION>` and the log warns
"missing terminals" + "zero emissivity for DieAttach/Silicon" â€” that's the sample's
configuration, not a failure; the `.cfd` is still generated.

---

## #1 Mistake to Avoid
**Treating the job `state` as the truth.** Two distinct failures hide behind it:
- Celsius2D/CFD: `succeeded` is fine, but the *result files live next to the input*, not
  in `job_dir` â€” `list_job_files` will look almost empty and mislead you.
- Celsius3D: the job stays `running` **forever** even after a fully successful solve.

**The fix that covers all three:** verify by **artifact on disk**, located relative to the
input project (not the job_dir). For Celsius3D specifically, declare done when
`SR3d.dat`/`case_Result_Summary.dat` exist at real size, then `Stop-Process` the idle PID.

### Other mistakes to watch for
- Passing a **placeholder/stale `session_id`** â†’ `Error: No open script session â€¦ It may
  have already been run/closed, or never created`. Fix: capture the id from
  `start_*_session` and reuse that exact string; do the whole composeâ†’run in one server
  lifetime.
- **Re-running in the same dir** for 3D/CFD â†’ guaranteed idle-stall. Fix: fresh-copy the
  project into a new `runs\<tool>_<n>\` per run.
- Assuming `cancel_job` reaps a Celsius3D process â€” it returned `running`; a manual
  `Stop-Process -Force <pid>` was required after the results were confirmed on disk.

*(Scratch job dirs from this exercise left in `runs\` as evidence: `celsius2d-9feeda9ae5`,
`c3d_1`/`celsius3d-5b66113f06`, `cfd_1`/`celsiuscfd-e23594fc3c`. `c3d_2` and the temp
client scripts were removed.)*

