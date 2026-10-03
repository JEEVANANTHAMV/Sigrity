# Workarounds: Auto-Derive Pour Boundary from Board Outline Is Disproven

## Verified Workaround

Use `allegro_get_board_extent_points(board_file, margin)` to derive a safe, board-specific rectangle from the board's **actual placed pin extents** plus a margin, then pass its `points` straight through to `allegro_create_copper_shape`. This is verified safer than the "Drawing Extents"/`sum`-report bounding box.

Example flow:
```
allegro_get_board_extent_points(board_file="…\\fd.brd", margin=500.0)
  -> {points:[[7500,13900],[14700,13900],[14700,19200],[7500,19200]], real_pin_extent:{...}}
allegro_create_copper_shape(session_id, layer="L2_GND", net_name="GND",
    points=[[7500,13900],[14700,13900],[14700,19200],[7500,19200]], dynamic=True)
```

Alternatively, pass your own exact outline/sub-region polygon (e.g., from your own design records, or from converting the outline's LINE segments via `axlDBComposeShapesFromLines` first — not wrapped by this tool).

Evidence: `sigrity_mcp/domains/cad/allegro_geometry_tools.py:406-413` (allegro_create_copper_shape docstring); `.forjinn/skills/sigrity-cad/SKILL.md:294-303` (Task 7 example).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | `allegro_get_board_extent_points` → pass `points` to `allegro_create_copper_shape` | worked — safe board-specific rectangle from pin extents + margin | `allegro_geometry_tools.py:406-413`; SKILL.md Task 7 |
| 2 | `(car (axlPolyFromDB (car (axlDBGetShapes "BOARD GEOMETRY/OUTLINE"))))` | didnt_work — returns nil on real boards (outline is LINE/ARC segments, not a shape object) | `sigrity_mcp/core/tool_status.py:274-279` |
| 3 | `axlDBGetExtents(axlDBGetDesign()->components nil)` (components bounding box) | didnt_work — returned degenerate `((0.0 0.0) (0.0 0.0))` box | `sigrity_mcp/core/tool_status.py:280-282` |
| 4 | `report_code="sum"` "Drawing Extents" (XL/YL/XU/YU) | unreliable — inherited drawing sheet size, not board geometry; two different boards reported byte-identical extents | `allegro_geometry_tools.py:410-413` |

## Prevention

1. Do NOT try to auto-derive the pour boundary from `axlDBGetShapes("BOARD GEOMETRY/OUTLINE")`. It returns `nil` on boards where the outline is drawn as LINE/ARC segments (the common case, including the real Fault-Detector sample).
2. Do NOT use the `report_code="sum"` "Drawing Extents" as the pour boundary. It is the drawing sheet size, not the board geometry.
3. Use `allegro_get_board_extent_points` for a safe "whole populated board" default, or pass your own exact outline polygon for shape-accurate pours.
4. Always verify the pour landed with an independent read (see the `stackup-plane-layer-no-copper-by-default` WORKAROUNDS.md for the 3-way verification method).

## Remaining Gaps

- `allegro_get_board_extent_points` derives a rectangle from pin extents + margin. This is NOT the same as the board's actual outline shape. For a board with a non-rectangular outline (e.g., an octagonal or L-shaped board), the extent rectangle will be an over-approximation — it will cover areas outside the physical board outline where there is no substrate. This is acceptable for a "populated-area" pour but not for a full-board-outline pour.
- There is no tool that converts the board's outline LINE/ARC segments into a shape polygon for `axlDBCreateShape`. The `axlDBComposeShapesFromLines` SKILL function exists but is not wrapped by any tool in this suite. A caller who needs an exact outline-shaped pour must hand-write the SKILL conversion.
- The components-bounding-box fallback is unreliable (degenerate box on the test board) and should NOT be used as a fallback for `axlDBGetShapes("BOARD GEOMETRY/OUTLINE")`.
