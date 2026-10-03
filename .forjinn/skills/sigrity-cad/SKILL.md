---
name: sigrity-cad
description: Allegro/OrCAD CAD domain (SPB 22.1) — report/DRC/dbdoctor, SPECCTRA autoroute, Gerber (artwork) export, SKILL PCB authoring (including real multi-layer/rigid-flex stackup authoring via generate_multilayer_stackup, verified live 2026-09-30, and real copper shape/plane-pour authoring via allegro_create_copper_shape, verified live 2026-10-02), and run_tool_pipeline, all verified live. Use for board analysis, DRC, SPECCTRA routing, Gerber/manufacturing export, SKILL geometry/padstack/film/stackup/copper-shape authoring, and multi-step job pipelines.
---

# Sigrity CAD domain — Allegro PCB (report/DRC/DRC, SPECCTRA, Gerber, SKILL, pipeline)

Platform/job rules inherit from the parent `sigrity` skill: `run_*`/`*_run_session` never block
(poll `wait_for_job`/`get_job_status`), `state` is a liar in BOTH directions (verify artifacts),
and `list_job_files` is NOT where most results live. Below is what is true for THIS domain,
verified end-to-end on live runs on 2026-09-27 (SPB_22.1 at `C:\Cadence\SPB_22.1`).

Sample board (routed, ground truth = 81 components, 2 DRC errors / 1 short, DRC state OUT OF DATE,
251 pins, 75 nets, 191 drills, 100% connection completion):
`C:\Cadence\SPB_22.1\tools\capture\samples\PCB-Layout\Fault-Detector\allegro\fault-detector_allegro_routed.brd`
Copy read-only sources into `runs\<task>\fd.brd` before running (`copy_file`), never edit a shipped sample.

## Task 1 — EASY: `run_allegro_report` → poll → read report

```
run_allegro_report(board_file="…\\t1_report\\fd.brd", report_code="sum", output_file="…\\t1_report\\sum_rep.rpt")
  -> {job_id, state:"running", job_dir, command:[report.exe,-v,sum,<brd>,<rpt>]}
wait_for_job(job_id, timeout_seconds=180) -> state:"succeeded", returncode:0   (~0.75 s)
```
- **Verified artifact** (NOT the job dir — job dir only has `dangling_lines.rpt`+logs): `sum_rep.rpt`
  (2604 B) at the `output_file` path. Contents: `Package Symbols: Total(81)`, `DRC Errors: 2`,
  `DRC State: OUT OF DATE`, `Pins(251)`, `Nets … Total(75)`, `Drills: Total(191)`,
  `Connection Completion … 100.00%`. Matches the board's ground truth exactly.
- **Error hit**: none. But note the report writes to `output_file`; if you omit it, look in the job dir.
- **#1 mistake**: trusting `state:"succeeded"`+rc0 without reading the report, or going to the job dir
  for the summary — the artifact is at `output_file`.

## Task 2 — MEDIUM: `run_allegro_batch_drc` — the "launcher-exits-early" state lie

```
run_allegro_batch_drc(board_file="…\\t2_drc\\fd.brd", nographic=true)     # nographic DEFAULT true
  -> {job_id, state:"running", job_dir, command:[batch_drc.exe,-nographic,<brd>]}
get_job_status(job_id)   # -> STILL state:"running", returncode:null  (even though work is done)
list_job_files(job_id)   # -> batch_drc.log, dbdoctor.log, job.json, run.log already exist
```
- **Verified**: the `state` lie reproduced exactly. `get_job_status` returned `running` /
  `returncode:null` (the launcher detached; `job.json` never flipped to a terminal state) while `list_job_files`
  already showed `batch_drc.log` + `dbdoctor.log`. Read them, not the state:
  - `batch_drc.log` → `DRC update completed … Total number of DRC errors  2`
  - `dbdoctor.log`  → `Original DRC errors:   2` / `Updated DRC errors:    2` / `DRC done; 2 errors detected.`
- **Error hit**: `tail_job_log(job_id)` returned 0 lines (the empty `run.log`) — useless here. The real
  output is `batch_drc.log` / `dbdoctor.log` in the job dir, read via `read_job_output_file`.
- **#1 mistake**: waiting for `state` to become `succeeded`/`failed` — it never does. Detect completion by
  reading `batch_drc.log` for "DRC update completed" (and the error count in `dbdoctor.log`). Do not
  `wait_for_job` indefinitely on this job.

## Task 3 — MEDIUM: SPECCTRA autoroute (export .dsn → route → read .sts + .ses)

```
run_spif_export_to_specctra(board_file="…\\t3_specctra\\fd.brd") -> {job_id, …}
wait_for_job(job_id, 180) -> state:"succeeded", rc 0
list_job_files(job_id)   # -> fd.dsn (85 KB, real Specctra deck), fd_rules.do, fd_forget.do
```
The `.dsn` lands in the **job dir** (`spif_batch-<hash>\fd.dsn`). `fd_rules.do` is a ready-made
constraints reference. Then write a minimal `.do` (use the write tool) pointing all paths at a runs dir:
```
# route.do
bestsave on C:\Users\aicoe\Desktop\Sigrity\runs\t3_specctra\route\best.wir
status_file C:\Users\aicoe\Desktop\Sigrity\runs\t3_specctra\route\route.sts
smart_route
write session C:\Users\aicoe\Desktop\Sigrity\runs\t3_specctra\route\routed.ses
report status C:\Users\aicoe\Desktop\Sigrity\runs\t3_specctra\route\final.sts
```
```
run_specctra_autoroute(dsn_file="…\\spif_batch-<hash>\\fd.dsn", do_file="…\\t3_specctra\\route.do")
wait_for_job(job_id, 300) -> state:"FAILED", returncode:4        #  <-- SEE GOTCHA BELOW
```
- **GOTCHA (the one to know for this tool)**: `specctra.exe` exits **rc 4 EVEN ON FULL SUCCESS**.
  `wait_for_job` reports `state:"failed"`, rc 4 — that is the documented normal exit, NOT a failure.
  Never treat rc 4 as an error. Judge success by the `.sts` files.
