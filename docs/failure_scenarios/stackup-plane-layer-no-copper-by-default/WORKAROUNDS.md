# Workarounds: PLANE Layer Has Zero Copper by Default After Stackup Authoring

## Verified Workaround

After `generate_multilayer_stackup`, call `allegro_create_copper_shape` for each PLANE layer that needs real copper. The tool requires:
- `layer`: the bare xsection layer name (e.g., `"L2_GND"`, matching the `name` you gave `generate_multilayer_stackup`)
- `net_name`: the net to bind the copper to (e.g., `"GND"`)
- `points`: an explicit closed boundary as `[[x, y], ...]` in board units — **REQUIRED, no auto-derive default** (see the `copper-shape-board-autoderive-disproven` scenario for why)
- `dynamic=True` (default): creates a `BOUNDARY/<layer>` shape (connectivity-driven plane pour); `dynamic=False`: creates a plain `ETCH/<layer>` static filled shape

Use `allegro_get_board_extent_points(board_file, margin)` to derive a safe whole-board rectangle from the board's actual placed pin extents, then pass its `points` to `allegro_create_copper_shape`.

CONFIRMED LIVE 3 independent ways (see `copper-shape-board-autoderive-disproven` WORKAROUNDS.md for the full verification evidence): in-session SKILL query, second independent Allegro process re-opening the saved board, and PowerSI BRD-bridge `.spd` translation.

Evidence: `.forjinn/skills/sigrity-cad/SKILL.md:293-345` (Task 7, full example + verification).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Call `allegro_create_copper_shape` with explicit `points` after stackup authoring | worked — real, net-bound, solid-filled copper on the PLANE layer, verified 3 ways | SKILL.md Task 7; `sigrity_mcp/core/tool_status.py:257-274` |
| 2 | Rely on `generate_multilayer_stackup` alone to create PLANE-layer copper | didnt_work — PLANE layer has zero copper, cross-section definition only | `sigrity_mcp/domains/cad/allegro_geometry_tools.py:81-95` |
| 3 | Auto-derive pour boundary from `axlDBGetShapes("BOARD GEOMETRY/OUTLINE")` | didnt_work — returns nil on real boards (see `copper-shape-board-autoderive-disproven`) | `sigrity_mcp/core/tool_status.py:274-283` |

## Prevention

1. Do NOT assume that `generate_multilayer_stackup` creates copper on PLANE layers. It does not. After any stackup authoring, check which PLANE layers need copper and call `allegro_create_copper_shape` for each one.
2. Always verify copper authoring with an independent read: `axlDBGetShapes("<class>/<layer>")` query (captured via SKILL's `outfile`/`fprintf`), a second Allegro process re-opening the saved board, or a `.spd` translation — at least two of the three for high-confidence verification.
3. If the pipeline is "stackup → route → DRC → analysis", insert an explicit "author copper on all PLANE layers" step between stackup and routing. A board with empty PLANE layers will pass DRC (no copper to violate) but fail analysis (no return path).

## Remaining Gaps

- `allegro_create_copper_shape` is a minimal-scope tool: it creates a single solid-filled shape on one layer/net. It does NOT handle voids, keepouts, or multiple non-contiguous pour regions. For complex pour patterns (keepout polygons, multi-region pours, hatched planes), the caller must hand-write SKILL from the real worked example `share/pcb/examples/skill/dbcreate/axldbctshp.il`.
- There is no tool that auto-generates the `points` boundary from the board's physical outline. The `allegro_get_board_extent_points` tool derives a safe rectangle from pin extents + margin, but this is NOT the same as the board's actual outline shape. For a board with a non-rectangular outline, the caller must pass their own exact outline polygon.
- There is no tool that pours copper on ALL PLANE layers in one call. Each PLANE layer requires a separate `allegro_create_copper_shape` call within the same SKILL session (or a hand-written SKILL script that loops over the PLANE layers).
