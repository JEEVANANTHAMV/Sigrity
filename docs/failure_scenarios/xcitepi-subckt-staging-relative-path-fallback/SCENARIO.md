# xcitepi-subckt-staging-relative-path-fallback

The `.include subckt_file_name` line inside a XcitePI tech file is resolved relative to the **job's own working directory (CWD)**, not the tech file's directory. If the subckt file is staged elsewhere, XcitePI reports `(Error)Cannot find subckt file` and produces **zero circuit placements** — the job can otherwise exit cleanly, masking the problem.

## What went wrong

XcitePI's tech files reference sub-circuit SPICE fragments via `.include subckt_file_name`. The batch engine resolves that name against the CWD of the `XcitePI.exe -b -tcl <macro.tcl>` process — which, for a job submitted through `run_session`/`submit_job`, is the job's own working/scratch directory, NOT the directory the `xpi_set_tech_file` path points at. So a tech file at `dirA/x.tech` containing `.include subckt.spc` looks for `dirA/subckt.spc` only if CWD happens to be `dirA`; otherwise it fails to find it.

Failure signature:
- `(Error)Cannot find subckt file` in the run log
- extraction completes but yields **zero circuit placements**
- process exits normally (no hang, no crash) — so `state:"succeeded"` + rc 0 can coexist with a useless, empty netlist

## Evidence

- tool_status.py `xcitepi` note: "SEPARATE BUG, applies to both features: `.include subckt_file_name` in a tech file is resolved relative to the job's own working directory, not the tech file's directory -- stage the subckt file into the job CWD or expect `(Error)Cannot find subckt file` and zero circuit placements."
- This is the "SEPARATE BUG" called out distinctly from both the PME bump failure and the `xpi_start` validity-check indefinite spin — a third, independent XcitePI failure mode.

## Affected code

- `sigrity_mcp/domains/pi/xcitepi_tools.py:33-39` — `start_xcitepi_session(tech_file=...)`; the wrapper takes only the tech file path, not its sibling subckt/def files, so it cannot enforce co-location on its own.
- The staging is the caller's responsibility (see WORKAROUNDS.md).
