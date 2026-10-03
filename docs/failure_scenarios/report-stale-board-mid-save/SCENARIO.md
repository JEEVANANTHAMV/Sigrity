# Report Reads Stale Board State While Allegro Session Is Mid-Save

**Slug**: `report-stale-board-mid-save`
**Tool(s) affected**: `run_allegro_report` (and any read-only tool) run concurrently with an in-progress `allegro_run_session`
**Status category**: `precondition_error`
**Pipeline stage**: analysis

## Symptom

A `run_allegro_report` job run **while an Allegro session is still mid-save** (i.e., the `allegro_run_session` job has not yet completed and the board file is being written to disk) reads the **STALE (pre-fix) board state** and produces a report that reflects the old board content, not the newly-saved changes. There is no error of any kind — the report job succeeds with `returncode 0`, writes a valid report file, and the operator sees plausible-looking statistics. The only way to detect the problem is to compare the report's contents against the expected post-save state and notice a mismatch.

Specifically: the Allegro session modifies the board (e.g., creates a net, fixes a DRC violation, authors a stackup layer) and queues `axlSaveDesign` before `quit`. While the save is in progress (the board file being written to disk), a concurrent `report.exe` invocation opens the same `.brd` file and reads whatever bytes are currently on disk — which is the pre-fix state, not the post-fix state.

## Root Cause

The board file (`.brd`) is a binary format that is written atomically by Allegro's save process. However, "atomically" here means Allegro writes the complete file and then closes it — it does NOT use a temp-file-and-rename pattern. During the write window (which can be seconds for a large board), a concurrent reader (like `report.exe`) may open the file and read a partially-written or pre-write version. Allegro does not hold an exclusive file lock during the save that would block concurrent readers (the `.lck` file is a design-level lock, not a file-level lock, and is only checked at open time, not during reads).

The precondition for a correct report read is: **the Allegro session must have fully completed (save finished, process exited) before any report job is submitted against the same board file.** The pipeline must enforce this ordering.

## Evidence

- `.forjinn/skills/sigrity-cad/SKILL.md:496-498` — "Treat a session that's still `running` well past ~30s as suspect; verify the board file's own mtime/diff before trusting any report run immediately afterward, since a report job run while the Allegro session is still mid-save will read STALE (pre-fix) board state with no error of its own."
- `.forjinn/skills/sigrity-cad/SKILL.md:470-471` — The end-to-end manual-override result shows the correct ordering: `allegro_run_session` → `wait_for_job` → THEN `run_allegro_report` (never concurrently).

## Pipeline Impact

Blocks the **analysis** stage. A report (or any downstream analysis: DRC, DRC violation inspection, net length queries, IPC-2581 export, SPECCTRA export) run against a mid-save board will produce **incorrect results that look valid**. This is particularly dangerous because:
1. The report job reports `succeeded` with `returncode 0` — no error signal
2. The report contents are plausible (real statistics, real net names, real DRC counts) — just based on stale data
3. The operator may make design decisions (e.g., "DRC is clean, proceed to Gerber export") based on incorrect data
4. The stale state may mask a real DRC violation or show a violation that was already fixed

This is a **precondition_error** — the tool (`report.exe`) is working correctly; the pipeline violated the precondition that the board must be fully saved before reading.
