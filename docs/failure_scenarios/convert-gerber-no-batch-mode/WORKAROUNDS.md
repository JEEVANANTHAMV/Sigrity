# convert-gerber-no-batch-mode — Workarounds

## What works (confirmed in-suite paths, not convert_gerber itself)

- **For Gerber-ecosystem → Allegro import, use IPC-2581 instead**: `run_ipc2581_import` (`ipc2581_in.exe`) is `confirmed_live` and is the suite's real, headless foreign-data → `.brd` import path ("the import direction of the already-wrapped ipc2581_out; produced a real, valid new .brd from a real IPC-2581 sample, independently re-verified with report.exe"). If the source shop can emit IPC-2581, route through that rather than `convert_gerber`.
- **For creating a board from scratch without a foreign-Gerber source**: `allegro_import_dxf` (`dxf2a.exe`, DXF+`.cnv`) or `allegro_new_blank_board` (shipped 2-layer template copy) — both confirmed live / available, no interactive prompt.
- There is **no in-suite wrapper or batch flag** for `convert_gerber.exe`; it is intentionally not wired because no non-interactive mode was discoverable.

## What was tried / ruled out

- Non-interactive / flag-driven invocation: not found — the exe only exhibits the repeating `Existing layout file name (*.brd):` stdin prompt. No `-help` batch path was located.

## Notes

- If a future pass finds a real batch/flag form for `convert_gerber`, the natural shape would be a `submit_job`-style wrapper that absolutizes its file paths (the same defensive convention used across this executable family) — but that is future work, not current capability.
