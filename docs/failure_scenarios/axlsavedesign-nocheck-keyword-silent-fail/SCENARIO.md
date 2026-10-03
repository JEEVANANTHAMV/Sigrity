# `axlSaveDesign ?noCheck` Invalid Keyword Causes Silent Save Failure

**Slug**: `axlsavedesign-nocheck-keyword-silent-fail`
**Tool(s) affected**: `run_allegro_specctra_import` (spif_specctra_tools.py), zrouter save (allegro_placement_tools.py), workflow save (aurora/scope_tools.py)
**Status category**: `tool_bug_fixed`
**Pipeline stage**: any Allegro SKILL session that ends with a no-check save

## Symptom

Every `axlSaveDesign` call written as `(axlSaveDesign ?noCheck t)` — a boolean-keyword form — **silently fails**: Allegro logs `*Error* axlSaveDesign: unrecognized keyword - ?noCheck` **only to Allegro's own `.jrl` journal**, never to the job's `run.log` or return code. The job still reports `state:"succeeded"`, rc 0, but **nothing was saved** — the board on disk (or at the requested `output_file`) is unchanged from before the session.

## Root Cause

`?noCheck` is **not a real keyword** in `axlSaveDesign`'s signature. Confirmed against the vendored `axlSaveDesign.txt` SKILL doc shipped on this install: the real no-db-check option is `?mode "nocheck"` — a **string option** (a `?mode` keyword whose argument is the string literal `"nocheck"`), not a standalone boolean keyword. SKILL's keyword dispatch is strict: an unrecognized keyword is a hard error that aborts the form call entirely (it does not just ignore the unknown keyword and proceed), and because SKILL errors inside a batch script are logged to Allegro's journal stream rather than the external process's stdout/returncode, the job's own `run.log`/return code stay clean and the job is marked `succeeded`.

This exact copy-pasted line appeared in **three** independent files (a "THIRD, unrelated pre-existing bug" found while live-verifying the first two specctra-import fixes):

1. `sigrity_mcp/domains/cad/spif_specctra_tools.py` — `run_allegro_specctra_import`
2. `sigrity_mcp/domains/cad/allegro_placement_tools.py` — the zrouter save
3. `sigrity_mcp/domains/aurora/scope_tools.py` — the workflow save

## Evidence

- `sigrity_mcp/core/tool_status.py:236-243` (the `allegro` entry's specctra-import note) — "A THIRD, unrelated pre-existing bug was also found and fixed in the same function (and, identically, in `allegro_placement_tools.py`'s zrouter save and `aurora/scope_tools.py`'s workflow save -- same copy-pasted line in all three): `(axlSaveDesign ?noCheck t)` used a keyword, `?noCheck`, that does not exist in `axlSaveDesign`'s real signature (confirmed against the vendored `axlSaveDesign.txt` SKILL doc: the real no-db-check option is `?mode \"nocheck\"`, a string option, not a boolean keyword) -- every save after these three operations was silently failing (`*Error* axlSaveDesign: unrecognized keyword - ?noCheck`, logged only to Allegro's own `.jrl` journal, never to the job's `run.log`/return code) while the job still reported `succeeded`."
- `sigrity_mcp/domains/cad/spif_specctra_tools.py:110-112` — the fixed form: `skill (axlSaveDesign ?design <path> ?mode "nocheck")` or `skill (axlSaveDesign ?mode "nocheck")`, depending on whether `output_file` was passed.
- Live end-to-end verification of all three fixes together (`sigrity_mcp/core/tool_status.py:244-256`): a real routed `.ses` (100% connected, 75 nets/163 connections) imported into a fresh board copy, import job `succeeded`, a **real** output `.brd` written (913896 bytes vs the 760024-byte source — genuinely different, sha1 differs), and `report.exe` (independent, SKILL-free) read the saved board back with matching routed-geometry statistics. A genuinely-different output file is direct proof the save actually executed this time; with the buggy keyword form, no output file with that content would have existed at all.

## Pipeline Impact

Any Allegro SKILL session using one of the three affected save call sites — or any hand-written SKILL script using the same buggy `(axlSaveDesign ?noCheck t)` form — **silently produces no persisted board change whatsoever**, while reporting `state:"succeeded"`/rc 0. For `run_allegro_specctra_import` specifically, this meant the SPECCTRA-import pipeline's headline deliverable (a real, updated output `.brd`) was not actually being produced, even though every job state reported success — an especially dangerous failure because the import step itself (the `specctra_in` command) genuinely did work, so a caller only checking "did the import run" would not notice the save never happened. The only reliable detection path is (a) an independent `report.exe` read-back of the expected output file showing it is unchanged/missing, or (b) reading Allegro's own `.jrl` journal for the exact `*Error* axlSaveDesign: unrecognized keyword` string — neither of which this suite surfaced automatically for this specific failure.
