# aurora-form-replay-reliability-unverified

- **tool**: `run_aurora_workflow` (`sigrity_mcp/domains/aurora/scope_tools.py`), which drives `allegro.exe`'s Aurora Workflow Manager form via a batch-script (`-s aurora_workflow.scr`) form replay
- **status_category**: `built_untested` (the tool is implemented and self-documenting, but the Aurora-specific FORM-replay sequence has never been run live and end-to-end against a real board to confirm the result files are actually produced)
- **verified_workaround**: NO for the in-design path — use the standalone solver equivalents returned by `get_in_design_analysis_alternatives` (PowerDC/PowerSI/Clarity3D/XtractIM) for confirmed, batch-run signoff numbers

## What went wrong (an unverified capability, not a confirmed crash)

`run_aurora_workflow` is built on a sound, *proven elsewhere* mechanism — Allegro's
batch-script form replay (`FORM …` commands inside an `allegro.exe -s script.scr` run,
the same mechanism `allegro_placement_tools.py`'s Z-Router automation uses) — applied
to Aurora's Workflow Manager form. **But the Aurora-specific command sequence is not
live-verified.** The Allegro/OrCAD (SPB 22.1) installation and Aurora's real,
license-gated, GUI-only nature were confirmed by direct research against the on-disk
doc set, yet the exact `FORM workflow …` spellings used here were transcribed as
*best-effort* and never executed end-to-end against a real board to confirm the six
checks actually run and write their result files (`.impida`, `.cplida`, `.xtalkida`,
`.rpida`, `.rfltida`, `.irida`).

So the failure mode is one of **unreliability/unverified-correctness**, not a hard
bug: the tool may work (the replay mechanism is real), or its specific form/field
names (`workflow_type`, `start_analysis`, the `form.workflow` window name) may not
match the actual Aurora Workflow Manager dialog and the job could stall, error, or
run but produce no Aurora result files. There is no live "OK, produced a real
`*_ida` artifact" evidence line to fall back on.

## Root cause

Aurora is a menu/dialog-driven mode inside `allegro.exe` (selected at the GUI product
chooser, then driven through `Analyze -> Workflow Manager`), performing six checks —
impedance, coupling, crosstalk, return path, reflection, IR drop — each writing its
own proprietary result-file extension. The suite's earlier research pass concluded
"**zero CLI or SKILL automation surface exists for any of these six checks** — every
workflow is menu/dialog-driven only." A later pass found that Allegro's own form-replay
mechanism *can* drive that same form headlessly, and `run_aurora_workflow` wraps that.
The gap between these two findings is exactly the unverified part: the mechanism is
proven (Z-Router), the Aurora-specific transcription of it is not. The doc set
confirms the workflow *exists* but does not document the exact `FORM` field names, so
they were transcribed/best-guessed rather than confirmed.

## Evidence

- `domains/aurora/__init__.py` docstring (the underlying research finding, updated):
  "Aurora is a real, license-gated MODE inside `allegro.exe` itself … performing six
  checks — impedance, coupling, crosstalk, return path, reflection, IR drop — each
  writing its own proprietary result-file extension (`.impida`, `.cplida`,
  `.xtalkida`, `.rpida`, `.rfltida`, `.irida`). Critically: **zero CLI or SKILL
  automation surface exists** … now confirmed by direct evidence … One dead end …
  `aurora.exe` … is a same-name-different-product false lead …
  `allegrosigritypi.exe`/`allegrosigritysi.exe` are … plain GUI product-launchers …
  not independently batch-scriptable."
- `domains/aurora/scope_tools.py` module docstring (UPDATED FINDING): "Aurora's six
  checks are driven through `allegro.exe`'s Workflow Manager form, and Allegro's own
  batch-script replay mechanism (`FORM …` commands inside a `-s script.scr` run — the
  same mechanism `allegro_placement_tools.py`'s Z-Router automation uses) can drive
  that same form headlessly. `run_aurora_workflow` below wraps it." — i.e. the
  *mechanism* is borrowed from a proven tool, applied to Aurora without the Aurora
  sequence being live-tested.
- `domains/aurora/scope_tools.py:109-115` — the actual command sequence is a
  best-transcription, not confirmed output: `setwindow pcb`, `workflow manager`,
  `setwindow form.workflow`, `FORM workflow workflow_type "{workflow_type}"`,
  `FORM workflow start_analysis`, `FORM workflow close`, then `axlSaveDesign … ?mode
  "nocheck"` and `quit` — these field names are transcribed from the doc set, not from
  a verified successful run.
- `domains/aurora/__init__.py` bottom line: "building tools that claim to launch,
  configure, or query live Aurora sessions would be fabricating a capability this
  environment cannot provide … This domain provides one honest scope-notice tool and
  one practical bridge … so a caller who reaches for 'Aurora' still finds the right
  pre/post-layout tool instead of a dead end."
- `core/tool_status.py` — the `aurora`/`run_aurora_workflow` tooling is NOT in the
  `confirmed_live` set (only the Cadence/Power tools such as `celsius3d`, `powersi`,
  `powerdc`, `allegro`, etc. are), consistent with an unverified/`built_untested`
  status for this entry point. (The Z-Router replay it borrows is the confirmed piece.)
- `README.md:49-54` and `README.md:787`: documents Domain 4 as providing
  `run_aurora_workflow` (in-design Workflow Manager automation) **plus** standalone
  solver equivalents — the "plus standalone" is exactly the safe fallback because the
  in-design path is the unverified one.

## Symptoms a caller MIGHT observe (none confirmed for the Aurora sequence)

- `run_aurora_workflow(board_file=…)` submits a background `allegro.exe -s
  aurora_workflow.scr <board>` job and returns
  `{job_id, state: "running", …, workflow_type}` — no error at submit.
- If the FORM field names do not match the real dialog, the Allegro session could:
  stall on the Workflow Manager form (no modal dismissed by the replay), error with a
  "form/field not found"-style line, or complete the script run but write **no**
  `*_ida` Aurora result files (a silent no-op of the Aurora step), and
  `axlSaveDesign` saves the board regardless.
- Because there is no live "produced a real `.xtalkida`/`.impida`" evidence line, a
  caller cannot distinguish "worked" from "ran but produced nothing" without
  independently checking for the proprietary Aurora result files on disk.

## Pipeline Impact

Treated as **unverified**: an automated pipeline that relies on `run_aurora_workflow`
for an in-design SI/PI check has no confirmed end-to-end proof that the check ran and
that the result files were produced. For any decision-critical signoff, the pipeline
should use the standalone solver equivalents (which ARE confirmed in their respective
domains) rather than the unverified in-design replay.
