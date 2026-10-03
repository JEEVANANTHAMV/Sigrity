# Workarounds — optimizepi-missing-simulation-trigger-no-whatif

## verified_workaround: None (no confirmed in-suite fix)

The WhatIf artifact is a GUI-only output. The two routes to actually get a report are both OUTSIDE the current toolset:

1. **Open the demo `.opix` interactively** in the OptimizePI GUI and run the WhatIf there — this is how the `.config`'s `demo_WhatIfResult.dat` was originally produced. Not automatable via the current `-b -tcl` MCP path.
2. **Extend `optimizepi_run_session` to append a real simulation trigger** (e.g. `sigrity::begin simulation {!}` as PowerDC does) — and still require the Optimization table from a pre-configured `.opix`. Neither is implemented. This is the project-scoped "do not edit source" boundary: the fix is a code change, not a caller workaround.

## Practical guidance

- **Do NOT claim the optimization ran** from `state:"succeeded"` + rc 0. OptimizePI's batch run opens the `.spd`, logs every command, and exits rc 0 with zero WhatIf artifact. Verify by checking for a real WhatIf artifact file in the staged dir — its absence, with rc 0, is the signature of this scenario.
- The confirmed-live path that DOES run a simulation is OptimizePI's own `-b -export_data` batch mode against a saved `.opix` workspace (tool_status note: fetched license, reported "Simulation succeed", saved demo.spd) — but `optimizepi_tools.py` does not expose that invocation; it exposes the `sigrity::` `-tcl -export_report` compose style.

## Known demo-data quirk (separate, will still bite)

Even interactively, this exact demo reports `Invalid Capacitor circuit (C2). Capacitor ID is not set.` — the `.opix` `DecapLibPrefPath` and the `demo_decap_library.xml`'s `.s2p` paths point at build-machine locations (`C:\Backup\temp\…`) that are absent. The R/L/C values are inline in the XML, so a rebuilt local library without the S-param paths is a valid workaround for the S-param-path problem — but it does not address the missing-simulation-trigger, which is the primary blocker here.
