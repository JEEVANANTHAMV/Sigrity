# dxf2a-nonzero-exit-on-success — Workarounds

## What works (confirmed)

- **Read the completion line, not the exit code**: `tail_job_log` / `read_job_output_file` the job's `run.log` and look for the final line `dxf2a complete.`. That string is the real success marker (module docstring + `tool_status` both prescribe this).
- **Verify the artifact independently**: re-open the produced `.brd` with `run_allegro_report(board_file=..., report_code="sum")` and check for a real summary (layer count, extents, DRC state). This was exactly how the rc-1-but-valid result was confirmed in the live evidence (bypassing dxf2a/SKILL entirely).
- **Do NOT retry the job** on rc 1: the board is already written; a re-run is at best redundant.

## What was tried / ruled out

- Trusting `state` / return code: ruled out by definition — that is the failure. There is no in-suite flag that changes dxf2a's exit code.

## Notes

- Generalizes to the whole family (manifest #96 `nonzero-rc-on-success-family`): specctra rc 4, artwork rc 1, dxf2a rc 1, dbdoctor rc 1 — each needs its own tool-specific completion evidence rather than a blanket rc check.
