# dxf2a-conductor-class-partial-layer-mapping

- **tool**: `dxf2a` (`dxf2a.exe`, wrapped as `allegro_import_dxf` in `sigrity_mcp/domains/cad/allegro_import_tools.py`)
- **status_category**: `known_blocked` (a genuine dxf2a limitation on a brand-new design's default class table; no in-suite fix)
- **verified_workaround**: NO in-suite fix — the mitigations are detection-only (scan the job log for `Invalid class` lines) plus choosing `-g`/an existing design when full fidelity is required

## What went wrong

When dxf2a creates a **brand-new** design (its default mode, no `-g`), the starting class table is the default one for a fresh, empty design. If the supplied Layer Conversion File (`.cnv`) maps a DXF layer to a class that this default table does not recognize, dxf2a emits repeated `ERROR: Invalid class CONDUCTOR.` lines and **silently drops those layer's content** — the import still "completes" and writes a valid `.brd`, but the board is missing the geometry that was supposed to land on the unrecognized class. A caller who only checks that a `.brd` exists will assume every layer mapped correctly; it did not.

This is the sample's own behavior: Cadence's shipped `flag_l.cnv` (used in the confirmed-live tutorial run) maps a DXF layer to the `CONDUCTOR` class, which a fresh empty design's class table does not yet contain.

## Evidence

- `core/tool_status.py` (`dxf2a` note): "The sample flag_l.cnv also mapped a DXF layer to a class ('CONDUCTOR') a fresh empty design's default class table didn't recognize, producing repeated 'ERROR: Invalid class CONDUCTOR.' lines — dxf2a still completed and wrote a valid board regardless, but a caller should check the log for these before assuming every layer landed as mapped."
- `allegro_import_tools.py` module docstring (lines 28–34): "The sample flag_l.cnv mapped a DXF layer to the CONDUCTOR class, which a brand-new empty design's default class table doesn't yet recognize — this produced repeated `ERROR: Invalid class CONDUCTOR.` lines in the log, but did NOT stop dxf2a from completing and writing a valid board. A caller supplying their own cnv_file should expect the same: read the job log for `Invalid class` lines to see which DXF layers didn't land, rather than assuming a produced .brd means every layer mapped correctly."
- `allegro_import_tools.py:120-121`: `-g` (`update_existing=True`) is the documented mode that "merge[s] DXF data into an already-existing board" — i.e. into a design whose class table already contains the target classes.

## Symptoms a caller observes

- Repeated `ERROR: Invalid class <CLASSNAME>.` lines in `run.log`
- Job still ends `dxf2a complete.` and a `.brd` is written (plus rc 1, see the sibling scenario)
- The resulting board is missing the copper/geometry from the unmapped DXF layer(s) — visible only by comparing the board's layers/content against the DXF, not from the job result
