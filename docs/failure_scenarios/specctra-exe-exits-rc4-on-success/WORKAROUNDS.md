# Workarounds: specctra.exe Exits with Return Code 4 on Full Success

## Verified Workaround

**Judge success by the `.sts` files, not the return code.** After `run_specctra_autoroute` completes (regardless of `state` or `returncode`), read the `final.sts` file for real completion statistics:
- `Completion = 100.00%` (or whatever the target completion is)
- `Unconnections = 0` (or a specific expected count)
- `Nets=<n> Connections=<m>` (matching the expected board)

Also confirm the `routed.ses` file is non-empty (a real session file with routing data).

This is verified: "Judge success by the `.sts` files" (`.forjinn/skills/sigrity-cad/SKILL.md:75`). The real MCP tool wrapper (`run_specctra_autoroute`) produces `state:"failed"` rc 4, but the artifacts are correct.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Read `final.sts` / `route.sts` for completion stats instead of trusting rc | worked | `.forjinn/skills/sigrity-cad/SKILL.md:75-78` |
| 2 | Check `routed.ses` is non-empty | worked (corroborating) | `.forjinn/skills/sigrity-cad/SKILL.md:77-78` |
| 3 | Treat `returncode == 0` as success | didnt_work — specctra exits 4 on success | `sigrity_mcp/core/tool_status.py:684-685` |

## Prevention

1. **Never treat `returncode == 0` as the success criterion for `run_specctra_autoroute`.** The job will report `state:"failed"` rc 4 on success. Always check the `.sts` files.
2. **In pipelines, add a step after `run_specctra_autoroute` that reads `final.sts`** and verifies `Completion` and `Unconnections` before proceeding to the import step.
3. **Document this quirk in pipeline comments** so future operators don't "fix" it by treating rc 4 as a bug.
4. **Apply the same pattern to other nonzero-on-success tools**: `artwork.exe` (rc 1), `dxf2a.exe` (rc 1), `dbdoctor.exe` (rc 1). For each, judge success by the tool-specific artifacts (`.art` files, `.brd` output, log text), not the exit code.
5. **Consider wrapping the exit code interpretation** in the MCP suite: if `run_specctra_autoroute` detects rc 4 + valid `.sts` file, it could report a custom state like `"succeeded_with_nonzero_rc"` instead of `state:"failed"`. Not currently implemented, but would be a UX improvement.

## Remaining Gaps

This is a **tool quirk**, not a bug. The specctra binary is Cadence's, and its exit code convention is what it is. There is no way to change specctra's exit code behavior without patching the binary (not feasible) or asking Cadence to change it (not feasible).

A 25-year senior designer would consider this **fully acceptable** — the workaround (read the `.sts` files) is simple, reliable, and documented. The only "gap" is cognitive: an operator unfamiliar with the quirk may misinterpret rc 4 as a failure. This is mitigated by:
- The SKILL.md playbook explicitly documenting the gotcha
- The tool_status.py note documenting the behavior
- This failure scenario manifest documenting the evidence

Full automation is not blocked — a pipeline can be written to check the `.sts` files instead of the return code. No code changes are needed in the current implementation.
