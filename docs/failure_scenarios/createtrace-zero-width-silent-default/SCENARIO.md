# allegro_create_trace with No Width Creates Zero-Width Copper

**Slug**: `createtrace-zero-width-silent-default`
**Tool(s) affected**: `allegro_create_trace` (allegro_geometry_tools.py)
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

When `allegro_create_trace`'s original implementation called `axlPathStart(points)` with NO width argument, the resulting trace had **zero width** on every segment. Live-confirmed via `axlDBGetConnect`'s own segment/width attributes: `width=0.0` on every one of the 7 segments of a tool-created trace. This produced real new "Minimum Neck Width" DRC violations (required 5 MIL, actual 0 MIL) and spurious near-zero-clearance "Line to Line"/"Line to Pin Spacing" violations against unrelated nearby copper (a 0-width line consumes none of the real clearance budget, so it reads as sitting almost exactly on top of neighboring copper/pins even when its center-line path was chosen to clear them). Per the vendored `axlPathStart.txt` doc, the second argument (`f_width`) "becomes the default width for all ... segments" — omitting it does NOT mean "inherit the net's/board's default trace width" as might be assumed; it silently creates zero-width copper.

## Root Cause

`axlPathStart(points)`'s second argument (`f_width`) is the trace width in board/design units. It is NOT optional with a meaningful default — omitting it defaults to 0 (zero width). The original `allegro_create_trace` implementation called `axlPathStart(points)` with no second argument, assuming that Allegro would inherit the board's or net's default trace width. Allegro does not do this: the width defaults to 0. The result is a trace with zero-width copper that immediately violates DRC (Minimum Neck Width, near-zero clearance spacing) despite the center-line path being geometrically valid.

This is now FIXED: `width` is a REQUIRED parameter (no silent default) threaded straight into `axlPathStart`. A caller who omits `width` gets a `TypeError` from Python, not a silent zero-width trace.

## Evidence

- `sigrity_mcp/core/tool_status.py:323-328` — "(b) it called `axlPathStart(points)` with NO width argument; per `axlPathStart.txt`, the second argument IS the trace width and silently defaults to 0 if omitted -- live-reproduced via `axlDBGetConnect`'s own segment/width attributes showing `width=0.0` on every segment of a tool-created trace, which in turn produced real new \"Minimum Neck Width\" DRC violations (required 5 MIL, actual 0 MIL) and spurious near-0-clearance spacing violations against unrelated nearby copper; fixed by adding a REQUIRED `width` parameter (no silent default) threaded into `axlPathStart`."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:157-176` (allegro_create_trace docstring) — "`width` (board/design units, e.g. mils) is REQUIRED — a second, independent real bug found live in the same routing-capability investigation that found the layer-string bug above: the original implementation called `axlPathStart(points)` with NO second argument. Per the vendored `axlPathStart.txt` doc, that second argument (`f_width`) \"becomes the default width for all ... segments\" — omitting it does not mean \"inherit the net's/board's default trace width\" as might be assumed; it silently creates **zero-width copper**. LIVE-CONFIRMED on the real Fault-Detector sample: a trace created the old way, independently re-queried via `axlDBGetConnect`'s own `segments`/`width` attributes, showed `width=0.0` on every one of its 7 segments, and `run_allegro_batch_drc` + `run_allegro_report(..., report_code=\"drc\")` flagged it with real new \"Minimum Neck Width\" (required 5 MIL, actual 0 MIL) and near-zero \"Line to Line\"/\"Line to Pin Spacing\" violations against nearby copper."
- `.forjinn/skills/sigrity-cad/SKILL.md:453-459` (Task 9, bug 2) — "**Width**: called `axlPathStart(points)` with no width arg — per `axlPathStart.txt`, that argument IS the trace width, defaulting to 0 if omitted. Live-confirmed `width=0.0` on every segment of a tool-created trace (via `axlDBGetConnect`'s own `seg->width`), producing real new \"Minimum Neck Width\" DRC violations and spurious near-0-clearance spacing hits against unrelated nearby copper (a 0-width line consumes none of the real clearance budget). Now fixed: `width` is a REQUIRED parameter (no silent default) threaded straight into `axlPathStart`."

## Pipeline Impact

Affects any trace-creation pipeline. Before the fix, a caller who omitted `width` (or who used an older copy of the tool) got a zero-width trace that violated DRC. The DRC violations are REAL (not false positives) — the trace really is zero-width. After the fix, `width` is required and a caller cannot create a zero-width trace without explicitly passing `width=0.0` (which would still be a DRC violation, but at least the caller made a conscious choice).
