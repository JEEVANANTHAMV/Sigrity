# stream-out-needs-predefined-films

- **tool**: `stream_out.exe` (GDSII Stream export; **not wrapped** by this suite)
- **status_category**: `built_untested` (a real, found-but-unwrapped executable whose prerequisite class is known but not wired up)
- **verified_workaround**: NO (unwrapped) — the precondition *pattern* is known and already solved for `artwork.exe`/`gbplot` via `allegro_create_film`, just not connected to this tool

## What went wrong (the gap)

`stream_out.exe` (GDSII Stream export) was found during the `tools/bin` audit but **not wrapped**. The reason is a precondition: it **needs pre-defined artwork film records** on the board — the same prerequisite class `artwork.exe`/`gbplot` require. That precondition is already solved in-suite (`allegro_create_film` + `allegro_save_design` in a SKILL session), but the stream_out wrapper was not wired up this pass, so there is no headless path to exercise it.

## Evidence

- `README.md` (known-gaps / corrections section): "Left unwrapped entirely: `stream_out.exe` (GDSII Stream export — **needs pre-defined artwork film records, the same precondition class already solved for `gbplot`/`artwork.exe` via `allegro_create_film`, just not wired up for this tool yet**) ..."
- Manifest status: `stream_out` is `built_untested` with a "NO" confirmed workaround, title "stream_out needs film records; unwrapped."
- The shared precondition is documented for the related tools: `core/tool_status.py` (`allegro_artwork`) — "The missing piece was authoring those film records at all — ... the real documented SKILL equivalent, `axlFilmCreate` (now wrapped as `allegro_create_film` ...), does it headlessly"; and `allegro_manufacturing_tools.py`'s note that `gbplot`/`artwork` both operate on board-defined films.
- There is **no `stream_out` wrapper / logical tool** registered in the CAD domain (the manufacturing wrapper set stops at `run_pdf_export`).

## Symptoms

- Not directly observable via the suite (no wrapper). If hand-run on a board with no film records, the expected behavior — by analogy to `artwork.exe`'s documented silent/emits-nothing behavior — is that it has nothing to stream, though this specific tool's exact failure signature was not live-characterized (never wrapped/run).
