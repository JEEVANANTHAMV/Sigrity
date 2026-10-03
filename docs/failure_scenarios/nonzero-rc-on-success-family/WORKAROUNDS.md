# Workarounds: Nonzero Return Code on Genuine Success

## Verified Workaround (in-suite)

**Per-tool completion evidence, never the exit code.** For every member of the family the confirmed success signal is a specific log line and/or a real, non-empty artifact — not `returncode`. The suite's own composition already does this rather than gating on state:

- **specctra** → read the **final STATUS file** (`final.sts`) / confirm routed geometry on disk, not the job `state`. (Manifest row 48: "YES (read final.sts)".)
- **dxf2a** → read the log for **`dxf2a complete.`** (README:304, tool_status.py:821).
- **dbdoctor** → read the log for the **`0 errors detected` / `0 warnings, 0 errors detected`** text (manifest row 46: "YES (read '0 errors detected' text)"; e.g. `create_sym` re-verified with `dbdoctor.exe -check_only` → "0 warnings, 0 errors detected", README:384-385).
- **artwork** → read the log + confirm **`.art` files and `photoplot.log`** exist and are non-empty (manifest row 34: "YES (read .art + photoplot.log)").

And in a composition the suite **does not gate on these jobs' state at all**: `run_placement_and_routing_assistance` explicitly skips gating on the specctra job's pass/fail (README:513-515) and the DRC pass targets whichever board is actually real on disk.

## What NOT to do

1. **Do not add an in-suite rc-rewrite patch** to `jobs.py` to force rc 4/1 → `succeeded`. The literal `rc==0` mapping (jobs.py:266-267) is intentional: the platform's stance is that the log/artifact is the source of truth (SKILL.md rule 2). "Fixing" the state would *mask* the fact that rc is not trustworthy here and would break the general invariant elsewhere.
2. **Do not treat `state="failed"` on one of these tools as a genuine failure** without reading `tail_job_log` + the artifact first.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Gate pipeline step on `returncode == 0` | **fails on a real success** for every family member (specctra rc4, dxf2a rc1, artwork rc1, dbdoctor rc1) | jobs.py:266-267; README:300-302, :514 |
| 2 | Read tool-specific completion log line + artifact | **works** for all four; this is the confirmed in-suite convention | tool_status.py per-tool notes; manifest rows 30/34/46/48 |
| 3 | Composition that does not gate on these jobs' state (e.g. `run_placement_and_routing_assistance`) | **works** — the route lands even though specctra reports rc 4 | README:513-515 |

## Prevention

1. For any `run_*`/`*_run_session` tool in this family, the success check is **`tail_job_log` + a non-empty artifact newer than the job start**, in the *input file's* directory (SKILL.md rule 3), never `get_job_status`/`wait_for_job` state.
2. In pipelines, if a family-member step is in the middle, branch on **log/artifact evidence** (or simply proceed, as the placement+route composition does), not on the step job's `state`.
3. When adding a new standalone-exe wrapper, ask at build time: "does this product return nonzero on success?" and record its completion signal in `tool_status.py` so the family stays complete.

## Remaining Gaps

The family is **known and documented per tool**, but there is **no in-suite, tool-agnostic mechanism** that auto-detects "success-despite-nonzero-rc" and reclassifies the job state. Detection is always caller-side (read the right log line / artifact). The set of known members (specctra, artwork, dxf2a, dbdoctor) is the only confirmed list; any newly-wrapped standalone exe must be re-audited for the same behavior.