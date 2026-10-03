# powersi-missing-save-document-empty-options — Workarounds

## What works (confirmed)

- **Add `powersi_save_document` immediately after `start_powersi_session`**, before any other composed step — for any design that is not already `.spd`. In the macro it becomes line 2, directly after `sigrity::open document {…} {!}` (verified Task 3 flow; `sigrity::save {…} {!}`).
- **Omit `powersi_save_document` when the input is already `.spd`** (the happy-path `.spd` flow, Task 2, does not save and works).
- **Sanity gate before a long run**: after composing, use `preview_tcl_session(session_id)` and confirm the `sigrity::save {...}` line is present on line 2, BEFORE the freq/ports lines (prescribed in Task 3).
- **Recovery**: on the empty-options-only fingerprint (`_Options.xml` + `_PowerSI.err`, no `.spd`/`.sNp` in `runs/`), re-run the session with `powersi_save_document` right after `start_powersi_session`.

## What was tried / ruled out

- Expecting a tool error or nonzero rc when the save is omitted: ruled out — it doesn't happen. The missing save is *silent* (rc 0, no error); only the artifact fingerprint in `runs/` reveals it.
- Placing `powersi_save_document` later in the macro (after `set_frequency_sweep` / `add_ports_auto`): ruled out — that ordering also silently produces no output. Save must be line 2.

## Notes

- Distinct from `powersi-silent-success-runs-dir`: here the run is a **real failure** that merely *looks* identical to a successful silent run. The empty `Options.xml` (no `.spd`/`.sNp` at all) is what separates "missing save" from "silent success" (which produces a real `_S.<N>p`).
