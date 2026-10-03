# `spif_in` Dialog Left Open Causes Silent No-Op of Every Following Command

**Slug**: `spif-in-form-not-closed-silent-noop`
**Tool(s) affected**: `run_allegro_specctra_import` (spif_specctra_tools.py)
**Status category**: `tool_bug_fixed`
**Pipeline stage**: specctra routing import

## Symptom

`specctra_in <file>` (the correctly-spelled, one-word form) completes the SPECCTRA import successfully — it auto-fills the form's `SES_IN` field and clicks `TRANSLATE_TO` ("Run") in one step, confirmed live via the replay journal — **but leaves its dialog open afterward** (modeless): `share/pcb/text/forms/spif_in.form`, form name `spif_in`, fields `SES_IN`/`TRANSLATE_TO`/`CLOSE`. Every following top-level command — the save, another command, even `quit` — is **refused** with a real, logged `Finish current command first` error and **silently does nothing**. The import itself works; everything after it is a no-op.

## Root Cause

`specctra_in` opens the `spif_in` form and, when given the file as a same-line argument, drives `SES_IN`/`TRANSLATE_TO` automatically — but it does **not** close the form when done. Allegro's command dispatcher is a strict one-active-command-at-a-time system: while a form/command is still the active window, any subsequent top-level command is rejected outright with `Finish current command first`. Because the rejection happens at the dispatcher level, the refused command never executes — no error propagates to the job's `run.log` or return code, so the **job still reports `succeeded`** while, in practice, nothing after the `specctra_in` line actually ran. The real error is logged only in Allegro's own `.jrl` journal file, which is not part of the normal job-output surface.

## Evidence

- `sigrity_mcp/core/tool_status.py:228-235` (the `allegro` entry's specctra-import note) — "A SECOND, independent bug was found while verifying the first fix: `specctra_in <file>` (CONFIRMED live, via the replay journal, to accept the session path as a same-line argument and auto-click Run -- not just the bare dialog-opener the docs describe) leaves its dialog (`share/pcb/text/forms/spif_in.form`, form name `spif_in`, fields `SES_IN`/`TRANSLATE_TO`/`CLOSE`) open afterward; any following top-level command (the save, even `quit`) was refused with a real, logged `Finish current command first` error and silently did nothing -- so the import itself worked but nothing after it did. Fixed by inserting `setwindow form.spif_in` / `FORM spif_in CLOSE` / `setwindow pcb` between the `specctra_in` line and whatever runs next."
- `sigrity_mcp/domains/cad/spif_specctra_tools.py:96-107` — the fix in code, with an inline comment: "`specctra_in <file>` … drives the real 'Import From Auto-Router' dialog headlessly, auto-filling `SES_IN` and clicking `TRANSLATE_TO` ('Run') in one step -- CONFIRMED live via the replay journal (no separate FORM lines needed for that part). But the form stays open (modeless) afterward, and Allegro's command dispatcher refuses any further top-level command with 'Finish current command first' (CONFIRMED live) until it is explicitly closed -- so every caller must close it before anything else (a save, another command, or `quit`) or that next command silently no-ops."
- `.forjinn/skills/sigrity-cad/SKILL.md:110-114` (Task 3) — "…and still closes the `spif_in` dialog (`setwindow form.spif_in` / `FORM spif_in CLOSE` / `setwindow pcb`) before anything else runs — skipping that close step makes every following command (including the save) silently no-op with a `Finish current command first` error you'll only see in the design's own `allegro.jrl`, never in the job's `run.log`."
- Live end-to-end verification of the fixed function (`sigrity_mcp/core/tool_status.py:244-256`): import job `succeeded`, a real output `.brd` written (913896 bytes vs the 760024-byte source, genuinely different sha1), `report.exe` read the saved board back with matching routed-geometry statistics — proof the save (the command that would otherwise have silently no-opped) actually executed.

## Pipeline Impact

Any pipeline calling `run_allegro_specctra_import` against an unpatched copy of the file gets a **false success**: `state:"succeeded"`, rc 0, but the board was never saved to the requested `output_file` (or at all, if no `output_file` was given), and any command queued after the `specctra_in` line — including `quit` — never executed. `run_placement_and_routing_assistance`'s `specctra_import` stage is directly affected: even if the import itself works, the final DRC pass would run against a board that was never actually saved with the new routing, without any error surfacing in the pipeline's own stage state or logs. The only detectable signal is the `Finish current command first` line in Allegro's `.jrl` journal — which no tool in this suite reads or surfaces through `run.log`.
