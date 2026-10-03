# convert-gerber-no-batch-mode

- **tool**: `convert_gerber.exe` (standalone; **not wrapped** by this suite)
- **status_category**: `gui_only_no_batch` (a GUI/interactive stdin-prompt loop with no discoverable non-interactive flag)
- **verified_workaround**: NO in-suite wrapper; for Gerber → Allegro *import*, use `run_ipc2581_import` (IPC-2581 XML) instead

## What went wrong

`convert_gerber.exe` (Gerber → Allegro import) is a real installed executable, but it is an **interactive stdin-prompt loop with no batch/headless mode**: it **repeatedly re-prompts `Existing layout file name (*.brd):` forever**. With a job's stdin never connected, it spins on that prompt indefinitely rather than failing cleanly or reading the answer from an argument. No `-help`/flag-driven non-interactive invocation was found.

It was deliberately **not wrapped** — matching the suite's standing discipline of documenting an interactive dead end rather than fabricating an automation surface (the same treatment given to `zrouter`'s standalone/native paths and `Eagle2Cp`).

## Evidence

- `allegro_import_tools.py` module docstring (lines 57–63): "Investigated and confirmed NOT automatable this same pass, for honesty rather than silent omission (matching this suite's treatment of zrouter/Aurora elsewhere): `convert_gerber.exe` (Gerber -> Allegro import) and `EagleImport\\Eagle2Cp.exe` (Eagle -> Concept-HDL bridge) are both real executables, but both are interactive stdin-prompt loops with no `-help`/flag-driven non-interactive mode found (`convert_gerber.exe` repeatedly re-prompts 'Existing layout file name (*.brd):' forever; `Eagle2Cp.exe` halts on 'waiting for forcelabel parameter (yes or no)') — neither is wrapped here."
- `README.md` (dxf bridge section): "`convert_gerber.exe` (Gerber import) and `EagleImport\Eagle2Cp.exe` (Eagle import) are both real executables but both are interactive stdin-prompt loops with no discoverable non-interactive flag — documented as a known gap rather than silently skipped, matching this suite's treatment of zrouter."
- The suite has **no wrapper**: `allegro_import_tools.py` exposes only `allegro_import_dxf`/`allegro_export_dxf`/`allegro_new_blank_board`; there is no `run_convert_gerber` anywhere in the CAD domain.

## Symptoms a caller would observe (if hand-run)

- `Existing layout file name (*.brd):` repeated on every loop iteration
- No progress, no output file, process alive on an unconnected stdin
