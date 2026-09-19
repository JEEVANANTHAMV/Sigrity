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

Six more standalone-CLI modules, added after a full audit of every executable in
`C:\\Cadence\\SPB_22.1\\tools\\bin` (350+ files) against the shipped doc tree and each
exe's own `-help` output, following the same "call the standalone exe directly, verify
against real `-help`/doc text, never fabricate a flag" discipline as
`allegro_batch_tools.py`:

- `allegro_drc_tools.py` — headless DRC (`batch_drc.exe`) and standalone constraint/rule
  checking (`checkplus.exe`).
- `allegro_placement_tools.py` — real auto-*placement* (`placement.exe`, confirmed via
  `allegro_batch placement -help`'s "Allegro auto-place program" banner), NC drill-route
  generation (`ncroute.exe`), and best-effort via/pin-escape fanout routing
  (`zrouter.exe`). NOTE: no batch-CLI or SKILL surface for general trace *autorouting*
  was found anywhere on this installation (`apr.exe`/`placeroute.exe` are GUI-only) — see
  the module's own docstring for the full scope note.
- `allegro_manufacturing_tools.py` — IPC-2581, IPC-356, and STEP (3D/MCAD) export, plus
  best-effort Gerber plot.
- `allegro_library_tools.py` — IBIS model checking (`ibischk3`-`ibischk6`) and die-
  abstract validation/comparison (`diacheck`/`diacompare`, 3D-IC/interposer flows).
- `allegro_extraction_tools.py` — Allegro's own design/connectivity data extractor
  (`designextractor.exe`, distinct from Sigrity's EM extraction in Domain 3).
- `interchange_tools.py` — schematic/netlist interchange translators (`con2xml`,
  `cap2xml`, `dml2con`, `apd2con`) confirmed real but license-blocked on this machine
  (fails with "No Product License selected" before printing usage) — see
  `core.tool_status` and the module's own docstring.

Confirmed GUI-only or with no documented/discoverable batch surface anywhere in the
shipped doc tree (deliberately NOT wrapped, to avoid fabricating a capability that
doesn't exist): `apr.exe`/`placeroute.exe` themselves (interactive autorouting UI —
see `spif_specctra_tools.py` below for the real headless alternative), `padstack_editor.exe`,
`symboleditor.exe`/`symbolcreator.exe` (library authoring GUIs — see
`allegro_geometry_tools.py` for the real SKILL-scriptable alternative), `dfa_dlg.exe`,
`pdnsim.exe`, `apd.exe` (the GUI half of the license-blocked Package Designer bridge),
`orcad.exe`/`orcadx.exe` (redundant GUI entry points into Capture).

**Three corrections from a follow-up research pass** — each of these was previously
(wrongly) written off, until a broader/differently-worded search of the same local doc
tree and SKILL function reference turned up a real, confirmed automation surface:

- **`spif_specctra_tools.py`** — general trace *autorouting* IS automatable, just not
  via `apr.exe`/`placeroute.exe` directly: Allegro ships a genuine SPECCTRA-router
  bridge (`spif_batch.exe` + `specctra.exe -nog -do <script>.do -quit`), confirmed live
  producing a 100%-routed, 0-conflict result on both a Cadence tutorial design and this
  suite's own real sample board. The reverse import step
  (`spif_batch.exe -i <board> <session.ses>`) is confirmed to crash on this machine —
  see that module's docstring for the honest, not-yet-fully-working caveat.
- **`allegro_constraint_tools.py`** — Allegro's Constraint Manager IS SKILL-scriptable:
  the earlier "no `axl*Constraint*` API found" conclusion only failed because it
  searched for the wrong substring. The real naming convention is `axlCNS*`/`axlCns*`
  (~60 real documented functions in `share/pcb/examples/skill/DOC/FUNCS/`) — spacing
  rules, physical rules, electrical constraint sets (ecsets), and net-level constraint
  queries are wrapped here.
- **`allegro_geometry_tools.py`** and **`pspice_tools.py`** — real, SKILL-scriptable
  trace/via/padstack/module-placement/net-assignment (a genuine alternative to
  "GUI-only" library/placement authoring) and a genuine headless PSpice batch simulator
  (`psp_cmd.exe`, distinct from the GUI-only `pspice.exe`/`pspiceaa.exe`) were both found
  the same way.

All four new modules are `built_untested`: every function signature was independently
confirmed real via its own local doc page (not guessed, not taken on faith from
external claims), but most were not yet each individually exercised live against a real
board on this machine — see `core.tool_status` and each module's own docstring.
"""

from sigrity_mcp.domains.cad import (  # noqa: F401
    allegro_batch_tools,
    allegro_constraint_tools,
    allegro_drc_tools,
    allegro_extraction_tools,
    allegro_geometry_tools,
    allegro_library_tools,
    allegro_manufacturing_tools,
    allegro_placement_tools,
    allegro_tools,
    capture_tools,
    interchange_tools,
    pspice_tools,
    spif_specctra_tools,
)
