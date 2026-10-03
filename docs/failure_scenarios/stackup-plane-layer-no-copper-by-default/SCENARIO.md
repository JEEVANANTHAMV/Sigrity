# PLANE Layer Has Zero Copper by Default After Stackup Authoring

**Slug**: `stackup-plane-layer-no-copper-by-default`
**Tool(s) affected**: `generate_multilayer_stackup` (rigid_flex_stackup_tools.py), `allegro_create_stackup` (allegro_tools.py)
**Status category**: `precondition_error`
**Pipeline stage**: design

## Symptom

After authoring a multi-layer stackup via `generate_multilayer_stackup` (or `allegro_create_stackup`), any layer with `layer_type: "PLANE"` in the `layers` list has **zero actual copper** on it. The layer exists in the cross-section with the correct name, type, material, and thickness — but there is no copper geometry, no pour, no solid fill. The layer is a bare cross-section definition only. This is a precondition error: the caller must separately author copper geometry on the PLANE layer using `allegro_create_copper_shape` (with an explicit `points` boundary) before the layer has any physical copper. A board built purely from `generate_multilayer_stackup` with no follow-up copper-shape authoring will have PLANE layers that are electrically empty — no reference plane for adjacent signal layers, no return path, no ground plane.

## Root Cause

`generate_multilayer_stackup` and `allegro_create_stackup` use `axlXSectionCreate` (via `make_axlXSection`) which authors the layer **structure** (name/layerType/material/thickness) in the cross-section definition. This is a geometry-independent, structural operation — it defines what the layer IS (its dielectric thickness, its material, its name), but it does not create any copper geometry ON the layer. Creating actual copper (a shape, a pour, a solid fill) is a separate database operation (`axlDBCreateShape`) that requires explicit boundary coordinates and a net binding. The two operations are distinct in Allegro's data model: xsection (cross-section definition) vs. db (design database geometry). The tool suite's `generate_multilayer_stackup` only calls the former; it never calls the latter.

## Evidence

- `sigrity_mcp/core/tool_status.py:257-259` — "COPPER SHAPE / PLANE POUR: `generate_multilayer_stackup` authors layer STRUCTURE (name/layerType/material/thickness via axlXSectionCreate) but never created any actual copper -- a new tool, `allegro_create_copper_shape` (axlDBCreateShape, allegro_geometry_tools.py), closes this gap."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:81-95` (module docstring) — "`allegro_create_copper_shape` (`axlDBCreateShape`) closes a real, high-leverage gap found in a later pass: `generate_multilayer_stackup`/`allegro_create_stackup` ... author layer STRUCTURE (name/type/material/thickness via `axlXSectionCreate`) but never create any actual copper geometry — a \"PLANE\"-typed layer from those tools is a cross-section definition only, zero copper poured onto it."
- `.forjinn/skills/sigrity-cad/SKILL.md:287-288` (Task 7) — "`generate_multilayer_stackup` (Task 6) authors layer STRUCTURE only — a \"PLANE\"-typed layer it creates has zero actual copper on it. `allegro_create_copper_shape` (`axlDBCreateShape`, `allegro_geometry_tools.py`) closes that gap."

## Pipeline Impact

Affects any pipeline that authors a stackup and then proceeds to routing, DRC, or analysis without separately authoring copper on the PLANE layers. A signal layer adjacent to an empty PLANE layer has no reference plane (no return path), which affects:
1. **Impedance calculations**: a signal layer with no adjacent copper plane has uncontrolled impedance.
2. **DRC**: spacing rules between signal copper and the (empty) plane layer may not be enforced correctly.
3. **Routing**: the autorouter may not recognize the PLANE layer as a valid reference for return-path routing.
4. **PowerDC/analysis**: a PLANE layer with no copper cannot carry current, so net-pair binds and power-flow analysis will not work on that layer.
