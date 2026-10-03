# Workarounds: Report Reads Stale Board State While Allegro Session Is Mid-Save

## Verified Workaround

**Wait for the Allegro session to fully complete before running any report or read-only tool against the same board file.** The correct pipeline ordering is:

```
allegro_run_session(session_id, board_file=...)
wait_for_job(job_id, timeout_seconds=120)   # wait for Allegro to exit (save complete)
run_allegro_report(board_file=..., report_code="sum", output_file=...)
wait_for_job(job_id, timeout_seconds=120)   # wait for report to complete
```

Additionally, **verify the board file's mtime** before running a report: check that the file's modification time is within the expected window of the just-completed Allegro session. If the mtime has not changed since the last known state, the save may not have landed.

This is verified in the SKILL.md playbook (`sigrity-cad` Task 4, Task 6, Task 9) where every `run_allegro_report` call is preceded by a `wait_for_job` on the preceding `allegro_run_session`.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | `wait_for_job` on Allegro session before running report | worked — report reflects post-save state | `.forjinn/skills/sigrity-cad/SKILL.md` — every task follows this pattern |
| 2 | Verify board file mtime before running report | worked (defensive check) | `.forjinn/skills/sigrity-cad/SKILL.md:496-497` |
| 3 | Run report concurrently with Allegro session | didnt_work — reads stale pre-save state | `.forjinn/skills/sigrity-cad/SKILL.md:497-498` |

## Prevention

1. **Never run `run_allegro_report` (or any read-only tool) until the preceding `allegro_run_session` has completed.** Use `wait_for_job` with an appropriate timeout (120s for typical sessions, 240s for complex sessions like stackup authoring).
2. **After `wait_for_job` returns `succeeded`, verify the board file's mtime** is recent (within the last few minutes) before running a report. This catches the edge case where the Allegro process exited but the save did not complete (e.g., disk full, permission error).
3. **In pipelines via `run_tool_pipeline`, ensure the `wait_for_job` step is ordered between the Allegro session and the report** (see Task 5 in SKILL.md for the correct pattern).
4. **Use independent verification** (bypassing SKILL entirely): run `report.exe` on the board, then compare the report's statistics (net count, pin count, DRC error count, connection completion) against the expected post-save values. A mismatch indicates a stale read or a failed save.
5. **Use SHA-1 comparison**: hash the board file before and after the Allegro session. If the hash has not changed, the save did not produce a different file (possible silent save failure — see the `axlSaveDesign ?noCheck` bug history).

## Remaining Gaps

This is a **pipeline ordering issue**, not a tool bug. The tools work correctly; the precondition (board fully saved before reading) must be enforced by the pipeline. There is no in-tool mechanism to detect a stale read — `report.exe` has no way to know whether the board is still being written to.

A 25-year senior designer would consider this **fully solved** for automated pipelines (the `wait_for_job` pattern is standard and reliable). The only residual risk is operator error: a human running `report.exe` manually against a board that Allegro is still saving. This is acceptable risk — it is standard file-system discipline (don't read a file while it's being written), and the SKILL.md playbook explicitly documents the correct ordering.

No code changes are needed. This is a documentation and pipeline-discipline issue, fully addressed by the SKILL.md playbook and the `wait_for_job` pattern.
