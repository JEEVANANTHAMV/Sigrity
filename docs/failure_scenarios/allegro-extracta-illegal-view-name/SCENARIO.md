# Extracta Rejects Invented View Names — 'Illegal view name'

**Slug**: `allegro-extracta-illegal-view-name`
**Tool(s) affected**: `run_allegro_extracta` (`sigrity_mcp/domains/cad/allegro_extraction_tools.py`), `allegro_get_board_extent_points` (same file, which wraps `run_allegro_extracta(view_type="pins")`)
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design / extraction

## Symptom

`run_allegro_extracta` failed for **every** built-in `view_type` (`bom`, `nets`, `components`, `pins`, `testpoints`, `drc`) — 100% of the time. Each `wait_for_job` call returned `state=failed, returncode=2` with no actionable detail at the job-result level: `run.log` only ever said `"Extract ended ... see extract.log for errors."` with no path. Across two separate campaign conversations there were 17 total `wait_for_job` `state=failed, returncode=2` results for this tool, and a dedicated repro produced 10 consecutive `run_allegro_extracta` + `wait_for_job` failures.

When the real `extract.log` was finally read from the correct location, the true error was:

```
ERROR(SPMHDX-10): Illegal view name.
```

The cause was a bug in this suite's own wrapper: the `EXTRACTION_TEMPLATES` dict embedded in `allegro_extraction_tools.py` invented view-name and field-name keywords — `NETS`, `COMPONENTS`, `PINS`, `TESTPOINTS`, `DRC`, `COMP_LOCATION_X`, `COMP_LOCATION_Y`, `COMP_ROTATION`, `COMP_MIRRORED`, `TESTPOINT_NAME`, `DRC_ERROR_NAME`, `DEVICE`, `VALUE`, `TOLERANCE`, etc. — that real `extracta.exe` does not recognize. Real extracta view names are `COMPONENT`, `LOGICAL_PIN`, `COMPONENT_PIN`, `COMPOSITE_PAD`, `DRC_ERROR`, etc.

## Root Cause

Two independent facts combined to make this failure look like an opaque product bug rather than a wrapper keyword mistake:

1. **Invented keywords in the wrapper.** The original `EXTRACTION_TEMPLATES` did not use Cadence's documented view/field vocabulary. Cadence ships the real command files under `share/pcb/text/views/*.txt` (e.g. `bom_rep.txt` → `COMPONENT`, `net_rep.txt` → `LOGICAL_PIN`, `cmp_rep.txt` → `COMPONENT`, `cpin_bv.txt` → `COMPONENT_PIN`, `tstpoint.txt` → `COMPOSITE_PAD`, `drc_rep.txt` → `DRC_ERROR`); the wrapper did not source from these, so every emitted command file contained an illegal first line (the view name). extracta's own validation rejects an unknown view name with `ERROR(SPMHDX-10): Illegal view name.` before any data is written.

2. **The real error lives in a log nobody reads.** `extracta.exe` writes `extract.log` into its process **cwd**, which is the submitted job's own `job_dir` (per `core.jobs` `submit()` semantics, `cwd=job_dir`), **not** next to `board_file` or `output_file`. Because every diagnostic attempt looked for the error beside the input/output files (or relied on `run.log` alone), the `Illegal view name` line was never seen for many calls, and the failure appeared to be an unexplained `returncode=2`.

## Evidence

- `sigrity_mcp/core/tool_status.py:600-608` — `allegro_extracta` note: "`run_allegro_extracta`'s EXTRACTION_TEMPLATES used invented view-name/field-name keywords ("NETS", "COMPONENTS", "PINS", "TESTPOINTS", "DRC", "COMP_LOCATION_X/Y", "COMP_ROTATION", "COMP_MIRRORED", "TESTPOINT_NAME", "DRC_ERROR_NAME", ...) that real extracta.exe genuinely rejects outright for EVERY view_type with `ERROR(SPMHDX-10): Illegal view name.` -- this reproduces 100% of the time (confirmed: 10 consecutive failed run_allegro_extracta+wait_for_job calls, 17 total wait_for_job 'state=failed, returncode=2' results for this tool overall)."
- `sigrity_mcp/core/tool_status.py:610-614` — the reason misdiagnosis is easy: "the real error only appears in `extract.log`, which extracta.exe writes into its own process cwd -- i.e. the submitted JOB's own job_dir (per core.jobs' submit(), cwd=job_dir) -- not next to board_file/output_file where every attempt to read it looked (run.log's own text, 'Extract ended ... see extract.log for errors', gives no path, which is misleading here)."
- `sigrity_mcp/core/tool_status.py:614-617` — root-cause confirmation path: "Root cause confirmed by directly inspecting a job_dir's real extract.log by hand (not through any SKILL/tool layer). FIXED: EXTRACTION_TEMPLATES now uses the real, Cadence-documented view/field keywords copied directly from the shipped `share/pcb/text/views/*.txt` command files."
- `sigrity_mcp/domains/cad/allegro_extraction_tools.py:52-67` — module comment: "the view-name/field-name keywords below are copied from Cadence's own shipped extract command files ... NOT invented. This replaces an earlier version of this dict that used made-up view names ("NETS", "COMPONENTS", "PINS", "TESTPOINTS", "DRC") and made-up field names ... that extracta.exe genuinely rejects outright with `ERROR(SPMHDX-10): Illegal view name.`"
- `sigrity_mcp/domains/cad/allegro_extraction_tools.py:68-135` — the corrected `EXTRACTION_TEMPLATES`: `bom`→`COMPONENT`, `nets`→`LOGICAL_PIN`, `components`→`COMPONENT`, `pins`→`COMPONENT_PIN`, `testpoints`→`COMPOSITE_PAD`, `drc`→`DRC_ERROR`.
- `.forjinn/skills/sigrity-cad/SKILL.md:400-408` (Task 8) — "FIXED, was a real 100%-repro bug: `view_type` in {bom,nets,components,pins,testpoints,drc} ... those templates used to contain invented view-name/field-name keywords ... that extracta.exe rejects outright with `ERROR(SPMHDX-10): Illegal view name.` for every single view_type, 100% of the time. Now fixed to use real keywords copied from Cadence's own shipped `share/pcb/text/views/*.txt` files."

## Pipeline Impact

Broke the entire headless `.brd` database-extraction path (BOM, nets, components, pins, test points, DRC) — every extraction view failed with `returncode=2`. This also silently broke the downstream helper `allegro_get_board_extent_points` (which derives a copper-pour boundary from a real `view_type="pins"` extraction), because its inner `run_allegro_extracta` job could not succeed. Nothing downstream of these extractions (e.g. copper-shape boundary derivation, BOM/nets reporting from raw `.brd`) could rely on this tool until the fix. Because the failure signature was only visible in `run.log` as a generic `returncode=2` with a pointer to `extract.log`, repeated diagnostic calls wasted time before the correct log was located.
