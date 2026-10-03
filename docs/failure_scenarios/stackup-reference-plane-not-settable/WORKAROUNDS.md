# Workarounds: Reference Plane Not Settable via Any SKILL API

## Verified Workaround

Order your layers so the intended reference plane is **physically adjacent** to its signal layer in the stackup. Since Allegro infers reference plane from cross-section adjacency to a PLANE layer, the workaround is a design-planning decision made before calling `generate_multilayer_stackup`: arrange the `layers` list so that each signal layer's intended reference plane layer is the immediate neighbor (above or below) in the top-to-bottom sequence.

Example: if `L3_SIG1` should reference `L2_GND`, order the layers so `L2_GND` is immediately above `L3_SIG1` in the list (since index 0 = physical top, `L2_GND` would be at a lower index than `L3_SIG1` if it's physically above, or at a higher index if physically below).

Evidence: `.forjinn/skills/sigrity-cad/SKILL.md:266` — "Order your layers so the intended plane is physically adjacent to its signal layer."

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Order layers so intended plane is physically adjacent to signal layer | worked — Allegro's impedance calc infers ref plane from adjacency | SKILL.md Task 6 LIMITATION |
| 2 | Use `ref_plane`/`zone`/`hatched_plane` keys in layer dict to set explicit ref plane | didnt_work — metadata-only, no SKILL call generated | `sigrity_mcp/core/tool_status.py:210-214`; SKILL.md Task 6 |
| 3 | Search for a Constraint-Manager API to set ref plane | not_found — no `axlCNS*`/`axlCns*` function sets a physical ref-plane assignment | `sigrity_mcp/core/tool_status.py:211-212` |

## Prevention

1. Do NOT use `ref_plane`/`zone`/`hatched_plane` in a layer dict expecting them to create a real electrical reference-plane assignment. They are metadata-only bookkeeping keys. If you need to document the intended reference plane, use these keys for documentation purposes only, and separately verify physical adjacency in the `x-section` report.
2. When planning a multi-layer stackup, decide the reference-plane assignment per signal layer as part of the layer-ordering step, not as a separate attribute. Draw the stackup (top-to-bottom) on paper or in a spreadsheet, mark each signal layer's intended reference plane, and then pass the ordered list to `generate_multilayer_stackup`.
3. After stackup authoring, verify with `run_allegro_report(..., report_code="x-section")` that each signal layer's physical neighbor matches the intended reference plane. The report shows the top-to-bottom sequence with layer types — a PLANE layer adjacent to a CONDUCTOR layer is the inferred reference plane.

## Remaining Gaps

- **No in-suite fix exists.** This is a fundamental Allegro design-model limitation, not a tool gap. The reference plane is inferred, not assigned. No SKILL API on SPB 22.1 offers an explicit ref-plane setter.
- There is no tool-level validation that warns a caller when `ref_plane` is set but the physically adjacent layer is not a PLANE layer (or is not the one specified by `ref_plane`). The mismatch is silent and only detectable by reading the `x-section` report and comparing against intent.
- For high-speed designs where reference-plane assignment is critical (impedance control, return-path continuity), the physical adjacency constraint may conflict with other design requirements (e.g., a signal layer needing to be between two different plane layers for splitting reasons). There is no SKILL-level mechanism to override or annotate the inferred ref plane.
