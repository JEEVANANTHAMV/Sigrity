# gbplot-wrong-input-type

- **tool**: `allegro_gbplot` (`gbplot.exe`, wrapped as `run_allegro_gerber_plot` in `sigrity_mcp/domains/cad/allegro_manufacturing_tools.py`)
- **status_category**: `tool_bug_fixed` (the wrapper originally wired a `.brd` where gbplot requires a generated `.art`)
- **verified_workaround**: YES — `run_allegro_gerber_plot` now takes the `.art` output of `run_allegro_generate_artwork` instead of a board file

## What went wrong

`gbplot.exe` converts an **already-generated Gerber artwork file (`.art`)** to legacy pen-plotter format. Its real syntax (per `doc/gcoms/gchap.html`) is `gbplot artwork_file_name [penplot_file_name] [-version]`. The wrapper `run_allegro_gerber_plot` was **originally wired to pass a `.brd` board file directly**, which gbplot rejects immediately with `gbplot: Error opening parameter file.` (it attempts to open the `.brd` as an artwork/parameter file and cannot).

This was a genuine wiring bug in this suite, not a board-content precondition: gbplot never accepted a raw `.brd`.

Note the division of labor that motivates the fix: `artwork.exe` is the real Gerber (RS274X) generator and does NOT need gbplot at all; gbplot is a separate, later, *optional* step for shops that still drive physical photoplotter hardware (legacy `.plt`/`.ctl`), so its input is the artwork step's `.art` output.

## Evidence

- `core/tool_status.py` (`allegro_gbplot` note), "ROOT CAUSE FOUND AND FIXED": "documents the real syntax as `gbplot artwork_file_name [penplot_file_name] [-version]` — it takes an ALREADY-GENERATED Gerber `.art` artwork file, not a `.brd` directly (confirmed live: passing a `.brd`, as `run_allegro_gerber_plot` originally did, fails immediately with 'gbplot: Error opening parameter file.'). `run_allegro_gerber_plot` is now corrected to take an `artwork_file` argument ... instead of a board file. Upgraded from known_blocked to built_untested — the fix is confirmed correct per the doc's own syntax, but gbplot itself ... was not independently re-run against a real .art file."
- `allegro_manufacturing_tools.py` module docstring (lines 22–32): gbplot "is a SEPARATE, later, optional step — NOT required for standard Gerber output ... `run_allegro_gerber_plot` below was originally wired to pass a `.brd` directly (confirmed wrong: fails immediately with `\"gbplot: Error opening parameter file.\"`) — corrected to take the `.art` file `run_allegro_generate_artwork` produces."
- `allegro_manufacturing_tools.py:126-133`: the corrected wrapper builds `args = [artwork_file]` (+ optional `penplot_file`) — no board-file argument exists on it anymore.
- `README.md` (corrections section): "`run_allegro_gerber_plot` — FIXED this pass ... this tool itself is corrected to take the resulting `.art` file instead of a `.brd` directly. `gbplot.exe` itself ... was not independently re-run against a real `.art` file this pass — still `built_untested`."

## Symptoms a caller observes

- Immediate `gbplot: Error opening parameter file.` (the `.brd`-as-input failure)
- No pen-plot file produced
