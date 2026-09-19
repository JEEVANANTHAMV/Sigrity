"""Domain 7 — Thermal (Celsius).

Celsius is Cadence's electrothermal/thermal-stress simulation product line, installed
alongside the rest of the Sigrity Suite at `C:\\Cadence\\Sigrity2024.0\\tools\\bin`
(`Celsius3D.exe`, `CelsiusCFD.exe`, `Celsius2D.exe`, `CelsiusStudio.exe`,
`CelsiusEngine.exe`, `celsius_client.exe`, ...). Before this domain existed, this whole
product line was completely unwrapped — a real, genuine gap.

**How the batch interface was actually found**: a bare `Celsius3D.exe -help`/`-h` prints
only *"You are using the legacy command line syntax. Run 'Celsius3D -h' to know the
details about the new one"* and nothing else — a dead end by itself. The real answer was
found in `share/PostInstallationCheck/bin/postInstallCheck.pl`, Cadence's own installer
self-test script, which drives every Sigrity tool (including Celsius3D/CelsiusCFD/
Celsius2D) the exact same way it drives the already-confirmed PowerSI/PowerDC: for
Celsius3D/CelsiusCFD, `<exe> -tcl <script>.tcl` against a real `.tcl` macro using the
identical `sigrity::`-namespaced command language as every other domain in this suite;
for Celsius2D, `<exe> -b -XIMSAVE -r <workspace>.pdcx` (the same convention PowerDC's own
CLI uses).

**Confirmed live on this machine** (not just documentation/script-reading) by running
each tool directly against the real sample projects Cadence ships under
`share/PostInstallationCheck/{celsius3d,celsiuscfd,celsius2d}/`:
- `Celsius3D.exe -tcl case.tcl` — exit 0, "Stress engine started and completed
  successfully!", real numeric displacement/strain/stress results written to
  `case_Result_Summary.dat`/`.json`.
- `CelsiusCFD.exe -tcl pcb_pkg_sav.tcl` — exit 0, "CelsiusECSolver is completed", a real
  CFD network file (`.cfd`) generated.
- `Celsius2D.exe -b -XIMSAVE -r demo_sim.pdcx` — exit 0, "Simulation succeed", full
  thermal+stress engine logs with real memory/timing/mesh statistics.

`celsius3d_tools.py` and `celsiuscfd_tools.py` follow this suite's standard
compose-then-run session pattern (see `core.tclsession`): `start_*_session` opens a
session and records the confirmed `sigrity::configure version`/`sigrity::open file`
preamble, then `*_run_session` appends the confirmed `sigrity::begin simulation`/
`sigrity::end simulation -fileName`/`sigrity::close exe` trailer and launches the tool.
`celsius2d_tools.py` is a single CLI-only tool (`run_celsius2d_workspace`) since the
confirmed invocation runs directly against an already-built `.pdcx` workspace with no
separate Tcl script involved, matching `powerdc_export_signoff_report`'s shape in
Domain 1.

**Deliberately NOT wrapped, still a genuine gap**: `CelsiusStudio.exe` (the unified GUI
launcher — `doc/CelsiusStudioUG` documents only interactive desktop-icon launch, no CLI),
`CelsiusEngine.exe`/`celsius_client.exe` (internal worker/dispatch processes — the latter
launches a real solver subprocess directly when probed, confirming it's plumbing, not a
user-facing entry point), `CelsiusT3d.exe` (segfaults immediately on any probe — broken
standalone on this install). Celsius's own Tcl scripting guide
(`doc/CelsiusTcl/chap1_tk_Playing_Tcl_Commands.html`) documents an *additional*,
different automation surface — recording/replaying Tcl via the GUI's own Script Console
("Tools -> Script -> Play") — which is real but interactive-GUI-bound, not the headless
`-tcl` batch mode this domain actually wraps.
"""

from sigrity_mcp.domains.thermal import celsius2d_tools, celsius3d_tools, celsiuscfd_tools  # noqa: F401
