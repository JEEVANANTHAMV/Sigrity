# eagle2cp-no-batch-mode

- **tool**: `Eagle2Cp.exe` (`EagleImport\Eagle2Cp.exe`, Eagle → Concept-HDL bridge; **not wrapped** by this suite)
- **status_category**: `gui_only_no_batch` (an interactive stdin-prompt hang with no batch/flag mode)
- **verified_workaround**: NO (not wrapped; no non-interactive mode found)

## What went wrong

`Eagle2Cp.exe` (the Eagle → Concept-HDL import bridge) is a real installed executable, but it **halts on an interactive prompt: `waiting for forcelabel parameter (yes or no)`**. With no connected stdin and no discoverable flag to supply that parameter (or bypass the prompt), it cannot complete headlessly. No `-help`/flag-driven non-interactive mode was found.

Like `convert_gerber.exe`, it was **deliberately not wrapped** — documented as a known gap rather than silently skipped, matching the suite's treatment of `zrouter` and per its standing discipline against fabricating automation surfaces.

## Evidence

- `allegro_import_tools.py` module docstring (lines 57–63): "`EagleImport\Eagle2Cp.exe` (Eagle -> Concept-HDL bridge) ... real executable, but ... an interactive stdin-prompt loop with no `-help`/flag-driven non-interactive mode found ... `Eagle2Cp.exe` halts on 'waiting for forcelabel parameter (yes or no)' ... — neither is wrapped here."
- `README.md` (dxf bridge section): "`EagleImport\Eagle2Cp.exe` (Eagle import) ... real executable but ... an interactive stdin-prompt loop with no discoverable non-interactive flag — documented as a known gap rather than silently skipped."
- The suite has **no wrapper** for it: the CAD domain's import surface is `allegro_import_dxf`/`allegro_export_dxf`/`allegro_new_blank_board` only.
- Status per manifest: `gui_only_no_batch`, verified_workaround `NO (not wrapped)`.

## Symptoms a caller would observe (if hand-run)

- Halt on `waiting for forcelabel parameter (yes or no)` with no further output
- No Concept-HDL output produced, process parked at the prompt
