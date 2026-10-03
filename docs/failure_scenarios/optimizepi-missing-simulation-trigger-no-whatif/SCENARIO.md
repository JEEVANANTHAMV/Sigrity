# optimizepi-missing-simulation-trigger-no-whatif

`optimizepi_run_session` has **no simulation-run trigger**. The batch run opens the `.spd`, logs every setup command cleanly, and exits rc 0 with **zero WhatIf artifact** because `genReport` has no completed simulation to report on. The `.config`'s `demo_WhatIfResult.dat` is produced by an interactive GUI WhatIf run and is NOT reproducible through the current `-b -tcl` MCP toolset.

## What went wrong

PowerDC's `run_session` appends `sigrity::begin simulation {!}` (the actual solve trigger). OptimizePI's `optimizepi_run_session` (optimizepi_tools.py:182-193) appends **nothing** — it composes the setup and calls `sigrity::do genReport {!}`, which then fails against an empty result:

Confirmed across 5 live runs (job `optimizepi-029df6c93e` is the representative), the macro log shows every setup command accepted cleanly, then:

```
sigrity::update deviceOPTI -name {OptimumDefault} -refDes {U1}
    -> Can not find the port: U1
sigrity::update deviceOPTI -name {U1_VCC_GND} -refDes {U1_VCC_GND}
    -> Can not find the Optimization: U1_VCC_GND
sigrity::do genReport
    -> The simulation result is not ready. Run a simulation first.
```

Two independent root causes:
1. **No simulation trigger**: `optimizepi_run_session` never appends `begin simulation`, so there is no completed result to report.
2. **No pre-configured Optimization objects**: `sigrity::update deviceOPTI` requires the named *Optimization* setup objects that only exist inside a pre-configured `.opix` workspace (`OptimizeSetupTable`). `optimizepi_attach_layout` only does `sigrity::open document -attach <spd>` — it does NOT load an `.opix`'s optimization table. Passing the `.opix` as the "spd" gives `SPDLinks.exe failed to translate {…}.opix` (it is not an SPD).

A prior interactive run of this exact demo (a log left in the staged dir) confirms the same demo opens the `.opix` and reports `Invalid Capacitor circuit (C2). Capacitor ID is not set.` — a known demo-data quirk (the `.opix` `DecapLibPrefPath` points at a build-machine path, and the decap library `.s2p` files reference `C:\Backup\temp\…` which is absent).

## Affected code

- `sigrity_mcp/domains/pi/optimizepi_tools.py:182-193` — `optimizepi_run_session` (no `begin simulation` appended). Contrast with `powerdc_tools.py:313-323` which does append it.
- `sigrity_mcp/domains/pi/optimizepi_tools.py:45-49` — `optimizepi_attach_layout` (only `-attach` an `.spd`, no `.opix` optimization-table load).
- `core/tool_status.py` — `optimizepi` note: the batch `-b -export_data` path is confirmed live (fetched license, "Simulation succeed", saved demo.spd), but `optimizepi_tools.py`'s own `sigrity::` `-b -tcl <script> -export_report` compose path was never independently re-run — no Tcl-scripted sample shipped for OptimizePI to test that exact path against.
