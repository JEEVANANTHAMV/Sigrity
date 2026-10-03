# Allegro Session Fails with rc -536870904 at ~137s (Watchdog Hang)

**Slug**: `allegro-137s-watchdog-hang`
**Tool(s) affected**: `allegro_run_session` (and any tool that launches `allegro.exe` via session)
**Status category**: `unreliable_intermittent`
**Pipeline stage**: design

## Symptom

`allegro_run_session` returns `state=failed, returncode=-536870904` after almost exactly ~137-138 seconds. The `run.log` shows only the Allegro startup banner (3 lines) — no SKILL execution output, no error message, no dialog log. The failure recurs with suspiciously consistent timing across multiple diagnostic runs. The same specific negative return code and ~137s duration recur every time.

This occurs even with:
- NO overlapping Allegro launches (strictly sequential harness)
- No pre-existing lock file
- A freshly-copied board (no stale state)

The consistent ~137s timing across every occurrence suggests a real internal watchdog/timeout rather than a random crash. Roughly 1-in-4 launches hit this failure mode.

## Root Cause

Not fully isolated. The leading hypothesis is a different unlabeled modal dialog (not the Product Choices or .lck dialog, both of which are already handled), a transient license-server hiccup, or some other internal Allegro timing mechanism. The fact that the duration is so consistent (~137s every time) points to a real internal watchdog or timeout inside Allegro's process, not a random OS-level kill.

The `check_design_lock` diagnostic tool, when called after a failed run, reliably finds a lock file that the failed run itself orphaned — confirming the process was killed mid-execution (rather than exiting cleanly), which is consistent with a watchdog kill.

This is a **genuinely separate** failure mode from the stale-lock and Product Choices dialogs. It was first surfaced via the vLLM-driven manufacturing eval (`scripts/eval_manufacturing.py`).

## Evidence

- `sigrity_mcp/core/tool_status.py:163-180` — "`allegro_run_session` can return `state=failed, returncode=-536870904` after almost exactly ~137-138s, with run.log showing only the startup banner -- the same specific negative code and ~137s duration recurs across multiple diagnostic runs, independent of the stale-lock root cause above (already found and fixed). This occurs even with NO overlapping Allegro launches (strictly sequential harness, board freshly copied) and no pre-existing lock file, so it is a genuinely separate, still-not-fully-isolated cause -- possibly a different modal dialog, a transient license-server hiccup, or something else entirely; the consistent ~137s timing across every occurrence suggests a real internal watchdog/timeout rather than a random crash."
- `sigrity_mcp/core/tool_status.py:174-180` — "Calling the new `check_design_lock` diagnostic tool afterward reliably finds a lock the failed run itself orphaned... Treat an Allegro batch launch that's still `running` well past its usual 15-20s load time, or that fails with this exact code, as a known, real, empirically-recurring (roughly 1-in-4 launches) reliability issue -- not yet fully root-caused, retry rather than treat as a hard blocker."

## Pipeline Impact

Blocks the **design** stage intermittently (~25% of launches). Any SKILL-based board authoring (nets, components, stackup, copper shapes, traces, films, saves, DRC) can fail with this watchdog kill. Because the failure is intermittent and the log shows no useful diagnostic, a pipeline that encounters it once will appear to have hung or crashed with no clear cause. The orphaned lock left by the killed run can also trigger the stale-lock dialog on the retry if not cleared.
