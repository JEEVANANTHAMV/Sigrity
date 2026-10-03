# Workarounds: `spif_batch -i` Session Import Hard Crash (SPMHDB-238)

## Verified Workaround

**Use `run_allegro_specctra_import` instead of `run_specctra_import_session`.** `run_allegro_specctra_import` drives Allegro's own native `specctra_in <session_file>` command via a full Allegro batch-script replay — a separate code path that never touches the standalone `spif_batch.exe` binary at all, sidestepping the crash entirely. Confirmed live end-to-end: a real routed `.ses` (100% connected, 75 nets/163 connections) imported into a fresh board copy, import job `succeeded`, real output `.brd` written (genuinely different size/sha1), `report.exe` read-back matched source statistics exactly (451.50 inches total trace, 0 vias).

Evidence: `sigrity_mcp/core/tool_status.py:215-256` (full live verification of `run_allegro_specctra_import`, promoted to CONFIRMED LIVE end-to-end); `sigrity_mcp/domains/cad/spif_specctra_tools.py:85-122` (the tool itself); `.forjinn/skills/sigrity-cad/SKILL.md:97-105` (the verified live call sequence and independent-verification step).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Switch to `run_allegro_specctra_import` (Allegro script-replay path) | worked — live-verified end-to-end, real `.brd` written, `report.exe` read-back matched | `sigrity_mcp/core/tool_status.py:215-256`; spif_specctra_tools.py:85-122; SKILL.md:97-105 |
| 2 | Any flag variant of `spif_batch -i` | didnt_work — the crash is in the `-i` code path itself, deterministic, regardless of other flags | spif_specctra_tools.py:34-38 (full switch set is `-o|-r|-i|-c`; `-i` is the only import path, no bypass exists) |
| 3 | `specctra.exe`-side session import | not_available — its documented startup options contain no session-import path at all | spif_specctra_tools.py:35-38 |
| 4 | Dialog dismissal (`DismissWatcher`/`auto_dismiss_dialogs`) | not_applicable — confirmed live, zero windows are ever shown during the crash (20ms win32gui polling saw none) | spif_specctra_tools.py:31-32 |
| 5 | Pre-cleaning the board with `dbdoctor` before retrying `spif_batch -i` | didnt_work — the board already reports "0 errors, 0 errors could be fixed" and the crash reproduces identically on a fresh untouched copy; board state is not the cause | spif_specctra_tools.py:33-34 |
| 6 | `cancel_job` on the crashed job's record, or simply waiting longer for the job to resolve | didnt_work — the worker crashes and detaches; the launcher never reaps it, so `job.json` stays `state:"running"`/`returncode:null` forever and `cancel_job` returns the zombie still `running` | SKILL.md:87-92; SKILL.md:551 (cross-cutting notes) |

## Prevention

1. **Never** use `run_specctra_import_session` as the primary import path on this installation — it is documented as `KNOWN BROKEN` in the tool's own docstring (spif_specctra_tools.py:126-128). Use `run_allegro_specctra_import` by default.
2. If you ever **must** attempt `run_specctra_import_session` (e.g. to check whether a future Cadence patch fixed the binary), do **not** `wait_for_job` on it and do **not** read `get_job_status`'s `state`/`crash` field as the completion signal — neither will ever reflect this crash. Instead, poll `list_job_files(job_id)` for the `spif_batch_P00122.1_AllegroMiniDump.dmp` artifact and `read_job_output_file` for the `ERROR(SPMHDB-238)` log line.
3. Treat any `run_specctra_import_session` job left in a persistent `running` state with no further log activity and no output file as **already crashed and orphaned**, not merely slow to start — the only distinguishing evidence is the `.dmp`/`SPMHDB-238` pair, not the job record itself.
4. `run_placement_and_routing_assistance` already builds its final DRC stage around this failure (placement_routing_assistance_tools.py:129-160): it attempts the import best-effort and, if it fails, explicitly reports via a `caveat` field which board state the DRC pass actually checked. Do not remove that caveat-handling logic if refactoring the pipeline — it exists specifically because of this bug.

## Remaining Gaps

- This is a **genuine product bug** in the SPB_22.1 build of `spif_batch.exe` that this suite cannot fix in code — only route around. The working route (`run_allegro_specctra_import`) exists and is live-verified, but the broken tool `run_specctra_import_session` is still shipped (kept only "to re-verify it... as a reference for the standalone-CLI approach", spif_specctra_tools.py:37-44) with **no automated guardrail** preventing a caller — or an LLM agent choosing between the two tools — from picking the broken path by mistake.
- There is no way to know from a `running`-state `spif_batch -i` job record alone that it has in fact crashed-and-detached rather than merely being slow — the `.dmp`/`SPMHDB-238` evidence lives outside `get_job_status` entirely (see also sibling scenario `batch-drc-launcher-exits-early-state-lie`, a different but related "state stays running forever" failure mode with a different root cause).