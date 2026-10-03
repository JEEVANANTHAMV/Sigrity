# generate-sim-variant-drc-disabled — Workarounds

## What works (confirmed)

- **Treat DRC-disabled as intended**: do not "fix" it by re-enabling DRC or by running batch_drc against a variant expecting a clean result — the tool's own `-help` states the variant's elements may legitimately violate spacing against their oversized neighbors. The violations are the what-if, not a bug.
- **Verify the variant with `report.exe` re-read, not DRC**: `run_allegro_report(board_file=<variant>, report_code="sum")` — the confirmed-live evidence validated the output this way (81 packages / 191 drills / 163 connections, matching the master's real content). This confirms the file is a real, non-corrupt derivative without invoking the (deliberately-)disabled DRC.
- **Read DRC-style reports with the caveat in mind**: if you do pull a `report_code="drc"` view of a variant, interpret the listed spacing hits as what-if artifacts.

## What was tried / ruled out

- Running DRC on the variant expecting clean: ruled out as a valid expectation — the `-help` explicitly disables on-line DRC for this purpose. There is no "make the variant DRC-clean" lever, because the violations reflect the requested geometry.

## Notes

- The tool's live confirmation used `-c "1.0"` / `-d "1.0"` (percentage oversize) in the documented example; the DRC-disabled behavior is a property of any variant it produces, independent of the specific over/undersize values.
