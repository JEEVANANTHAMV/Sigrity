# Allegro Session Hangs for Minutes with Zero Dialog Windows

**Slug**: `allegro-session-minutes-hang-no-dialog`
**Tool(s) affected**: `allegro_run_session` — specifically triggered by multi-branch net rip-up + recreate workflows
**Status category**: `unreliable_intermittent`
**Pipeline stage**: design

## Symptom

`allegro_run_session` hangs for **minutes** (versus the normal ~5-6s completion time) with no modal dialog present. `DismissWatcher`'s own window enumeration finds **zero dialog windows** — just the normal main Allegro window still responding (`Responding=True`). The process is not dead, not killed by a watchdog, not blocked by a dialog — it is simply stuck in some internal operation for an extended period.

Specifically reproduced: ripping up one branch of a multi-branch/multi-pin net via `allegro_assign_net(ripup=True)`, then recreating that branch with `allegro_create_trace`, causes the session to hang. Reproduced **2-for-2** on fresh board copies. The `run.log` is completely silent (no growth) during the hang.

This is a **different** failure mode from:
- The ~137s watchdog kill (rc -536870904) — this one does NOT produce that return code
- The modal Qt dialog hang — no dialog windows are present
- The stale .lck dialog hang — no lock file involved

## Root Cause

Not root-caused. The leading candidate hypothesis: recreating one branch of a net whose OTHER branches/pins are still attached at a shared junction may trigger an expensive connectivity/cline-merge recompute inside Allegro that takes minutes to complete (or never completes). The hang is specifically triggered by the **multi-branch** nature of the net — the same rip-up + recreate operation on a simple 2-pin/single-branch net completes reliably in ~5-6s every time.

The `ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS = 300` (`sigrity_mcp/core/tclsession.py:121`) was set specifically to catch this class of hang. The comment at `sigrity_mcp/core/tclsession.py:116-120` states: "a real, repeatedly-confirmed failure mode (ripping up and re-routing a multi-branch/multi-pin net) hangs the session indefinitely with the log gone completely silent, and nothing catches it for two hours."

No working fix for the hang itself was found — per-branch rip-up, shorter-timeout polling, and per-object delete-and-recreate were all tried and still hit the same hang (`sigrity_mcp/core/tclsession.py:160-163`).

## Evidence

- `sigrity_mcp/core/tool_status.py:357-368` — "FOUND A THIRD REAL, REPRODUCIBLE GOTCHA attempting the fix on the shortest of these (N08984, a real 4-pin/multi-branch net): ripping up just one branch via `allegro_assign_net(ripup=True)` then recreating it with `allegro_create_trace` made `allegro_run_session` hang for minutes (vs the usual ~5-6s) -- REPRODUCED 2-FOR-2 on fresh board copies, with `DismissWatcher`'s own window enumeration finding zero dialog windows (just the normal main Allegro window still responding), ruling out the already-documented modal-dialog explanation. Root cause not isolated (candidate: recreating one branch of a net whose OTHER branches/pins are still attached at a shared junction may trigger an expensive connectivity/cline-merge recompute)."
- `sigrity_mcp/core/tool_status.py:365-368` — "`allegro_assign_net(ripup=True)` + `allegro_create_trace` is CONFIRMED reliable (~5-6s, every time) for a simple 2-pin/single-branch net... but NOT yet confirmed reliable for a multi-branch net -- treat a multi-branch rip-up-and-refix as higher-risk until this is root-caused."
- `sigrity_mcp/core/tclsession.py:112-121` — Comment explaining the 300s stall timeout: "a real, repeatedly-confirmed failure mode (ripping up and re-routing a multi-branch/multi-pin net) hangs the session indefinitely with the log gone completely silent."
- `sigrity_mcp/core/tclsession.py:160-163` — "No working chat-level fix for the hang itself was found (per-branch rip-up, shorter-timeout polling, and per-object delete-and-recreate were all tried and still hit the same hang); this at least bounds the damage and reports it clearly (`stall_timeout_killed=True` on the job record)."
- `.forjinn/skills/sigrity-cad/SKILL.md:492-498` — "GOTCHA — a single `allegro_run_session` hung for minutes (vs the usual ~5-6s) during this investigation with no modal dialog detected (`DismissWatcher`'s own window-enumeration found zero dialog windows, just the normal main Allegro window) — a DIFFERENT symptom from the previously-documented ~137s-watchdog and dialog-hang modes."

## Pipeline Impact

Blocks the **design** stage for multi-branch net rip-up-and-refix workflows. The hang can last minutes to (without the 300s stall timeout) indefinitely. Any pipeline that attempts to surgically fix routing on a multi-branch net (length-matching, DRC violation repair on dense bus nets) is at risk. The failure is silent — no error, no dialog, no log growth — making it hard to diagnose in real time. The 300s stall timeout bounds the maximum damage but does not prevent the hang.
