# Workarounds: Multi-Branch Net Rip-Up & Re-Route Hangs `allegro_run_session`

## Verified Workaround

**Target a single-branch (2-pin, `nBranches=1`) net instead of a multi-branch net for the rip-up-and-refix cycle, when the goal is a localized re-route or a demonstrable length match.** This is not a code fix — it is the **workflow substitution** the live investigation itself used to complete the task after hitting this hang 2-for-2 on a real 4-pin net (`N08984`).

The same toolchain (`allegro_assign_net(ripup=True)` + `allegro_create_trace`) was confirmed reliable (~5-6s, every time) for single-branch nets in **two** separate cases within the same investigation:

1. The original single-branch DRC short fix (net X8 vs N03774, a real 0-mil "Line to Line Spacing" short at marker coordinate `(11762.5, 17005.0)`) — fixed in the normal ~5-6s per cycle, `Short DRC` 1→0, `Missing Connections: 0`, `Connection Completion: 100.00%`.
2. The length-matching demonstration itself — after hitting the 2-for-2 hang on multi-branch `N08984`, the investigation **switched** to the simpler single-branch pair `N02684`/`N08580` (both `nBranches=1`) and completed the fix: `N08580` ripped up, recreated with a precisely-calculated meander adding exactly 700 mil, `allegro_run_session` in the normal ~5-6s, `axlDBGetLength` confirmed the result as **exactly** `3100.0` mil (0-mil residual vs `N02684`, inside the 25-mil DDR4 budget).

Evidence: `.forjinn/skills/sigrity-cad/SKILL.md:510-543` (Task 9, Gotcha #3 through Gotcha #4 and the completed single-branch length-match) and `sigrity_mcp/core/tool_status.py:356-386` (the same arc in the `allegro` status note, including the explicit "SWITCHED to a simpler single-branch net pair... for the actual end-to-end demonstration" decision).

This is a **workflow** workaround, not a code change — consistent with the manifest's `verified_workaround: NO` for this scenario (no generally-applicable in-suite fix exists), while still being the demonstrated-practical path the investigation actually used to finish.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Switch to a single-branch (2-pin, `nBranches=1`) net with the same toolchain | worked — both the DRC-fix and the length-matching demos completed in the normal ~5-6s, verified via `axlDBGetLength`/`report.exe` read-backs | SKILL.md:461-479, 523-538; tool_status.py:330-386 |
| 2 | Rip up only **one** branch of a multi-branch net (rather than the whole net) and recreate just that branch | didnt_work — this *is* the exact reproduction sequence; hung 2-for-2 on a real 4-pin net despite limiting the rip-up/refix to a single branch | SKILL.md:510-521; tool_status.py:356-368 |
| 3 | Rely on `DismissWatcher` to detect and dismiss a dialog during the hang | not_applicable — confirmed live (2-for-2) that **no** dialog window exists during this hang; `DismissWatcher` found zero windows to act on, unlike the modal-dialog hang scenarios | SKILL.md:515-516; tool_status.py:361-362 |
| 4 | Fall back to full-board autorouting (SPECCTRA) instead of a surgical multi-branch re-route | not_tested_in_this_investigation — no evidence was gathered in the routing-capability investigation running the full SPECCTRA bridge specifically to test it as a fix for a multi-branch hang; the investigation's own resolution was the single-branch substitution above, not a full-reroute substitution. Listed for completeness as the plausible alternative a caller would reach for, but **unverified** for this specific failure | — (no evidence found in the sources read this pass) |

## Prevention

1. Before attempting a manual rip-up-and-refix (`allegro_assign_net(ripup=True)` + `allegro_create_trace`), **check the target net's branch count** (e.g. via `axlDBGetConnect`/net-attribute queries already used in this investigation — the same queries that surfaced `nBranches=1` for the chosen single-branch demo nets). If `nBranches > 1`, treat the attempt as high-risk and prefer selecting a single-branch net for the demonstration/fix, or a full-board autoroute, before spending minutes waiting on a hang with no confirmed recovery path.
2. **Do not** assume this hang will be caught by the existing `DismissWatcher`-based dialog handling — it is a dialog-free hang, explicitly ruled out from that mechanism during the live 2-for-2 repro. Do not build automation that relies on "dialog appeared → click through → continue" as this scenario's recovery path.
3. **Do not** assume the ~137s watchdog will fire at a known rc for this hang the way it does for `allegro-137s-watchdog-hang` — this hang has no confirmed fixed duration or known rc; treat it as open-ended until root-caused.
4. After **any** suspiciously long `allegro_run_session` (this hang or any other), verify the board file's own mtime/diff and re-run `report.exe` **only after** confirming the session is truly terminal — otherwise the report can silently read stale pre-change board state (see sibling scenario `report-stale-board-mid-save`).

## Remaining Gaps

- **No confirmed root cause** — the shared-junction recompute hypothesis is untested/unconfirmed; until it is, there is no way to predict (beyond the coarse "count the branches" heuristic above) whether a given multi-branch rip-up-and-refix will hang or simply run slowly-but-finish.
- **No in-suite auto-detection or auto-recovery** for this specific hang — the manifest correctly carries this as `verified_workaround: NO`; nothing in the current codebase pre-checks branch count before allowing the operation, enforces a timeout-and-abort specifically for this hang's signature (distinct from the generic ~137s watchdog), or even documents branch count in the `allegro_assign_net`/`allegro_create_trace` docstrings as a known-risk input.