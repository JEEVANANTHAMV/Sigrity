# Reference Plane Not Settable via Any SKILL API

**Slug**: `stackup-reference-plane-not-settable`
**Tool(s) affected**: `generate_multilayer_stackup` (rigid_flex_stackup_tools.py), `allegro_create_stackup` (allegro_tools.py), any layer-dict caller using `ref_plane`/`zone`/`hatched_plane` keys
**Status category**: `known_blocked`
**Pipeline stage**: design

## Symptom

A caller cannot explicitly assign an electrical "reference plane" to a signal layer via any SKILL API on this SPB 22.1 install. The `ref_plane`, `zone`, and `hatched_plane` keys in a `generate_multilayer_stackup` layer dict are **metadata-only** — they are echoed back in the tool's return value for bookkeeping but produce no real SKILL call and have no effect on the design database. Allegro infers a signal layer's reference plane from stackup **adjacency** to a PLANE layer, not from a settable field. A caller who expects `{"name":"L3_SIG1","layer_type":"CONDUCTOR","ref_plane":"L2_GND"}` to create an explicit electrical reference-plane assignment gets no such assignment landed — only the physical adjacency (if any) determines the reference plane.

## Root Cause

Searched the full `axlXSectionGet.txt` attribute table plus every `axlCNS*`/`axlCns*` Constraint-Manager function on this install: **no SKILL attribute exists anywhere** for an explicit "reference plane" assignment. The xsection attributes that ARE real and settable are limited to `name`, `layerType`, `material`, and `thickness` (confirmed against `axlXSectionGet.txt`'s own attribute table and the real example `share/pcb/examples/skill/dbcreate/xsection.il`). The Constraint Manager (`axlCNS*`/`axlCns*`) functions deal with electrical rules (spacing, width, length matching, via rules) but not with the physical-to-electrical plane-adjacency mapping. Allegro's impedance calculator and routing engine infer the reference plane purely from which PLANE layer is physically adjacent to the signal layer in the cross-section — this is a design-level inference, not a settable field.

## Evidence

- `sigrity_mcp/core/tool_status.py:210-214` — "NOT settable via any SKILL API found on this install (searched the full axlXSectionGet.txt attribute table plus every axlCNS*/axlCns* Constraint-Manager function): an explicit electrical \"reference plane\" assignment -- Allegro infers this from stackup adjacency to a PLANE layer, not a field you set, so `ref_plane`/`zone`/`hatched_plane` in a layer dict are metadata-only, not real SKILL calls."
- `.forjinn/skills/sigrity-cad/SKILL.md:257-266` (Task 6, LIMITATION) — "only `name`/`layerType`/`material`/`thickness` are real, settable xsection attributes (confirmed against `axlXSectionGet.txt`'s own attribute table and the real example `share/pcb/examples/skill/dbcreate/xsection.il`). There is **no SKILL attribute anywhere** for an explicit \"reference plane\" assignment — searched the full attribute table plus every `axlCNS*`/`axlCns*` Constraint-Manager function on this install. Allegro's impedance calculator infers a signal layer's reference plane from stackup ADJACENCY to a PLANE layer, not from a settable field — so `ref_plane`/`zone`/`hatched_plane` in a layer dict are metadata echoed back for bookkeeping only, not real SKILL calls. Order your layers so the intended plane is physically adjacent to its signal layer."

## Pipeline Impact

Affects any stackup authoring pipeline where the caller intends to set an explicit reference plane per signal layer. The `ref_plane`/`zone`/`hatched_plane` keys in the layer dict give a false sense of assurance — they appear in the tool's return value but have no effect on the board. The only way to control reference plane assignment is to physically order the layers so the intended plane layer is adjacent to the signal layer in the cross-section. This is a design-planning constraint, not a tool-call constraint.
