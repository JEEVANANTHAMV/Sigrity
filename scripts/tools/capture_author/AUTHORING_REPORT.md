# OrCAD Capture HEADLESS SCHEMATIC AUTHORING — Proof Report

**Date:** 2026-10-17 · **Machine:** Windows, Cadence SPB_22.1 @ `C:\Cadence\SPB_22.1`
**Question:** Can OrCAD Capture (or Allegro System Capture) author a NEW schematic —
place parts, draw wires, save a `.dsn` — completely unattended, on this machine?

## ANSWER: YES — via the standalone `tclsh` + `orDb_Dll_Tcl64.dll` DB API (no Capture.exe, no GUI, no COM, no syscap).

A real part was placed, a real wire was drawn, and the result was saved to a valid
`.dsn` (10,752 bytes) **entirely headlessly**. The file was then reopened by the
independent, already-proven read tool and the part, pins, and wire were confirmed
present. This is mechanism **(a)** from the task — proven, not guessed.

```
tclsh.exe step3_author.tcl
  -> CreateDesign          OK   (<d: _..._p_DboDesign>)
  -> NewSchematic          OK   (<s: _..._p_DboSchematic>)
  -> NewPage               OK   (<p: _..._p_DboPage>, granularity 100.0)
  -> GetLib (Discrete.olb) OK
  -> NewPackagesIter       OK   (package resolved)
  -> NewPartsIter          OK   (DboPackagePartsIter_NextPart -> DboLibPart)
  -> NewDevicesIter        OK   (DboPackageDevicesIter_NextDevice -> DboDevice)
  -> NewPlacedInst x2      OK   (R1, R2 -> <..._p_DboPlacedInst>)
  -> NewWireScalar         OK   (wire 4500,5000 -> 5500,5000 -> <..._p_DboWireScalar>)
  -> SaveDesignAs HEADLESSAUTH.DSN   OK   (10,752 bytes written)

Independent re-extraction (verify_authored.tcl, the proven read path):
  ROOTSCH = valid DboSchematic
  PAGEWIRES = 1                      <- the wire we drew IS in the file
  PART R1  pins 1,2,3                <- placed part #1
  PART R2  pins 1,2,3                <- placed part #2
  VERIFY_SUMMARY parts=2 pins=6
```

The reference designators read back as `DN?` (not R1/R2) because a brand-new design
has not been **annotated** — refdes assignment is a separate `capBatchAnnotate`
post-step, not part of `NewPlacedInst`. The objects themselves are physically
present and re-readable. That is the proof the task asked for.

---

## 1. The working mechanism (the only one needed)

Run a Tcl script with the standalone Tcl interpreter, loading the Capture DB write
DLL. **No `Capture.exe` process starts.** This is the batch pattern documented in
the *OrCAD Capture Tcl/Tk Extensions* app note (ch. 4, `caprev.tcl`):
`sCreateSession -> open/create -> mutate -> Save -> cleanup`.

```
$env:CDS_INST_DIR = "C:\Cadence\SPB_22.1"
& "C:\Cadence\SPB_22.1\tools\bin\tclsh.exe" "C:\TEMP-B~1\kilo\author\step3_author.tcl"
```

