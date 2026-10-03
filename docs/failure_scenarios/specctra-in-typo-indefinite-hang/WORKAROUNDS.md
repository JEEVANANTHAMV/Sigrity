# Workarounds: `specctra in` Two-Word Typo Causes Indefinite Hang

## Verified Workaround

Use `run_allegro_specctra_import` as it exists **in the current repo** (spif_specctra_tools.py), which emits `specctra_in "<path>"` (one word, underscore), not `specctra in "<path>"`. This is a code fix, not a runtime workaround — the two-word form is not a real command, so there is no flag, environment variable, or alternative invocation that makes it valid. Confirmed live end-to-end (see below): a real routed `.ses` (100% connected, 75 nets/163 connections) imported into a fresh board copy, import job `succeeded`, real output `.brd` written (genuinely different size/sha1 from the 760024-byte source), and `report.exe` (independent, SKILL-free) read the saved board back with matching statistics (451.50 inches, 0 vias).

Evidence: `sigrity_mcp/core/tool_status.py:215-256` — the full root-cause + fix + live end-to-end verification, concluding "`run_allegro_specctra_import` is correspondingly promoted from 'recommended but unverified' to CONFIRMED LIVE end-to-end."

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Fix the emitted script line to `specctra_in` (one word) | worked — process exits cleanly in under 2 seconds; full end-to-end import verified live | `sigrity_mcp/core/tool_status.py:215-256`; spif_specctra_tools.py:95 |
| 2 | Any flag/environment-variable/alternate-spelling workaround against the two-word form | not_applicable — `specctra in` is not a real command at all; there is no alternate form to try | `sigrity_mcp/core/tool_status.py:221-223` |

## Prevention

1. If `run_allegro_specctra_import` ever hangs again with this exact signature (indefinite hang, 0% CPU, no dialog, `run.log` stuck at the 3-line startup banner), immediately check that `sigrity_mcp/domains/cad/spif_specctra_tools.py` still emits `specctra_in` (one word) — the fix is a single line and is easy to regress if the file is ever hand-edited.
2. Do **not** try to treat this as a dialog-dismissal problem: unlike the modal-Qt-dialog hang, there is no window for `DismissWatcher` to enumerate or click away. If your hang-handling code is keyed on "found a dialog window," it will miss this one entirely.
3. Distinguish this signature from the other two Allegro hang modes before choosing a response: this one is **indefinite** (no fixed deadline), **0% CPU**, and **zero windows**; the ~137s-watchdog hang has a fixed ~137s duration and a distinct rc (-536870904); the modal-Qt-dialog hang has a visible, enumerable dialog window.

## Remaining Gaps

- None for this specific bug — it is fully root-caused, fixed in code, and live-verified end-to-end. The only residual risk is future regression of that single emitted line, which has no independent guardrail (no unit test asserts the exact literal string `specctra_in` in the emitted script — the evidence base for the fix is the live repro only).
