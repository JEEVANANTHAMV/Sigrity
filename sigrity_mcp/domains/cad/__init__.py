"""Domain: CAD Creation (Allegro/OrCAD, SPB 22.1).

A second, sibling Cadence install (C:\\Cadence\\SPB_22.1) on this machine, separate from
the Sigrity Suite everything else in this project automates — used for schematic
capture (OrCAD Capture) and PCB layout (Allegro PCB Editor) rather than post-layout
signal/power analysis.

Status, verified live (not just from documentation):

- `allegro_batch_tools.py` (report/dbdoctor via their standalone exes) — fully
  confirmed, headless, no GUI dialog involved at all.
- `allegro_tools.py` (SKILL-scripted PCB layout) — the initial "Product Choices"
  license-tier dialog blocker is resolved (the user set a default product
  interactively); the session/query mechanics are now confirmed live (a real board
  loads, a real SKILL query executes and returns, the process exits cleanly). Database
  *mutation* calls (create net/component/etc.) are implemented from documentation but
  did not complete within two minutes in live testing — treat those specific compose
  tools as unverified until independently confirmed; see the module's own docstring.
- `capture_tools.py` (Tcl-scripted schematic capture) — a bare launch now opens
  cleanly, but the batch-script invocation itself remains unreliable across repeated
  attempts (inconsistent behavior, once triggering a crash-recovery dialog per
  Cadence's own docs). Built from documentation and real sample scripts, but not
  confirmed working end-to-end — see the module's own docstring.
"""

from sigrity_mcp.domains.cad import allegro_batch_tools, allegro_tools, capture_tools  # noqa: F401
