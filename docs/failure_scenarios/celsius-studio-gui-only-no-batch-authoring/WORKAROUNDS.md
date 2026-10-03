# celsius-studio-gui-only-no-batch-authoring — Workarounds

## What works (confirmed, as the intended flow)

- **Build the project in the GUI, then run it headless.** Author the `.3dth`/`.pdcx`
  (materials, sources, boundary conditions, mesh) in `CelsiusStudio.exe`'s GUI (or via
  PowerDC's thermal features in Domain 1), then hand the pre-built project file to the
  suite's run tools:
  - Celsius3D: `start_celsius3d_session(project_file=…)` → `celsius3d_run_session(…)`
  - CelsiusCFD: `start_celsiuscfd_session(…)` → `celsiuscfd_run_session(…)`
  - Celsius2D: `run_celsius2d_workspace(pdcx_file=…)`
  This is the confirmed, working division of labor: GUI/PowerDC authors, the MCP
  tools run.
- **Use PowerDC's thermal feature commands to author the setup when starting from a
  PowerDC project.** Confirmed during Domain 1 development:
  `powerdc_mark_thermal_component` and `powerdc_set_power_dissipation` are the
  in-suite path to create thermal/electro-thermal setup (the celsius3d scope note
  explicitly names these), then the built project is what the Celsius run tools
  consume.
- **Use Cadence's own self-test script as the canonical invocation reference.**
  `share/PostInstallationCheck/bin/postInstallCheck.pl` shows exactly how the CLI is
  driven — `<exe> -tcl <script>.tcl` for 3D/CFD and `<exe> -b -XIMSAVE -r <ws>.pdcx`
  for 2D — which is what the suite transcribes. (This confirms the RUN surface only;
  it has no authoring commands.)

## What was tried / ruled out

- Wrapping `CelsiusStudio.exe` for headless authoring: ruled out — probed and found
  GUI-only (deliberately not wrapped; see `README.md:434-436`).
- Wrapping the internal workers `CelsiusEngine.exe` / `celsius_client.exe`: ruled out
  — internal-dispatch, not a usable authoring CLI (deliberately not wrapped).
- Finding a Celsius-specific `sigrity::` setup vocabulary (materials/BCs/power maps/
  mesh) in the shipped doc tree: ruled out — the doc tree documents only the
  open/run/close sequence; no authoring `sigrity::` commands were found.
- `Celsius3D.exe -help` / a batch authoring subcommand: ruled out — a bare `-help`
  only prints the "legacy command line syntax" pointer and exits; there is no
  authoring subcommand.

## Prevention

1. Pre-stage GUI-built (or PowerDC-authored) project files for every automated
   thermal pipeline; the MCP tools will not create them.
2. Route any "set up thermal from scratch" ask to the GUI/PowerDC step explicitly,
   then to the run tools — do not expect a single MCP tool to do both.
3. If a real project ever reveals additional confirmed `sigrity::` setup commands,
   extend `celsius3d_tools.py`/`celsiuscfd_tools.py` per the scope note's invitation —
   but do not claim authoring capability until a confirmed command exists.

## Notes

- `status_category` is `gui_only_no_batch` and the manifest marks **verified_workaround:
  NO** in the sense that there is **no in-suite authoring tool** — the "workaround" is
  a *different entry point* (the CelsiusStudio GUI / PowerDC), not a headless
  alternative implemented here. The headless path is real for the RUN step; the AUTHOR
  step is out of scope for this suite by design.
- This is the same honest-scoping pattern used for other GUI-only products in the suite
  (see e.g. `zrouter-standalone-and-native-command-dead-ends` for a GUI-only tool that
  HAS a headless replay path, versus this one which has none for authoring).
