# XtractIM Session Mode Regenerates an Incomplete Workspace → "incomplete setup" at begin simulation

**Slug**: `xtractim-session-mode-incomplete-setup`
**Tool(s) affected**: `start_xtractim_session` → `xtractim_select_net` / `xtractim_set_mode` / `xtractim_set_package_type` / `xtractim_set_circuits` / `xtractim_set_pg_analysis_options` / `xtractim_process_and_save` → `xtractim_run_session` (XtractIM session/Tcl mode)
**Status category**: `unreliable_intermittent`
**Pipeline stage**: extraction (XtractIM 2.5D/3D package & PCB PG/EPA extraction)

## Symptom

The XtractIM **session/Tcl compose mode** runs the full 8-tool sequence (start → select net → set mode → set package type → set circuits → set PG options → process & save → run) to `state: succeeded, returncode 0` in ~3 s, but **produces no RLC output**. `list_job_files` shows only `macro.tcl`, `macro_<timestamp>.log`, `run.log`, `job.json`. The macro log's last lines are:

```
[Run Tcl Command: sigrity::begin simulation]
→ Tcl Result(Line 11):
   Failed to run the simulation because of incomplete setup. Ensure that
   stackup is set up correctly and start the simulation again.
```

So "the job succeeded (rc 0)" is a **false positive** — `begin simulation` aborted internally. Reproduced a second time (jobs `xtractim-53ba14b533` and `xtractim-4f8e65c43c`) with the identical error line.

## Root Cause

The compose-mode workspace **is regenerated** (the saved `.ximx` changes: 29 KB → 29 KB, `CircuitTopology="2"`), **but it is missing the detailed per-net geometry / stackup parameters that were in the original hand-authored `.ximx`.** The pre-built `Wirebond_EPA.ximx` (used by the working workspace mode) carries, per net, `Selected="1"`, `ShapeSelected="1"`, `RiseTime="100"`, `PercentageCoupling="5"`, plus `Advanced3DSettings` mesh sections. The session-mode compose tools (`xtractim_select_net`, `xtractim_set_mode`, `xtractim_set_package_type`, `xtractim_set_circuits`, `xtractim_set_pg_analysis_options`, `xtractim_process_and_save`) do **not** expose any way to re-create those fields, so the solver rejects the resulting workspace as incomplete at `begin simulation`.

This matches the extraction domain's standing rule: **session mode is not a shortcut that always works** — compose mode can regenerate the workspace, but the final `begin simulation` still fails (reported rc 0) when the rebuilt workspace's stackup isn't fully specified.

A second, related precondition: the `.spd` opened in session mode must be the **same physical layout** the `.ximx` references; if the session tool writes its own workspace to a different directory than where a matching `.spd`/`.ximx` pair lives, the two won't line up and you get the same "stackup not set up" error.

## Evidence

- `.forjinn/skills/sigrity-extraction/SKILL.md:116-178` (Task 3) — "**The verified failure — rc 0 but no extraction.** The job `succeeded` (rc 0) in 3 s. `list_job_files` shows only `macro.tcl`, `macro_<timestamp>.log`, `run.log`, `job.json`. No RLC output. The macro log's last line: `[Run Tcl Command: sigrity::begin simulation] → Tcl Result(Line 11): Failed to run the simulation because of incomplete setup…` **The compose-mode workspace is regenerated (29 KB → 29 KB, `CircuitTopology="2"` changed) but it's missing the detailed per-net geometry / stackup parameters that were in the original hand-authored `.ximx`, so `begin simulation` bails out silently.** Reproduced a second time (job `xtractim-4f8e65c43c`) with the identical error line."
- `.forjinn/skills/sigrity-extraction/SKILL.md:163-173` — "**What actually worked (Task 1) is the workspace-XML mode** — the pre-built `Wirebond_EPA.ximx` carries every net's `Selected="1"`, `ShapeSelected="1"`, `RiseTime="100"`, `PercentageCoupling="5"`, plus `Advanced3DSettings` mesh sections. The session-mode tools don't yet expose a way to re-create any of those fields… **Mistake #1 for session mode:** treating it as a drop-in replacement for `run_xtractim_workspace`. It's not — if you already have a good `.ximx`, **use it**."
- `.forjinn/skills/sigrity-extraction/SKILL.md:175-178` — "Second thing to know: the `.spd` you open in session mode must be the same physical layout the `.ximx` references."
- `.forjinn/skills/sigrity-extraction/SKILL.md:21-23` (inviolable rule 2) — "Session mode is not a shortcut that always works. XtractIM's compose mode can regenerate the workspace but the final `begin simulation` will still fail rc 0 if the rebuilt workspace's stackup isn't fully specified."
- `sigrity_mcp/domains/extraction/xtractim_tools.py:69-176` — the compose tools (`xtractim_select_net` … `xtractim_process_and_save`) only append `sigrity::` lines; none set per-net `ShapeSelected`/`RiseTime`/`PercentageCoupling`/`Advanced3DSettings` mesh fields. `xtractim_run_session` (`:166-176`) appends `sigrity::apply OutputACR {1}` + `sigrity::begin simulation {!}` then launches `XtractIM.exe -b -tcl <script>`.
- `sigrity_mcp/core/tool_status.py:76,742-745` — `"xtractim": "confirmed_live"`, confirmed against the **workspace-XML** sample (`XtractIM.exe -b Wirebond_EPA.ximx`, genuine S600.2 RLC extraction) — the live confirmation is for **mode (a) workspace XML, not session/Tcl mode (b)**.

## Pipeline Impact

A pipeline that uses XtractIM session mode (`start_xtractim_session` + compose tools + `xtractim_run_session`) to build a *new* extraction setup for a different `.spd` will get a **silent false success** (rc 0, no RLC matrices) and must catch the `incomplete setup` text in the macro log. Because the job reports `succeeded`, a naive state-based check will pass the no-extraction result downstream. The reliable path on this machine remains **workspace-XML mode** (`run_xtractim_workspace`) with a complete pre-built `.ximx`.
