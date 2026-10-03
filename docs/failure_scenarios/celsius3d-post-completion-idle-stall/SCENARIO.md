# celsius3d-post-completion-idle-stall

- **tool**: `celsius3d` (`Celsius3D.exe`, wrapped as `start_celsius3d_session` / `celsius3d_run_session` in `sigrity_mcp/domains/thermal/celsius3d_tools.py`)
- **status_category**: `known_blocked` (a real post-completion exit defect in the solver process; no in-suite fix, the process must be killed after results are on disk)
- **verified_workaround**: YES — detect completion by "result files exist at real size" and kill the idle PID (see WORKAROUNDS.md)

## What went wrong

`Celsius3D.exe` **finishes the simulation and writes the full result set, then idles
forever without exiting.** The job therefore stays `state: "running"` indefinitely
even after the work is done and verified on disk. `wait_for_job` keeps returning
`"running"`; `get_job_status` shows a live `pid` with `returncode: null` and frozen
CPU; `tail_job_log` shows only the "legacy command line syntax" banner.

This is a distinct failure from the re-run-in-place hang: it can happen on a
**completely fresh, never-run** project directory — so a clean target directory is
necessary but not sufficient to make the process exit on its own.

## Root cause

Confirmed by direct window-tree inspection (pywin32, `core/win32gui_helper.py`):
after the solve completes and the full result set is written (~20-30 s, identical
to a fresh run), the process stays alive and idle — CPU frozen, main Qt workbench
window open, **no modal dialog with a clickable button in its window tree**.
Instead an "Unsaved Project" Qt `QMainWindow` appears as a second visible top-level
window (class `Qt5159QWindowIcon`, empty window text, zero visible/enabled children
in `EnumWindows`), but it is not a classic Win32 dialog — `WM_CLOSE` / synthetic
`VK_ENTER` / `BN_CLICKED` posted to any child do not dismiss it, and there is no
Yes/No button window to find. It is a post-completion **exit stall**, not a
dismissable GUI prompt: the process has simply decided not to terminate after
`close exe`.

## Evidence

- `domains/thermal/celsius3d_tools.py` module docstring (lines 13-48): the detailed
  window-tree diagnosis — "the simulation itself COMPLETEs and writes the full result
  set (~20-30 s, identical to a fresh run), but afterwards the process stays alive
  and idle (CPU frozen, main Qt workbench window open, NO modal dialog with a
  clickable button in its window tree) — an 'Unsaved Project' Qt QMainWindow appears
  as a second visible top-level window (class `Qt5159QWindowIcon`, empty window text,
  zero visible/enabled children in EnumWindows) … WM_CLOSE / synthetic Enter /
  BN_CLICKED to any child do not dismiss it … It is NOT a GUI overwrite-confirmation
  prompt … it is a post-completion exit stall. It also happens on the very FIRST run
  of a 'fresh' project … even though re-runs reliably exhibit it."
- `.forjinn/skills/sigrity-celsius/SKILL.md` Ground rule 5 + Task 2b/2c: live
  demonstration — at `get_job_status` still `running` (pid 7552, returncode null)
  the full result set was already on disk in `runs\c3d_1\case_SS_W\`
  (`SR3d.dat` 21,172,917 bytes; `case_Result_Summary.dat` 1,623 bytes;
  `case_Result_Summary.json` 2,284 bytes; `case.log`: "INFO:Stress engine started
  and completed successfully!"). "The process will never exit on its own. Fix: kill
  it." `cancel_job` "still reports 'running' (cancel doesn't force-kill the idle
  proc here)"; `Stop-Process -Id <pid> -Force` "killed (work is already on disk)."
- SKILL.md Task 2c (the "not re-run-only" proof): "Reproduced on a **completely
  fresh, never-run** dir (`runs\c3d_2`, same sample): sim completed in ~30 s,
  `SR3d.dat`/`case_Result_Summary.*` written, yet the process still idled 'running'
  at the 120 s check. So a fresh-copy dir is necessary but **not sufficient** to
  avoid the stall."
- SKILL.md "Real numeric values" block confirms the stall hides a *correct,
  complete* result (e.g. 1stPrincipal_max 2.02918e+08 Pa, vonMisesStress_max
  1.14399e+08 Pa), so the failure mode is purely the process not exiting, not bad
  physics.

## Symptoms a caller observes

- `wait_for_job(job_id, timeout_seconds=90)` → `state: "running"` (STILL RUNNING
  after 90 s = the stall; the sim is already done).
- `get_job_status(job_id)` → `state: "running"`, a valid `pid`, `returncode: null`,
  CPU frozen.
- `tail_job_log` → only the startup banner.
- On disk in the project dir: `case_SS_W\SR3d.dat` + `case_Result_Summary.dat`/`.json`
  present at real size, and `case.log` contains "Stress engine started and completed
  successfully!".

## Pipeline Impact

A pipeline that gates on `state: "succeeded"` for Celsius3D will never see
`succeeded` for a successful solve — it times out or burns its whole budget waiting
for a process that will never self-exit. The actual engineering result is valid on
disk; only the process lifecycle is broken. Any "sign off when the job completes"
gate must be replaced by an artifact-exists gate + explicit kill.
