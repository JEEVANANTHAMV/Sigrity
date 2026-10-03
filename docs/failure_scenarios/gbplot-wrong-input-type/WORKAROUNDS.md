# gbplot-wrong-input-type — Workarounds

## What works (confirmed)

- **Pass the `.art`, not the `.brd`**: `run_allegro_gerber_plot(artwork_file="…\\TOP.art", penplot_file=None)` — the corrected wrapper (`allegro_manufacturing_tools.py:126-133`) takes the `.art` output of `run_allegro_generate_artwork`. This is the doc-confirmed correct input shape.
- **Full sequence**: `allegro_create_film` + `allegro_save_design` + `allegro_run_session` (author films, see the no-films scenario) → `run_allegro_generate_artwork` → `run_allegro_gerber_plot(artwork_file=<job_dir>/<film>.art)`.
- If the consumer can take standard Gerber/RS274X (the common case), **skip gbplot entirely** — `artwork.exe`'s `.art` output is the real Gerber; gbplot only matters for physical photoplotter shops.

## What was tried / ruled out

- Passing a `.brd`: live-confirmed to fail with `gbplot: Error opening parameter file.` — do not use it as input.

## Evidence gap (honest)

- The wrapper's *fix* is confirmed correct per the doc's own syntax, but **gbplot itself has not been independently re-run against a real `.art` file** — the manifest keeps it at `built_untested` for the conversion step. The "error opening parameter file" failure on a `.brd` was live-confirmed; the positive "converts a `.art` cleanly" path is doc-confirmed, not live-rerun, this pass.
