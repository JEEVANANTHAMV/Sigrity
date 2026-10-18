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

Reference designators: `NewPlacedInst`'s Name arg does NOT land the refdes (instances
come back with the placeholder `DN?`); a follow-up `DboPartInst_SetReference <inst>
<CString>` calls successfully updates the in-session object's reference (confirmed live:
`sGetReference` reports the new value in the same Tcl process), but the persisted
"reference designator" that a fresh `GetDesignAndSchematics` reopen reports is a separate
design-level ANNOTATE step (`capBatchAnnotate` — a GUI Command-Window operation) that has
no confirmed headless equivalent in this DLL build (probed 2026-05: `DboRefDesMgr`/
`DboRefDesManager`/`DboRefDesAnnotation` family and `DboSchematic_Annotate` overloads all
reject every arg-count tried from Tcl). This tool therefore emits `SetReference`
after each placement for the best in-session display, but a fresh reopen of the saved
`.dsn` will still report sequential `INS1/INS2/...` (the auto-name) until the design is
annotated in the GUI. The `ref` field is still accepted and forwarded (both as
`NewPlacedInst`'s Name slot and to `SetReference`), so the value is recorded on the
object; it just does not survive an annotation-free round-trip. Net connectivity
(`NewFlatNetsIter`) still does not populate for the same GUI-connectivity-engine reason
documented above for the read path — wire-to-pin connectivity is implicit in page
geometry (confirmed: the drawn wire IS present and counted on reopen) rather than
computed into a named net.
"""

from __future__ import annotations

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
    """The three small Tcl helpers both the read and write scripts below share:
    `isnull` (every `Next*`/failed-lookup call returns the literal string "NULL", not
    Tcl's empty string, when exhausted — confirmed live to segfault tclsh.exe outright
    if dereferenced without this guard), `cstrval` (reads a CString HANDLE's actual
    text), and `dbstr` (calls a `*_sGet*`-style getter and reads its CString result in
    one `catch`-guarded step, for a getter that might not exist on every object)."""
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


def _build_author_script(
    design_name: str,
    library_file: str,
    components: list[dict],
    wires: list[dict],
    output_dsn: str,
    package_name: Optional[str],
) -> TclScript:
    """The confirmed-working headless authoring sequence (create design -> schematic ->
    page -> resolve one package/part/device from `library_file` -> place N instances of
    it -> draw N wires -> SaveDesignAs), generalized from the exact call forms an earlier
    investigation confirmed live (see `AUTHORING_REPORT.md` under
    `scripts/tools/capture_author/` for the full trial-and-error trail this was built
    from — PDF-documented signatures for `NewSchematic`/`NewPlacedInst`/
    `MarkAllLibForSave`/etc. do NOT all match this DLL build; only the forms used here
    were confirmed to actually bind).

    All components in one call share a single resolved package/part/device (confirmed
    live for N=2 identical placements) — this is a real, deliberate scope limit, not an
    oversight: call this once per distinct package/library combination for a
    heterogeneous BOM. `package_name`, if given, is matched by walking
    `NewPackageNamesIter`/`NewPackagesIter` in lockstep and taking the position where the
    name matches — this specific by-name selection was NOT part of the original
    live-confirmed trail (which only ever took the library's first package) and should be
    treated as best-effort until independently verified; omit it to get the exact
    proven "first package in the library" behavior.

    `components`/`wires` coordinates are in page "user units", multiplied at runtime by
    the page's own `GetPhysicalGranularity` (confirmed live to be 100.0 on a fresh page,
    but read live rather than assumed, since a different page/template could differ) to
    get real document coordinates — same convention the original trial script used.
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

    script.raw(f"set csName [DboTclHelper_sMakeCString {tcl_str(design_name)}]")
    script.raw("set lDesign [$lSession CreateDesign $lStatus $csName $csName 0]")
    script.raw(
        'if {[$lStatus Failed] || [isnull $lDesign]} { puts "AUTHOR_ERROR: create design failed"; exit 1 }'
    )
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

    script.raw(f"set csLib [DboTclHelper_sMakeCString {tcl_path(library_file)}]")
    script.raw("set lLib [$lSession GetLib $csLib $lStatus]")
    script.raw(
        'if {[$lStatus Failed] || [isnull $lLib]} { puts "AUTHOR_ERROR: library open failed"; exit 1 }'
    )

    # Resolve the target package: walk names + objects in lockstep, matching by name if
    # given (best-effort -- see docstring), else take the first package found (the
    # exact, fully-proven behavior).
    target_pkg = tcl_str(package_name) if package_name else '""'
    script.raw(f"set targetPkgName {target_pkg}")
    script.raw('set lPackage ""')
    script.raw('set resolvedPkgName ""')
    script.raw("set nameIt [$lLib NewPackageNamesIter $lStatus]")
    script.raw("set objIt  [$lLib NewPackagesIter $lStatus]")
    script.raw("while {1} {")
    script.raw('  set csN [DboTclHelper_sMakeCString ""]')
    script.raw("  catch {DboLibPackageNamesIter_NextName $nameIt $csN}")
    script.raw("  set curName [cstrval $csN]")
    script.raw("  set curObj [DboLibPackagesIter_NextPackage $objIt $lStatus]")
    script.raw('  if {$curName eq "" && [isnull $curObj]} { break }')
    script.raw('  if {$resolvedPkgName eq "" && ![isnull $curObj]} {')
    script.raw("    set lPackage $curObj")
    script.raw("    set resolvedPkgName $curName")
    script.raw("  }")
    script.raw('  if {$targetPkgName ne "" && $curName eq $targetPkgName} {')
    script.raw("    set lPackage $curObj")
    script.raw("    set resolvedPkgName $curName")
    script.raw("    break")
    script.raw("  }")
    script.raw("  if {[isnull $curObj]} { break }")
    script.raw("}")
    script.raw(
        'if {[isnull $lPackage]} { puts "AUTHOR_ERROR: no package resolved in library"; exit 1 }'
    )
    script.raw('puts "AUTHOR_PACKAGE=$resolvedPkgName"')
    script.raw("set csPkgNM [DboTclHelper_sMakeCString $resolvedPkgName]")

    script.raw("set partIt [DboPackage_NewPartsIter $lPackage $lStatus]")
    script.raw("set lPart [DboPackagePartsIter_NextPart $partIt $lStatus]")
    script.raw('if {[isnull $lPart]} { puts "AUTHOR_ERROR: no part in package"; exit 1 }')
    script.raw("set devIt [DboPackage_NewDevicesIter $lPackage $lStatus]")
    script.raw("set lDevice [DboPackageDevicesIter_NextDevice $devIt $lStatus]")
    script.raw(
        'if {[isnull $lDevice]} { puts "AUTHOR_ERROR: no device in package"; exit 1 }'
    )

    script.raw("set placed_count 0")
    for comp in components:
        ref = tcl_str(str(comp["ref"]))
        x = comp["x"]
        y = comp["y"]
        rotation = comp.get("rotation", 0)
        script.raw(f"set csRef [DboTclHelper_sMakeCString {ref}]")
        script.raw(f"set xy [docxy $gran {x} {y}]")
        script.raw("set cpt [DboTclHelper_sMakeCPoint [lindex $xy 0] [lindex $xy 1]]")
        # Plain concatenation (not an f-string) -- this block is full of literal Tcl
        # braces, which an f-string would require doubling ({{/}}) for every single one.
        script.raw(
            "if {[catch {set lInst [$lPage NewPlacedInst $lStatus $csRef $csPkgNM "
            "$lPart $lDevice $cpt " + str(rotation) + "]} eplace]} {\n"
            '  puts "AUTHOR_WARN: placement of ' + ref + ' failed: $eplace"\n'
            "} elseif {[isnull $lInst]} {\n"
            '  puts "AUTHOR_WARN: placement of ' + ref + ' returned NULL"\n'
            "} else {\n"
            # NewPlacedInst's Name arg does NOT land the reference designator (it comes
            # back as the placeholder DN?): the 7-arg overload binds Name to an internal
            # name, not the user-visible refdes. DboPartInst_SetReference DOES update
            # the in-session object but the persisted field on SaveDesignAs is the
            # design-level ANNOTATE step (capBatchAnnotate) -- a GUI Command-Window
            # operation with no confirmed headless equivalent. So `ref` is accepted
            # and best-effort (it is forwarded to NewPlacedInst's Name slot and to
            # SetReference after placement), but a fresh reopen will still report
            # sequential INS1/INS2/... until the design is annotated in the GUI.
            "  catch {DboPartInst_SetReference $lInst $csRef}\n"
            "  incr placed_count\n"
            "}"
        )

    script.raw("set wire_count 0")
    for wire in wires:
        x1, y1, x2, y2 = wire["x1"], wire["y1"], wire["x2"], wire["y2"]
        script.raw(f"set wp1 [docxy $gran {x1} {y1}]")
        script.raw(f"set wp2 [docxy $gran {x2} {y2}]")
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

    script.raw("catch {$lPage MarkModified}")
    script.raw("catch {$lSchematic MarkModified}")
    script.raw("catch {$lSession MarkAllLibForSave $lLib}")
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

    `components`: list of `{"ref": str, "x": number, "y": number, "rotation": int=0}`.
    All components in this one call are placed as instances of the SAME package/part/
    device, resolved once from `library_file` (first package found, or the one matching
    `package_name` if given — see `_build_author_script`'s docstring for why by-name
    selection is best-effort). For a heterogeneous BOM, call this once per distinct
    package/library and union the results (not done automatically — a real scope limit,
    not an oversight).

    `wires`: list of `{"x1", "y1", "x2", "y2"}` (page user-units, same coordinate space
    as `components`' `x`/`y` — both get multiplied by the page's own
    `GetPhysicalGranularity` at runtime). Defaults to no wires if omitted.

    Reference designators: `NewPlacedInst`'s Name arg does NOT land the refdes (you'd
    otherwise get `DN?`); this tool follows each successful placement with a
    `DboPartInst_SetReference` call that updates the in-session object (sGetReference
    reports the requested value in the same Tcl process). HOWEVER the persisted
    reference designator that a fresh reopen via `GetDesignAndSchematics` reports is a
    separate design-level ANNOTATE step (`capBatchAnnotate`, GUI Command-Window) that
    has no confirmed headless equivalent in this DLL build — so a fresh reopen of the
    saved `.dsn` still shows sequential `INS1/INS2/...` until the design is annotated
    in the GUI. Pass unique `ref` values (the value is recorded in-session; it just
    does not survive an un-annotated round-trip). Net connectivity also does not
    populate (same GUI-connectivity-engine limitation as the read path) — verify
    success via `placed`/`wires` counts and by reopening the file, not by net content
    or refdes.
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
        if not all(k in wire for k in ("x1", "y1", "x2", "y2")):
            raise ValueError(f"each wire needs 'x1','y1','x2','y2': got {wire!r}")

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
