# Workarounds — capture-batch-open-hang

## No confirmed in-suite fix

`verified_workaround: None` in the manifest is accurate for the main `Open <project>`-step hang. The suite's own evidence says so directly:

- `core/tool_status.py` `capture` note (line ~577): "Treat `capture_run_session` as genuinely non-deterministic on this machine, not reliably blocked or reliably working." and (line ~720): "no CLI flag or documented workaround found in the local doc tree, and no reproducible fix available to this suite's Python wrapper layer."
- `capture_tools.py` docstring: "Actually authoring a real, populated schematic end-to-end on this machine is still blocked on the Capture-level defect above; nothing in this module's Python code is a workaround for that."
- `capture_tools.py` docstring (line ~221): "actually authoring schematics end-to-end on this machine would require a Cadence-level patch/reinstall or a working `syscap.exe` batch mode."

## What was tried (and what it did NOT fix)

- **Stale `.lck` auto-clear** (`clear_stale_design_lock`, now called automatically in `start_capture_session` and `allegro_run_session` before launch): proven live for **Allegro** (a planted fake stale lock was auto-cleared, job completed in 5.3s instead of hanging) and may explain *some* fraction of Capture's past non-determinism — but the `capture` note explicitly states it "does NOT fully resolve it — something else about Capture's batch invocation remains broken or unconfirmed."
- **Longer waits** (full 5-minute wait instead of 60s, to allow time for a one-time approval dialog): results are *inconsistent* — this confirms it is not a simple one-time dialog that, once accepted, permanently fixes every run (unlike allegro.exe's product-chooser dialog).
- **A different, simpler sample project** (FullAdder.opj, minimal Open+Close+Exit script): hang reproduces identically — rules out project-content as the cause.
- **Manual dialog clicking during the hang**: not possible — zero windows exist for the entire hang (live EnumWindows check), so there is no dialog to click.

## What works instead for the same goal (confirmed live)

Because Capture's batch path cannot be relied on, the suite documents these **alternative, confirmed-live paths** for the capability this tool is supposed to provide (see `core/tool_status.py` and `README.md` for each):

- **Create/duplicate a schematic project from scratch**: `copyproject.exe` via `allegro_copy_project` (confirmed live — full new project tree, "SUCCESS(COPYPROJ-67): Copy Project Success."), or `xcon2project.exe` via `allegro_package_xcon_project` (confirmed live). `core/tool_status.py` `copyproject` note: "flag-driven and fully headless (no GUI), unlike Capture.exe's/syscap.exe's unconfirmed batch reliability."
- **The real CAD-to-analysis bridge for a `.brd`**: PowerSI BRD-bridge — `start_powersi_session` accepts a real Allegro `.brd` directly (PowerSI's built-in BRDExtractor translates it on open) and `powersi_save_document` writes the native `.spd` (confirmed live producing a real 237KB `.spd`, README lines 144-149).
- **PSpice batch simulation**: `psp_cmd.exe` via `run_pspice_simulation` (confirmed live — separate headless batch simulator; see pspice-gui-entrypoints-hang-on-help).
- **Checklist-style verification without Capture**: `run_schematic_checklist` operates on real `report.exe -v net`/`-v bom` CSV output (confirmed-live `run_allegro_report`), not on Capture objects.

## Still open (future leads, not confirmed)

- A working headless/batch mode for `syscap.exe` ("Allegro System Capture") — an extensively documented Tcl API exists (`doc/scap_tcl_comms/`, incl. `newProject`) but neither `-help` nor `-tcl <script>` produced usable live evidence (see syscap-headless-batch-mode-unconfirmed). Not yet implemented per the suite's no-fabrication discipline.
- A Cadence-level patch/reinstall of Capture.exe itself.
