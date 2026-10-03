# idf-idx-import-untested-no-sample-file — Workarounds

## What works (confirmed)

- **The confirmed-live export tools are the practical path today**: `run_idf_export` (`idf_out.exe`) and `run_idx_export` (`idx_out.exe`) are both `confirmed_live` ("run bare against a real board with zero preconditions") — use these for Allegro → IDF/IDX mechanical exchange. There is no evidence gap on the export direction.
- The import tools **resolve their file paths to absolute** (`allegro_manufacturing_tools.py:202-233`), so when a sample file is eventually supplied, the common relative-path pitfall in this executable family (see the dxf2a re-prompt scenario) is already guarded against.

## What was tried / ruled out

- **No in-machine sample exists to test the import direction** — a machine-wide search found no `.emn`/`.bdf`/`.out` (IDF/PTC/SDRC) file for `idf_in` and no `.idx` file for `idx_in`. This is a sample-availability blocker, not an invocation problem, so there is no confirmed in-suite workaround for exercising the import itself.

## How to close the gap (requires external input)

- Supply a real IDF file (`.emn`/`.bdf`/`.out`) → `run_idf_import(idf_file=..., idf_format="IDF"|"PTC"|"SDRC")`; or a real `.idx` (ProSTEP EDMD) → `run_idx_import(idx_file=...)`. The `-help` banners already document the argument shapes, so the wrappers are ready to be confirmed once a file appears.
- Until then, treat exact flag behavior as "best transcription of the `-help` banner, not guaranteed-correct" (the suite's `built_untested` contract in `core/tool_status.py` STATUS_DESCRIPTIONS).

## Notes

- Same status family as `bem2d3` (never run, no sample) and `syscap` (documented API, no confirmed batch) — untested-by-input-availability.
