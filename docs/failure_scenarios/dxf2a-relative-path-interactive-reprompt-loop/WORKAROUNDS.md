# dxf2a-relative-path-interactive-reprompt-loop — Workarounds

## What works (confirmed — the fix already in code)

- **Pass paths the wrappers will absolutize**: `allegro_import_dxf`/`allegro_export_dxf` call `core/paths.py` `resolve_path` on `cnv_file`/`dxf_file`/`board_file` (`allegro_import_tools.py:124`, `:150`), relative to the MCP server's own working directory — NOT the job's scratch cwd. This closes off the most common cause (a caller cwd different from the job cwd).
- **Prefer absolute paths in the first place** for these tools; "a genuinely wrong/nonexistent absolute path will still trigger the same loop" (module docstring), so existence matters as much as absoluteness.
- **Detection**: if a dxf2a/a2dxf job runs long past its normal few-second completion, suspect this exact loop before assuming a hang; inspect `run.log` for the repeated prompt lines.

## What was tried / ruled out

- The pre-fix behavior (relative path, job scratch cwd, unconnected stdin) is the documented failure — it is the thing the fix removed, reproducing the 205–209 MB log twice during development.

## Notes

- The same defensive absolute-resolution convention is now applied uniformly across this executable family — see the seven tools in `allegro_manufacturing_tools.py` (each `_resolve(...)`s its file arguments) and `allegro_create_symbol` in `allegro_library_tools.py`.
