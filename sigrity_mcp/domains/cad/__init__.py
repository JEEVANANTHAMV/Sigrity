"""Domain: CAD Creation (Allegro/OrCAD, SPB 22.1).

A second, sibling Cadence install (C:\\Cadence\\SPB_22.1) on this machine, separate from
the Sigrity Suite everything else in this project automates — used for schematic
capture (OrCAD Capture) and PCB layout (Allegro PCB Editor) rather than post-layout
signal/power analysis.

Current status, verified live (not just from documentation): the two GUI editors
themselves — `allegro.exe` (SKILL-scriptable layout) and `Capture.exe` (Tcl-scriptable
schematic) — both open an interactive product/license-chooser dialog on every launch
attempt observed so far, even with a documented print-and-exit flag or an explicit
`-product=<name>` argument, and block there rather than proceeding headlessly. This is
NOT a license failure (the dialog genuinely lists real license tiers, including
Sigrity Aurora, as available choices) — it looks like a one-time per-user-profile
interactive confirmation that hasn't been done yet on this machine. Design *creation*
(placing components, defining nets/board outline/stackup) needs a live session inside
one of these two editors, so no `capture_tools.py`/`allegro_tools.py` compose-session
tools exist yet — building them before this is resolved would mean shipping tools with
no way to verify they actually work.

What IS confirmed safe and working right now: the standalone batch/report executables
that ship alongside the two editors (verified against real sample board files, not just
`-help` text). `allegro_batch_tools.py` wraps these directly — see its module docstring
for why they're called directly rather than through the `allegro_batch.exe` multiplexer
Cadence's own docs describe as the entry point for them.
"""

from sigrity_mcp.domains.cad import allegro_batch_tools  # noqa: F401
