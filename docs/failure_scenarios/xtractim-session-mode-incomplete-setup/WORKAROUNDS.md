# Workarounds: XtractIM Session Mode → "incomplete setup" at begin simulation

## Verified Workaround

**Use `run_xtractim_workspace` (workspace-XML mode) with a complete pre-built `.ximx`, instead of session/Tcl compose mode.** This is the confirmed-live, artifact-producing path (SKILL.md Task 1: `XtractIM.exe -b Wirebond_EPA.ximx` → rc 0 in ~40 s wall, real RLC matrices: `EPAResult_*.eparesult`, `NetLoopInd.csv`, `PinInductanceAll_{LC,LB}.csv`, `PinRLofEachNet_*.csv`, `*_XtractIM.err`, and `Ref_Files/` IC/LB/LC matrix files, all written next to the `.ximx` — i.e., in the input's directory, **not** the job dir).

For session mode specifically: **if you already have a good `.ximx`, use it** (do not re-derive it via compose tools). Session mode is only appropriate for authoring a *new* setup for a *different* `.spd` layout, and even then you need the exact `sigrity::` commands that fully specify per-net stackup/geometry — which the current compose tools do not expose.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Use `run_xtractim_workspace` with the pre-built `Wirebond_EPA.ximx` | **worked.** rc 0, real RLC output (L/C/R CSVs + `.eparesult` + `Ref_Files/`). The confirmed, reliable path. | `SKILL.md:27-74` (Task 1); `tool_status.py:742-745` |
| 2 | Run the full 8-tool session-mode compose sequence (`start_xtractim_session` … `xtractim_run_session`) | **failed / false success.** rc 0, ~3 s, no RLC output; macro log `Failed to run the simulation because of incomplete setup`. Reproduced 2×. | `SKILL.md:116-161` (jobs `xtractim-53ba14b533`, `xtractim-4f8e65c43c`) |
| 3 | Ensure the session's `.spd` matches the `.ximx` it references (same physical layout, same directory) | **necessary but insufficient.** Even with a matched `.spd`, the rebuilt workspace still lacks per-net `ShapeSelected`/`RiseTime`/`PercentageCoupling`/`Advanced3DSettings` fields, so `begin simulation` still fails. | `SKILL.md:175-178` (layout must match) + `:157-161` (missing fields) |

## Prevention

1. **Default to workspace-XML mode** when a valid `.ximx` exists. Only reach for session/tcl compose mode to build a genuinely new setup for a layout you have no `.ximx` for.
2. **Never trust `state: succeeded` + rc 0 alone for session mode.** Read the **macro log** (`macro_<timestamp>.log`) for `begin simulation … incomplete setup / stackup` text before declaring an extraction done. This is the same "verify the artifact, not the return code" invariant (and the same artifacts-are-outside-job-dir issue — see `xtractim-workspace-artifacts-outside-jobdir`).
3. **Know which fields the compose tools cannot set** (per-net `Selected`/`ShapeSelected`, `RiseTime`, `PercentageCoupling`, `Advanced3DSettings` mesh). If a required `.ximx` needs them and the source is a `.spd` (not a `.ximx`), session mode will not reproduce them — the compose vocabulary stops at Mode/PackageType/Circuits/PGAnalysis/process+save.
4. **Keep the session's `.spd` and workspace in the same physical layout/directory** so the rebuilt workspace lines up with the layout it's meant to extract.

## Remaining Gaps

Session/Tcl compose mode **cannot currently produce a complete workspace** from a bare `.spd`, because the exposed compose tools do not include the `sigrity::` commands that write per-net geometry / stackup / advanced-mesh fields into the regenerated `.ximx`. The "incomplete setup" failure at `begin simulation` is therefore expected for from-.spd session-mode authoring today, not a fluke. Closing it requires either (a) adding the missing `sigrity::` per-net/stackup/mesh authoring commands to the compose tools and live-validating them, or (b) continuing to rely on a complete pre-built `.ximx` via workspace-XML mode. The manifest categorizes it `unreliable_intermittent` with `verified_workaround: YES (use run_xtractim_workspace)` — i.e., the workaround is to **route around session mode**, not to fix session mode itself.
