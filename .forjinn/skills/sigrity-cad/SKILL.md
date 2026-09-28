---
name: sigrity-cad
description: Allegro/OrCAD CAD domain (SPB 22.1) — report/DRC/dbdoctor, SPECCTRA autoroute, Gerber (artwork) export, SKILL PCB authoring, and run_tool_pipeline, all verified live (2026-09-27). Use for board analysis, DRC, SPECCTRA routing, Gerber/manufacturing export, SKILL geometry/padstack/film authoring, and multi-step job pipelines.
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
  Route success = read `final.sts` for `Completion = 100.00%` + confirm `routed.ses` is non-empty. Import is
  a known product bug — don't burn time on it.

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