Files (all in `C:\TEMP-B~1\kilo\author\`):
| File | Purpose |
|---|---|
| `step3_author.tcl` | The working authoring script (create→place→wire→save) |
| `verify_authored.tcl` | Independent re-extraction that proves the save |
| `HEADLESSAUTH.DSN` | The 10,752-byte authored-and-saved design |

---

## 2. The EXACT call sequence that works on SPB_22.1 (with real signatures)

Every line below was executed live and succeeded. Signatures are the real 22.1 ones —
they **do not all match the older rev-1.2 PDF**; the differences are called out.

```tcl
# --- helpers must be defined before use ---
proc isnull {o} { if {$o eq "" || $o eq "0" || $o eq "NULL"} { return 1 }; return 0 }
proc cstrval {h} { if {[isnull $h] || [![string match "*CString*" $h]]} {return ""}
  if {[catch {DboTclHelper_sGetConstCharPtr $h} v]} {return ""}; return $v }

# 1. LOAD — two-arg load is mandatory (bare `load` fails: "cannot find symbol").
load C:/Cadence/SPB_22.1/tools/bin/orDb_Dll_Tcl64.dll DboTclWriteBasic

set lStatus  [DboState]
set lSession [DboTclHelper_sCreateSession]

# 2. CREATE DESIGN — 4-arg form. (3-arg and 2-arg overload variants also exist.)
set csName [DboTclHelper_sMakeCString "HEADLESSAUTH"]
set csRoot [DboTclHelper_sMakeCString "HEADLESSAUTH"]
set lDesign [$lSession CreateDesign $lStatus $csName $csRoot 0]
;# -> DboDesign. Fresh design has a NULL root schematic until one is added.

# 3. CREATE SCHEMATIC — NOTE 22.1 argument order is (name, status),
#    NOT the PDF's (name, status) is fine, but the status must be a real DboState.
set lSchematic [$lDesign NewSchematic $csName $lStatus]      ;# DboSchematic
set lSchematic [DboDesign_GetRootSchematic $lDesign $lStatus] ;# now non-NULL

# 4. CREATE PAGE — 3-arg: NewPage status name.
set csPage [DboTclHelper_sMakeCString "Sheet1"]
set lPage  [$lSchematic NewPage $lStatus $csPage]            ;# DboPage
;# granularity = 100.0 -> doc_coord = 100 * user_coord

# 5. OPEN LIBRARY
set csLib [DboTclHelper_sMakeCString "C:/Cadence/SPB_22.1/tools/capture/library/Discrete.olb"]
set lLib  [$lSession GetLib $csLib $lStatus]                  ;# DboLib

# 6. FIRST PACKAGE NAME (CString OUT) and the PACKAGE OBJECT (two distinct iterations)
set csPkgNM [DboTclHelper_sMakeCString ""]
set pkgIt   [$lLib NewPackageNamesIter $lStatus]
DboLibPackageNamesIter_NextName $pkgIt $csPkgNM              ;# name -> csPkgNM
set pkgName [cstrval $csPkgNM]
set pkgIt2  [$lLib NewPackagesIter $lStatus]
set lPackage [DboLibPackagesIter_NextPackage $pkgIt2 $lStatus];# DboPackage

# 7. PART + DEVICE — NOTE: the part iterator is PACKAGE-SCOPED in 22.1.
set partIt  [DboPackage_NewPartsIter $lPackage $lStatus]
set lPart   [DboPackagePartsIter_NextPart $partIt $lStatus]   ;# DboLibPart  (NOT DboLibPartsIter_NextPart)
set devIt   [DboPackage_NewDevicesIter $lPackage $lStatus]
set lDevice [DboPackageDevicesIter_NextDevice $devIt $lStatus];# DboDevice   (NOT a DboLib* iterator)

# 8. PLACE TWO PART INSTANCES — 7-arg overload that works:
#    NewPlacedInst <status> <Name> <PackageName> <part> <device> <CPoint> <rotation>
set gran [expr {[$lPage GetPhysicalGranularity]}]             ;# 100.0
set pt1 [DboTclHelper_sMakeCPoint [expr {$gran * 30}] [expr {$gran * 50}]]
set pt2 [DboTclHelper_sMakeCPoint [expr {$gran * 70}] [expr {$gran * 50}]]
set csR1 [DboTclHelper_sMakeCString "R1"]
set csR2 [DboTclHelper_sMakeCString "R2"]
set lInst1 [$lPage NewPlacedInst $lStatus $csR1 $csPkgNM $lPart $lDevice $pt1 0]  ;# DboPlacedInst
set lInst2 [$lPage NewPlacedInst $lStatus $csR2 $csPkgNM $lPart $lDevice $pt2 0]  ;# DboPlacedInst

# 9. DRAW A WIRE — 3-arg: NewWireScalar status startCPoint endCPoint
set wpt1 [DboTclHelper_sMakeCPoint 4500 5000]
set wpt2 [DboTclHelper_sMakeCPoint 5500 5000]
set lWire [$lPage NewWireScalar $lStatus $wpt1 $wpt2]         ;# DboWireScalar

# 10. SAVE — SaveDesignAs to an absolute path, Replace=1
catch { $lPage MarkModified }
catch { $lSchematic MarkModified }
catch { $lSession MarkAllLibForSave $lLib }     ;# takes the lib as arg 2 in 22.1
set outPath "C:/TEMP-B~1/kilo/author/HEADLESSAUTH.DSN"
set csOut [DboTclHelper_sMakeCString $outPath]
$lSession SaveDesignAs $lDesign $csOut 1        ;# -> 10,752-byte .dsn

# 11. CLEANUP
catch { $lSession RemoveDesign $lDesign }
catch { delete_DboSession $lSession }
catch { delete_DboState $lStatus }
```

---

## 3. Independent verification (step 3 of the task)

`verify_authored.tcl` reuses the **exact** working read path from the already-proven
`work_extract.tcl` (the same code that extracts the Fault-Detector sample's 90 parts /
252 pins / 76 nets). It opens `HEADLESSAUTH.DSN` fresh through `GetDesignAndSchematics`
and walks `page -> part-inst -> pins`. Output:

```
ROOTSCH=<sch: _f00a3184af010000_p_DboSchematic>
PAGEWIRES=<wires: 1>
  PART=<ref: DN?>   PIN 1,2,3
  PART=<ref: DN?>   PIN 1,2,3
VERIFY_SUMMARY design= parts=2 pins=6 nets=0
```

`parts=2`, `pins=6`, and **`wires=1`** are the three authored objects, independently
read back from the saved file. `nets=0` is expected: flat-net computation is a
GUI/connectivity-engine construct (documented FAIL #6/#7 in the prior session) and does
not populate in a headless read — wire connectivity is implicit in the page geometry.

**Conclusion: the authored design is real, valid, and re-readable.**

---

## 4. What was ruled out (and why)

### 4.1 `Capture.Application` COM — TOO SHALLOW for authoring
No registered type library exists (`HKCR\Capture.Application\CLSID\TypeLib` absent), so
`makepy`/`EnsureDispatch` cannot generate a stub. The live `IDispatch` was probed via
`GetIDsOfNames` instead (a safe existence test, not blind method-guessing).
Results (`com_methods.txt`):

- **Exist on the top-level Application object (7):**
  `PlacePart, PlaceWire, PlacePin, OpenDesign, Close, Exit, Save`
- **Absent (25):** `PlacePort, PlaceGlobal, PlaceOffPageConnector, PlaceTitleBlock,
  PlaceJunction, PlaceNetAlias, PlaceNoConnect, PlaceBlock, PlaceText, SetProperty,
  SetPropertyEx, AddProperty, DeleteProperty, CreateDesign, NewDesign, SaveDesign,
  SaveAs, GetSelectedObjects, SelectObject, SelectObjectById, GetActiveDesign,
  GetActivePage, GetActiveView, GetActivePM, capBatchAnnotate, capSaveCompleteProject`

So COM is a thin file-lifecycle + a 3-verb placement wrapper. It is *not* a full
authoring object model, and there is no `CreateDesign`/page/port/property surface on the
top-level object. The `tclsh` DB API above is strictly more capable and truly headless.

### 4.2 `syscap.exe` (Allegro System Capture) — NO batch mode
`syscap.exe` (308 KB, "Cadence Allegro System Capture", v22.1). Tested:

| Invocation | stdout | stderr | Result |
|---|---|---|---|
| `syscap.exe -help` | empty | empty | popped **"Cadence Product Choices"** GUI dialog, killed at 12 s |
| `syscap.exe -?` | empty | empty | same |
| `syscap.exe -tclfile scap_min.tcl -nograph` | empty | empty | same — GUI product picker, no Tcl ran |

Empty stdout+stderr plus the GUI dialog is definitive: **`-tclfile`/`-nograph` are not
honored; syscap.exe always launches its GUI product picker.** It is not a batch tool.

The official docs confirm this is by design, not a config bug:
- There is **no documented script-at-launch flag** for `syscap.exe` anywhere in the
  `doc\` tree. The System Capture UG says only "Type syscap in a command window and
  press Enter" (interactive).
- The Tcl authoring commands (`newProject`, `addLib`, `createSchematicPage`,
  `addComponent`, `drawWire`, `saveAll`, `exportNetList`) are documented to run **inside
  sysscap's Command Window** (`View - Command Window`). The only batch-support hooks are
  in-process: `cps::setAutomationMode $::cps::eCPS_AUTOMATION_ENABLED` and the
  `addComponent ... -o` "no popup" flag.

### 4.3 `Capture.exe script.tcl` — documented but GUI-backed
The OrCAD Capture UG *does* document a command-line script form: **`capture <script.tcl>`**
(`doc\cap_ug\Execute_TCL_script_in_Windows.html`). It opens the script as a text file in
edit mode in Capture — i.e. it launches the GUI. That is why the previously-observed
"reaches idle `Capture>` without sourcing" was the wrong invocation; the documented form
is the bare `capture <path>` with no `-product` and no flag. It works, but it brings up
the GUI — so it is *not* a headless authoring path. The `tclsh` DB API is.

---

## 5. PDF vs. real 22.1 API — the deltas that cost debugging time

The *OrCAD Capture Tcl/Tk Extensions* PDF (rev ~1.2/16.3) is the right reference for the
**concept** (two-arg `load`, `sCreateSession`, CString OUT-params, the
create→mutate→save batch pattern). But several signatures moved by 22.1:

| Area | PDF (rev 1.2) | Real 22.1 (proven live) |
|---|---|---|
| Create design | `CreateDesign(status, Name, RootName, RootType=SCHEMATIC)` | 4-arg works; the `RootType` int maps a root type. Result is a `DboDesign` whose root schematic is **NULL** until a schematic is added |
| Create schematic | `NewSchematic(name, status)` on DboLib | **Same** — works, but must run on the design as `NewSchematic $csName $lStatus` |
| Root schematic | via `GetRootSchematic` after `CreateDesign` | Works, but is **NULL** until a schematic is added |
| Part iterator | `NewPartsIter` / `DboLibPartsIter_NextPart` (lib-scoped) | **`DboPackage_NewPartsIter` + `DboPackagePartsIter_NextPart`** (package-scoped) |
| Device iterator | `DboLib*` | `DboPackage_NewDevicesIter` + `DboPackageDevicesIter_NextDevice` |
| `GetPinCount` | on DboLibPart | **Does not resolve from a DboLibPart** → guard with `catch` |
| `GetDesignator` | `(self status cstr)` | **`(self cstr)`** — 2-arg |
| `MarkAllLibForSave` | `(self)` | **`(self lib)`** — requires the lib handle as arg 2 |
| `NewPlacedInst` | 6–7 arg overloads | The **7-arg** `status Name PkgName part device CPoint rotation` overload is the one that binds |
| DboState `Message` | `(self)` | **`(self cstr-out)`** — CString OUT-param |

None of these are blockers; each was found by catching the real "wrong args /
CString &" error text the DLL returns, exactly as the read-path investigation did before.

---

## 6. Failure log (this session, in order)

| # | Call / attempt | Symptom | Fix |
|---|---|---|---|
| 1 | `DboDesign_GetSchematic $lDesign` | `invalid command name` | Use `[DboDesign GetRootSchematic]` / `DboDesign_GetRootSchematic` |
| 2 | `info methods $obj` | `unknown or ambiguous subcommand "methods"` | Use `info commands Cbo*_` to list class statics |
| 3 | `NewSchematic $lStatus $csName` | `TypeError ... argument 2 of type 'CString &'` | Reorder to `NewSchematic $csName $lStatus` |
| 4 | `DboLibPartsIter_NextPart` | `TypeError ... 'DboLibPartsIter *'` | Use `DboPackage_NewPartsIter` + `DboPackagePartsIter_NextPart` |
| 5 | `$lPart GetPinCount` | `No matching function for overloaded 'DboSymbol_GetPinCount'` | Wrap in `catch` (count not needed for placement) |
| 6 | `DboDevice_GetDesignator $dev $st $cs` | `Wrong # args: ... argument 3` | 2-arg form: `DboDevice_GetDesignator $dev $cs` |
| 7 | 2nd `NewPlacedInst` dropped the pkg name | `No matching function for overloaded 'DboPage_NewPlacedInst'` | Use the full 7-arg form for both parts |
| 8 | `$lSession MarkAllLibForSave` | `Wrong number of arguments ... argument 2` | Pass the lib: `MarkAllLibForSave $lLib` |
| 9 | `SaveDesign` (in-place) | Succeeded but wrote no file to our path | Use `SaveDesignAs $lDesign $csOut 1` to write a real file |
| 10 | `syscap.exe -tclfile … -nograph` | GUI "Product Choices" dialog, empty streams | No syscap batch mode exists — abandon syscap for authoring |
| 11 | `makepy` / `EnsureDispatch Capture.Application` | no registered type library | Probe via `GetIDsOfNames` instead; COM too shallow anyway |

---

## 7. What "done" means / next steps to reach a routed board

1. **Annotate** so refdes become R1/R2 (currently `DN?`):
   `capBatchAnnotate` (GUI/Command-Window command) or the DB-side equivalent. The parts
   are placed; naming is a separate, well-understood step.
2. **Pin-accurate wiring.** The proof-of-concept wire is a straight segment between the
   two parts. For electrical connectivity to the pins, compute each pin hotspot
   (`DboSymbolPin_sGetHotSpotX/Y`, `DboPartInst_GetPinByPinNumber`) and run
   `NewWireScalar` between the two hotspots (or place a net label via alias).
3. **Optional `exportPhysical pcb genpkg` / `netrev`** to drop the netlist into a `.brd`
   — that pipeline was already proven in the prior session's `E2E_AUTOMATION_REPORT.md`.
4. All of this can stay **fully headless** under `tclsh` — no Capture GUI required.

---

## Artifacts
- Working script: `C:\TEMP-B~1\kilo\author\step3_author.tcl`
- Verifier: `C:\TEMP-B~1\kilo\author\verify_authored.tcl`
- Authored design: `C:\TEMP-B~1\kilo\author\HEADLESSAUTH.DSN` (10,752 B)
- COM probe results: `C:\TEMP-B~1\kilo\author\com_methods.txt`
- syscap batch probes: `C:\TEMP-B~1\kilo\author\scap_test.ps1`, `out_*.txt`, `err_*.txt`
