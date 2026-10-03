# Workarounds: Overlapping Allegro Sessions Cause False-Negative "Block" Diagnosis

## Verified Workaround

**Run only one Allegro launch at a time.** This is the confirmed fix: "Run cleanly one Allegro launch at a time: three independent live confirmations against fresh copies of the real sample board" (`sigrity_mcp/core/tool_status.py:149-150`). With strictly sequential launches, `allegro_assign_net` (and all other Allegro session tools) complete cleanly in ~5-6s with no hang.

The MCP suite's job management (`submit_job`, `wait_for_job`) inherently supports sequential execution: submit one job, wait for it to complete, then submit the next. The pipeline should be structured so that no two `allegro_run_session` jobs are `running` simultaneously.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Run one Allegro launch at a time (sequential) | worked — all 3 independent confirmations passed | `sigrity_mcp/core/tool_status.py:149-157` |
| 2 | Fire off several overlapping diagnostic sessions simultaneously | didnt_work — license-seat contention causes indefinite hang | `sigrity_mcp/core/tool_status.py:147-148` |
| 3 | Increase license seat pool | not documented — no evidence in this codebase of additional licenses being added | not documented in this codebase |

## Prevention

1. **Never launch two `allegro.exe` processes simultaneously.** Structure the pipeline so that `allegro_run_session` jobs are strictly sequential: submit → wait_for_job → confirm success → submit next.
2. **Before starting a new Allegro session, verify no other `allegro.exe` process is running.** Use `tasklist` (Windows) or check for running Allegro windows via `win32gui_helper`.
3. **If a session appears to hang with no output and no dialog, check for other concurrent Allegro processes before diagnosing a tool bug.** This is the #1 false-negative source.
4. **Use `wait_for_job` with a reasonable timeout** (e.g., 120-180s for typical sessions) rather than indefinite polling. If a session is still `running` past 30s with no log growth, check for concurrent Allegro processes first.
5. **Document the license seat count** for the machine. If the pool is 1 (single-seat license), concurrent launches will ALWAYS fail. If the pool is >1, concurrent launches may work but are still risky.

## Remaining Gaps

This is fully solved for in-suite pipelines (sequential execution is the natural pattern). The only residual gap is for **out-of-suite** scenarios:
- A human hand-running `allegro.exe` from a terminal while an MCP pipeline is also running Allegro
- A third-party tool launching Allegro concurrently with the MCP suite

In these cases, the operator must manually ensure no concurrent Allegro processes. A 25-year senior designer would consider this **fully acceptable** — the rule "one Allegro at a time" is standard Cadence practice and is now documented in the tool status registry, the SKILL.md playbook, and the failure scenario manifest. No code changes are needed; this is an operational discipline.
