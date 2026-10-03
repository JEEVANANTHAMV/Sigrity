# xcitepi-xpi-start-validity-check-indefinite-spin

Whenever `xpi_start`'s validity check fails inside XcitePI, the process does not exit — it enters an indefinite CPU-burning spin (confirmed 25%–86% of one core, steady, for 65+ minutes across multiple real occurrences, zero further log/output growth) that only a manual kill ends. Confirmed via the tool_status note for `xcitepi` and the PME failure path (no bumps survive flattened GDS parsing on this install).

## What went wrong

XcitePI's batch path (`XcitePI.exe -b -tcl <macro.tcl>`) appends `xpi_start` / `xpi_close_design` / `xpi_exit` (xcitepi_tools.py:95-97). When `xpi_start`'s *validity check* fails — for any reason (known trigger on this machine: PME with no bumps; the flattened-GDS `gdscelldisplay > 0` issue) — the process enters a permanent spin:

- CPU 25%–86% of one core, **steady**, for 65+ minutes
- **zero** further log growth or output
- no exit; only a manual kill ends it
- multiple real occurrences, all the same signature

This is DISTINCT from a legitimately long extraction (a 108 MB GDS IOME run genuinely stays `running` for 15–25 min, but its log grows and it eventually exits 0). The spin signature is "flat CPU + frozen log"; the real-extraction signature is "busy CPU + growing log." They look the same from `get_job_status` (both report `state:"running"`).

## Evidence

- tool_status.py `xcitepi` note: "whenever `xpi_start`'s validity check fails (PME or otherwise), the process does not exit -- it enters an indefinite CPU-burning spin (confirmed %433-86% of one core, steady, for 65+ minutes across multiple real occurrences, zero further log/output growth) that only a manual kill ends."
- Known concrete trigger (PME path): every XcitePI-relevant sample workspace in this install is either empty-`<BumpPadPorts>`, missing its `.dat` DB, or the same die as demo_decap.gds; the batch GDS-read path never matches named bump cells, so `xpi_start`'s validity check always fails with `"no BUMPS in Flip-Chip design"`. A second, real run against a different GDS/map pairing confirmed the identical failure, ruling out a staging mistake.

## Affected code

- `sigrity_mcp/domains/pi/xcitepi_tools.py:92-104` — `xcitepi_run_session` (unconditionally appends `xpi_start`).
- `core/tool_status.py` — `xcitepi` note.
