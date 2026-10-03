# dxf2a-attached-flag-syntax-rejected

- **tool**: `dxf2a` (`dxf2a.exe`, wrapped as `allegro_import_dxf` in `sigrity_mcp/domains/cad/allegro_import_tools.py`)
- **status_category**: `precondition_error` (a caller-side invocation mistake, not a tool defect)
- **verified_workaround**: YES — use space-separated flag syntax (`-u MILS`, `-a 2`); the wrapper already does this

## What went wrong

dxf2a's flag options must be **space-separated** from their values. The attached/concatenated form is rejected outright: the live test `dxf2a.exe ... -uMILS -a2 ...` was refused with `ERROR: Invalid program arguments.` before any import work began. This is a non-obvious CLI convention (many Cadence-era tools accept either); a caller or wrapper that builds argv with attached flags fails at argument parsing with no import progress at all.

## Evidence

- `core/tool_status.py` (`dxf2a` note), quirk (2): "flag syntax is confirmed SPACE-separated (`-u MILS`, `-a 2`) — the attached form (`-uMILS`, `-a2`) was live-tested and rejected outright with 'ERROR: Invalid program arguments.'"
- `allegro_import_tools.py` module docstring: "Flag syntax is confirmed SPACE-separated (`-u MILS`, `-a 2`), NOT attached (`-uMILS`/`-a2` was live-tested and rejected outright with 'ERROR: Invalid program arguments.')."
- `README.md` (dxf bridge section): "flag syntax is confirmed SPACE-separated (`-u MILS`, `-a 2`) — the attached form (`-uMILS`) was live-tested and rejected outright."
- The wrapper at `allegro_import_tools.py:113-124` builds every option as a separate argv element: `args += ["-u", output_units]`, `args += ["-v", original_units]`, `args += ["-a", str(accuracy)]`, and bare flags (`-g`, `-t`) as standalone elements — i.e. the space-separated form is the only form the wrapped tool ever generates.

## Symptoms a caller observes

- Immediate exit with `ERROR: Invalid program arguments.` in the log
- No `.brd` written, no `dxf2a complete.` line
- No per-layer mapping or conversion output at all
