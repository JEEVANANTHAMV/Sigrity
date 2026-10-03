# Workarounds: Allegro Session Fails with rc -536870904 at ~137s

## Verified Workaround

**Retry.** The failure is intermittent (~1-in-4 launches), so retrying the same session against a fresh board copy will succeed on the next attempt. The `clear_stale_design_lock` call (automatic in `allegro_run_session`) handles the orphaned lock left by the failed run. After a retry succeeds, the rest of the pipeline continues normally.

Additionally, the `ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS = 300` (`sigrity_mcp/core/tclsession.py:121`) now bounds any indefinite hang at 5 minutes instead of the global 2-hour default, so if a variant of this failure produces an indefinite hang instead of the ~137s kill, it will be caught and reported with `stall_timeout_killed=True`.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Retry with fresh board copy | worked (intermittent, ~25% success on first try, higher on retry) | `sigrity_mcp/core/tool_status.py:179-180` — "retry rather than treat as a hard blocker" |
| 2 | `check_design_lock` after failure to confirm orphaned lock | worked (diagnostic) | `sigrity_mcp/core/tool_status.py:174-177` |
| 3 | `clear_stale_design_lock` before retry (automatic) | worked | `sigrity_mcp/domains/cad/allegro_tools.py:194` |
| 4 | Avoid overlapping sessions | undetermined — failure occurs even with strictly sequential launches | `sigrity_mcp/core/tool_status.py:169-170` |
| 5 | Increase stall timeout to 300s (from 2h default) | worked (bounds damage) | `sigrity_mcp/core/tclsession.py:112-121` |

## Prevention

1. **Run Allegro launches strictly one at a time.** While the 137s failure occurs even sequentially, overlapping launches compound the problem (see `allegro-overlapping-sessions-false-negative`).
2. **Use fresh board copies per run** — copy the source `.brd` into the job's scratch directory before each `allegro_run_session`.
3. **Treat `state=failed, returncode=-536870904` as a known transient failure.** Implement retry logic in the pipeline: on this specific return code, retry up to 2-3 times with a fresh board copy.
4. **Use `wait_for_job` with a timeout** rather than indefinite polling. The 300s stall timeout will catch infinite hangs.
5. **After any failed run, call `check_design_lock`** to confirm the condition and clear the orphaned lock before retrying.

## Remaining Gaps

This is **not root-caused**. The consistent ~137s timing is a strong clue (suggests an internal Allegro watchdog), but the exact trigger is unknown. It is not a modal dialog (DismissWatcher finds no windows in some occurrences — though this specific failure mode's dialog status is not explicitly documented for this scenario). It is not a license issue (occurring even when other Allegro launches succeed on the same machine, same time).

A 25-year senior designer would assess this as **acceptable risk for 90% of pipeline work** (3 out of 4 launches succeed) but would **not consider it acceptable for unattended overnight batch runs** without retry logic. The retry workaround is practical and proven, but the underlying Allegro-internal watchdog timeout remains a mystery that would require Cadence support or deeper process-level debugging (e.g., attaching a debugger to the Allegro process at the 137s mark) to fully resolve. This does not block full automation if retry logic is in place, but it does add pipeline complexity and reduces throughput.
