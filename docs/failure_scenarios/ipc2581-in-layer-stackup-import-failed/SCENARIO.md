# ipc2581-in-layer-stackup-import-failed

- **tool**: `ipc2581_in` (`ipc2581_in.exe`, wrapped as `run_ipc2581_import` in `sigrity_mcp/domains/cad/allegro_manufacturing_tools.py`)
- **status_category**: `known_blocked` (a genuine partial-import limitation of ipc2581_in, surfaced as a readable warning — not a wrapper bug, not a crash)
- **verified_workaround**: NO (no in-suite fix) — detection + optional fallback to the no-`-x -g` basic import

## What went wrong

Running `ipc2581_in.exe` with the layer-stackup / layer-feature import flags (`-x -g` = `import_stackup=True, import_layer_features=True`) against a real IPC-2581 file surfaces the readable warning **`Layer stackup import failed.`** The import does not crash — it completes and writes a (larger) `.brd` — but the requested layer stackup was not imported, i.e. the result is a genuine **partial import**. A caller that requested stackup+features and only checks that a `.brd` was produced assumes the stackup landed; it did not.

For context, the same tool **without** those flags (basic import) completed cleanly against the same sample.

## Evidence

- `core/tool_status.py` (`ipc2581_in` note): "Live-tested against the real shipped sample share/Translators/Samples/ipc2581/demo2.xml (3.4MB): produced a genuine 200KB .brd (basic import) and, with -x -g (import layer stackup + layer features), a fuller 1.58MB .brd -- both independently confirmed valid boards by re-reading with report.exe (real layer/DRC data). One real, readable warning surfaced (\"Layer stackup import failed.\") on the -x -g run -- not a crash, a genuine partial-import diagnostic to surface to the caller."
- `allegro_manufacturing_tools.py:137-157`: `run_ipc2581_import` maps `import_stackup` → `-x` and `import_layer_features` → `-g`, so the wrapper itself does construct the flag combination that triggers the warning; the flag spelling is not the problem.

## Symptoms a caller observes

- `run_ipc2581_import(..., import_stackup=True, import_layer_features=True)` job completes (a `.brd` is written, larger than the basic-import version)
- `Layer stackup import failed.` line in the job log
- The produced board is missing the layer stackup that `-x` was meant to import (only fully verifiable by re-reading the board's x-section, not from the job result)
