# spdsim-standalone-launch-fails-skip-license-fetch — Workarounds

## What works (confirmed)

- **There is no confirmed in-suite workaround to run SPDSIM to completion today** (manifest #68: verified_workaround = NO). The tool is `known_blocked` from a standalone launch. Do not expect `run_spdsim_simulation` to produce a solve.

## What was tried / ruled out

- **Flag-style variation** (`-b` vs `-as` / `-spice -run`): ruled out — both fail identically ("Skip license fetch" → "Failed to open the file").
- **Sample-file variation** (legacy `ESD_testcase0.spd` vs modern 3D-EM `diff_via.spd`): ruled out — two different real samples, identical failure, so it is not an input problem.
- **Direct standalone `submit_job` launch**: ruled out as structurally wrong for this install — SPDSIM appears to require the license/IPC context of a live PowerSI Tcl session.

## Promising direction (not yet implemented)

- Per `tool_status` and `README`, the likely real fix is to drive SPDSIM **from inside a PowerSI session** as a child process: `sigrity::do exec "...spdsim.exe" -as "file.spd" &` composed in `powersi_tools.py`, instead of its own direct process launch. **This is NOT yet implemented** — until it is, SPDSIM standalone is a dead end on this install.

## Notes

- The "Skip license fetch" string is a strong in-suite tell: it has **never** appeared on any other confirmed-working tool in the suite, which is what isolates this as an SPDSIM-specific (child-context) issue rather than a general license failure. (Distinct from `powersi-license-issue-suspected-useless`, where PowerSI itself works and only the *flag* is useless.)
