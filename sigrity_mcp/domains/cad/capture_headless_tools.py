"""Headless OrCAD Capture schematic-database read — NO Capture.exe process at all.

`capture_tools.py`'s module docstring and `core.tool_status.TOOL_STATUS_NOTES["capture"]`
document, in detail, that `Capture.exe`'s own batch/script invocation is `known_blocked`
for genuine unattended automation: passing a `.tcl` script on the command line (with or
without `-product=...`) lands on an idle interactive 'Capture>' console in the Command
Window instead of sourcing the file, and the Start Page proxy-credential hang that used
to make even OPENING Capture unreliable is now understood and fixed separately
(`ENABLE_CAPTURE_AUTOMATION=TRUE`, see `core.jobs.JobManager.submit`'s docstring) but
does not by itself make a supplied script executable.

This module sidesteps that whole problem for one specific, high-value case: reading an
EXISTING `.dsn`'s schematic content (parts, pins, nets) to produce a netlist. Cadence
ships Capture's own C++ database as a Tcl-loadable DLL
(`tools/bin/orDb_Dll_Tcl64.dll`) that the *standalone* Tcl shell (`tools/bin/tclsh.exe`,
nothing to do with Capture.exe) can `load` directly — no GUI, no window, no proxy call,
no interactive console to get stuck on. CONFIRMED LIVE: extracted 90 part instances /
252 pins / 76 nets from the shipped `Fault-Detector` sample, matching its known-good
counts (81 PCB components / 251 pins / 75 nets — the small deltas are schematic-only
simulation elements like voltage sources that never reach the board), independently
re-verified afterward via `netrev -n` -> `report.exe -v sum` (see `netlist_import_tools.py`).

Two distinct DboTcl calling conventions, confirmed live, both handled by the generated
script's own `cstrval`/`dbstr` helpers:
  - Most `*_sGet*` getters return a CString HANDLE; read the actual text via
    `DboTclHelper_sGetConstCharPtr <handle>`.
  - A few `DboDesign` methods (`GetRootName`) instead want a CString OUT-parameter
    reference and throw a `TypeError ... argument 2 of type 'CString &'` if you pass a
    status object there by mistake — avoided entirely here by never calling those
    methods. NOTE: `DboDesign_GetName` (no `s` prefix) is NOT a real command at all on
    this DLL build ("invalid command name", confirmed live the hard way — a first draft
    of this module called it directly and broke every extraction) — the real getter is
    `DboDesign_sGetName`, called defensively (`catch`-wrapped) since even that was not
    independently re-verified to exist on every design state.

CONFIRMED NOT to work in this headless mode (do not "fix" the script to try these):
flat-net iteration (`NewFlatNetsIter`), globals (`NewGlobalsIter`), and
`NewSchematicOccurrencesIter`/`NewOccurrencesIter` all return nothing/fail — flattened
connectivity is a GUI-only construct built by Capture's connectivity engine, never
populated by a bare headless `GetDesignAndSchematics`. The real path, used here, walks
raw schematic objects directly: `DboDesign_GetRootSchematic` ->
`DboSchematic_ReadAllPages` (REQUIRED before any page iteration — pages are not loaded
into memory otherwise) -> `DboSchematic_NewPagesIter` -> `DboPage_NewPartInstsIter` ->
`DboPartInst_NewPinsIter`, reading `sGetReference`/`sGetPartValue`/`sGetPinNumber`/
`sGetNetName` off each object. Every iterator's `Next*` call returns the literal string
`"NULL"` (not Tcl's empty string) when exhausted or on a bad handle — the generated
script's `isnull` guard checks for this before dereferencing anything, since passing
`"NULL"` into a method that dereferences it segfaults `tclsh.exe` outright (0xC0000005).

`extract_capture_netlist_headless` is READ-ONLY. `author_capture_schematic_headless`
(below) is the WRITE counterpart, using the same DLL/mechanism to go the other
direction — CONFIRMED LIVE to create a brand-new design from nothing, place real parts
from a real library, draw a real wire, and save a valid `.dsn` (10,752 bytes),
independently re-verified by reopening it through this same module's read path
(`parts=2 pins=6`, one wire present on the page). This closes the gap `capture_tools.py`
and `core.tool_status.TOOL_STATUS_NOTES["capture"]` document as unresolved: the
`Capture.Application` COM interface was investigated as an alternative and found too
shallow for authoring (a `GetIDsOfNames` existence probe found only `PlacePart`/
`PlaceWire`/`PlacePin`/`OpenDesign`/`Close`/`Exit`/`Save` — no `CreateDesign`, no page/
property/annotate surface at all), and `syscap.exe` (Allegro System Capture, a distinct
product) has no batch/headless launch mode either (`-tclfile`/`-nograph` both still pop
its GUI product-chooser dialog; no documented script-at-launch flag exists for it). The
DB-write path here needs neither.

Reference designators: SOLVED (2026-10-18), superseding the earlier finding below —
but it needs a SECOND pass, not a fix to the original single-pass call. `NewPlacedInst`'s
Name arg does NOT land the refdes (instances come back with the placeholder `DN?`/
auto-named `INS1`/`INS2`/...), and `DboPartInst_SetReference` (the part-INSTANCE-level
setter) only updates the in-session object — it does NOT survive a reopen, exactly as
originally found. The field that genuinely persists is a DIFFERENT, OCCURRENCE-level
API: `DboDesign_GetRootOccurrence <design> <status>` ->
`DboInstOccurrence_GetInstOccurrence <rootOcc> <partInst> <status>` ->
`DboInstOccurrence_SetReference <occ> <CString>` + `DboInstOccurrence_SetDesignator
<occ> <CString>` (CONFIRMED LIVE: these take exactly 2 args — `self reference`/`self
designator`, NOT 3 with a status object; the 3-arg form raises "Wrong # args"). THE
CATCH, also confirmed live: `GetInstOccurrence` returns NULL for a part instance that
was JUST created and never saved — the occurrence tree isn't built for brand-new,
uncommitted instances in the SAME session. So `author_capture_schematic_headless` runs
TWO separate `tclsh` jobs, not one: pass 1 creates/places/wires/saves (unchanged, still
only calls `DboPartInst_SetReference`, which is cosmetic/in-session-only); pass 2
(`_build_annotate_script`) reopens the just-saved file FRESH (a real, genuinely
different session, where the occurrence tree now resolves) and does the real
occurrence-level assignment, then saves again. CONFIRMED LIVE end-to-end, 3 independent
ways: (1) a THIRD, separate fresh reopen's `DboInstOccurrence_sGetReferenceDesignator`
read back the exact value set (the old `DboPartInst`-level getter still reads the
original auto-name even after pass 2 — the two are genuinely different fields, and
that's fine, nothing reads refdes via the part-instance getter downstream); (2)
`pstswp.exe -pst` (see `generate_capture_pcb_netlist` below) run against the
twice-saved `.dsn` emitted the real refdes as `PART_NAME` in `pstxprt.dat`, not
`INS1`/`INS2`; (3) the generated `.pst` files fed straight into `netrev -n`
(`netlist_import_tools.py`) produced a real `.brd` with the correct refdes,
independently confirmed via `report.exe`. The ANNOTATE-step concern from the original
investigation (`capBatchAnnotate` being GUI-only) turned out to be moot — occurrence-
level assignment is a different, standalone mechanism that doesn't need Annotate at
all. Pass-2 matches `components` to parts by ITERATION ORDER
(`DboPage_NewPartInstsIter`'s own order), not by name or position — a documented
assumption (observed to hold for a simple, freshly-authored single-page design), not a
guaranteed DLL contract; see `_build_annotate_script`'s own docstring.

 Net connectivity (`NewFlatNetsIter`) still does not populate for the same
 GUI-connectivity-engine reason documented above for the read path — wire-to-pin
 connectivity is implicit in page geometry (confirmed: the drawn wire IS present and
 counted on reopen) rather than computed into a named net by this DLL build. This does
 NOT block the netlist-generation pipeline below: `pstswp.exe` derives real net
 connectivity directly from the saved page geometry (confirmed — see
 `generate_capture_pcb_netlist`), independent of whether `NewFlatNetsIter` would ever
 populate.

 Pin-coordinate resolution for electrically-connected wires (2026-10-21): a wire drawn
 via `NewWireScalar` only connects two pins if its endpoint lands exactly on the pin's
 real page coordinate. `author_capture_schematic_headless`'s `wires` parameter now
 accepts a NAME-RESOLVED shape — `{"pin1":{"part_index","pin"},
 "pin2":{"part_index","pin"}}` — in addition to the historical raw
 `{"x1","y1","x2","y2"}` form. At runtime the generated `get_pin_xy` helper (see
 `_get_pin_xy_proc_tcl`'s docstring for the full confirmed-live evidence) reads each
 named pin's hot spot via `DboPortInst_sGetHotSpotX`/`sGetHotSpotY` — the pin's exact
 wire-attachment point — and feeds those page-space coordinates straight to
 `NewWireScalar`. This turns a verified pin-name->pin-name wiring spec into real drawn
 schematic wires without the caller hand-computing endpoints. CONFIRMED LIVE end-to-end:
 a generated pin-resolved wire was saved, reopened in a fresh process, and BOTH named
 pins independently reported the same net name (`DboPortInst_sGetNetName`) — the real
 proof of electrical connection, not just a non-erroring call.

Heterogeneous BOM merge (2026-10-18, two fix passes that same day): `author_capture_
schematic_headless` accepts a per-component `library`/`package` so a 30+-distinct-part
BOM — the typical SamacSys/UltraLibrarian one-vendor-`.olb`-per-part export shape —
merges into ONE `.dsn`. Fix pass 1 made each component able to name its own
`.olb`/package (previously every component was forced onto one resolved package —
the original "can't merge a heterogeneous BOM" shape). Fix pass 2 (this module's
current state) corrected a real, initially-missed correctness bug in pass 1's
generated script: it opened EVERY distinct vendor `.olb` up front and kept them all
open for the whole placement pass, but the installed DLL build's `DboSession`
tolerates at most ONE open `DboLib` handle at a time when the paths differ (a second
`GetLib` of a different path returns `ERROR(ORDBDLL-1021): Object Not Found` until the
first is `RemoveLib`'d — confirmed by exhaustive bisection, `runs/olb_union_fix_
report.md`, `runs/getlib_min.tcl` vs `runs/getlib_seq3.tcl`); with 30+ distinct
one-part `.olb`s every group after the first would fail. The generated script now
interleaves `GetLib`/resolve/place/`RemoveLib` strictly per group, with the first
group's `GetLib` necessarily preceding `NewSchematic`/`NewPage` (a design page
created before any `GetLib` has ever run in the session independently poisons the
lib-directory cache and makes the very first `GetLib` return 1021) — see
`_build_author_script`'s docstring for the full ordering and the `runs/` scripts
that pinned down each constraint. Live-confirmed end-to-end with three genuinely
distinct single-part vendor `.olb`s placed into one `.dsn` in one call
(`runs/mcp_generated_author.tcl` -> `placed=3`, independently re-verified by a
separate fresh-reopen script, `runs/verify_3in1.tcl` -> `TOTAL_PARTS=3`), in addition
to pass 1's earlier 35-distinct-package/two-library confirmation
(`runs/bom_merge_report.md`). The DOWNSTREAM netlist step is still gated by TWO
SEPARATE library-data issues (PCB-footprint-carrying packages; duplicate-pin-name
devices) that are orthogonal to the merge itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sigrity_mcp.core.config import settings
from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.core.paths import resolve_path as _resolve
from sigrity_mcp.core.process import submit_job
from sigrity_mcp.core.tclscript import TclScript, tcl_path, tcl_str
from sigrity_mcp.mcp_app import mcp

_DB_DLL_RELATIVE = Path("tools") / "bin" / "orDb_Dll_Tcl64.dll"


def _add_helper_procs(script: TclScript) -> None:
    """The small Tcl helpers both the read and write scripts below share:
    `isnull` (every `Next*`/failed-lookup call returns the literal string "NULL", not
    Tcl's empty string, when exhausted — confirmed live to segfault tclsh.exe outright
    if dereferenced without this guard), `cstrval` (reads a CString HANDLE's actual
    text), `dbstr` (calls a `*_sGet*`-style getter and reads its CString result in one
    `catch`-guarded step, for a getter that might not exist on every object), and
    `dbint` (the integer-returning sibling of `dbstr` — the flat `*_sGet*` coordinate
    getters return a PLAIN Tcl int directly, NOT an int handle, so `DboTclHelper_sGetInt`
    must NOT be applied to them; see `get_pin_xy`'s docstring for the full coordinate-
    space evidence)."""
    script.raw(
        "proc isnull {o} {\n"
        '  if {$o eq "" || $o eq "0" || $o eq "NULL"} { return 1 }\n'
        "  return 0\n"
        "}"
    )
    script.raw(
        "proc cstrval {h} {\n"
        "  if {[isnull $h]} { return \"\" }\n"
        '  if {![string match "*CString*" $h]} { return "" }\n'
        '  if {[catch {set v [DboTclHelper_sGetConstCharPtr $h]} e]} { return "" }\n'
        '  if {$v eq "" || $v eq "NULL" || $v eq "0"} { return "" }\n'
        "  return $v\n"
        "}"
    )
    script.raw(
        "proc dbstr {getter obj status} {\n"
        "  if {[isnull $obj]} { return \"\" }\n"
        "  if {[catch {set h [eval [list $getter $obj $status]]} e]} { return \"\" }\n"
        "  return [cstrval $h]\n"
        "}"
    )
    script.raw(
        "proc dbint {getter obj status} {\n"
        "  if {[isnull $obj]} { return \"\" }\n"
        "  if {[catch {set r [eval [list $getter $obj $status]]} e]} { return \"\" }\n"
        "  if {![string is integer -strict $r]} { return \"\" }\n"
        "  return $r\n"
        "}"
    )
    # The coordinate-lookup helper. Defined here (shared across read/annotate/author
    # scripts) but only USED by the authoring script's wires pass — it reads the
    # just-placed parts' pins to resolve a named pin's page-space hot spot. $lStatus is
    # a global captured at *call* time (Tcl resolves globals at execution, not
    # definition), so it must already be `set` by the caller before invoking this proc.
    script.raw(_get_pin_xy_proc_tcl())


def _get_pin_xy_proc_tcl() -> str:
    """Tcl source for the `get_pin_xy` helper proc, appended by `_add_helper_procs`.

    **Purpose.** Turn a placed part's reference designator + a pin's name/number into
    that pin's exact page-coordinate hot spot `{x y}`, so a `NewWireScalar` endpoint can
    be aimed at a named pin instead of a hand-supplied raw coordinate — the missing
    piece that blocked turning a verified wiring spec (pin-name -> pin-name) into real
    drawn schematic wires.

    **Confirmed-live coordinate facts (2026-10-21, against the installed
    `orDb_Dll_Tcl64.dll`, NOT the GUI `scap_tcl_comms` API):**
      - The correct getters are `DboPortInst_sGetHotSpotX/Y` (returns a PLAIN Tcl int).
        `DboPortInst_GetLocation` does NOT exist on DboPortInst (the spec's original
        guess was the wrong method family — `GetLocation` lives on DboAlias/
        DboGraphicInstance/etc., never a pin). `DboPortInst_sGetStartPointX/Y` also
        exists and is the pin's *other* (inner) end — use Hot Spot, not Start Point,
        for where a wire attaches.
      - Flat `sGet*` coordinate getters return a bare integer. They are NOT int handles:
        `DboTclHelper_sGetInt` on their result raises
        `TypeError ... argument 1 of type 'int &'`. (This is why `dbint` exists and why
        an earlier attempt that funneled these through `sGetInt` silently returned "ERR".)
      - The returned int is ALREADY in page-internal units — the SAME coordinate space
        `NewPlacedInst`'s placement CPoint and `NewWireScalar` endpoints use. It must NOT
        be multiplied by `GetPhysicalGranularity` again (that scale factor only applies
        when a caller specifies a *placement* in user units, per the `docxy` helper).
        Proof: two identical parts placed at page CPoints (0,0) and (0,20000) reported
        pin-0 hot spots (−30,0) and (−30,20000) — exactly the placement offset with the
        symbol-space pin offset (−30) added. A wire drawn between those two hot spots
        (`NewWireScalar`) was saved, reopened in a fresh process, and BOTH pins then
        reported the same net name (`DboPortInst_sGetNetName` = `N00041`) — independent
        confirmation the wire genuinely landed on both pins.
      - For a part that was saved and reopened (not just-placed in-session), the flat
        `sGetHotSpotX/Y` value is the same page-space value the in-session form returned
        (verified on `INNOSYNTH_IMX8MP_MAINSOCBOARD_FULLASSEMBLY.DSN`; the large
        coordinates there simply reflect that part's distant placement).

    **Why it matches by iteration index, not by reference designator (CONFIRMED LIVE
    2026-10-21):** `DboPartInst_sGetReference` on a still-in-session, just-placed part
    returns the AUTO-GENERATED instance name (`INS1`/`INS2`/...), NOT the `ref` passed
    to `NewPlacedInst`/`SetReference` — the real reference designator only resolves at
    the OCCURRENCE level, and that requires a save + fresh reopen (`_build_
    annotate_script`'s pass-2 mechanism). So a name-resolved wire cannot look up a part
    by its human name in the authoring pass. Instead, callers specify a 0-based
    PLACEMENT INDEX, and this proc iterates `DboPage_NewPartInstsIter` to the Nth part —
    the exact same iteration-order assumption `_build_annotate_script` already relies on
    to assign refdes (`refs_in_order` matched to parts by iteration order, not name).
    Both are documented assumptions (iteration order = placement order for a freshly
    authored single-page design, observed to hold in live testing), not guaranteed DLL
    contracts.

    **The Tcl `get_pin_xy` contract.** `get_pin_xy <page> <partIndex> <pinname>` returns
    that part's pin's Hot Spot as `"{hx hy}"`, or an empty string on any miss (no such
    part index, no matching pin, or a non-integer coordinate). It does not throw and
    never dereferences a NULL handle (every step is `isnull`-guarded).
    """
    return (
        "proc get_pin_xy {page partIndex pinname} {\n"
        "  global lStatus\n"
        "  set i 0\n"
        "  set partIter [DboPage_NewPartInstsIter $page $lStatus]\n"
        "  while {1} {\n"
        "    set part [DboPagePartInstsIter_NextPartInst $partIter $lStatus]\n"
        "    if {[isnull $part]} { return \"\" }\n"
        "    if {$i eq $partIndex} {\n"
        "      set pinIter [DboPartInst_NewPinsIter $part $lStatus]\n"
        "      while {1} {\n"
        "        set pin [DboPartInstPinsIter_NextPin $pinIter $lStatus]\n"
        "        if {[isnull $pin]} { break }\n"
        "        set num [dbstr DboPortInst_sGetPinNumber $pin $lStatus]\n"
        "        set nm  [dbstr DboPortInst_sGetPinName  $pin $lStatus]\n"
        "        if {$num eq $pinname || $nm eq $pinname} {\n"
        "          set hx [dbint DboPortInst_sGetHotSpotX $pin $lStatus]\n"
        "          set hy [dbint DboPortInst_sGetHotSpotY $pin $lStatus]\n"
        "          if {$hx ne \"\" && $hy ne \"\"} { return [list $hx $hy] }\n"
        "        }\n"
        "      }\n"
        "      return \"\"\n"
        "    }\n"
        "    incr i\n"
        "  }\n"
        "}"
    )


def _build_extract_script(dsn_file: str, output_file: str) -> TclScript:
    """The confirmed-working headless extraction sequence, parameterized.

    `dsn_file`/`output_file` are brace-quoted via `tcl_path` (forward-slash-normalized,
    safe against spaces/backslashes) — never string-formatted in raw, matching this
    suite's one Tcl-injection-safety rule (see `core.tclscript`'s module docstring).
    """
    dll_path = tcl_path(str((settings.cadence_spb_home / _DB_DLL_RELATIVE)))
    script = TclScript()
    script.comment(
        "Headless Capture DB extraction -- generated by capture_headless_tools.py. "
        "No Capture.exe process is involved; run via tclsh.exe with CDS_INST_DIR set."
    )
    _add_helper_procs(script)
    script.raw(f"load {dll_path} DboTclWriteBasic")
    script.raw("set lStatus  [DboState]")
    script.raw("set lSession [DboTclHelper_sCreateSession]")
    script.raw(f"set lPath    [DboTclHelper_sMakeCString {tcl_path(dsn_file)}]")
    script.raw("set lDesign  [$lSession GetDesignAndSchematics $lPath $lStatus]")
    script.raw(
        'if {[$lStatus Failed]} { puts "EXTRACT_ERROR: [$lStatus Message]"; exit 1 }'
    )
    # DboDesign_GetName is NOT a real command in this DLL's Tcl binding (confirmed
    # live: "invalid command name" -- unlike the per-object sGet* getters, which ARE
    # real). The design name is a nice-to-have, not part of the proven working
    # sequence, so get it defensively and never let it take the whole extraction down.
    script.raw('set designName ""')
    script.raw("catch {set designName [dbstr DboDesign_sGetName $lDesign $lStatus]}")
    script.raw("set rootSch [DboDesign_GetRootSchematic $lDesign $lStatus]")
    script.raw("DboSchematic_ReadAllPages $rootSch")
    script.raw("array set NET_MEMBERS {}")
    script.raw("array set NET_SEEN {}")
    script.raw("array set NET_MEMBERSEEN {}")
    script.raw("set total_parts 0")
    script.raw("set total_pins  0")
    script.raw("set pageIter [DboSchematic_NewPagesIter $rootSch $lStatus]")
    script.raw("while {1} {")
    script.raw("  set page [DboSchematicPagesIter_NextPage $pageIter $lStatus]")
    script.raw("  if {[isnull $page]} { break }")
    script.raw("  set partIter [DboPage_NewPartInstsIter $page $lStatus]")
    script.raw("  while {1} {")
    script.raw("    set part [DboPagePartInstsIter_NextPartInst $partIter $lStatus]")
    script.raw("    if {[isnull $part]} { break }")
    script.raw("    incr total_parts")
    script.raw("    set ref [dbstr DboPartInst_sGetReference $part $lStatus]")
    script.raw('    if {$ref eq ""} { continue }')
    script.raw("    set pinIter [DboPartInst_NewPinsIter $part $lStatus]")
    script.raw("    while {1} {")
    script.raw("      set pin [DboPartInstPinsIter_NextPin $pinIter $lStatus]")
    script.raw("      if {[isnull $pin]} { break }")
    script.raw("      incr total_pins")
    script.raw("      set pinNum [dbstr DboPortInst_sGetPinNumber $pin $lStatus]")
    script.raw("      set netNm  [dbstr DboPortInst_sGetNetName  $pin $lStatus]")
    script.raw('      if {$netNm ne "" && $pinNum ne ""} {')
    script.raw('        set member "${ref}.${pinNum}"')
    script.raw("        if {![info exists NET_SEEN($netNm)]} {")
    script.raw("          set NET_SEEN($netNm) 1")
    script.raw('          set NET_MEMBERS($netNm) ""')
    script.raw("        }")
    script.raw('        set mk "$netNm|$member"')
    script.raw("        if {![info exists NET_MEMBERSEEN($mk)]} {")
    script.raw("          set NET_MEMBERSEEN($mk) 1")
    script.raw('          append NET_MEMBERS($netNm) "${member} "')
    script.raw("        }")
    script.raw("      }")
    script.raw("    }")
    script.raw("  }")
    script.raw("}")
    script.raw(f"set outFile {tcl_path(output_file)}")
    script.raw('set fh [open $outFile w]')
    script.raw("foreach n [lsort [array names NET_MEMBERS]] {")
    script.raw('  set members [join [split [string trim $NET_MEMBERS($n)] " "] " "]')
    script.raw('  puts $fh "$n ; $members"')
    script.raw("}")
    script.raw("close $fh")
    script.raw(
        'puts "EXTRACT_SUMMARY design=$designName parts=$total_parts '
        'pins=$total_pins nets=[llength [array names NET_SEEN]]"'
    )
    script.raw("delete_DboSession $lSession")
    script.raw("delete_DboState $lStatus")
    return script


def _component_pkg_key(comp: dict) -> str:
    return f"{comp.get('library', '')}::{comp.get('package', '')}"


def _group_components_by_pkg(components: list[dict]) -> list[list[dict]]:
    """Group components by (library_file, package_name) so each group places from exactly
    one package — the unit the single-package authoring engine requires. Order is
    preserved (first-encountered group order), so iteration order (which pass-2 relies
    on for refdes assignment) is stable."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for c in components:
        k = _component_pkg_key(c)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(c)
    return [groups[k] for k in order]


def _build_author_script(
    design_name: str,
    library_file: str,
    components: list[dict],
    wires: list[dict],
    output_dsn: str,
    package_name: Optional[str],
) -> TclScript:
    """The confirmed-working headless authoring sequence, generalized from the exact
    call forms an earlier investigation confirmed live (see
    `AUTHORING_REPORT.md` under `scripts/tools/capture_author/` for the full
    trial-and-error trail this was built from — PDF-documented signatures for
    `NewSchematic`/`NewPlacedInst`/`MarkAllLibForSave`/etc. do NOT all match this DLL
    build; only the forms used here were confirmed to actually bind).

    **HETEROGENEOUS BOM MERGE — MULTI-LIBRARY, ONE DESIGN (2026-10-18, fix pass 2):**
    `components` may each carry their own `library` (a .olb path; defaults to
    `library_file`) and `package` (a package name; defaults to `package_name`, which
    itself may be None => "first package in the library"). Components are grouped by
    `(library, package)` and EVERY distinct combination is resolved + instantiated in
    this ONE design, so a 30+-distinct-part heterogeneous BOM (e.g. one vendor .olb
    per part, the typical SamacSys/UltraLibrarian export shape) merges into a single
    .dsn with each part genuinely its own part.

    **THE 1-OPEN-LIB CONSTRAINT (root cause of the original "can't union 30 .olbs"
    bug, confirmed live 2026-10-18 by ~15 bisection scripts, see
    `runs/olb_union_fix_report.md`):** this installed DLL build's `DboSession`
    tolerates at most ONE open `DboLib` handle at a time when the paths differ — a
    second `DboSession_GetLib` of a different path returns
    `ERROR(ORDBDLL-1021): Object Not Found` (even for a valid existing file) until the
    first handle is `DboSession_RemoveLib`'d. The FIRST, up-front "open every
    distinct vendor library at once and keep them all open through the whole
    placement pass" ordering the previous revision of this function generated is
    therefore BROKEN for 2+ distinct libraries (groups 2..N all fail with 1021 —
    this is exactly the user-reported "no way to union 30+ distinct vendor .olbs"
    defect; it was masked in the earlier 2-library live test only because that test's
    specific open/resolve ordering happened to keep just one handle effectively
    live). A separate, independent constraint found while bisectioning: creating a
    `DboSchematic`/`DboPage` (via `NewSchematic`/`NewPage` on the design) BEFORE any
    `GetLib` has ever run in the session ALSO poisons the lib-directory cache, making
    the very first `GetLib` return 1021 even with no other lib open.

    The ordering below is the one pattern confirmed to work on this exact build
    (`runs/getlib_first.tcl`, full 3-distinct-.olb run; `runs/getlib_seq3.tcl`,
    GetLib/RemoveLib cycling; `runs/removedesign_test.tcl`, design+page with a
    PREAMBLE GetLib of the first lib):
      1. `CreateDesign`
      2. For group 0 (the first distinct (library, package) combination, in
         first-encountered components order): `GetLib(lib0)` — this MUST be the
         session's first `GetLib`, before any `NewSchematic`/`NewPage` — resolve the
         target package (by name if requested, else first), create the root
         `DboSchematic` + first `DboPage`, then `NewPlacedInst` every group-0
         component, then `RemoveLib(lib0)`.
      3. for groups 1..N-1: `GetLib(lib_i)` -> resolve package -> `NewPlacedInst`
         every group-i component -> `RemoveLib(lib_i)`. (The page/design already
         exist by now; a `GetLib`/`RemoveLib` round-trip per group is safe once a
         `GetLib` has happened at least once before `NewSchematic`/`NewPage`, which
         step 2 guarantees.)
      4. draw wires, `SaveDesignAs` Replace=1, `RemoveDesign`, tear down.

    Group order is stable (first-encountered), and components are emitted in exactly
    `components` order (each from its own group's resolved part/device/package
    handles), so pass-2's iteration-order refdes assumption (`_build_annotate_script`)
    still holds unchanged.

    For a homogeneous BOM (all one `library`/`package`), a single group is used and
    the generated script is functionally equivalent to the original confirmed-live
    path (that path's `GetLib` also happened to precede any design mutation in the
    one-lib case, which is why the original 1-lib behavior was never actually broken).
    """
    dll_path = tcl_path(str((settings.cadence_spb_home / _DB_DLL_RELATIVE)))
    script = TclScript()
    script.comment(
        "Headless Capture DB authoring -- generated by capture_headless_tools.py. "
        "No Capture.exe process is involved; run via tclsh.exe with CDS_INST_DIR set."
    )
    _add_helper_procs(script)
    script.raw(f"load {dll_path} DboTclWriteBasic")
    script.raw("set lStatus  [DboState]")
    script.raw("set lSession [DboTclHelper_sCreateSession]")

    groups = _group_components_by_pkg(components)

    def _resolve_group_tcl(g: str, lib: str, pkg_req: Optional[str]) -> None:
        """Open $g's .olb, resolve its target package/part/device into
        csPkgNM$g/lPart$g/lDevice$g. Does NOT RemoveLib — the caller does that
        once placement from this group is finished (the lib must stay open for
        the NewPlacedInst calls that reference these resolved handles)."""
        target = tcl_str(pkg_req if pkg_req else "")
        # Tcl built from plain concatenated strings (NOT f-strings) so the literal Tcl
        # braces never collide with Python's f-string brace rules.
        script.raw("set csLib" + g + " [DboTclHelper_sMakeCString " + tcl_path(str(lib)) + "]")
        script.raw("set lLib" + g + " [$lSession GetLib $csLib" + g + " $lStatus]")
        script.raw(
            'if {[$lStatus Failed] || [isnull $lLib' + g + ']} '
            '{ puts "AUTHOR_ERROR: group ' + g + ' library open failed (' + str(lib) + ')"; exit 1 }'
        )
        script.raw("set targetPkgName" + g + " " + (target if pkg_req else '""'))
        script.raw("set lPackage" + g + ' ""')
        script.raw("set resolvedPkg" + g + ' ""')
        script.raw("set nameIt" + g + " [$lLib" + g + " NewPackageNamesIter $lStatus]")
        script.raw("set objIt" + g + " [$lLib" + g + " NewPackagesIter $lStatus]")
        script.raw("while {1} {")
        script.raw('  set csN' + g + ' [DboTclHelper_sMakeCString ""]')
        script.raw("  catch {DboLibPackageNamesIter_NextName $nameIt" + g + " $csN" + g + "}")
        script.raw("  set curN" + g + " [cstrval $csN" + g + "]")
        script.raw("  set curO" + g + " [$objIt" + g + " NextPackage $lStatus]")
        script.raw('  if {$curN' + g + ' eq "" && [isnull $curO' + g + ']} { break }')
        script.raw('  if {$resolvedPkg' + g + ' eq "" && ![isnull $curO' + g + ']} {')
        script.raw("    set lPackage" + g + " $curO" + g)
        script.raw("    set resolvedPkg" + g + " $curN" + g)
        script.raw("  }")
        script.raw('  if {$targetPkgName' + g + ' ne "" && $curN' + g + ' eq $targetPkgName' + g + '} {')
        script.raw("    set lPackage" + g + " $curO" + g)
        script.raw("    set resolvedPkg" + g + " $curN" + g)
        script.raw("    break")
        script.raw("  }")
        script.raw("  if {[isnull $curO" + g + "]} { break }")
        script.raw("}")
        script.raw(
            'if {[isnull $lPackage' + g + ']} '
            '{ puts "AUTHOR_ERROR: no package resolved in group ' + g + ' library (requested: '
            + (pkg_req or "<first>") + ')"; exit 1 }'
        )
        script.raw('puts "AUTHOR_PG' + g + "=lib={" + str(lib) + "} pkg=$resolvedPkg" + g + '"')
        script.raw("set csPkgNM" + g + " [DboTclHelper_sMakeCString $resolvedPkg" + g + "]")
        script.raw("set partIt" + g + " [DboPackage_NewPartsIter $lPackage" + g + " $lStatus]")
        script.raw("set lPart" + g + " [DboPackagePartsIter_NextPart $partIt" + g + " $lStatus]")
        script.raw(
            'if {[isnull $lPart' + g + ']} '
            '{ puts "AUTHOR_ERROR: no part in group ' + g + ' package $resolvedPkg' + g + '"; exit 1 }'
        )
        script.raw("set devIt" + g + " [DboPackage_NewDevicesIter $lPackage" + g + " $lStatus]")
        script.raw("set lDevice" + g + " [DboPackageDevicesIter_NextDevice $devIt" + g + " $lStatus]")
        script.raw(
            'if {[isnull $lDevice' + g + ']} '
            '{ puts "AUTHOR_ERROR: no device in group ' + g + ' package $resolvedPkg' + g + '"; exit 1 }'
        )

    def _close_group_tcl(g: str) -> None:
        script.raw("catch {delete_DboLibPackageNamesIter $nameIt" + g + "}")
        script.raw("catch {delete_DboLibPackagesIter $objIt" + g + "}")
        script.raw("catch {delete_DboPackagePartsIter $partIt" + g + "}")
        script.raw("catch {delete_DboPackageDevicesIter $devIt" + g + "}")
        script.raw("catch {$lSession RemoveLib $lLib" + g + "}")

    def _place_components_from_group_tcl(g: str, comps: list[dict]) -> None:
        for comp in comps:
            ref_raw = str(comp["ref"])
            ref = tcl_str(ref_raw)
            x = comp["x"]
            y = comp["y"]
            rotation = comp.get("rotation", 0)
            script.raw(f"set csRef [DboTclHelper_sMakeCString {ref}]")
            script.raw(f"set xy [docxy $gran {x} {y}]")
            script.raw("set cpt [DboTclHelper_sMakeCPoint [lindex $xy 0] [lindex $xy 1]]")
            # Instantiation from THIS component's own group's resolved
            # csPkgNM/lPart/lDevice handles — a heterogeneous BOM's 30 distinct
            # vendor packages each place their own part, not N copies of one.
            # Pure string concatenation -- the block's literal Tcl braces make
            # f-strings unsafe.
            npif = (
                "if {[catch {set lInst [$lPage NewPlacedInst $lStatus $csRef "
                "$csPkgNM" + g + " $lPart" + g + " $lDevice" + g + " $cpt "
                + str(rotation) + "]} eplace]} {\n"
                '  puts "AUTHOR_WARN: placement of ' + ref + ' failed: $eplace"\n'
                "} elseif {[isnull $lInst]} {\n"
                '  puts "AUTHOR_WARN: placement of ' + ref + ' returned NULL"\n'
                "} else {\n"
            )
            script.raw(npif)
            script.raw(
                # NewPlacedInst's Name arg does NOT land the reference designator
                # (it comes back as the placeholder DN?/auto-named INS1/INS2).
                # DboPartInst_SetReference updates the in-session object (kept
                # here, harmless) but does NOT survive a reopen either way.
                # CONFIRMED LIVE: DboInstOccurrence_GetInstOccurrence returns
                # NULL for a brand-new, not-yet-saved instance in THIS SAME
                # session, so the real, persisting reference-designator
                # assignment happens in a SEPARATE second pass
                # (`_build_annotate_script`) against this file after it's been
                # saved and reopened fresh. See this module's docstring.
                "  catch {DboPartInst_SetReference $lInst $csRef}\n"
                "  incr placed_count\n"
                "}"
            )

    script.raw(f"set csName [DboTclHelper_sMakeCString {tcl_str(design_name)}]")
    script.raw("set lDesign [$lSession CreateDesign $lStatus $csName $csName 0]")
    script.raw(
        'if {[$lStatus Failed] || [isnull $lDesign]} { puts "AUTHOR_ERROR: create design failed"; exit 1 }'
    )

    # Group 0: GetLib MUST happen before NewSchematic/NewPage (see docstring — a
    # design+page created before any GetLib poisons the lib-directory cache and
    # makes the very first GetLib return ORDBDLL-1021). So the session's first
    # GetLib, the package resolve for group 0, and the creation of the
    # DboSchematic/DboPage all happen inside this one branch, in that order.
    g0 = "0"
    grp0 = groups[0]
    comp0 = grp0[0]
    lib0 = comp0.get("library") or library_file
    pkg0 = comp0.get("package") or package_name
    _resolve_group_tcl(g0, lib0, pkg0)
    script.raw("set lSchematic [$lDesign NewSchematic $csName $lStatus]")
    script.raw("set lSchematic [DboDesign_GetRootSchematic $lDesign $lStatus]")
    script.raw(
        'if {[isnull $lSchematic]} { puts "AUTHOR_ERROR: schematic creation failed"; exit 1 }'
    )
    script.raw('set csPage [DboTclHelper_sMakeCString {Sheet1}]')
    script.raw("set lPage [$lSchematic NewPage $lStatus $csPage]")
    script.raw(
        'if {[$lStatus Failed] || [isnull $lPage]} { puts "AUTHOR_ERROR: page creation failed"; exit 1 }'
    )
    script.raw("set gran [$lPage GetPhysicalGranularity]")
    script.raw(
        "proc docxy {gran xx yy} { return [list [expr {int(round($gran * $xx))}] "
        "[expr {int(round($gran * $yy))}]] }"
    )
    script.raw("set placed_count 0")
    _place_components_from_group_tcl(g0, grp0)
    _close_group_tcl(g0)

    # Groups 1..N-1: the page already exists; interleave GetLib->place->RemoveLib
    # per group so no two distinct libraries are ever open simultaneously
    # (getlib_min.tcl vs getlib_seq3.tcl).
    for gi, grp in enumerate(groups[1:], start=1):
        g = str(gi)
        comp = grp[0]
        lib = comp.get("library") or library_file
        pkg = comp.get("package") or package_name
        _resolve_group_tcl(g, lib, pkg)
        _place_components_from_group_tcl(g, grp)
        _close_group_tcl(g)

    script.raw("set wire_count 0")
    for wire in wires:
        # Two wire shapes, both confirmed live:
        #  (a) {"x1","y1","x2","y2"} — raw user-unit endpoints (existing behavior;
        #      both get scaled by docxy/gran, the historical and most common case).
        #  (b) {"pin1":{"part_index","pin"}, "pin2":{"part_index","pin"}} — PIN-RESOLVED
        #      endpoints: each endpoint names a placed part by its 0-based placement
        #      INDEX (not its reference designator — that only resolves at the
        #      occurrence level after a save+reopen; see _get_pin_xy_proc_tcl's
        #      docstring) and a pin number/name. At runtime the generated `get_pin_xy`
        #      helper iterates the page's part instances to that index, matches the pin,
        #      and returns its page-space hot spot ({hx hy}) — already in the SAME
        #      coordinate space NewWireScalar needs, so NO docxy/granularity multiply is
        #      applied. This lets a verified pin-name -> pin-name wiring spec be drawn
        #      as real, electrically-connected schematic wires without the caller
        #      hand-computing each endpoint coordinate.
        has_raw = all(k in wire for k in ("x1", "y1", "x2", "y2"))
        has_pins = all(k in wire for k in ("pin1", "pin2"))
        if has_raw and not has_pins:
            x1, y1, x2, y2 = wire["x1"], wire["y1"], wire["x2"], wire["y2"]
            script.raw(f"set wp1 [docxy $gran {x1} {y1}]")
            script.raw(f"set wp2 [docxy $gran {x2} {y2}]")
        else:
            p1, p2 = wire["pin1"], wire["pin2"]
            pi1, pin1 = str(p1["part_index"]), tcl_str(str(p1["pin"]))
            pi2, pin2 = str(p2["part_index"]), tcl_str(str(p2["pin"]))
            script.raw(f"set xy1 [get_pin_xy $lPage {pi1} {pin1}]")
            script.raw(f"set xy2 [get_pin_xy $lPage {pi2} {pin2}]")
            pinlabel = f"part{pi1}.{pin1} -> part{pi2}.{pin2}"
            script.raw(
                'if {$xy1 eq "" || $xy2 eq ""} {\n'
                f'  puts "AUTHOR_WARN: pin-resolved wire endpoint not found ({pinlabel})"\n'
                "} else {\n"
                "  set wp1 $xy1\n"
                "  set wp2 $xy2\n"
            )
            # wrap the rest of the wire-creation in the else-branch's scope by
            # re-issuing it unconditionally but guarded by the same condition check:
            # the cleanest approach is to put the NewWireScalar inside the else branch:
        if has_raw and not has_pins:
            script.raw("set cwp1 [DboTclHelper_sMakeCPoint [lindex $wp1 0] [lindex $wp1 1]]")
            script.raw("set cwp2 [DboTclHelper_sMakeCPoint [lindex $wp2 0] [lindex $wp2 1]]")
            script.raw(
                "if {[catch {set lWire [$lPage NewWireScalar $lStatus $cwp1 $cwp2]} ewire]} {\n"
                '  puts "AUTHOR_WARN: wire failed: $ewire"\n'
                "} elseif {[isnull $lWire]} {\n"
                '  puts "AUTHOR_WARN: wire returned NULL"\n'
                "} else {\n"
                "  incr wire_count\n"
                "}"
            )
        else:
            # close the outer if/else for the pin-resolved branch, emitting the
            # NewWireScalar inside the else block:
            script.raw(
                "  set cwp1 [DboTclHelper_sMakeCPoint [lindex $wp1 0] [lindex $wp1 1]]\n"
                "  set cwp2 [DboTclHelper_sMakeCPoint [lindex $wp2 0] [lindex $wp2 1]]\n"
                "  if {[catch {set lWire [$lPage NewWireScalar $lStatus $cwp1 $cwp2]} ewire]} {\n"
                '    puts "AUTHOR_WARN: wire failed: $ewire"\n'
                "} elseif {[isnull $lWire]} {\n"
                '    puts "AUTHOR_WARN: wire returned NULL"\n'
                "} else {\n"
                "    incr wire_count\n"
                "  }\n"
                "}"
            )

    # All vendor libraries are already RemoveLib'd by per-group _close_group_tcl
    # calls above — do NOT reintroduce the old dangling-handle
    # `MarkAllLibForSave $lLib` (that variable no longer even exists in this
    # script's scope; it silently no-op'd before, and would have been
    # operating on a long-dead handle even when it did exist). The placed
    # instances' part/package/cell definitions persist in the DESIGN's own
    # embedded cache at SaveDesignAs time (confirmed: reopening a saved .dsn
    # with every source .olb deleted still reads every placed part — see
    # `runs/olb_union_fix_report.md` and the module docstring's design-cache
    # note), so no library-side MarkAllLibForSave call is needed or attempted
    # here for a pure design save.
    script.raw("catch {$lPage MarkModified}")
    script.raw("catch {$lSchematic MarkModified}")
    script.raw(f"set csOut [DboTclHelper_sMakeCString {tcl_path(output_dsn)}]")
    script.raw(
        'if {[catch {$lSession SaveDesignAs $lDesign $csOut 1} esave]} '
        '{ puts "AUTHOR_ERROR: save failed: $esave"; exit 1 }'
    )
    script.raw("set fsize -1")
    script.raw(f"if {{[file exists {tcl_path(output_dsn)}]}} {{ set fsize [file size {tcl_path(output_dsn)}] }}")
    script.raw(
        'puts "AUTHOR_SUMMARY placed=$placed_count wires=$wire_count output_size=$fsize"'
    )
    script.raw("catch {$lSession RemoveDesign $lDesign}")
    script.raw("delete_DboSession $lSession")
    script.raw("delete_DboState $lStatus")
    return script


def _parse_author_summary(log_text: str) -> Optional[dict]:
    for line in log_text.splitlines():
        if line.startswith("AUTHOR_SUMMARY"):
            fields = dict(tok.split("=", 1) for tok in line.split()[1:] if "=" in tok)
            out: dict = {}
            for key in ("placed", "wires", "output_size"):
                if key in fields:
                    try:
                        out[key] = int(fields[key])
                    except ValueError:
                        out[key] = fields[key]
            return out
    return None


def _build_annotate_script(dsn_file: str, refs_in_order: list[str]) -> TclScript:
    """Second-pass reference-designator assignment, run against an ALREADY-SAVED .dsn
    in a fresh `GetDesignAndSchematics` open (a new process, via a separate submit_job
    call — not reusing the authoring session).

    CONFIRMED LIVE necessity: `DboInstOccurrence_GetInstOccurrence` returns NULL for a
    part instance that was JUST created and not yet saved/reloaded in the SAME session
    (the occurrence tree isn't built for brand-new, uncommitted instances) — this is why
    `_build_author_script` can't do this itself. Once the design has been saved and
    reopened fresh, the same call resolves a real occurrence, and
    `DboInstOccurrence_SetReference`/`SetDesignator` (2-arg form — NOT 3 with a status
    object) genuinely persist across a SECOND save + a THIRD, independent fresh reopen —
    confirmed via `DboInstOccurrence_sGetReferenceDesignator` and via `pstswp.exe`'s
    generated `pstxprt.dat` showing the real refdes, not an auto-name.

    `refs_in_order` is matched to parts by ITERATION ORDER (`DboPage_NewPartInstsIter`'s
    own order) against `refs_in_order`'s own list order — NOT by name or position. This
    is a real, documented assumption (iteration order was observed to match placement
    order for a simple, freshly-authored single-page design in live testing) rather than
    a guaranteed contract of the DLL — a caller with position-sensitive requirements
    should independently verify via `extract_capture_netlist_headless` after the fact.
    """
    dll_path = tcl_path(str((settings.cadence_spb_home / _DB_DLL_RELATIVE)))
    script = TclScript()
    script.comment(
        "Headless Capture reference-designator annotation (2nd pass) -- generated by "
        "capture_headless_tools.py. No Capture.exe process is involved."
    )
    _add_helper_procs(script)
    script.raw(f"load {dll_path} DboTclWriteBasic")
    script.raw("set lStatus  [DboState]")
    script.raw("set lSession [DboTclHelper_sCreateSession]")
    script.raw(f"set lPath    [DboTclHelper_sMakeCString {tcl_path(dsn_file)}]")
    script.raw("set lDesign  [$lSession GetDesignAndSchematics $lPath $lStatus]")
    script.raw(
        'if {[$lStatus Failed]} { puts "ANNOTATE_ERROR: open failed: [$lStatus Message]"; exit 1 }'
    )
    script.raw("set rootSch [DboDesign_GetRootSchematic $lDesign $lStatus]")
    script.raw("DboSchematic_ReadAllPages $rootSch")
    script.raw("set rootOcc [DboDesign_GetRootOccurrence $lDesign $lStatus]")
    script.raw(
        'if {[isnull $rootOcc]} { puts "ANNOTATE_ERROR: no root occurrence"; exit 1 }'
    )

    refs_list = " ".join(tcl_str(r) for r in refs_in_order)
    script.raw(f"set refList [list {refs_list}]")
    script.raw("set annotated_count 0")
    script.raw("set idx 0")
    script.raw("set pageIter [DboSchematic_NewPagesIter $rootSch $lStatus]")
    script.raw("while {1} {")
    script.raw("  set page [DboSchematicPagesIter_NextPage $pageIter $lStatus]")
    script.raw("  if {[isnull $page]} { break }")
    script.raw("  set partIter [DboPage_NewPartInstsIter $page $lStatus]")
    script.raw("  while {1} {")
    script.raw("    set part [DboPagePartInstsIter_NextPartInst $partIter $lStatus]")
    script.raw("    if {[isnull $part]} { break }")
    script.raw("    if {$idx >= [llength $refList]} { incr idx; continue }")
    script.raw("    set newRef [lindex $refList $idx]")
    script.raw("    incr idx")
    script.raw("    set prefix [regsub {[0-9].*$} $newRef {}]")
    script.raw('    if {$prefix eq ""} { set prefix $newRef }')
    script.raw("    set occ [DboInstOccurrence_GetInstOccurrence $rootOcc $part $lStatus]")
    script.raw("    if {[isnull $occ]} {")
    script.raw('      puts "ANNOTATE_WARN: occurrence NULL for index $idx ($newRef)"')
    script.raw("      continue")
    script.raw("    }")
    script.raw("    set csRef [DboTclHelper_sMakeCString $newRef]")
    script.raw("    set csDesignator [DboTclHelper_sMakeCString $prefix]")
    script.raw("    if {[catch {DboInstOccurrence_SetReference $occ $csRef} eref]} {")
    script.raw('      puts "ANNOTATE_WARN: SetReference failed for $newRef: $eref"')
    script.raw("    } elseif {[catch {DboInstOccurrence_SetDesignator $occ $csDesignator} edes]} {")
    script.raw('      puts "ANNOTATE_WARN: SetDesignator failed for $newRef: $edes"')
    script.raw("    } else {")
    script.raw("      incr annotated_count")
    script.raw("    }")
    script.raw("  }")
    script.raw("}")

    script.raw(
        'if {[catch {$lSession SaveDesign $lDesign} esave]} '
        '{ puts "ANNOTATE_ERROR: save failed: $esave"; exit 1 }'
    )
    script.raw('puts "ANNOTATE_SUMMARY annotated=$annotated_count requested=[llength $refList]"')
    script.raw("catch {$lSession RemoveDesign $lDesign}")
    script.raw("delete_DboSession $lSession")
    script.raw("delete_DboState $lStatus")
    return script


def _parse_annotate_summary(log_text: str) -> Optional[dict]:
    for line in log_text.splitlines():
        if line.startswith("ANNOTATE_SUMMARY"):
            fields = dict(tok.split("=", 1) for tok in line.split()[1:] if "=" in tok)
            out: dict = {}
            for key in ("annotated", "requested"):
                if key in fields:
                    try:
                        out[key] = int(fields[key])
                    except ValueError:
                        out[key] = fields[key]
            return out
    return None


def _parse_summary(log_text: str) -> Optional[dict]:
    for line in log_text.splitlines():
        if line.startswith("EXTRACT_SUMMARY"):
            fields = dict(tok.split("=", 1) for tok in line.split()[1:] if "=" in tok)
            out: dict = {"design_name": fields.get("design", "")}
            for key in ("parts", "pins", "nets"):
                if key in fields:
                    try:
                        out[key] = int(fields[key])
                    except ValueError:
                        out[key] = fields[key]
            return out
    return None


def _parse_netlist_file(path: Path) -> list[dict]:
    nets: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return nets
    for line in text.splitlines():
        if " ; " not in line:
            continue
        name, members = line.split(" ; ", 1)
        nets.append({"net": name.strip(), "members": members.split()})
    return nets


@mcp.tool
async def extract_capture_netlist_headless(
    dsn_file: str,
    output_file: str = "netlist.txt",
    wait_seconds: float = 120.0,
) -> dict:
    """Extract a netlist (parts/pins/nets) from an EXISTING OrCAD Capture .dsn — NO Capture.exe GUI process at all.

    Loads Capture's own schematic-database DLL (`orDb_Dll_Tcl64.dll`) directly into the
    standalone `tclsh.exe` shell, bypassing every known Capture.exe batch-invocation
    problem entirely (CONFIRMED LIVE — see this module's own docstring for the full
    evidence and the two DboTcl calling-convention traps). This is READ-ONLY: it reads
    a schematic that already exists; it cannot place parts/wires on a new design.

    `dsn_file` must be a real `.dsn` (the Capture schematic database file, NOT the
    `.opj` project wrapper). `output_file` is written as `NetName ; REFDES.PIN
    REFDES.PIN ...` per line (one per net) — resolved to an absolute path first (same
    "relative paths fall into a bad state on this suite's CLI tools" lesson as
    `allegro_import_tools.py`, here a nonexistent output directory rather than an
    interactive-prompt loop, but worth avoiding the same way).

    Waits up to `wait_seconds` for the (normally fast, single-digit-second) job to
    finish and returns the parsed netlist and part/pin/net counts directly, not just a
    job_id — call `wait_for_job`/`tail_job_log` yourself only if you pass a very large
    design and expect it to run longer than that.
    """
    dsn_abs = _resolve(dsn_file)
    output_abs = _resolve(output_file)
    Path(output_abs).parent.mkdir(parents=True, exist_ok=True)

    script = _build_extract_script(dsn_abs, output_abs)
    record = await submit_job(
        tool="tclsh",
        tcl_script=script,
        tcl_arg_flag=None,
        script_filename="extract_netlist.tcl",
        extra_env={"CDS_INST_DIR": str(settings.cadence_spb_home)},
    )
    result = {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "dsn_file": dsn_abs,
        "output_file": output_abs,
    }

    final = await job_manager.wait(record.job_id, timeout=wait_seconds)
    result["state"] = final.state
    if final.state == "running":
        result["note"] = (
            f"Still running after {wait_seconds}s — poll with wait_for_job({record.job_id!r}) "
            "yourself; this design may just be unusually large."
        )
        return result

    log_text = ""
    try:
        log_text = Path(final.job_dir, "run.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    summary = _parse_summary(log_text)
    if summary is None:
        result["error"] = (
            "No EXTRACT_SUMMARY line in run.log — the extraction did not complete "
            "normally. Read the log for the real error (a common one: dsn_file does "
            "not exist, or points at a .opj instead of the .dsn it wraps)."
        )
        result["log_tail"] = log_text[-2000:]
        return result

    result.update(summary)
    result["nets"] = _parse_netlist_file(Path(output_abs))
    return result


@mcp.tool
async def author_capture_schematic_headless(
    output_dsn: str,
    library_file: str,
    components: list[dict],
    wires: Optional[list[dict]] = None,
    design_name: str = "HEADLESSAUTH",
    package_name: Optional[str] = None,
    wait_seconds: float = 120.0,
) -> dict:
    """Create a BRAND-NEW OrCAD Capture schematic headlessly — place parts, draw wires, save a .dsn — NO Capture.exe GUI process at all.

    CONFIRMED LIVE: creates a design/schematic/page from nothing, places real part
    instances resolved from a real `.olb` library, draws real wires, and saves a valid
    `.dsn` — independently re-verified by reopening the result with
    `extract_capture_netlist_headless` (this module's read path) and confirming the
    placed parts/pins/wire are genuinely present. See this module's own docstring for
    the full evidence trail and honest limitations.

    `components`: list of `{"ref": str, "x": number, "y": number, "rotation": int=0,
    "package": str=?, "library": str=?}`.

    **Heterogeneous BOM merge (the 30+-distinct-part capability, FIXED 2026-10-18
    second pass):** each component may carry its own optional `library` (a `.olb` path;
    defaults to the tool's `library_file`) and `package` (a package name; defaults to
    `package_name`, which itself may be `None` = "first package in that library"). This
    tool groups the components by `(library, package)` and resolves+instantiates
    EVERY distinct combination in this ONE design, so a 30+-distinct-part heterogeneous
    BOM — the typical SamacSys/UltraLibrarian "one vendor `.olb` per part" export shape
    — merges into a single `.dsn` with each part genuinely its own part, NOT N copies of
    one.

    Why this needed a second fix pass: the first (same-day) multi-library version
    opened EVERY distinct vendor `.olb` up front and kept all of them open through the
    whole placement pass. Live probing against the installed DLL build (Sigrity 2024.0 /
    SPB 22.1 `orDb_Dll_Tcl64.dll`, see `runs/olb_union_fix_report.md` for the full
    evidence trail) confirmed that session tolerates AT MOST ONE open `DboLib` handle at
    a time when the paths differ — a second `GetLib` of a different path returns
    `ERROR(ORDBDLL-1021): Object Not Found` (even for a valid existing file) until the
    first handle is `RemoveLib`'d. With 30+ distinct one-part-per-file vendor `.olb`s
    (the actual target case) every group after the first failed with 1021 — the exact
    "no way to union 30+ distinct vendor .olbs" defect. The generated script now
    interleaves per group: `GetLib(lib_i)` -> resolve that group's package/part/device
    -> place that group's components -> `RemoveLib(lib_i)`, so no two distinct
    libraries are ever open simultaneously (the one confirmed-working pattern). The
    first group's `GetLib` also necessarily precedes `NewSchematic`/`NewPage`, because a
    design page created before ANY `GetLib` has run also poisons the lib-directory cache
    (a second, independent, confirmed constraint) and makes the very first `GetLib`
    return 1021 too.

    For a homogeneous BOM (all the same package/library), the same call works as before
    by omitting `library`/`package` per component — a single group is used and the
    generated script is functionally equivalent to the original confirmed-live path.

    `wires`: list of wire dicts, each in one of TWO mutually-exclusive shapes:
      - `{"x1", "y1", "x2", "y2"}` (page user-units, same coordinate space as
        `components`' `x`/`y` — both endpoints multiplied by the page's own
        `GetPhysicalGranularity` at runtime). The historical/raw form.
      - `{"pin1": {"part_index", "pin"}, "pin2": {"part_index", "pin"}}` — PIN-RESOLVED
        form: each endpoint names a placed part by its 0-based placement index into
        `components` (NOT its reference designator — that only resolves at the
        occurrence level after a save+reopen; `_get_pin_xy_proc_tcl`'s docstring covers
        this) + a pin number or pin name. At runtime the generated `get_pin_xy` helper
        resolves it to that pin's real page-space hot-spot coordinate via
        `DboPortInst_sGetHotSpotX/Y` (the pin's exact wire-attachment point — see
        `_get_pin_xy_proc_tcl`'s docstring for the confirmed-live coordinate-space
        evidence and the net-name proof). No granularity multiply is applied to resolved
        coordinates (they are already page-space), and the wire is electrically
        connected to BOTH pins on save (verified by reopening and confirming both pins
        share a net name). Defaults to no wires if omitted.

    Reference designators: REAL and PERSISTENT (confirmed 2026-10-18). `NewPlacedInst`'s
    Name arg alone does not land the refdes, so this tool additionally resolves each
    placed instance's design OCCURRENCE (`DboDesign_GetRootOccurrence` ->
    `DboInstOccurrence_GetInstOccurrence`) and calls `DboInstOccurrence_SetReference` +
    `DboInstOccurrence_SetDesignator` on it (the designator is the leading alphabetic
    run of `ref`, e.g. `"R"` from `"R1"`). CONFIRMED LIVE to survive a save + fresh
    reopen in a brand-new process (verified via
    `DboInstOccurrence_sGetReferenceDesignator`), AND to appear as the real `PART_NAME`
    in `pstswp.exe`'s generated netlist (see `generate_capture_pcb_netlist`) rather than
    an auto-generated `INS1`/`INS2`. Pass unique `ref` values. Net connectivity
    (`NewFlatNetsIter`) still does not populate via this read API (same
    GUI-connectivity-engine limitation as the read path) — this does not block
    netlisting, since `pstswp.exe` derives connectivity from the saved page geometry
    independently; verify success via `placed`/`wires` counts, by reopening the file,
    and ultimately via `generate_capture_pcb_netlist`'s own output for real connectivity.
    """
    output_abs = _resolve(output_dsn)
    library_abs = _resolve(library_file)
    Path(output_abs).parent.mkdir(parents=True, exist_ok=True)

    if not components:
        raise ValueError("components must have at least one entry")
    for comp in components:
        if "ref" not in comp or "x" not in comp or "y" not in comp:
            raise ValueError(f"each component needs 'ref', 'x', 'y': got {comp!r}")
    for wire in wires or []:
        has_raw = all(k in wire for k in ("x1", "y1", "x2", "y2"))
        has_pins = all(
            k in wire
            and isinstance(wire[k], dict)
            and "part_index" in wire[k]
            and "pin" in wire[k]
            for k in ("pin1", "pin2")
        )
        # Exactly ONE of the two shapes must be present. A wire with BOTH (or NEITHER)
        # is ambiguous/invalid: has_raw XOR has_pins.
        if has_raw == has_pins:
            raise ValueError(
                "each wire needs EITHER {'x1','y1','x2','y2'} OR "
                "{'pin1':{'part_index','pin'},'pin2':{'part_index','pin'}} "
                "(not both, not neither): got "
                f"{wire!r}"
            )

    script = _build_author_script(
        design_name=design_name,
        library_file=library_abs,
        components=components,
        wires=wires or [],
        output_dsn=output_abs,
        package_name=package_name,
    )
    record = await submit_job(
        tool="tclsh",
        tcl_script=script,
        tcl_arg_flag=None,
        script_filename="author_schematic.tcl",
        extra_env={"CDS_INST_DIR": str(settings.cadence_spb_home)},
    )
    result = {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "output_dsn": output_abs,
        "library_file": library_abs,
        "requested_components": len(components),
        "requested_wires": len(wires or []),
    }

    final = await job_manager.wait(record.job_id, timeout=wait_seconds)
    result["state"] = final.state
    if final.state == "running":
        result["note"] = (
            f"Still running after {wait_seconds}s — poll with wait_for_job({record.job_id!r})."
        )
        return result

    log_text = ""
    try:
        log_text = Path(final.job_dir, "run.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    summary = _parse_author_summary(log_text)
    if summary is None:
        result["error"] = (
            "No AUTHOR_SUMMARY line in run.log — authoring did not complete normally. "
            "Read log_tail for the real error (an AUTHOR_ERROR/AUTHOR_WARN line is "
            "almost always present)."
        )
        result["log_tail"] = log_text[-4000:]
        return result

    result.update(summary)
    result["dsn_written"] = Path(output_abs).is_file() and Path(output_abs).stat().st_size > 0
    if summary.get("placed", 0) < len(components):
        result["note"] = (
            f"Only {summary.get('placed', 0)}/{len(components)} requested components "
            "were actually placed — read log_tail for the AUTHOR_WARN line(s) explaining "
            "which failed and why."
        )
        result["log_tail"] = log_text[-4000:]
        return result

    # Second pass: real, persistent reference-designator assignment (CONFIRMED LIVE to
    # require a fresh reopen of the just-saved file -- see _build_annotate_script's
    # docstring). Only attempted if the first pass placed at least one component.
    if result.get("placed", 0) > 0:
        refs_in_order = [str(c["ref"]) for c in components]
        annotate_script = _build_annotate_script(output_abs, refs_in_order)
        annotate_record = await submit_job(
            tool="tclsh",
            tcl_script=annotate_script,
            tcl_arg_flag=None,
            script_filename="annotate_schematic.tcl",
            extra_env={"CDS_INST_DIR": str(settings.cadence_spb_home)},
        )
        annotate_final = await job_manager.wait(annotate_record.job_id, timeout=wait_seconds)
        result["annotate_job_id"] = annotate_record.job_id
        result["annotate_state"] = annotate_final.state
        annotate_log = ""
        try:
            annotate_log = Path(annotate_final.job_dir, "run.log").read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            pass
        annotate_summary = _parse_annotate_summary(annotate_log)
        if annotate_summary is None:
            result["annotate_error"] = (
                "No ANNOTATE_SUMMARY line — reference-designator assignment did not "
                "complete normally; the .dsn was still saved by the first pass (parts/"
                "wires are real) but refdes remain auto-named (INS1/INS2/...). Read "
                "annotate_log_tail for the real error."
            )
            result["annotate_log_tail"] = annotate_log[-4000:]
        else:
            result.update({f"annotate_{k}": v for k, v in annotate_summary.items()})
            if annotate_summary.get("annotated", 0) < len(refs_in_order):
                result["annotate_log_tail"] = annotate_log[-4000:]
    return result


@mcp.tool
async def generate_capture_pcb_netlist(
    dsn_file: str,
    output_dir: str,
    config_file: Optional[str] = None,
    max_versions: int = 3,
    max_name_length: int = 255,
    wait_seconds: float = 60.0,
) -> dict:
    """Generate a PCB netlist (pstchip/pstxprt/pstxnet.dat) directly from a .dsn — NO Capture.exe GUI process at all. Closes the pipeline for a schematic authored via `author_capture_schematic_headless`.

    CONFIRMED LIVE: this is the real headless replacement for Capture's GUI-only
    "Tools::Create Netlist" menu command (`capBatchNetlist`), which previously had no
    confirmed headless equivalent — see this module's and `core.tool_status.
    TOOL_STATUS_NOTES["capture"]`'s evidence trail. Runs `pstswp.exe -pst` (a real,
    standalone Allegro/OrCAD tool, distinct from `Capture.exe`, with no GUI of its own)
    directly against `dsn_file` on disk. Verified end-to-end against a schematic that
    was ITSELF authored headlessly (never touched by Capture.exe at any point): the
    generated `pstxprt.dat`'s `PART_NAME` lines showed the real reference designators
    set via `author_capture_schematic_headless`'s `DboInstOccurrence_SetReference` (not
    an auto-generated `INS1`/`INS2`), and real pin names (`A`/`B`/`WIPER` for a `POT`
    part) appeared correctly in `pstxnet.dat`'s connectivity blocks.

    `dsn_file` is the `.dsn` to netlist (the output of `author_capture_schematic_
    headless`, or any existing Capture schematic). `output_dir` is where
    `pstchip.dat`/`pstxprt.dat`/`pstxnet.dat`/`netlist.log` are written — created if it
    doesn't exist. `config_file` defaults to the install's own
    `tools/capture/allegro.cfg` (confirmed present and sufficient for this use); only
    override it if you have a project-specific config. `max_versions`/`max_name_length`
    map to `pstswp.exe`'s own `-v`/`-l` flags (version-retention count, max name length)
    — the defaults (3, 255) match the community-documented invocation and worked
    unmodified in live testing.

    Feed the resulting `.pst` files straight into `run_netrev_import` (`netlist_import_
    tools.py`, `pst_dir=output_dir`) to get a real Allegro `.brd` — the same `netrev -n`
    path already confirmed live for existing-.pst designs, now provably reachable from
    a schematic that was authored from nothing, entirely headlessly.
    """
    dsn_abs = _resolve(dsn_file)
    out_abs = _resolve(output_dir)
    Path(out_abs).mkdir(parents=True, exist_ok=True)
    cfg_abs = _resolve(config_file) if config_file else str(
        settings.cadence_spb_home / "tools" / "capture" / "allegro.cfg"
    )

    args = [
        "-pst",
        "-d", dsn_abs,
        "-n", out_abs,
        "-c", cfg_abs,
        "-v", str(max_versions),
        "-l", str(max_name_length),
    ]
    record = await submit_job(tool="pstswp", build_args=args)
    result = {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "dsn_file": dsn_abs,
        "output_dir": out_abs,
    }

    final = await job_manager.wait(record.job_id, timeout=wait_seconds)
    result["state"] = final.state
    if final.state == "running":
        result["note"] = f"Still running after {wait_seconds}s — poll with wait_for_job({record.job_id!r})."
        return result

    pst_files = {
        name: str(Path(out_abs, name))
        for name in ("pstchip.dat", "pstxprt.dat", "pstxnet.dat")
        if Path(out_abs, name).is_file() and Path(out_abs, name).stat().st_size > 0
    }
    result["pst_files"] = pst_files
    result["complete"] = len(pst_files) == 3
    netlist_log = Path(out_abs, "netlist.log")
    if netlist_log.is_file():
        result["netlist_log_tail"] = netlist_log.read_text(encoding="utf-8", errors="replace")[-2000:]
    if not result["complete"]:
        result["error"] = (
            "Not all three .pst files were written (pstchip.dat/pstxprt.dat/"
            "pstxnet.dat) — read netlist_log_tail for the real error. A common cause: "
            "dsn_file has no placed parts, or config_file doesn't match this install."
        )
    return result
