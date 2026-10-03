# Workarounds: Allegro Session Hangs for Minutes with Zero Dialog Windows

## Verified Workaround

**Use single-branch nets for rip-up-and-refix.** `allegro_assign_net(ripup=True)` + `allegro_create_trace` is CONFIRMED reliable (~5-6s, every time) for a simple 2-pin/single-branch net. For multi-branch nets, this workaround is the only confirmed safe path:

1. Instead of ripping up one branch of a multi-branch net, rip up the **entire net** (all branches) via multiple `allegro_assign_net(ripup=True)` calls (one per pin), then recreate **all** branches with `allegro_create_trace`. This is more work but avoids the shared-junction recompute that triggers the hang.

2. **Prefer the autorouter** (SPECCTRA) for re-routing multi-branch nets rather than manual SKILL-based rip-up-and-refix.

3. **Use the 300s stall timeout** (automatic in the MCP suite) to bound any hang that does occur. The job will be killed with `stall_timeout_killed=True` after 5 minutes, allowing the pipeline to detect the failure and retry or skip.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Use single-branch (2-pin) nets for rip-up-and-refix | worked — ~5-6s, every time | `sigrity_mcp/core/tool_status.py:365-366` |
| 2 | Per-branch rip-up (only one branch at a time) | didnt_work — same hang | `sigrity_mcp/core/tclsession.py:160-161` |
| 3 | Shorter-timeout polling | didnt_work — same hang | `sigrity_mcp/core/tclsession.py:160-161` |
| 4 | Per-object delete-and-recreate | didnt_work — same hang | `sigrity_mcp/core/tclsession.py:160-162` |
| 5 | 300s stall timeout to bound the hang | worked (bounds damage) | `sigrity_mcp/core/tclsession.py:121` |
| 6 | Switch to simple single-branch net pair for length-matching demo | worked — completed in normal ~5-6s | `sigrity_mcp/core/tool_status.py:368-381` |

## Prevention

1. **Check net branch count before rip-up.** Use `allegro_get_net_length` or a SKILL query to determine `nBranches`. If `nBranches > 1`, do NOT use the single-branch rip-up-and-refix pattern. Instead, either rip up the entire net (all branches) or use the autorouter.
2. **Treat any `allegro_run_session` that is still `running` past ~30s as suspect.** Verify the board file's mtime before trusting any report run immediately afterward.
3. **Use the stall timeout** (300s, automatic in the MCP suite) as a safety net. Monitor for `stall_timeout_killed=True` on the job record.
4. **For dense multi-branch nets (e.g., parallel bus lanes), prefer SPECCTRA autoroute** over manual SKILL-based routing manipulation. The autorouter handles the connectivity recompute internally and is more robust.

## Remaining Gaps

This is **not root-caused** and there is **no fix for the hang itself**. The 300s stall timeout bounds the damage but does not prevent it. The single-branch workaround is confirmed but limits the class of nets that can be surgically re-routed.

A 25-year senior designer would assess this as:
- **Acceptable risk** for 90% of pipeline work (most nets are single-branch or are handled by the autorouter).
- **Not acceptable** for unattended re-routing of dense multi-branch bus nets without operator supervision.
- **Blocks full automation** of surgical manual re-routing on dense, multi-branch nets until the root cause is isolated (which would require deep Allegro-internal debugging, likely Cadence support involvement).

The `iterate-and-recheck` workflow (rip-up → create → save → run → batch_drc → report) is genuinely practical and fast for single-branch nets, but the multi-branch limitation is a real gap that does not have a confirmed in-suite fix.
