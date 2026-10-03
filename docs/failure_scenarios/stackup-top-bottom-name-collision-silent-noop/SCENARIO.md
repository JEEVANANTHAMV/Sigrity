# TOP/BOTTOM Name Collision Causes Silent No-Op in Stackup Authoring

**Slug**: `stackup-top-bottom-name-collision-silent-noop`
**Tool(s) affected**: `generate_multilayer_stackup` (rigid_flex_stackup_tools.py), `allegro_create_stackup` (allegro_tools.py)
**Status category**: `silent_noop`
**Pipeline stage**: design

## Symptom

When a `layers` list passed to `generate_multilayer_stackup` includes entries whose `name` is literally `"TOP"` or `"BOTTOM"` — the same names as the board's pre-existing default outer layers — those two specific `axlXSectionCreate` calls are a **silent no-op**: no duplicate layer is created, no error is raised, the job exits rc 0, and the existing TOP/BOTTOM entries' thickness/material attributes are left completely unchanged. Confirmed live on the full 18-layer `build_18layer_rigid_flex_stackup_definition()`: layer 1 (named "TOP") and layer 18 (named "BOTTOM") both silently failed to land; the board kept its pre-existing default TOP/BOTTOM entries with unchanged attributes. Only the 16 internal layers (L2_GND through L17_GND4, including the RA_COPPER flex pair) actually got created. No error message appears in the job log or anywhere else.

## Root Cause

Allegro does not allow layer names above "top" or below "bottom" — Cadence's documented restriction. When `axlXSectionCreate(nil 'bottom <defstruct>)` is called with a `?name` that collides with the board's existing outer-layer name ("TOP" or "BOTTOM"), Allegro silently skips the creation entirely: no duplicate is made, the existing entry is not modified, and no error is returned. The SKILL call "succeeds" (returns a value) but produces zero change to the design database. This is consistent with Cadence's documented "does not allow name layers above top or below bottom" restriction, but the failure mode is a silent no-op rather than an error.

## Evidence

- `sigrity_mcp/core/tool_status.py:198-203` — "FOUND: creating a layer whose `name` collides with the board's existing default TOP/BOTTOM outer layer (as the 18-layer definition's own layer 1/18 do, both literally named \"TOP\"/\"BOTTOM\") is a silent no-op -- no duplicate, no error, no change to the existing entry's attributes; only the 16 internal layers of that 18-layer list actually get created, matching Cadence's documented \"does not allow name layers above top or below bottom\" restriction."
- `.forjinn/skills/sigrity-cad/SKILL.md:223-231` (Task 6, TOP/BOTTOM NAME-COLLISION GOTCHA) — "if your `layers` list reuses the literal names \"TOP\"/\"BOTTOM\" ... those two specific creates are a **silent no-op** — no duplicate, no error, no change to the existing TOP/BOTTOM entry's thickness/material. Confirmed live on the full 18-layer definition: all 16 INTERNAL layers (L2_GND..L17_GND4, including the RA_COPPER flex pair) landed correctly; TOP/BOTTOM stayed exactly as the board's pre-existing defaults."
- `sigrity_mcp/core/tool_status.py:189-191` — "the full real 18-layer `build_18layer_rigid_flex_stackup_definition()` list -- each time independently verified (bypassing SKILL entirely) by re-reading the saved board with `run_allegro_report(..., report_code=\"x-section\")`."

## Pipeline Impact

Affects any stackup authoring pipeline where the `layers` list includes entries named "TOP" or "BOTTOM". The tool reports success, the job exits rc 0, and `state` is "succeeded" — but the outer layers are not modified. This is dangerous because:
1. The caller believes they set a specific thickness/material for the outer layer, but the board keeps its original value.
2. An `x-section` report read-back will show the original TOP/BOTTOM entries, not the intended values — the mismatch is only detectable by comparing the report against the intended input list.
3. Downstream analysis (impedance, plane adjacency) may use the wrong outer-layer thickness.
