# allegro_create_trace with Self-Overlapping Path Silently Returns Nil

**Slug**: `createtrace-self-overlapping-path-silent-nil`
**Tool(s) affected**: `allegro_create_trace` (allegro_geometry_tools.py)
**Status category**: `precondition_error`
**Pipeline stage**: design

## Symptom

When a manually-designed trace path (e.g., a meander for length-matching) **self-overlaps** — two segments coincident on the same axis (same Y for horizontal segments, or same X for vertical segments) with overlapping ranges on the other axis — `axlDBCreatePath` **silently returns nil**: 0 segments created, `Missing Connections: 1`, same failure signature as the bare-layer-name bug but a DIFFERENT cause (self-overlapping path geometry, not a tool bug). No error appears in the job log. The failure signature is identical to the layer-string bug (nil return, 0 segments, `Missing Connections: 1`), which makes it easy to misdiagnose. A corrected, non-self-overlapping meander ran in the normal ~5-6s and produced a real connected path.

## Root Cause

`axlDBCreatePath` rejects self-overlapping path geometry: if any two segments in the path share both an axis value (same X for vertical segments, same Y for horizontal segments) AND an overlapping range on the other axis, the path is considered invalid and the function silently returns nil. This is a geometric validity constraint on the path itself, not a tool bug. The first meander attempt in the length-matching investigation accidentally re-traced part of its own path (two segments coincident on the same Y, one running back over part of the other's X range) — `axlDBCreatePath` rejected it silently.

The detection criterion: for every pair of segments in the path, check whether they share an axis value (same X or same Y) AND have overlapping ranges on the other axis. If any pair does, the path self-overlaps and will be rejected.

## Evidence

- `sigrity_mcp/core/tool_status.py:372-380` — "FOUND A FOURTH thing worth recording, this one a real geometry-design mistake rather than a tool bug: a first attempt at the meander accidentally retraced part of its own path (two segments coincident on the same Y, one running back over part of the other's X range) -- `axlDBCreatePath` silently returned nil for this (0 segments created, `Missing Connections: 1`, same failure SIGNATURE as the layer-string bug above but a DIFFERENT cause -- self-overlapping path geometry, not a tool bug this time). A corrected, non-self-overlapping meander (verified point-by-point: no two segments share both an axis value AND an overlapping range) fixed it: `allegro_run_session` completed in the normal ~5-6s, `axlDBGetLength` independently confirmed the new real length as EXACTLY `3100.0` mil."
- `.forjinn/skills/sigrity-cad/SKILL.md:527-542` (Task 9, Gotcha #4) — "**Gotcha #4 (a geometry-design mistake, not a tool bug)**: the first meander attempt accidentally RETRACED part of its own path (two segments coincident on the same Y, one re-walking part of the other's X range) — `axlDBCreatePath` silently returned nil for this (0 segments, `Missing Connections: 1` — same FAILURE SIGNATURE as the layer-string bug, but a different cause). Lesson: when hand-designing a meander/detour, verify no two segments share both an axis value (same X or same Y) AND an overlapping range on the other axis — that's a self-overlap, and `axlDBCreatePath` rejects it silently just like a missing/wrong layer string, with no error anywhere in the job log."

## Pipeline Impact

Affects any manual trace-creation pipeline where the path is hand-designed (e.g., a meander for length-matching, a detour around keepouts). A self-overlapping path silently fails — the same failure signature as the (now-fixed) layer-string bug — and the only way to detect it is to independently verify via `run_allegro_report(report_code="sum")` (`Missing Connections` should be 0 for a successful trace) or by querying the created path via `axlDBGetConnect`. The failure is a precondition error on the caller's geometry, not a tool bug.
