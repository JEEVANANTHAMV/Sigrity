# Stackup Layer Ordering Inverted by 'bottom' Queuing

**Slug**: `stackup-layer-ordering-inverted`
**Tool(s) affected**: `generate_multilayer_stackup` (rigid_flex_stackup_tools.py), `allegro_create_stackup` (allegro_tools.py)
**Status category**: `precondition_error`
**Pipeline stage**: design

## Symptom

When queuing multiple layers into an `axlXSectionCreate(nil 'bottom <defstruct>)` stack in the order suggested by Cadence's own vendored doc tip ("build the stackup from bottom to top"), the resulting cross-section comes out **inverted**: the first-queued layer lands nearest the top, the last-queued layer lands nearest the true bottom. The board is not corrupted — no error is raised, the job exits rc 0, and the layer structure exists with correct name/layerType/material/thickness — but the physical stackup order is the mirror image of the caller's intent. A 3-layer live test (TOPTEST/PLANETEST/BOTTOMTEST in the doc-suggested reversed order) produced the exact opposite of the intended top-to-bottom layout; re-running with the list in chronological top-to-bottom order fixed it.

## Root Cause

`axlXSectionCreate`'s `'bottom` endpoint inserts each new layer directly adjacent to the board's real, pre-existing outer BOTTOM layer, pushing all previously inserted bottom-adjacent layers further up (toward the top) with each successive call. So queuing layers one per call via `'bottom` in the order you pass them chronologically (index 0 = your intended physical top) is what lands them in the correct top-to-bottom order — the opposite of the literal reading of `axlXSectionCreate.txt`'s "build the stackup from bottom to top" tip. `'top`/`'afterBottom` are restricted by Allegro to unnamed dielectric/MASK layers for PCB designs, so `'bottom` is the only endpoint usable for a real named CONDUCTOR/PLANE stackup, making the ordering behavior unavoidable and order-dependent.

This is a precondition error in the calling agent's understanding of the endpoint semantics, not a bug in the tool itself — the tool queues exactly what the caller passes, in the order passed. The fix is in the caller's layer-ordering logic, not in the SKILL emit.

## Evidence

- `sigrity_mcp/core/tool_status.py:193-197` — "CONFIRMED: name/layerType/material/thickness are genuinely authored and land in the correct top-to-bottom order PROVIDED you queue layers via `axlXSectionCreate(nil 'bottom <defstruct>)` IN THE SAME order as your top-to-bottom layer list (NOT reversed -- a literal reading of axlXSectionCreate.txt's own \"build the stackup from bottom to top\" tip was tried first and empirically produced the OPPOSITE, inverted order; see generate_multilayer_stackup's docstring for the full before/after evidence)."
- `.forjinn/skills/sigrity-cad/SKILL.md:211-222` (Task 6, ORDERING GOTCHA) — "every layer is queued via `axlXSectionCreate(nil 'bottom <defstruct>)` **in the same order you pass them** — do NOT reverse the list. A literal reading of Cadence's own vendored doc tip ... was tried and LIVE-VERIFIED WRONG — it produced the exact inverted order (first-queued landed nearest the top, last-queued landed nearest the true bottom). Empirically, each successive `'bottom` insert lands directly adjacent to the board's real outer BOTTOM layer, pushing earlier inserts further up."
- `sigrity_mcp/core/tool_status.py:186-192` — "run live 4 times against fresh copies of the real sample board -- a 3-layer test (twice, once with an ordering bug then again after fixing it) and the full real 18-layer `build_18layer_rigid_flex_stackup_definition()` list -- each time independently verified (bypassing SKILL entirely) by re-reading the saved board with `run_allegro_report(..., report_code=\"x-section\")`."

## Pipeline Impact

Affects any multi-layer stackup authoring pipeline. A board built with the inverted order will have the wrong physical adjacency between signal and plane layers (e.g., a signal layer that should be adjacent to a ground plane ends up adjacent to a different dielectric or signal layer), which propagates into impedance calculations, plane-adjacency assumptions for routing, and any downstream analysis that depends on the physical stackup order. The board loads, DRCs, and reports normally — the inversion is silent and only visible in an `x-section` report read-back.
