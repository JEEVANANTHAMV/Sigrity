# dxf2a-conductor-class-partial-layer-mapping — Workarounds

## What works (confirmed / documented)

- **Detection — always scan the job log for `Invalid class` lines** (explicitly prescribed by both the module docstring and `tool_status`): each named class in those lines tells you which DXF layer(s) from your `.cnv` did NOT land. A produced `.brd` alone proves nothing about per-layer completeness.
- **Use `update_existing=True` (dxf2a `-g`)** when merging into an existing board that already carries the needed class definitions — the failure is specific to a *fresh empty design's* default class table. (`allegro_import_dxf(update_existing=True)` at `allegro_import_tools.py:120-121`.)
- **Verify the result content**, not just existence: re-read the produced `.brd` with `run_allegro_report(report_code="sum")` and check the layer/geometry totals against what the `.cnv`+DXF map expected.

## What was tried / ruled out

- No in-suite mechanism creates or pre-populates classes on the fresh dxf2a design before mapping (no SKILL pre-step is wired into `allegro_import_dxf`); the only confirmed lever is the `-g`/existing-design mode. The manifest classifies the fresh-design partial mapping itself as `known_blocked`.

## Notes

- The sample `flag_l.cnv` triggers this out of the box (its `CONDUCTOR` mapping), so it reproduces with Cadence's own shipped tutorial input — this is not an exotic caller error.
