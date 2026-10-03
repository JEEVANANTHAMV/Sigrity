# dxf2a-attached-flag-syntax-rejected — Workarounds

## What works (confirmed)

- **Always pass space-separated flags**: `-u MILS`, `-a 2`, `-v MM`, etc. The attached form `-uMILS`/`-a2` is live-confirmed rejected.
- **The wrapped tool `allegro_import_dxf` already emits the correct form** (`allegro_import_tools.py:113-124`: each option and value is a separate argv entry). Callers that call through the MCP tool with `output_units="MILS"`, `accuracy=2`, etc. never hit this.
- Only when hand-running `dxf2a.exe` directly (outside the wrapper) must the space-separated convention be remembered.

## What was tried / ruled out

- Attached form (`-uMILS -a2`): live-tested, rejected with `ERROR: Invalid program arguments.` — do not retry with it.

## Notes

- There is no in-suite setting to change; this is pure argv construction. If this error ever appears in a job log produced by the wrapper, re-check the wrapper's argv-building block (it should still emit separate list elements).
