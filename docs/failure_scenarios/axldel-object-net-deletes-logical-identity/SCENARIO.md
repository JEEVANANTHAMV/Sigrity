# axlDeleteObject on NET Deletes Logical Identity Entirely

**Slug**: `axldel-object-net-deletes-logical-identity`
**Tool(s) affected**: `allegro_delete_connect` (allegro_geometry_tools.py), any caller using `object_type="NET"`
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

When `allegro_delete_connect` is called with `object_type="NET"` and `ripup=True` (which calls `axlDeleteObject(dbid 'ripup)` on the net's dbid), the net's **logical identity is deleted entirely** — not just its routed etch. Live-reproduced: after calling it on net X8, `run_allegro_report(..., report_code="net")` showed X8 had vanished from the net list completely (nets 75→74), its 2 pins went from W/Rats to Unused, and a subsequent `allegro_create_trace(..., net_name="X8")` created NOTHING (`axlDBCreatePath` silently returns nil for a nonexistent net name, per its own vendored doc). This is NOT a safe rip-up-for-reroute mechanism for whole nets.

## Root Cause

`axlDeleteObject(dbid 'ripup)` on a NET-type dbid performs a LOGIC delete of the net identity itself, not just its physical etch. The net's dbid is removed from the design database; the net ceases to exist as a logical entity. The `'ripup` flag erases the associated etch (the physical traces/vias), but the NET object itself is also destroyed. This is different from the intended use case of "rip up the etch, keep the net, re-route it" — the net is gone, so there is nothing to re-route to. The non-destructive rip-up that keeps the net intact is a different mechanism: `allegro_assign_net(object_type="PIN", ..., net_name=<the pin's own current net>, ripup=True)`, which strips the connected clines while leaving the net and its pins fully intact.

Note: `axlDeleteObject` without the `'ripup` flag (i.e., `ripup=False`) performs a "logic-only" delete per the vendored doc ("Deletion of nets is LOGIC only, and leaves the physical objects") — but this still deletes the net's logical identity, just without touching the physical etch. Either way, the net name cannot be reused by a subsequent `axlDBCreatePath` call because the net no longer exists in the database.

## Evidence

- `sigrity_mcp/core/tool_status.py:300-313` — "but with an important CAVEAT discovered the hard way: `axlDeleteObject` on a NET-type dbid (even with `'ripup`) deletes the net's LOGICAL IDENTITY ENTIRELY, not just its etch -- live-reproduced: after calling it on net X8, `run_allegro_report(..., report_code=\"net\")` showed X8 had vanished from the net list completely (nets 75->74), its 2 pins went from W/Rats to Unused, and a subsequent `allegro_create_trace(..., net_name=\"X8\")` created NOTHING (axlDBCreatePath silently returns nil for a nonexistent net net_name, per its own vendored doc) -- so this is NOT a safe rip-up-for-reroute mechanism for whole nets. The REAL, already-existing, non-destructive mechanism for that is `allegro_assign_net(object_type=\"PIN\", ..., net_name=<the pin's own current net>, ripup=True)` -- live-confirmed via `axlDBGetConnect`/net attribute queries that this correctly strips the connected clines (net goes to `unconnected=1`/ratsnest) while leaving the net and both pins fully intact."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:300-327` (allegro_delete_connect docstring) — "VERIFY, don't trust this tool's return value: SKILL return values never surface in the job log ... after `allegro_save_design` + `allegro_run_session`, independently confirm via `run_allegro_report(..., report_code=\"sum\")` (nets/pins/connections unchanged, the net now shows as ratsnest/unrouted) or `run_allegro_batch_drc` (the target violation gone)."
- `.forjinn/skills/sigrity-cad/SKILL.md:433-443` (Task 9) — "**DO NOT use `object_type=\"NET\"` expecting a non-destructive rip-up** — `axlDeleteObject` on a NET dbid deletes the net's LOGICAL IDENTITY ENTIRELY (live-reproduced: net count 75→74, its pins went Unused, and a follow-up `allegro_create_trace(..., net_name=\"<deleted net>\")` silently created NOTHING, since `axlDBCreatePath` returns nil for a nonexistent net per its own doc). **The real, non-destructive rip-up-for-reroute mechanism is the ALREADY-EXISTING `allegro_assign_net(object_type=\"PIN\", object_name=\"<a pin on the net>\", net_name=\"<that pin's own current net>\", ripup=True)`**."

## Pipeline Impact

Affects any rip-up-and-refix workflow that uses `allegro_delete_connect(object_type="NET")` to "rip up" a net before re-routing it. The net is destroyed, not just its etch. Subsequent `allegro_create_trace` calls targeting that net name will silently fail (nil return, no path created). The board's net count drops, and the deleted net's pins go to Unused. This is a hard failure, not a recoverable state — the net must be re-created (with a new `axlDBAssignNet` or equivalent) before it can be re-routed.
