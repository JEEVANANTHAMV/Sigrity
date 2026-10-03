# Overlapping Allegro Sessions Cause False-Negative "Block" Diagnosis

**Slug**: `allegro-overlapping-sessions-false-negative`
**Tool(s) affected**: `allegro_run_session` — any concurrent Allegro session launches
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

Running several Allegro diagnostic sessions **simultaneously** (overlapping launches) causes sessions to appear "blocked" or "hung" — a long-running session with no save landing on disk, no useful output, and the impression that the SKILL call is genuinely broken. The session runs for several minutes with no visible progress, leading to a false-negative diagnosis: the tool appears to be `known_blocked` when in fact the individual SKILL call works perfectly fine.

This false-negative was the basis for a **misreported status** of `allegro_assign_net` (`axlDBAssignNet`): it was previously documented as `known_blocked` based on a test where the session ran for several minutes with no save landing on disk. The actual cause was license-seat contention from the overlapping sessions, not a bug in the SKILL call.

## Root Cause

Allegro requires a **license seat** to run. When multiple `allegro.exe` processes are launched simultaneously, they compete for a limited license seat. If the pool of available seats is exhausted (or the license server is slow to grant a seat), the additional sessions queue indefinitely waiting for a license. From the outside, this looks identical to a hung or blocked session — no output, no progress, no error. The SKILL call itself is correct; the process simply never starts executing because it never acquires a license.

This is the **same class of false negative** as the original `axlDBCreateNet` block (which was also misdiagnosed as a SKILL bug before being traced to license/queue-related contention).

The fix is operational, not code-level: **run only one Allegro launch at a time.**

## Evidence

- `sigrity_mcp/core/tool_status.py:143-157` — "`allegro_assign_net` (axlDBAssignNet via a `(car (axlSelectByName ...))` resolver) was previously misreported here as known_blocked, based on a test where the session ran for several minutes with no save landing on disk -- that long-running symptom turned out to be a self-inflicted artifact of firing off several overlapping diagnostic sessions at once, competing for a limited license seat, not a bug in the SKILL call itself (the same class of false negative as the original axlDBCreateNet block). Run cleanly one Allegro launch at a time: three independent live confirmations against fresh copies of the real sample board... PROMOTED to confirmed_live -- net reassignment via this tool is real and does persist."
- `sigrity_mcp/core/tool_status.py:127-128` — "a hang past two minutes in the same session shape is license/queue-related, not a bug in the SKILL call itself."
- `README.md:129-136` — "after the user resolved a machine-wide licensing issue, `allegro_create_net` (`axlDBCreateNet`) was re-tested against a real board and completed cleanly in ~5.6 seconds (previously this hung past two minutes in the same session shape — the earlier block really was license/queue-related)."

## Pipeline Impact

Blocks the **design** stage when multiple Allegro sessions are launched concurrently. The false-negative diagnosis can lead to:
1. Incorrectly marking working tools as `known_blocked`
2. Unnecessary investigation time spent on "broken" tools that are actually fine
3. Pipeline steps being skipped or abandoned based on false failure signals

The failure is particularly dangerous because it mimics a genuine tool bug — the session appears to hang with no error, no dialog, and no log output, exactly like a real hang. The only distinguishing factor is the presence of other concurrent Allegro processes.
