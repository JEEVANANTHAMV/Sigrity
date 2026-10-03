# capture-custom-launch-recovery-dialog

A modal "Capture Custom Launch" dialog blocks a stuck Capture batch job. Cadence's own docs describe this dialog as a **crash-recovery prompt** ("displayed only after Capture fails at launching for the first time"), not a license chooser. status_category: `tool_bug_fixed` for the wrapper's handling of it.

## What went wrong

This dialog appeared at least once during repeated `capture_run_session` attempts. It was traced, via the crash artifacts it points at, to a **genuine prior-session crash dump**: an `ACCESS_VIOLATION` in `orPrmWebCompIE64.dll`, with the dialog's own `errorlog.xml` / `crashdump.dmp` pair found under `C:\temp-builder\Capture*`. In other words, it is a *separate, distinct* failure mode from the current-run `Open <project>` hang: the hang itself has **zero** windows (live EnumWindows check), so this recovery dialog is not what's hanging the main flow — it shows up from a crashed *earlier* session and then itself blocks the next launch until dismissed.

The wrapper layer originally had no way to dismiss it automatically; a stuck job with an empty log would stay stuck indefinitely because the modal dialog holds Capture's main message loop.

## Evidence

- `core/tool_status.py` `capture` note (lines ~510-516): "the 'Capture Custom Launch' recovery dialog was separately traced to a genuine *prior*-session crash dump (ACCESS_VIOLATION in orPrmWebCompIE64.dll, see `C:\temp-builder\Capture*`/errorlog.xml), not the current hang itself; it is now auto-dismissed by `capture_handle_custom_launch_dialog` as a separate defensive guard for that distinct failure mode."
- `sigrity_mcp/domains/cad/capture_tools.py` module docstring (lines 8-12): the dialog is a crash-recovery prompt per Cadence's docs; and (lines 28-32): "The 'Capture Custom Launch' recovery dialog seen along the way is a *separate*, distinct failure mode (a genuine prior-session crash-dump recovery prompt, confirmed from its own `errorlog.xml`/`crashdump.dmp` pair) and is handled by `capture_handle_custom_launch_dialog` below, which is a **real, live-verified fix for that specific, narrower problem** even though it does not fix the main `Open`-step hang."
- `README.md` Domain 6 write-up documents the same dialog in Capture's re-test.

## Affected code (now fixed)

- `sigrity_mcp/domains/cad/capture_tools.py` — two pieces:
  - `capture_handle_custom_launch_dialog(button="No")` (lines 188-196): finds the top-level window whose title contains "Capture Custom Launch" via `EnumWindows`/`GetWindowTextW`, then finds the matching child `Button` and clicks it via `SendMessageW(BM_CLICK)` (0x00F5) — a clean `WM_COMMAND` that works even when the dialog's own message loop is frozen.
  - `auto_dismiss_recovery_dialog_if_stuck(job_id, check_after_seconds=15.0)` (lines 247-277): polls one already-submitted Capture job; if it's still `running` with an empty `run.log` and a real "Capture Custom Launch" modal is present, clicks it ("No") and returns a note for the result. `generate_schematic_from_spec` opts into this (schematic_generation_tools.py lines 170-172).
