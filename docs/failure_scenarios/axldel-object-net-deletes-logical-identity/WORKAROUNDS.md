# Workarounds: axlDeleteObject on NET Deletes Logical Identity

## Verified Workaround

For a non-destructive rip-up-and-reroute, use the ALREADY-EXISTING `allegro_assign_net(object_type="PIN", object_name="<a pin on the net>", net_name="<that pin's own current net>", ripup=True)` instead of `allegro_delete_connect(object_type="NET")`. This correctly strips the net's connected clines (the net goes to `unconnected=1`/ratsnest, confirmed via `axlDBGetConnect`/net-attribute queries) while leaving the net and all its pins fully intact, ready for a clean re-route with `allegro_create_trace`.

Example flow:
```
allegro_assign_net(session_id, "PIN", "<a pin on the bad net>", "<that net's own name>", ripup=True)
allegro_create_trace(session_id, points=[...], layer="TOP", net_name="<net>", width=5.0)
allegro_save_design(session_id)
allegro_run_session(session_id, board_file=...)
wait_for_job(...)
run_allegro_batch_drc(board_file=...)
run_allegro_report(..., report_code="drc")   # confirm the targeted violation is gone
```

CONFIRMED LIVE for a simple 2-pin/single-branch net: ~5-6s per cycle, `Short DRC` 1→0, `DRC Errors` dropped by exactly 1, `Missing Connections: 0`, `Connection Completion: 100.00%`, Nets(75)/Pins(251) unchanged.

**CAVEAT**: `allegro_assign_net(ripup=True)` + `allegro_create_trace` is confirmed reliable ONLY for a simple 2-pin/single-branch net. For a **multi-branch net** (e.g., a 4-pin net), this combination made `allegro_run_session` hang for minutes (reproduced 2-for-2 on fresh board copies, zero dialog windows detected). Treat multi-branch rip-up-and-refix as higher-risk until root-caused — use a single-branch net for the actual fix, or re-route the whole net via SPECCTRA.

Evidence: `.forjinn/skills/sigrity-cad/SKILL.md:433-491` (Task 9, full rip-up-and-refix section + multi-branch gotcha).

`allegro_delete_connect` remains useful for its documented purpose: genuinely deleting an object outright (a stray component, an obsolete film, a via, etc.). Do NOT use it for rip-up-for-reroute.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | `allegro_assign_net(object_type="PIN", ..., ripup=True)` for non-destructive rip-up | worked — net + pins intact, etch stripped, clean re-route possible (single-branch nets) | `sigrity_mcp/core/tool_status.py:308-313`; SKILL.md Task 9 |
| 2 | `allegro_delete_connect(object_type="NET", ripup=True)` for rip-up-for-reroute | didnt_work — deletes net's logical identity entirely; subsequent `axlDBCreatePath` for that net returns nil | `sigrity_mcp/core/tool_status.py:300-307`; SKILL.md Task 9 |
| 3 | `allegro_delete_connect(object_type="NET", ripup=False)` (logic-only delete) | didnt_work — still deletes net's logical identity (just leaves physical objects); net name unusable for re-route | `sigrity_mcp/domains/cad/allegro_geometry_tools.py:318-320` |
| 4 | `allegro_delete_connect(object_type="COMPONENT"/"VIA"/other)` for genuine object deletion | worked — documented use case, verified | `sigrity_mcp/domains/cad/allegro_geometry_tools.py:300-327` |

## Prevention

1. Do NOT use `allegro_delete_connect(object_type="NET")` as a rip-up mechanism. Use `allegro_assign_net(object_type="PIN", ..., ripup=True)` instead.
2. Use `allegro_delete_connect` only for genuine object deletion (stray components, obsolete films, vias). Its docstring and SKILL.md now state this explicitly.
3. After any rip-up-and-refix cycle, verify with `run_allegro_batch_drc` + `run_allegro_report(report_code="drc")` + `run_allegro_report(report_code="sum")` (nets/pins/connections unchanged, targeted violation gone). Do not trust the tool's return value.
4. For multi-branch nets, do NOT use the manual rip-up-and-refix path until the hang is root-caused. Use SPECCTRA autoroute or a single-branch workaround.

## Remaining Gaps

- `allegro_delete_connect(object_type="NET")` still exists in the tool suite and will still delete the net's logical identity. There is no guard or warning that prevents a caller from using it for rip-up. The docstring and SKILL.md warn against it, but the tool does not refuse the call.
- The multi-branch rip-up hang (`allegro_assign_net(ripup=True)` + `allegro_create_trace` on a 4-pin net → `allegro_run_session` hangs for minutes, reproduced 2-for-2) is NOT root-caused. See the `multi-branch-net-ripup-reroute-hang` scenario.
- There is no SKILL primitive on this install to select a single unnamed CLINE/SEGMENT by location (e.g., "the trace nearest this DRC violation's coordinate"). `axlSelectByName` only resolves named objects. So "surgical" rip-up is limited to net granularity (or named object granularity), not sub-net segment surgery.
