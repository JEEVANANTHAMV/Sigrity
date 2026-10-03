# celsius-studio-gui-only-no-batch-authoring

- **tool**: `celsiusstudio` (`CelsiusStudio.exe` — **deliberately NOT wrapped**) + the scope of `celsius2d` / `celsius3d` / `celsiuscfd` (which *run*, they do not *author*)
- **status_category**: `gui_only_no_batch` (the tool's authoring surface is GUI-only; the headless path in this suite is to *run* an already-built project, so the "workaround" is a different entry point, not an in-suite authoring tool)
- **verified_workaround**: NO in-suite authoring tool — build the project in `CelsiusStudio.exe`'s GUI (or PowerDC's own thermal features in Domain 1) and then let the suite's `run_*`/`start_*_session` tools run it

## What went wrong

There is **no headless/CLI/Tcl path in this suite (or in the shipped Sigrity 2024.0
doc tree) for *authoring* a Celsius project from bare geometry** — no way to create
materials, boundary conditions, power maps, or mesh settings via the MCP tools.
`CelsiusStudio.exe` (the authoring GUI) and its internal workers (`CelsiusEngine.exe`,
`celsius_client.exe`) are deliberately **not wrapped** — confirmed by probing to be
GUI-only or internal-dispatch.

Concretely, the suite's Celsius tools are scoped to **running** an already-built
project:
- `start_celsius3d_session` / `celsius3d_run_session` expect a `.3dth` project that
  **already has its thermal setup configured** (materials, sources, boundary
  conditions).
- `start_celsiuscfd_session` / `celsiuscfd_run_session` expect a `.3dth` project that
  **already has its CFD setup configured**.
- `run_celsius2d_workspace` takes an already-built `.pdcx` workspace.

So a caller trying to "author a new Celsius simulation from a geometry file via MCP"
hits a hard scope wall: the tools can only RUN projects whose setup was created
through the GUI (or PowerDC's thermal features). A bare `Celsius3D.exe -help` is a
dead end — it only prints "You are using the legacy command line syntax. Run
'Celsius3D -h' to know the details about the new one" and exits.

## Root cause

The shipped Tcl macro vocabulary for the Celsius solvers, as documented in the
installer doc tree, contains only the **open / run / close** sequence:
`sigrity::configure version -version {5}`, `sigrity::open file -file {…}`,
`sigrity::begin simulation -fileName {…}`, `sigrity::end simulation -fileName {…}`,
`sigrity::close exe`. That is all the suite transcribes (confirmed live to work for
*running*). No additional Celsius-specific `sigrity::` setup vocabulary — materials,
boundary conditions, power maps, mesh settings — was found documented anywhere in the
shipped doc tree beyond that open/run/close sequence. Therefore authoring is
genuinely GUI-only: the setup lives in the project file that the GUI produces, and the
batch/Tcl path merely opens and runs it.

## Evidence

- `domains/thermal/celsius3d_tools.py` module docstring (SCOPE NOTE, lines 50-61):
  "unlike PowerDC/PowerSI (which have many `sigrity::set`/`sigrity::add` compose
  tools for building up a simulation from scratch), **no additional Celsius3D-specific
  Tcl setup vocabulary (materials, boundary conditions, power maps, mesh settings) was
  found documented anywhere in the shipped doc tree beyond this confirmed open/run/
  close sequence.** In practice this means `start_celsius3d_session` expects a `.3dth`
  project file that already has its thermal setup (materials, sources, boundary
  conditions) configured — via `CelsiusStudio.exe`'s GUI, or IMPORTANT and confirmed
  during Domain 1 development, PowerDC's own thermal/electro-thermal features
  (`powerdc_mark_thermal_component`, `powerdc_set_power_dissipation`) — this tool only
  automates *running* an already-built Celsius3D project, **not authoring one from
  bare geometry.** Extend this module if a real project surfaces additional confirmed
  `sigrity::` commands."
- `domains/thermal/celsiuscfd_tools.py` module docstring (lines 22-26): "Same scope
  note as celsius3d_tools.py: `start_celsiuscfd_session` expects a `.3dth` project
  that already has its CFD setup (geometry, materials, boundary conditions)
  configured — this automates *running* an existing project, **not authoring one from
  bare geometry**, since no additional CelsiusCFD Tcl setup vocabulary was found
  documented anywhere in the shipped doc tree beyond this confirmed sequence."
- `domains/thermal/celsius2d_tools.py` module docstring (lines 4-10): the confirmed
  invocation is `-b -XIMSAVE -r <workspace>.pdcx`, "transcribed from Cadence's own
  installer self-test script … which drives Celsius2D exactly this way with no separate
  `.tcl` macro involved" — i.e. it runs an already-built `.pdcx` workspace.
- `README.md:430-436`: "**Scope note**: no additional Celsius-specific Tcl *authoring*
  vocabulary (materials, boundary conditions, power maps) was found documented beyond
  this confirmed open/run/close sequence — these tools automate *running* an
  already-built project, **not constructing one from bare geometry (build that via
  `CelsiusStudio.exe`'s GUI, or PowerDC's own thermal features in Domain 1).
  `CelsiusStudio.exe` itself, and internal workers `CelsiusEngine.exe`/`celsius_client.exe`,
  are deliberately not wrapped (GUI-only or internal-dispatch, confirmed by probing).**"
- `README.md` Known-gaps list: "`CelsiusStudio.exe`'s own setup/authoring GUI —
  Celsius3D/CelsiusCFD/Celsius2D's batch mode (Domain 7) can *run* an already-built
  project, not construct one from bare geometry via CLI/Tcl."

## Symptoms a caller observes

- No MCP tool exists that creates a `.3dth`/`.pdcx` from geometry + setup parameters.
- Attempting `Celsius3D.exe -help` yields only the "legacy command line syntax" pointer
  and exits; there is no authoring subcommand.
- `start_celsius3d_session(project_file=…)` / `run_celsius2d_workspace(pdcx_file=…)`
  require a **pre-built** project file; passing one whose setup is incomplete/empty runs
  "successfully" in CLI terms but produces no meaningful physics (the setup never
  existed).

## Pipeline Impact

A fully automated, end-to-end "geometry → signed-off thermal result" pipeline is not
composable in-suite: the *authoring* step must be done in `CelsiusStudio.exe`'s GUI (or
via PowerDC's thermal feature commands in Domain 1) up front, and only the *run* step
is automatable. Pipelines must pre-stage a GUI-built project file; they cannot
generate it from MCP tools. This is a scope boundary, not a bug — the tools honestly
refuse to claim an authoring capability the environment does not expose.
