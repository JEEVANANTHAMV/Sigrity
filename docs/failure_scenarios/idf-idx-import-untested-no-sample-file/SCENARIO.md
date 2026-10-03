# idf-idx-import-untested-no-sample-file

- **tools**: `idf_in` / `idx_in` (`idf_in.exe`, `idx_in.exe`, wrapped as `run_idf_import` / `run_idx_import` in `sigrity_mcp/domains/cad/allegro_manufacturing_tools.py`)
- **status_category**: `built_untested` (implemented and self-documenting, never executed against a real sample on this machine)
- **verified_workaround**: NO (no sample input file exists on this machine to exercise them)

## What went wrong (the gap)

The IDF/IDX **import** tools are real, wrapped, and have fully self-documenting `-help` banners — but they were **never live-tested** because no real mechanical-import sample file (`.emn`/`.bdf`/`.out` for `idf_in`; `.idx` for `idx_in`) exists anywhere on this machine. The confirmed-live `idf_out`/`idx_out` (export) do run, but their import direction has no confirmed end-to-end evidence.

Important framing: "untested" here is not "known to fail" — the `-help` text documents that each tool can **create a brand-new `.brd` from mechanical data** (omitting `-i`/input design defaults the output design name), the same class of finding as `dxf2a`/`ipc2581_in`. The wrappers were deliberately wrapped despite being untested because they are the direct import-direction complement to the confirmed-live exporters.

## Evidence

- `core/tool_status.py` (`idf_in` note): "Real, fully self-documenting -help banner confirmed (`idf_in [-d <name_type>] <idf_file> [-o <output_design>] [-i <input_design>] [-p|-m|-f] [-a <accuracy>]`) -- explicitly supports creating a brand-new .brd from IDF mechanical data when -i is omitted (\"Default: <drawing_name>.brd\"), the same class of finding as dxf2a. Not live-tested: no real .emn/.bdf/.out (PTC/IDF/SDRC) sample file was found anywhere on this machine to test against."
- `core/tool_status.py` (`idx_in` note): "Real, fully self-documenting -help banner confirmed (`idx_in <idx_file> [-i <input_design>] [-o <output_design>]`), including a worked example. Not live-tested: no real .idx sample file was found on this machine."
- `allegro_manufacturing_tools.py` module docstring (lines 34–47): both exporters "CONFIRMED LIVE ... both run bare against a real board with zero preconditions," while "`idf_in.exe`/`idx_in.exe` ... are wrapped too but `built_untested`: no real `.emn`/`.bdf`/`.idx` sample file was found on this machine to run them against."
- `README.md` (mechanical exchange section): "`run_idf_import`/`run_idx_import` are also wrapped (`built_untested` — real, fully self-documenting `-help` banners confirmed, including each one's own documented ability to create a brand-new `.brd` from mechanical data the same way `dxf2a`/`ipc2581_in` do, but no real `.emn`/`.bdf`/`.idx` sample file was found on this machine to run them against)."
- Wrappers: `run_idf_import` (`allegro_manufacturing_tools.py:202-220`) and `run_idx_import` (`:223-233`), both `_resolve` their file paths and noted "BUILT, UNTESTED" in their own docstrings.

## What "success" would look like (unconfirmed)

- A real `.brd` (or merge into an existing board via `-i`/`input_board_file`), valid by `report.exe` re-read — analogous to the `ipc2581_in` / `dxf2a` import confirmations. Not yet produced.
