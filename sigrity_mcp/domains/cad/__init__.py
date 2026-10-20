"""Domain: CAD Creation (Allegro/OrCAD, SPB 22.1).

A second, sibling Cadence install (C:\\Cadence\\SPB_22.1) on this machine, separate from
the Sigrity Suite everything else in this project automates — used for schematic
capture (OrCAD Capture) and PCB layout (Allegro PCB Editor) rather than post-layout
signal/power analysis.

Status, verified live (not just from documentation):

- `allegro_batch_tools.py` (report/dbdoctor via their standalone exes) — fully
  confirmed, headless, no GUI dialog involved at all.
- `allegro_tools.py` (SKILL-scripted PCB layout) — the initial "Product Choices"
  product-chooser dialog blocker is resolved (the user set a default product
  interactively -- a one-time GUI product selection, not a license issue on this
  no-license-required install); the session/query mechanics are now confirmed live (a real board
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
  `cap2xml`, `dml2con`, `apd2con`). **WORK via the GUI** (product-chooser + "Translate"
  dialog, user-confirmed 2026-10-18) — NOT a blocked/defective/missing-feature class and
  NOT a license problem. Drive them with `launch_translator_gui("<tool>")`; the `run_*`
  CLI helpers are a best-effort headless fallback (doc-verified contracts, all switch-based
  + `-product pcb_librarian_expert`) that on this build stops at the `pcb_librarian_expert`
  checkout when driven bare — a property of the headless path, not the tools. See
  `core.tool_status` and the module's own docstring.

**MAJOR CORRECTION (2026-10-18) — `apd_package_tools.py` is added, and the "APD/apd.exe
GUI-only / no headless autorouting" claim below is now WRONG for APD + APR.** The earlier
audit concluded `apr.exe`/`placeroute.exe`/`apd.exe` were GUI-only with no batch surface
and were deliberately not wrapped. That was correct for `apr.exe`/`placeroute.exe`
*bare* (they open a GUI with no CLI args), but it was wrong as a claim about Allegro
Package Designer (APD) and the Advanced Package Router (APR) as *features*: `apd_package_
tools.py` proves, **live and headless**, that (a) `apd -product <APD tier> -nograph -s
<script> <design.mcm>` loads a package design and runs SKILL with no GUI (CONFIRMED:
journal + saved design independently re-read), (b) Z-Router fanout routes real new vias
headlessly via `allegro -nograph -s` + FORM replay (CONFIRMED: via diff 0->2 +
Zrouter.log + valid re-read), and (c) the Advanced Package Router (APR) runs a complete
headless auto-route via `apd -product <APD+> -option "Advanced Package Router" -nograph
-s` + `pkg_router`/`FORM icp_pkg_router route` (CONFIRMED: 91.4% completion, 1718 real
vias, independently re-read). So general board-level autorouting is in
`spif_specctra_tools.py`, dense flip-chip package autorouting (APR) + Z-Router fanout +
the APD batch base are in `apd_package_tools.py`. Only the BARE `apr.exe`/`placeroute.exe`
launchers remain genuinely GUI-only.

Confirmed GUI-only or with no documented/discoverable batch surface anywhere in the
shipped doc tree (deliberately NOT wrapped, to avoid fabricating a capability that
doesn't exist): the BARE `apr.exe`/`placeroute.exe` launchers themselves (they open an
interactive autorouting UI with no CLI args — the real headless autorouting alternatives
are `spif_specctra_tools.py` for board-level SPECCTRA and `apd_package_tools.py` for
APR/Z-Router; see the correction above), `padstack_editor.exe`,
`symboreditor.exe`/`symbolcreator.exe` (library authoring GUIs — see
`allegro_geometry_tools.py` for the real SKILL-scriptable alternative), `dfa_dlg.exe`,
`pdnsim.exe`, `orcad.exe`/`orcadx.exe` (redundant GUI entry points into Capture).
(`apd.exe` is no longer in this list — it is a confirmed-live headless batch runner, see
`apd_package_tools.py`; `apd2con`'s standalone bridge exe remains blocked on this build.)

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

**Five more modules, added to close FORJINN discovery-form gaps** (each `built_untested`
or stronger caveats — see its own module docstring for specifics):

- `schematic_checklist_tools.py` — a rule engine (decoupling/pull-up-down/clocks/
  resets/test-points) over real `report.exe -v net`/`-v bom` CSV output.
- `schematic_generation_tools.py` — `generate_schematic_from_spec`, composing
  `capture_tools.py`'s primitives into one requirement-to-schematic authoring call.
  Inherits Capture's own documented `known_blocked` batch-reliability caveat — see its
  docstring's "HONEST LIMITATION" section. UPDATE: the underlying problem this tool
  works around is now solved by a different mechanism —
  `capture_headless_tools.author_capture_schematic_headless` — not yet wired into this
  specific composite tool; see that module and this tool's own "UPDATE" note.
- `placement_routing_assistance_tools.py` — one call chaining real placement,
  SPECCTRA export+autoroute, the (confirmed-broken-on-this-machine) round-trip import,
  and a post-route batch DRC pass — honestly scoped around both of those already-known
  real quirks rather than papering over them.
- `manufacturing_analysis_tools.py` — structural completeness/well-formedness checks
  over Gerber/IPC-2581/IPC-356 outputs (not an electrical DFM check — no batch surface
  exists on this installation for that; `dfa_dlg.exe` remains confirmed GUI-only).
- `capture_check_design_rules` (added to `capture_tools.py` itself) — Capture's real
  ERC equivalent ("Design Rules Check", PCB menu, per its own confirmed doc entry).

**`allegro_import_tools.py`, added this pass to close a real gap**: this suite had no
way to create a brand-new `.brd` at all — every existing tool assumes a board already
exists on disk. `allegro_import_dxf` (`dxf2a.exe`) is CONFIRMED LIVE to do exactly that:
its own `-help` banner documents its default mode as "new design, only", and a live run
against Cadence's own shipped `flag.dxf`/`flag_l.cnv` sample produced a real `.brd` that
an independent tool (`report.exe`) then opened and correctly summarized. `allegro_export_dxf`
(`a2dxf.exe`, the reverse direction) is likewise CONFIRMED LIVE against this suite's own
real routed sample board, producing a valid DXF file. `allegro_new_blank_board` covers
the DXF-less case with a plain template-file copy (Cadence's own shipped blank 2-layer
board). See the module's own docstring for full live-test evidence and confirmed flag
syntax (space-separated, not attached — attached form was live-tested and rejected).
`convert_gerber.exe` and `EagleImport\\Eagle2Cp.exe` were also investigated this pass as
candidate importers and confirmed to be interactive-stdin-prompt-only with no headless
mode — not wrapped, documented as a known gap rather than silently skipped.

**`capture_headless_tools.py` / `netlist_import_tools.py`, added after root-causing the
long-standing Capture batch-automation block**: the Start Page proxy-credential hang that
made even OPENING Capture unreliable is now understood and fixed (`ENABLE_CAPTURE_
AUTOMATION=TRUE`, injected automatically for every `tool="capture"` job — see
`core.jobs.JobManager.submit`'s docstring), but making a *supplied Tcl script* actually
execute unattended is still unresolved (every invocation form tried lands on an idle
interactive console instead of sourcing the file — see `core.tool_status.
TOOL_STATUS_NOTES["capture"]` for the full evidence trail and a real `Capture.Application`
COM automation interface found as a promising next lead). For the specific, high-value
case of reading a netlist out of an EXISTING `.dsn`, there is a complete, CONFIRMED-LIVE,
Capture.exe-free alternative: `capture_headless_tools.extract_capture_netlist_headless`
loads Capture's own schematic-database DLL directly into the standalone `tclsh.exe`
(no GUI, no window, no proxy call, nothing to hang), and `netlist_import_tools.py`
(`run_netrev_import`/`run_netin_import`) feeds the result straight into a real Allegro
`.brd` — independently re-verified with `report.exe`/`dbdoctor.exe` to match a sample
design's known-good component/net/pin counts exactly.

**UPDATE — schematic AUTHORING is also solved, by the same mechanism, and the gap below
is now CLOSED**: `capture_headless_tools.author_capture_schematic_headless` creates a
brand-new design from nothing (`CreateDesign` -> `NewSchematic` -> `NewPage`), places
real part instances resolved from a real `.olb` library, draws real wires, and saves a
valid `.dsn` — all via the same DLL-in-`tclsh` mechanism, CONFIRMED LIVE and
independently re-verified by reopening the result with the read-side tool. The
`Capture.Application` COM interface mentioned above as a "promising lead" was
investigated and ruled OUT for authoring specifically (a safe `GetIDsOfNames` existence
probe found no `CreateDesign`/page/property surface on it at all — just a thin 7-method
file-lifecycle wrapper), as was `syscap.exe` (Allegro System Capture — confirmed to have
no batch/headless launch mode either). See `core.tool_status.TOOL_STATUS_NOTES
["tclsh"]` for the full evidence trail.

**UPDATE (2026-10-18) — the "placeholder refdes" gap is CLOSED, and so is PCB netlist
generation.** Placed instances now get a REAL, PERSISTENT reference designator via a
second, separate pass (`DboDesign_GetRootOccurrence` -> `DboInstOccurrence_
GetInstOccurrence` -> `DboInstOccurrence_SetReference`/`SetDesignator`, a different API
from the part-instance-level setter that doesn't persist) — the catch found along the
way: that occurrence API only resolves against an instance that's already been saved and
reopened, so `author_capture_schematic_headless` now runs two `tclsh` jobs internally
(create+place+save, then reopen+annotate+resave), not one. SEPARATELY, a new tool,
`generate_capture_pcb_netlist`, wraps `pstswp.exe` — a real, standalone, GUI-free
executable that generates a PCB netlist (`pstchip`/`pstxprt`/`pstxnet.dat`) directly
from a `.dsn`, closing the "Capture's own Create-Netlist menu command is GUI-only" gap
with no Capture.exe involvement at all. CONFIRMED LIVE, 4 independent ways, on one
authored-from-nothing test design: a fresh reopen read back the real refdes; the
generated netlist's `PART_NAME` showed the real refdes, not an auto-name; feeding that
netlist into `run_netrev_import` produced a real Allegro `.brd`; and `report.exe`'s own
BOM report (a fully independent code path) confirmed the correct `REFDES` on the final
board. The full Capture-schematic-to-Allegro-board pipeline — author, annotate,
netlist, import, independently verify — is now closed end to end with zero Capture.exe
GUI involvement at any step. See `core.tool_status.TOOL_STATUS_NOTES["tclsh"]`/
`["pstswp"]` for the complete evidence trail.

**RESOLVED — the `syscap.exe` lead below was investigated and RULED OUT; schematic
authoring is solved a different way.** `syscap.exe` (`Allegro System Capture`) has a
real, extensively documented Tcl command reference (`doc/scap_tcl_comms/`, ~600
commands) including `newProject`/`createSchematicPage`/`addComponent`/`drawWire`/
`saveDesign` — but a follow-up pass confirmed it has NO batch/headless launch mode at
all: `syscap.exe -tclfile scap_min.tcl -nograph` (and `-help`/`-?`) all still pop its
GUI "Cadence Product Choices" product-chooser dialog with empty stdout/stderr, and no
script-at-launch flag is documented anywhere in its doc tree (the UG says only "type
syscap in a command window and press Enter" — interactive by design). The original
text of this note is kept below for the historical trail; do not act on it as a live
lead.

The REAL answer turned out to be `capture_headless_tools.author_capture_schematic_
headless`: load Capture's OWN database DLL (`orDb_Dll_Tcl64.dll`) directly into the
standalone `tclsh.exe` — no Capture.exe, no syscap.exe, no GUI at all —
`CreateDesign` -> `NewSchematic`/`NewPage` -> resolve a package/part/device from a real
`.olb` -> `NewPlacedInst` -> `NewWireScalar` -> `SaveDesignAs`. CONFIRMED LIVE: created
a design from nothing, placed 2 real parts, drew 1 real wire, saved a valid `.dsn`,
independently re-verified by reopening it through the companion read tool
(`extract_capture_netlist_headless`): parts/pins/wire all genuinely present. See
`core.tool_status.TOOL_STATUS_NOTES["tclsh"]` for the complete evidence trail,
including why `Capture.Application`'s COM interface was ALSO investigated and ruled
out for authoring (a safe `GetIDsOfNames` existence probe found no `CreateDesign`/
page/property surface on it — just a thin 7-method file-lifecycle wrapper).

Original (now-superseded) note, kept for the historical trail: "A promising,
NOT-yet-implemented lead found this same pass, for whoever picks this up next:
`syscap.exe` ... has a real, extensively documented Tcl command reference
(`doc/scap_tcl_comms/`, ~600 commands) including `newProject <name> <design_name>
<project_path> sch composite` — a genuinely-documented, from-nothing 'create a brand
new schematic project' call ... This would be a much more promising schematic-authoring
path than `capture_tools.py`'s already-documented `known_blocked` Tcl batch
reliability, IF `syscap.exe` has a working headless/batch launch mode. That launch
mechanism is NOT confirmed [at the time this note was written] ..."
"""

from sigrity_mcp.domains.cad import (  # noqa: F401
    allegro_batch_tools,
    apd_package_tools,
    allegro_constraint_tools,
    allegro_drc_tools,
    allegro_extraction_tools,
    allegro_geometry_tools,
    allegro_import_tools,
    allegro_library_tools,
    allegro_manufacturing_tools,
    allegro_placement_tools,
    allegro_project_tools,
    allegro_tools,
    audit_approval_tools,
    capture_headless_tools,
    capture_tools,
    document_generation_tools,
    interchange_tools,
    manufacturing_analysis_tools,
    netlist_import_tools,
    placement_routing_assistance_tools,
    pspice_tools,
    rigid_flex_stackup_tools,
    schematic_checklist_tools,
    schematic_generation_tools,
    spif_specctra_tools,
)

