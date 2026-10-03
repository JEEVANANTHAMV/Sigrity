# ipc2581-in-layer-stackup-import-failed — Workarounds

## What works (confirmed / documented)

- **Detection — read the job log for `Layer stackup import failed.`** on any `-x -g` run. The `tool_status` note explicitly frames this as "a genuine partial-import diagnostic to surface to the caller," so surfacing it is the prescribed handling.
- **Fall back to the basic import** (`import_stackup=False, import_layer_features=False`) when a valid board is acceptable without the IPC-2581 layer stackup — that path is confirmed to complete cleanly (200 KB `.brd`, valid by `report.exe`).
- **Verify the imported board's stackup** with `run_allegro_report(report_code="x-section")` on the produced `.brd` if the layer stackup matters (independent read, not the job result).
- **Author the stackup in-suite if needed**: `generate_multilayer_stackup` (SKILL `axlXSectionCreate`, see sigrity-cad SKILL.md Task 6) can build a real multi-layer stackup on an already-imported board, decoupling the (working) geometry import from the (failing) stackup import.

## What was tried / ruled out

- No in-suite mechanism makes `-x -g` import the stackup successfully against the confirmed sample — the manifest classifies this as `known_blocked` / "genuine partial-import limitation." There is no alternate ipc2581_in flag that changes the outcome.

## Notes

- The basic-import board and the `-x -g` board both re-read valid with real layer/DRC data; the difference is specifically the stackup content, so "it produced a board" is necessary but not sufficient evidence of a full `-x -g` import.
