# Auto-Derive Pour Boundary from Board Outline Is Disproven

**Slug**: `copper-shape-board-autoderive-disproven`
**Tool(s) affected**: `allegro_create_copper_shape` (allegro_geometry_tools.py) — specifically the rejected design of an auto-derive-from-board-outline default
**Status category**: `precondition_error`
**Pipeline stage**: design

## Symptom

The earlier design consideration of defaulting `allegro_create_copper_shape`'s pour boundary to `(car (axlPolyFromDB (car (axlDBGetShapes "BOARD GEOMETRY/OUTLINE"))))` ("pour the whole board outline with no coordinates needed") was **live-tested and disproven** against the real Fault-Detector sample board. `axlDBGetShapes("BOARD GEOMETRY/OUTLINE")` returned `nil` — the board's physical outline is drawn as plain LINE/ARC segments, NOT a shape database object that `axlDBGetShapes` can find. A components-bounding-box fallback (`axlDBGetExtents(axlDBGetDesign()->components nil)`) was also tried live and returned a degenerate `((0.0 0.0) (0.0 0.0))` box. There is NO reliable SKILL-based auto-derive path for the board outline. The tool therefore requires an explicit `points` boundary (no silent, possibly-empty default).

## Root Cause

Allegro's board physical outline is NOT stored as a shape database object on all boards. On the real Fault-Detector sample board, the physical board outline is drawn as plain LINE and ARC segments (a set of individual line/arc geometry primitives), not as a `BOARD GEOMETRY/OUTLINE` shape object. There are 157 real shapes on this board, ALL of them `PACKAGE GEOMETRY/*` (component silkscreen, assembly outlines, place-bound outlines) — **zero** `BOARD GEOMETRY/*` shapes of any kind. The `axlDBGetShapes` function queries the shape database, which does not contain the board outline as a shape object on this board. The components-bounding-box fallback fails because the components' extents do not meaningfully bound the board (the board outline extends beyond the component cluster, and in this case the component extents query returned a degenerate zero-area box).

The `report_code="sum"` "Drawing Extents" (XL/YL/XU/YU) is also NOT reliable for this purpose — it is the inherited drawing sheet size, not the board geometry. Confirmed on two structurally different real boards reporting byte-identical extents (the same sheet size).

## Evidence

- `sigrity_mcp/core/tool_status.py:274-283` — "KEY FINDING (corrects an original design assumption): auto-deriving the pour boundary from `axlDBGetShapes(\"BOARD GEOMETRY/OUTLINE\")` (\"pour the whole board outline with no coordinates needed\") was tried first and LIVE-DISPROVEN -- on the real Fault-Detector sample board this returned nil; the board's physical outline is drawn as plain LINE/ARC segments, not a shape database object (confirmed: the board has 157 real shapes total, all of them `PACKAGE GEOMETRY/*` component silkscreen/assembly/place-bound outlines -- zero `BOARD GEOMETRY/*` shapes of any kind). A components-bounding-box fallback (`axlDBGetExtents(axlDBGetDesign()->components nil)`) was also tried live and returned a degenerate `((0.0 0.0) (0.0 0.0))` box, so `allegro_create_copper_shape` instead REQUIRES an explicit `points` boundary (no silent, possibly-empty default)."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:389-413` (allegro_create_copper_shape docstring) — "REQUIRED, deliberately with NO auto-derive-from-board-outline default: an earlier design considered defaulting to `(car (axlPolyFromDB (car (axlDBGetShapes \"BOARD GEOMETRY/OUTLINE\"))))` ... but this was LIVE-TESTED and DISPROVEN against a real board (the Fault-Detector sample): `axlDBGetShapes(\"BOARD GEOMETRY/OUTLINE\")` returned `nil` — a real board's physical outline is typically drawn as plain LINE/ARC segments, not a \"shape\" database object, so there is nothing for `axlDBGetShapes` to find there (confirmed: this board has 157 real shapes total, all of them `PACKAGE GEOMETRY/*` ... zero `BOARD GEOMETRY/*` shapes of any kind). A components-bounding-box fallback ... was also tried live and returned a degenerate `((0.0 0.0) (0.0 0.0))` box."
- `.forjinn/skills/sigrity-cad/SKILL.md:316-327` (Task 7) — "points is REQUIRED — there is deliberately no auto-derive-from-board-outline default. An earlier design considered defaulting to `(car (axlPolyFromDB (car (axlDBGetShapes \"BOARD GEOMETRY/OUTLINE\"))))` ... and this was LIVE-TESTED AND DISPROVEN against the real Fault-Detector sample: `axlDBGetShapes(\"BOARD GEOMETRY/OUTLINE\")` returned `nil` ... So: read the board's real extents first (`run_allegro_report(..., report_code=\"sum\")` → `Drawing Extents XL/YL/XU/YU`, in mils) and pass them as an explicit rectangle, or pass your own exact outline/sub-region polygon."

## Pipeline Impact

Affects any pipeline that expected to auto-derive a copper pour boundary from the board outline without explicitly passing `points`. The auto-derive default was rejected at design time; the tool requires explicit `points`. A caller who does not pass `points` (or passes an empty/invalid list) will get a `ValueError` from the tool's `len(points) < 3` check. There is no silent fallback.