- **Verified artifact**: `final.sts` → `Completion   =  100.00%   Unconnections = 0`, `Nets=75 Connections=163`,
  `Routed length=451495.010`, per-layer TOP/BOTTOM routing tables. All written into the runs dir:
  `routed.ses` (48,872 B, real), `best.wir` (34,831 B), `final.sts`, `route.sts`.
- **Then the known-broken import (try ONCE, then move on)**:
  ```
  run_specctra_import_session(board_file="…\\t3_specctra\\fd.brd", session_file="…\\route\routed.ses")
  tail_job_log(job_id) -> "mh_appl_restore(): Nothing to restore"
                          "ERROR(SPMHDB-238): The design is corrupted. …"
  ```
  - **Crash evidence that DOES appear**: a real `spif_batch_P00122.1_AllegroMiniDump.dmp` in the job dir
    + the `SPMHDB-238` log line. This is the documented product bug (known-blocked).
  - **REFINEMENT to the documented claim**: `get_job_status` did **NOT** gain a `crash` field — the worker
    (`spif_batch.exe -i`) crashes/detaches and the launcher never reaps it, so `job.json` stays
    `state:"running"` / `returncode:null` forever. `crash_signature()` (core/jobs.py:243) only fires when
    `returncode` is a 0xC0000005-family code, which this detached crash never produces. So detect the crash
    by the **`.dmp` artifact + SPMHDB-238 log line**, not the `crash` field. `cancel_job` on it returns the
    zombie still `running` (can't kill the detached worker).
- **#1 mistake**: aborting the route because `state:"failed"`/rc 4, or waiting for `state` on the import.
  Route success = read `final.sts` for `Completion = 100.00%` + confirm `routed.ses` is non-empty. Import via
  `run_specctra_import_session` (`spif_batch.exe -i`) is a known product bug (SPMHDB-238 crash) — don't burn
  time on it.
- **USE `run_allegro_specctra_import` INSTEAD — CONFIRMED LIVE end-to-end (2026-10-01), this is the real,
  working import path**:
  ```
  run_allegro_specctra_import(board_file="…\\fd.brd", session_file="…\\routed.ses", output_file="…\\fd_imported.brd")
  wait_for_job(job_id, 90) -> state:"succeeded", rc 0
  ```
  then independently verify with `run_allegro_report(board_file="…\\fd_imported.brd", report_code="sum", ...)`
  (SKILL-free, no modal risk) — expect `Connection Completion: Total(100.00%)` matching the `.ses`'s own stats,
  and the output file's size/sha1 genuinely different from the pre-import board.
  - **Do NOT call this tool with an unpatched/older copy of `spif_specctra_tools.py`** — a real, 3-for-3
    reproducible indefinite hang existed here until 2026-10-01 (0% CPU, no window, `run.log` stuck forever at
    the 3-line startup banner) caused by a literal typo in the emitted script line (`specctra in "<path>"`,
    two words — not a real command; the real one is `specctra_in`, one word). If you ever see this tool hang
    silently again with that exact signature, check `sigrity_mcp/domains/cad/spif_specctra_tools.py` still
    emits `specctra_in` (not `specctra in`) and still closes the `spif_in` dialog
    (`setwindow form.spif_in` / `FORM spif_in CLOSE` / `setwindow pcb`) before anything else runs — skipping
    that close step makes every following command (including the save) silently no-op with a `Finish current
    command first` error you'll only see in the design's own `allegro.jrl`, never in the job's `run.log`.
  - See `core.tool_status`'s `allegro` entry (2026-10-01 note) for the full live-repro evidence and the
    third, unrelated bug found/fixed alongside it (`axlSaveDesign`'s `?noCheck` keyword doesn't exist; the
    real no-check option is `?mode "nocheck"`).

## Task 4 — COMPLEX: Gerber (RS274X) end-to-end via SKILL films → artwork

Films must be authored **in the board** before artwork.exe emits anything. One session composes films + save,
then a standalone artwork job renders. `output_file` on `allegro_save_design` left `None` = save in place
to the already-loaded board path.
```
start_allegro_session()                                              -> {session_id}
allegro_create_film(session_id, film_name="TOP",    layers=["ETCH/TOP"])
allegro_create_film(session_id, film_name="BOTTOM", layers=["ETCH/BOTTOM"])
allegro_save_design(session_id)                                      # no output_file -> saves loaded board
allegro_run_session(session_id, board_file="…\\t4_gerber\\fd.brd")   # board_file REQUIRED here; appends bare `quit`
wait_for_job(job_id, 240) -> state:"succeeded", rc 0   (~17 s; allegro.exe loads board 15-20 s)
tail_job_log(job_id)   # only the Allegro banner — film/save results are NOT in the log
run_allegro_generate_artwork(board_file="…\\t4_gerber\\fd.brd")      # all films (or film_names=[…])
wait_for_job(job_id, 180) -> state:"FAILED", returncode:1   #  <-- SEE GOTCHA
list_job_files(job_id)   # -> TOP.art, BOTTOM.art, photoplot.log, run.log
```
- **GOTCHA**: `artwork.exe` exits **rc 1 ("had warnings") even on full success** (missing `art_param.txt` /
  outline rect warnings). `state:"failed"` rc 1 here is normal. Judge by the `.art` files + `photoplot.log`.
- **Verified artifact** (in the artwork job dir): `TOP.art` (12,209 B) and `BOTTOM.art` (6,036 B), both real
  RS274X Gerber — `G04 File Format:  Gerber RS274X`, `G04 Layer:  ETCH/TOP`, `%FSLAX25Y25*MOIN*%`,
  `%ADD10C,.005*%`, real `G01 … D01*` plot data. `photoplot.log` → `SUMMARY: TOP created with warnings /
  BOTTOM created with warnings`.
- **Error hit**: none on the happy path. If a prior allegro job against the same board path was killed, a
  stale `<brd>.lck` makes the next `allegro.exe` hang on a modal "design locked" dialog — the tool clears a
  stale sibling `.lck` before launch, but if you hand-ran allegro, delete `<brd>.lck` first.
- **#1 mistake**: running `run_allegro_generate_artwork` on a board that has no film records — it emits
  nothing. Always `allegro_create_film` + `allegro_save_design` in a SKILL session (on that same board copy)
  first, then artwork. And don't chase rc 1 / empty `tail_job_log` as failure.

## Task 5 — COMPLEX: `run_tool_pipeline` with `${name.field}` placeholders

```
run_tool_pipeline(stop_on_error=true, steps=[
  {"tool":"run_allegro_report",  "args":{board_file:"…\\t5_pipeline\\fd.brd", report_code:"sum",
     output_file:"…\\t5_pipeline\\sum_rep.rpt"}, "save_as":"rep"},
  {"tool":"run_allegro_dbdoctor","args":{board_file:"…\\t5_pipeline\\fd.brd", check_only:true,
     output_file:"…\\t5_pipeline\\dbdoctor.log"}, "save_as":"doc"},
  {"tool":"wait_for_job","args":{job_id:"${rep.job_id}", timeout_seconds:120}, "save_as":"w_rep"},
  {"tool":"wait_for_job","args":{job_id:"${doc.job_id}", timeout_seconds:120}, "save_as":"w_doc"},
])
  -> {step_count:4, succeeded_count:4, failed_count:0}
```
- **Verified**: `${rep.job_id}` / `${doc.job_id}` resolved to the real job_ids and both `wait_for_job`
  results came back — `rep` → `succeeded` rc 0; `doc` → `state:"failed"` rc 1. So: placeholders thread
  results between steps, `wait_for_job` works inside a pipeline, and the two exit behaviors are distinct
  (report rc 0, dbdoctor rc 1).
- **dbdoctor artifact gotcha**: `check_only=True` (default) + a board whose DRC is OUT OF DATE exits **rc 1**
  and reports in the **job dir** `dbdoctor.log` (→ `WARNING(SPMHDB-42): Run batch DRC to regenerate DRC
  errs`; `1 warnings, 0 errors detected, 0 errors could be fixed`). The `-outfile` path I passed stayed
  **0 bytes** — dbdoctor writes its real report to the job dir, not the `-outfile` arg. Read
  `<job_dir>\dbdoctor.log`.
- **HARNESS trap (not a server bug — but you MAY hit it)**: if you drive this through the local
  `runs/mcp_client.py` helper and nest `${…}` placeholders inside `run_tool_pipeline`'s `steps`, the helper's
  own `_sub` re-substitutes them against its *outer* (empty) `saved` first, turning `"${rep.job_id}"` into
  `{}` and failing step validation. The real MCP server resolves `${name.field}` within a pipeline correctly
  (proved by a direct `Client(mcp)` call to `run_tool_pipeline` → 4/4 succeeded). Keep placeholders OUT of
  the nested steps when using the helper, or drive the pipeline directly.
- **#1 mistake**: passing a value a step didn't return as a placeholder target. `run_*` job tools return only
  `{job_id, state, job_dir, command}` — they do NOT echo back `board_file` or other inputs, so
  `${rep.board_file}` resolves to `{}` / errors. Thread `job_id` (always present); pass other literals directly.

## Task 6 — COMPLEX: real multi-layer (rigid-flex) stackup authoring via `generate_multilayer_stackup`

`generate_18layer_rigid_flex_stackup` only ever wrote human-readable `#`-comment lines — it
never touched a real board. The real, executing path is `generate_multilayer_stackup`
(`rigid_flex_stackup_tools.py`), which queues one real `axlXSectionCreate` SKILL call per
layer into an `allegro_tools` session, same Model B session mechanics as everything else in
this file. `allegro_create_stackup` (`allegro_tools.py`) was also upgraded in the same pass:
it used to emit a bare, attribute-less `(axlXSectionCreate nil 'position)` (only ever created
one unnamed default-material dielectric); it now builds a real
`make_axlXSection(?name ?layerType ?material ?thickness)` defstruct, so a single call can
author one fully-specified layer.

```
start_allegro_session()                                          -> {session_id}
generate_multilayer_stackup(session_id, layers=[
    {"name":"L2_GND",  "layer_type":"PLANE",     "material":"COPPER",    "thickness_mil":1.4},
    {"name":"L3_SIG1", "layer_type":"CONDUCTOR", "material":"COPPER",    "thickness_mil":0.7},
    ... ])                                                        # queues len(layers) SKILL lines
allegro_save_design(session_id)                                   # REQUIRED -- nothing persists without this
allegro_run_session(session_id, board_file="…\\t6_stackup\\fd.brd")
wait_for_job(job_id, 120) -> state:"succeeded", rc 0   # SEE GOTCHA below re: a modal dialog
run_allegro_report(board_file="…\\t6_stackup\\fd.brd", report_code="x-section",
                    output_file="…\\t6_stackup\\xsection.rpt")     # the REAL, independent verify step
wait_for_job(job_id, 60) -> state:"succeeded", rc 0
```

- **`layers` is TOP-TO-BOTTOM order** (index 0 = physical top). Each dict:
  `name` (required), `layer_type` (required; "CONDUCTOR"/"PLANE"/"DIELECTRIC"/"MASK"),
  `thickness_mil` (real), `material` (real, e.g. "COPPER"/"RA_COPPER"), plus
  `zone`/`ref_plane`/`hatched_plane` which are **informational only** (see LIMITATION below).
- **ORDERING GOTCHA (the one that will bite you)**: every layer is queued via
  `axlXSectionCreate(nil 'bottom <defstruct>)` **in the same order you pass them** — do NOT
  reverse the list. A literal reading of Cadence's own vendored doc tip
  (`axlXSectionCreate.txt`: "If populating multiple internal layers, use the 'bottom option
  and build the stackup from bottom to top") suggests queuing the physically-bottom-most
  layer first; this was tried and LIVE-VERIFIED WRONG — it produced the exact inverted order
  (first-queued landed nearest the top, last-queued landed nearest the true bottom).
  Empirically, each successive `'bottom` insert lands directly adjacent to the board's real
  outer BOTTOM layer, pushing earlier inserts further up — so queuing chronologically in your
  own top-to-bottom order is what lands correctly. `'top'`/`'afterBottom` are restricted by
  Allegro to unnamed dielectric/MASK layers for PCB designs, so `'bottom'` is the only
  endpoint usable for a real named CONDUCTOR/PLANE stackup.
- **TOP/BOTTOM NAME-COLLISION GOTCHA**: if your `layers` list reuses the literal names "TOP"/
  "BOTTOM" (as `build_18layer_rigid_flex_stackup_definition()`'s own layer 1/18 do, matching
  the board's default outer layer names), those two specific creates are a **silent no-op** —
  no duplicate, no error, no change to the existing TOP/BOTTOM entry's thickness/material.
  Confirmed live on the full 18-layer definition: all 16 INTERNAL layers (L2_GND..L17_GND4,
  including the RA_COPPER flex pair) landed correctly; TOP/BOTTOM stayed exactly as the
  board's pre-existing defaults. Either drop "TOP"/"BOTTOM"-named entries from `layers`
  (the physical outer layers already exist) or separately drive `axlXSectionGet(nil "TOP")` +
  `axlXSectionModify` + `axlXSectionSet` to actually change them (not wrapped by any tool yet).
- **GOTCHA — modal dialog, now handled automatically (no agent action needed)**: a
  stackup-authoring `allegro_run_session` launch can raise an unlabeled modal Qt dialog a
  couple seconds in (before the board even finishes loading) — content-independent, most
  likely the same general Allegro launch flakiness documented above (product-chooser/
  license dialogs, historically ~1-in-4), reproduced 4-for-4 in one round of testing and
  independently re-confirmed live (see `core.win32gui_helper.DismissWatcher`'s docstring
  for the exact window shape captured: a `Qt5QWindowIcon`-classed popup whose title is
  identical to the app's own name, with the main shell window's `enabled` bit genuinely
  flipped to 0 for as long as it's up). Previously this required the calling agent to
  separately poll `core.win32gui_helper.auto_dismiss_dialogs(pid, timeout=...)`
  concurrently — that was a real, confirmed-live gap (a production job hung 2.5+ hours on
  exactly this with no agent-side way to recover). **As of this fix, every
  `tool="allegro"` session job (i.e. every `allegro_run_session`/`run_allegro_*_import`/
  zrouter-run call that goes through `core.tclsession.run_session`) automatically starts
  a background `win32gui_helper.DismissWatcher` for the job's whole lifetime and stops it
  when the job ends — there is nothing for the calling agent to do.** Dismissal has zero
  observed effect on correctness — every run's `x-section` read-back matched its input
  exactly once dismissed.
- **Verified artifact**: `run_allegro_report(..., report_code="x-section")`'s CSV-style report
  (`Subclass Name,Type,Material,Thickness (MIL),...`) — this is the ONLY reliable verify step;
  SKILL return values never surface in the job log for `axlXSectionCreate` (just the Allegro
  banner). Confirmed live 3 times: a 3-layer test (TOPTEST/PLANETEST/BOTTOMTEST, CONDUCTOR/
  PLANE/CONDUCTOR, COPPER/COPPER/RA_COPPER, 1.4/1.4/0.7 mil) landed as
  `TOP, DIELECTRIC, TOPTEST, PLANETEST, BOTTOMTEST, BOTTOM` with every attribute exact; the
  full 18-layer definition landed all 16 internal layers correctly (see above).
- **LIMITATION (honest, checked against this install's vendored SKILL docs)**: only
  `name`/`layerType`/`material`/`thickness` are real, settable xsection attributes (confirmed
  against `axlXSectionGet.txt`'s own attribute table and the real example
  `share/pcb/examples/skill/dbcreate/xsection.il`). There is **no SKILL attribute anywhere**
  for an explicit "reference plane" assignment — searched the full attribute table plus every
  `axlCNS*`/`axlCns*` Constraint-Manager function on this install. Allegro's impedance
  calculator infers a signal layer's reference plane from stackup ADJACENCY to a PLANE layer,
  not from a settable field — so `ref_plane`/`zone`/`hatched_plane` in a layer dict are
  metadata echoed back for bookkeeping only, not real SKILL calls. Order your layers so the
  intended plane is physically adjacent to its signal layer.
- **#1 mistake**: reversing the `layers` list expecting `'bottom` to need bottom-most-first
  (it's the opposite — see ORDERING GOTCHA), or trusting a `state:"succeeded"` without an
  independent `x-section` report read-back, or expecting a "TOP"/"BOTTOM"-named entry in your
  list to actually change the board's real outer layers.
- **FIXED 2026-10-01 — `layers` arriving as a JSON string no longer errors**: a calling model
  (observed live: qwen3-max via vLLM, through the real forji-desk app) serialized `layers`
  (and other `list`/`dict`-typed arguments elsewhere in this suite) as a JSON-encoded *string*
  (e.g. `"[{\"name\":...}]"`) instead of a native array. FastMCP 4.0.4's strict pydantic
  argument validation used to reject that outright with a `list_type` `ValidationError` before
  this tool's body ever ran. A server-wide middleware
  (`sigrity_mcp/core/argument_coercion_middleware.py`, registered once in `mcp_app.py`) now
  pre-parses any string-valued argument for a parameter whose schema doesn't accept a plain
  string, for EVERY tool in the suite — not just this one. So `layers=[...]` and
  `layers='[...]'` (JSON string) both work identically now; no client-side workaround needed.
  A parameter that legitimately accepts either a string or a list (e.g. `ref_des: Union[str,
  list[str]]` elsewhere in this suite) is left alone either way, since a plain string is
  already valid there.

## Task 7 — COMPLEX: real copper shape / plane pour via `allegro_create_copper_shape`, and the PowerDC pdcVRM investigation it was built to settle

`generate_multilayer_stackup` (Task 6) authors layer STRUCTURE only — a "PLANE"-typed layer it
creates has zero actual copper on it. `allegro_create_copper_shape` (`axlDBCreateShape`,
`allegro_geometry_tools.py`) closes that gap: given a layer name, a net name, and an explicit
closed boundary, it pours a real, solid-filled, net-bound copper shape onto that layer, same
Model B session mechanics as everything else in this file.

```
start_allegro_session()                                           -> {session_id}
generate_multilayer_stackup(session_id, layers=[... incl. {"name":"L2_GND","layer_type":"PLANE",
    "material":"COPPER","thickness_mil":1.4}, ...])                # Task 6
allegro_create_copper_shape(session_id, layer="L2_GND", net_name="GND",
    points=[[0,0],[34000,0],[34000,22000],[0,22000]], dynamic=True) # the board's own real extents
                                                                     # (from run_allegro_report
                                                                     # report_code="sum" on THIS board
                                                                     # -- always read real extents,
                                                                     # never assume a size)
allegro_save_design(session_id)
allegro_run_session(session_id, board_file="…\\fd.brd")
wait_for_job(job_id, 120) -> state:"succeeded", rc 0
```

- **`layer` is the bare xsection layer name** (e.g. `"L2_GND"`, matching `generate_multilayer_
  stackup`'s `name`) — the tool builds the real class/subclass string itself: `dynamic=True`
  (default) → `"BOUNDARY/<layer>"` (a real connectivity-driven flood-fill pour); `dynamic=False`
  → `"ETCH/<layer>"` (a plain static filled shape). Per the vendored
  `axlDBCreateOpenShape.txt` doc: "A static shape is created if you create shape on class ETCH,
  dynamic shapes are created if class is BOUNDARY … The same rule also applies to
  axlDBCreateShape."
- **`points` is REQUIRED — there is deliberately no auto-derive-from-board-outline default.**
  An earlier design considered defaulting to `(car (axlPolyFromDB (car (axlDBGetShapes "BOARD
  GEOMETRY/OUTLINE"))))` ("pour the whole board, no coordinates needed") and this was
  LIVE-TESTED AND DISPROVEN against the real Fault-Detector sample: `axlDBGetShapes("BOARD
  GEOMETRY/OUTLINE")` returned `nil` — this board's physical outline is drawn as plain LINE/ARC
  segments, not a shape database object (confirmed: the board has 157 real shapes total, ALL of
  them `PACKAGE GEOMETRY/*` component silkscreen/assembly/place-bound outlines — zero `BOARD
  GEOMETRY/*` shapes of any kind). A components-bounding-box fallback
  (`axlDBGetExtents(axlDBGetDesign()->components nil)`) was also tried live and returned a
  degenerate `((0.0 0.0) (0.0 0.0))` box. So: read the board's real extents first
  (`run_allegro_report(..., report_code="sum")` → `Drawing Extents XL/YL/XU/YU`, in mils) and
  pass them as an explicit rectangle, or pass your own exact outline/sub-region polygon.
- **Verified LIVE, 3 independent ways** (fresh board copy, real 8-layer stackup with 2 new
  PLANE layers, pour on `L2_GND`/net `GND`):
  1. An in-session SKILL query right after creation (`axlDBGetShapes("BOUNDARY/L2_GND")`,
     captured to a file via SKILL's own `outfile`/`fprintf` since return values never surface in
     the job log) → 1 real shape dbid, not nil.
  2. A SECOND, fully independent `allegro.exe` launch (no shared memory with the session that
     created it) opening the already-SAVED board from disk found the shape on BOTH
     `BOUNDARY/L2_GND` AND `ETCH/L2_GND` (1 each) — the dynamic/BOUNDARY shape genuinely
     generates real computed ETCH copper underneath it, matching
     `axlShapeChangeDynamicType.txt`'s own description of BOUNDARY-class dynamic shapes
     generating real ETCH-layer geometry.
  3. Translating the board to `.spd` via the already-confirmed PowerSI BRD-bridge (Task 3 in
     `sigrity-si`'s SKILL.md: `start_powersi_session(spd_file=brd)` +
     `powersi_save_document(spd_file=out.spd)` + `powersi_set_frequency_sweep` +
     `powersi_add_ports_auto` + `powersi_run_session`) produced a `.spd` containing a real
     `.Shape Plane$L2_GNDpkgshape` / `PatchSignal$L2_GND Shape = Plane$L2_GNDpkgshape Layer =
     Signal$L2_GND` block with real `Node<n>::GND … Layer = Signal$L2_GND` entries — an entirely
     separate translation engine (SPDIF) independently confirming the pour is real geometry.
- **The downstream hypothesis this was built to test — NOT CONFIRMED.** The working theory was
  that PowerDC `sigrity::add pdcVRM -auto -net {power,ground} -ckt {RefDes} -voltage {v}` fails
  with `"The net pair '-net {power net name, ground net name}' is not specified."` on
  `generate_multilayer_stackup`-built boards because there's no real copper for a VRM to bind
  to. Tested live end-to-end (pour real `GND`-bound copper on `L2_GND` → translate to `.spd` →
  `start_powerdc_session` → `powerdc_add_vrm(power_net="+15V", ground_net="GND", ref_des="U1",
  voltage=15.0)` → `powerdc_run_session`): **the exact same error reproduced, byte-for-byte**,
  read from the real `macro_<ts>_<pid>.log` PowerDC writes next to the attached `.spd` (NOT
  `list_job_files`/job dir — same PowerDC log-location fingerprint documented in
  `sigrity-pi`'s SKILL.md). Ruled out across 4 separate live runs, each reproducing the
  identical error text: real copper present vs the original no-copper board; a net name with a
  `+` character (`+15V`) vs a plain alnum net (`SUPPLYBUS`) from the same board's real net list;
  `powerdc_set_simulation_mode` queued after `-attach` (this suite's actual order) vs before it
  (matching Cadence's own shipped `MB.tcl` sample exactly); `-auto` vs the doc's alternate short
  spelling `-a`. The emitted Tcl line is byte-for-byte the same SHAPE as every real
  Cadence-authored sample on this install and matches the official doc format
  (`doc/pdc_ug/c9_TCL_Create_by_Using_Existing_Components.html`) exactly — so this is not an
  argument-syntax bug in `powerdc_add_vrm`. **Leading (unconfirmed) hypothesis for a future
  pass**: every real Cadence sample's power-side value is literally the string `PowerNets`
  (never an actual board net name), and this suite's own confirmed-live `IR_Package.pdcx`
  contains literal `PowerNets`/`GroundNets` attribute values in its saved workspace XML —
  suggesting `-auto -net {X,Y}` resolves against PRE-DEFINED PowerDC Net Classes (set up via the
  GUI or Analysis Model Manager), not raw net-name strings, so a bare SPDIF-translated `.spd`
  with no Net Class/AMM setup may never satisfy it regardless of real net names or real copper.
  See `core.tool_status`'s `powerdc`/`allegro` notes for the complete investigation log.
- **#1 mistake**: assuming a `pdcVRM` net-pair failure means missing plane copper — it does not,
  necessarily; here it reproduced identically with real, independently-verified copper present.
  Don't skip the auto-derive-from-outline default either, expecting it to "just work" — read the
  board's real extents first (`report_code="sum"`) and pass explicit `points`.

## Task 8 — EASY once you know the real keywords: `run_allegro_extracta` (BOM/nets/components/pins/DRC dump)

```
run_allegro_extracta(board_file="…\\t8_extract\\fd.brd", view_type="bom", output_file="…\\t8_extract\\fd_bom.txt")
  -> {job_id, state:"running", job_dir, command:[extracta.exe,<brd>,<cmdfile>,<outfile>], command_file}
wait_for_job(job_id, timeout_seconds=60) -> state:"succeeded", returncode:0   (~0.3 s)
```
- **Verified artifact**: the `output_file` path, a `!`-delimited flat text dump (header row prefixed `A!`,
  a `J!` metadata row, then one `S!...` row per record). `view_type="drc"` genuinely lists real DRC
  violations (confirmed: real Package-to-Package / Line-to-Line spacing errors on the sample board).
- **FIXED 2026-10-02, was a real 100%-repro bug**: `view_type` in `{bom,nets,components,pins,testpoints,drc}`
  builds a command file from a built-in template — those templates used to contain invented
  view-name/field-name keywords (`NETS`, `COMPONENTS`, `PINS`, `COMP_LOCATION_X`, ...) that extracta.exe
  rejects outright with `ERROR(SPMHDX-10): Illegal view name.` for every single view_type, 100% of the
  time. Now fixed to use real keywords copied from Cadence's own shipped `share/pcb/text/views/*.txt`
  files (`COMPONENT`, `LOGICAL_PIN`, `COMPONENT_PIN`, `COMPOSITE_PAD`, `DRC_ERROR`). If you ever need a
  view this tool doesn't cover, copy another real file from that directory rather than guessing a
  keyword — extracta's command-file syntax is NOT self-explanatory and wrong keywords fail silently at
  the job-result level.
- **#1 mistake, the reason this bug went undiagnosed for 10+ calls in a single conversation**: the real
  error (`Illegal view name`) is ONLY in `extract.log`, and extracta.exe writes that file into its own
  process's cwd — which is the **job's own `job_dir`** (same directory as `run.log`/`job.json`), NOT next
  to `board_file`/`output_file`. `run.log` itself only ever says the unhelpful "Extract ended ... see
  extract.log for errors." with no path. On any `allegro_extracta` failure, `list_job_files(job_id)` +
  `read_job_output_file(job_id, relative_path="extract.log")` — not a guess at the input directory — is
  the only way to see why.

## Task 9 — COMPLEX: real routing-quality analysis and surgical manual rip-up-and-refix

Investigated live (2026-10-02) whether this suite can (a) analyze routing quality beyond
pass/fail DRC and (b) surgically rip up and refix ONE bad route without redoing the whole
board. Used the real routed Fault-Detector sample (`scenario_6/fd.brd`: 81 components, 75
nets, 163 connections, 2 pre-existing DRC errors incl. 1 real short) copied into a private
`runs/routing_capability_investigation/` scratch dir — never touch the live campaign's own
copy.

**Routing-quality signals that already existed and are real**: `run_allegro_report(...,
report_code="drc")` gives exact violation coordinates/required-vs-actual values/element
names; SPECCTRA's own `final.sts` gives board-TOTAL length/via/ratio stats (no per-net
breakdown); `report_code="vialist_net"` gives per-net via counts (0 on an all-TOP/BOTTOM
board like this sample). **What was missing**: a per-net REAL MEASURED LENGTH query (only
`allegro_get_net_constraint`/`axlCnsNetFlattened` existed, which returns a RULE value like
`MAX_VIAS`, never a measured length) — this is what you need to actually check
length-matching compliance (not just "DRC passed").

**What was missing for manual override**: a delete/rip-up tool at all.

### Two new tools built and confirmed live

- **`allegro_get_net_length(session_id, net_name)`** (`axlDBGetLength`,
  `allegro_geometry_tools.py`) — real measured net length, works on partially-routed nets
  too. CONFIRMED LIVE via outfile/fprintf capture (SKILL return values never surface in the
  job log — same caveat as every other `axl*` query in this suite): `X8_length=2447.5`,
  `N03774_length=5177.5` on the real sample board.
- **`allegro_delete_connect(session_id, object_type, object_name, ripup=True)`**
  (`axlDeleteObject`, same file) — deletes a named object by `(car (axlSelectByName
  object_type object_name))`, same resolver `allegro_assign_net` uses. CONFIRMED LIVE, but
  **DO NOT use `object_type="NET"` expecting a non-destructive rip-up** — `axlDeleteObject`
  on a NET dbid deletes the net's LOGICAL IDENTITY ENTIRELY (live-reproduced: net count
  75→74, its pins went Unused, and a follow-up `allegro_create_trace(...,
  net_name="<deleted net>")` silently created NOTHING, since `axlDBCreatePath` returns nil
  for a nonexistent net per its own doc). **The real, non-destructive rip-up-for-reroute
  mechanism is the ALREADY-EXISTING `allegro_assign_net(object_type="PIN", object_name=
  "<a pin on the net>", net_name="<that pin's own current net>", ripup=True)`** —
  CONFIRMED LIVE: this strips the net's connected clines (net goes to
  `unconnected=1`/ratsnest, confirmed via `axlDBGetConnect`/net-attribute queries) while
  leaving the net and all its pins fully intact. Use `allegro_delete_connect` for what it's
  actually for (deleting a stray component/via/film/etc. outright), not for this workflow.

### Two real bugs found (and fixed) in the existing `allegro_create_trace`

Found while exercising the rip-up-and-refix cycle above — both now fixed, covered by
tests, and independently re-verified live:
1. **Layer string**: passed the bare layer name (`"TOP"`) straight to `axlDBCreatePath`'s
   `t_layer` arg. The vendored doc's own example uses `"ETCH/TOP"`. Bare `"TOP"` silently
   created NOTHING (nil return, 0 segments, `Missing Connections: 1`) even on `rc 0`. Now
   fixed: builds `"ETCH/<layer>"` automatically (same as `allegro_create_copper_shape`).
2. **Width**: called `axlPathStart(points)` with no width arg — per `axlPathStart.txt`,
   that argument IS the trace width, defaulting to 0 if omitted. Live-confirmed
   `width=0.0` on every segment of a tool-created trace (via `axlDBGetConnect`'s own
   `seg->width`), producing real new "Minimum Neck Width" DRC violations and spurious
   near-0-clearance spacing hits against unrelated nearby copper (a 0-width line consumes
   none of the real clearance budget). Now fixed: `width` is a REQUIRED parameter (no
   silent default) threaded straight into `axlPathStart`.

### End-to-end manual-override result

```
start_allegro_session()
allegro_assign_net(session_id, "PIN", "<a pin on the bad net>", "<that net's own name>", ripup=True)
allegro_create_trace(session_id, points=[...corrected path...], layer="TOP", net_name="<net>", width=5.0)
allegro_save_design(session_id)
allegro_run_session(session_id, board_file=...)
wait_for_job(...)
run_allegro_batch_drc(board_file=...) ; wait_for_job(..., timeout_seconds=15)   # read batch_drc.log, don't trust state
run_allegro_report(..., report_code="drc")   # confirm the ONE targeted violation is gone, nothing new
run_allegro_report(..., report_code="sum")   # confirm Nets/Pins/Connection Completion unchanged
```
Using the corrected tools, a real 0 MIL "Line to Line Spacing" short (net X8 vs net
N03774, exact DRC marker `(11762.5, 17005.0)`) was independently located via a live
`axlDBGetConnect` segment-geometry query that matched the DRC coordinate to the mil, then
DEFINITIVELY fixed: every corrected attempt showed `Short DRC` 1→0, `DRC Errors` dropped
by exactly 1 (leaving only the pre-existing, unrelated Package-to-Package violation),
`Missing Connections: 0`, `Connection Completion: 100.00%`, Nets(75)/Pins(251) unchanged.

**Honest limitation found, not a tool-chain gap**: net X8 turned out to be one lane of a
tightly-packed 8-line parallel mux bus (X1-X8) running directly through a separately dense
analog feedback-network pocket (4+ other nets weaving through the same small area).
Picking a fully clean ALTERNATE route by hand required discovering each neighbor one at a
time via live `axlDBGetConnect` queries; even a carefully-reasoned, maximally-surgical
reroute still left double-digit new spacing violations against previously-unseen
neighbors in this specific spot — the same problem a human hand-routing this exact area
would hit. The mechanical loop itself (rip-up → create → save → run → batch_drc → report)
is fast (each full cycle well under a few seconds for DRC/report, ~5-6s for the Allegro
session) and genuinely practical for iterate-and-recheck — but it does not replace an
autorouter's or a human's keepout awareness for a dense board region.

**GOTCHA — a single `allegro_run_session` hung for minutes** (vs the usual ~5-6s) during
this investigation with no modal dialog detected (`DismissWatcher`'s own window-enumeration
found zero dialog windows, just the normal main Allegro window) — a DIFFERENT symptom from
the previously-documented ~137s-watchdog and dialog-hang modes. Treat a session that's
still `running` well past ~30s as suspect; verify the board file's own mtime/diff before
trusting any report run immediately afterward, since a report job run while the Allegro
session is still mid-save will read STALE (pre-fix) board state with no error of its own.

### Scaled to a harder case: length-matching, and a THIRD real gotcha (multi-branch net rip-up hang)

Queried real per-net lengths for 4 structurally-analogous "matched leg" nets of a
repeating LED-driver sub-circuit: `N08416=13062.5`, `N08752=10567.51`, `N08984=8052.5`,
`N09192=12677.5` mil — a real, large, unmatched spread. Compared against a real
`get_high_speed_constraint_preset("DDR4")` tolerance (`addr_ctrl_to_clk_length_match_mils
=25.0` mil) to confirm the suite can genuinely detect a length-matching violation (here,
thousands of mils outside a 25 mil budget).

**Gotcha #3 (new, distinct from the session-hang above)**: attempting the fix on the
shortest net (`N08984`, a real 4-pin/MULTI-BRANCH net) — ripping up just one branch via
`allegro_assign_net(ripup=True)` then recreating it with `allegro_create_trace` — made
`allegro_run_session` hang for MINUTES (vs the usual ~5-6s), REPRODUCED 2-FOR-2 on fresh
board copies. `DismissWatcher`'s window enumeration found zero dialog windows (just the
normal, still-`Responding=True` main Allegro window), ruling out the already-documented
modal-dialog explanation. Not root-caused (candidate: recreating one branch of a net whose
OTHER branches/pins are still attached at a shared junction may trigger an expensive
connectivity/cline-merge recompute). **`allegro_assign_net(ripup=True)` +
`allegro_create_trace` is CONFIRMED reliable (~5-6s, every time) only for a simple 2-pin/
single-branch net** (as used for the DRC fix above) — treat a multi-branch net's rip-up-
and-refix as higher risk until this is root-caused.

Switched to a simple single-branch pair instead: `N02684`=3100.0 mil, `N08580`=2400.0 mil
(both `nBranches=1`). Ripped up `N08580`, recreated it with a meander calculated to add
exactly 700 mil (closing the gap to `N02684`).

**Gotcha #4 (a geometry-design mistake, not a tool bug)**: the first meander attempt
accidentally RETRACED part of its own path (two segments coincident on the same Y, one
re-walking part of the other's X range) — `axlDBCreatePath` silently returned nil for
this (0 segments, `Missing Connections: 1` — same FAILURE SIGNATURE as the layer-string
bug, but a different cause). Lesson: when hand-designing a meander/detour, verify no two
segments share both an axis value (same X or same Y) AND an overlapping range on the
other axis — that's a self-overlap, and `axlDBCreatePath` rejects it silently just like a
missing/wrong layer string, with no error anywhere in the job log. A corrected,
non-overlapping meander ran in the normal ~5-6s and `axlDBGetLength` confirmed the new
length as EXACTLY `3100.0` mil — matching `N02684` to the mil (0 mil residual, well
inside the 25 mil budget) — with `Missing Connections: 0`/`Connection Completion:
100.00%`/correct Nets(75)/Pins(251). 4 new minor spacing violations appeared against
previously-unsurveyed neighbors in this new local area (same lesson as the main DRC-fix
case: picking a fully keepout-clean path by hand requires surveying the SPECIFIC local
neighborhood, wherever on the board it is) — but the length objective itself landed
exactly. See `runs/routing_capability_investigation/t3_length_matching/` for the full
before/after evidence of all of the above.

## Cross-cutting notes (domain-specific, verified this run)

- **Three different non-terminal state lies, three different completions**:
  - `run_allegro_batch_drc` → `get_job_status` stays `running`/`rc null` forever → read `batch_drc.log`/`dbdoctor.log`.
  - `run_specctra_autoroute` → completes with `state:"failed"` rc 4 (normal) → read `final.sts`/`route.sts` + `routed.ses`.
  - `run_allegro_generate_artwork` → `state:"failed"` rc 1 (warnings, normal) → read `TOP.art`/`BOTTOM.art`/`photoplot.log`.
  - `run_specctra_import_session` → worker crash; `get_job_status` stays `running` (no `crash` field here) → detect via `.dmp` + `SPMHDB-238` log.
- **Where results actually land** (job dir vs input dir vs `output_file`): report → `output_file`; batch_drc
  & dbdoctor → job-dir logs; SPECCTRA route → paths from the `.do`; artwork → job-dir `.art`; spif export `.dsn`
  → job dir. `list_job_files` is the reliable locator for all of the job-dir ones.
- **SKILL return values never appear in the tool result** — they go to the job log, and for most `axl*`
  mutation calls the log is just the Allegro banner. Verify SKILL authoring by a downstream read (here:
  `run_allegro_report` again, or `artwork.exe` emitting real Gerber), not by a non-empty log.
- **`allegro_run_session` appends a bare `quit`** and passes the board as `allegro.exe`'s positional (there is
  no "open" step in the macro); it clears a stale sibling `.lck` before launch. A session closes on run —
  reusing a closed `session_id` errors `No open script session`.
