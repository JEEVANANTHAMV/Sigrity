# step3_author.tcl - Full headless authoring (procs defined first)
proc isnull {o} { if {$o eq "" || $o eq "0" || $o eq "NULL"} { return 1 }; return 0 }
proc cstrval {h} {
  if {[isnull $h]} { return "" }
  if {![string match "*CString*" $h]} { return "" }
  if {[catch {DboTclHelper_sGetConstCharPtr $h} v]} { return "" }
  if {$v eq "" || $v eq "NULL" || $v eq "0"} { return "" }
  return $v
}

load C:/Cadence/SPB_22.1/tools/bin/orDb_Dll_Tcl64.dll DboTclWriteBasic
set lStatus [DboState]
set lSession [DboTclHelper_sCreateSession]

# === Create Design ===
set csName [DboTclHelper_sMakeCString "HEADLESSAUTH"]
set csRoot [DboTclHelper_sMakeCString "HEADLESSAUTH"]
set lDesign [$lSession CreateDesign $lStatus $csName $csRoot 0]
puts "DESIGN=<d: $lDesign> failed=[expr {[$lStatus Failed]?1:0}]"
if {[$lStatus Failed]} { puts "DESIGN_FAIL"; exit 1 }

# === Create Schematic (root) ===  PDF form: NewSchematic(name, status)
set lSchematic [$lDesign NewSchematic $csName $lStatus]
puts "SCH=<s: $lSchematic> failed=[expr {[$lStatus Failed]?1:0}]"
set lSchematic [DboDesign_GetRootSchematic $lDesign $lStatus]
puts "ROOTSCH=<s: $lSchematic>"
if {[isnull $lSchematic]} { puts "SCH_FAIL"; exit 1 }

# === Create Page ===
set csPage [DboTclHelper_sMakeCString "Sheet1"]
set lPage [$lSchematic NewPage $lStatus $csPage]
puts "PAGE failed=[expr {[$lStatus Failed]?1:0}]"
if {[$lStatus Failed] || [isnull $lPage]} { puts "PAGE_FAIL"; exit 1 }
puts "PAGE=<p: $lPage>  GRAN=<g: [$lPage GetPhysicalGranularity]>"

# === Open Library + Resolve Package/Part/Device ===
set csLib [DboTclHelper_sMakeCString "C:/Cadence/SPB_22.1/tools/capture/library/Discrete.olb"]
set lLib [$lSession GetLib $csLib $lStatus]
if {[$lStatus Failed]} { puts "LIB_FAIL"; exit 1 }
puts "LIB=<lib: $lLib>"

# Get first package via the names iterator (CString OUT)
set csPkgNM [DboTclHelper_sMakeCString ""]
set pkgIt [$lLib NewPackageNamesIter $lStatus]
DboLibPackageNamesIter_NextName $pkgIt $csPkgNM
set pkgName [cstrval $csPkgNM]
puts "PKGNAME=<pn: $pkgName>"
if {$pkgName eq ""} { puts "NO_PKG"; exit 1 }

# GetPackage: real API wants a CString OUT at arg 1 of the static form per live probe.
# Use the PACKAGE OBJECT we already can reach via GetCachedPackage/iterator instead.
# Enumerate package OBJECTS directly (cleaner than name->handle).
set lPackage ""
if {[catch { set pkgIt2 [$lLib NewPackagesIter $lStatus] } epi]} {
  puts "NEWPKGITER_ERR: $epi"
} else {
  if {[catch { set lPackage [DboLibPackagesIter_NextPackage $pkgIt2 $lStatus] } epn]} {
    puts "NP_NEXTPKG_ERR: $epn"
  }
}
if {[isnull $lPackage]} {
  # Fallback: static GetPackage with OUT cstring (the documented 16.3 form)
  set csGet [DboTclHelper_sMakeCString $pkgName]
  if {[catch { set lPackage [$lLib GetPackage $lStatus $csGet] } egs]} {
    puts "GETPKG_STATIC_ERR: $egs"
  }
  if {[isnull $lPackage]} { 
    # try NewPackageNamesIter first name + GetCachedPackage
    if {[catch { set lPackage [$lLib GetCachedPackage $csGet $lStatus] } egc]} { puts "GETCACHED_ERR: $egc" }
  }
}
puts "PACKAGE=<pkg: $lPackage>"
if {[isnull $lPackage]} { puts "PKG_FAIL"; exit 1 }

set partIt [DboPackage_NewPartsIter $lPackage $lStatus]
set lPart [DboPackagePartsIter_NextPart $partIt $lStatus]
puts "LIBPART=<lp: $lPart>"
if {[isnull $lPart]} { puts "NO_PART"; exit 1 }
set devIt [DboPackage_NewDevicesIter $lPackage $lStatus]
set lDevice [DboPackageDevicesIter_NextDevice $devIt $lStatus]
if {[isnull $lDevice]} { set lDevice [DboPackage_GetDevice $lPackage $lStatus [DboTclHelper_sMakeInt 1]] }
set pinct 0
if {[catch { set pinct [$lPart GetPinCount] } epc]} { }
puts "DEVICE=<dev: $lDevice>  PINCOUNT=<pins: $pinct>"
if {[isnull $lDevice]} { puts "NO_DEVICE"; exit 1 }

# === Place Two Parts (NewPlacedInst has an overload; probe arg forms) ===
set gran [expr {[$lPage GetPhysicalGranularity]}]
proc docxy {gran xx yy} { return [list [expr {int(round($gran * $xx))}] [expr {int(round($gran * $yy))}]] }
set p1 [docxy $gran 30 50]
set p2 [docxy $gran 70 50]
set pt1 [DboTclHelper_sMakeCPoint [lindex $p1 0] [lindex $p1 1]]
set pt2 [DboTclHelper_sMakeCPoint [lindex $p2 0] [lindex $p2 1]]
puts "PT1=( [lindex $p1 0] [lindex $p1 1] )  PT2=( [lindex $p2 0] [lindex $p2 1] )"

# Device name (CString OUT) - 2-arg form (self designator)
set devName ""
if {[catch { set csDev [DboTclHelper_sMakeCString ""]; DboDevice_GetDesignator $lDevice $csDev; set devName [cstrval $csDev] } edev]} { set devName "<err>" }
puts "DEVDESIG=<dd: $devName>"

set csR1 [DboTclHelper_sMakeCString "R1"]
set csR2 [DboTclHelper_sMakeCString "R2"]
set lInst1 ""
# Documented: NewPlacedInst status Name PkgName part device CPoint [rotation]
if {[catch { set lInst1 [$lPage NewPlacedInst $lStatus $csR1 $csPkgNM $lPart $lDevice $pt1 0] } epi1]} {
  puts "NPI_formA_ERR: [string range $epi1 0 150]"
  # alt: NewPlacedInst status Name part device CPoint
  if {[catch { set lInst1 [$lPage NewPlacedInst $lStatus $csR1 $lPart $lDevice $pt1 0] } epi2]} {
    puts "NPI_formB_ERR: [string range $epi2 0 150]"
    # alt: NewPlacedInst status Name device CPoint
    if {[catch { set lInst1 [$lPage NewPlacedInst $lStatus $csR1 $lDevice $pt1 0] } epi3]} {
      puts "NPI_formC_ERR: [string range $epi3 0 150]"
    }
  }
}
if {[$lStatus Failed] || [isnull $lInst1]} {
  # Last resort: use the device-object form without package name
  if {[isnull $lInst1]} {
    if {[catch { set lInst1 [$lPage NewPlacedInst $lStatus $csR1 $lDevice $pt1] } epi4]} {
      puts "NPI_formD_ERR: [string range $epi4 0 150]"
    }
  }
}
puts "INST1=<i1: $lInst1> failed=[expr {[$lStatus Failed]?1:0}]"
if {[isnull $lInst1]} { puts "FATAL: inst1 null"; exit 1 }

set lInst2 [$lPage NewPlacedInst $lStatus $csR2 $csPkgNM $lPart $lDevice $pt2 0]
puts "INST2=<i2: $lInst2> failed=[expr {[$lStatus Failed]?1:0}]"

# === Draw Wire ===
set wx1 [lindex [docxy $gran 45 50] 0]; set wy1 [lindex [docxy $gran 45 50] 1]
set wx2 [lindex [docxy $gran 55 50] 0]; set wy2 [lindex [docxy $gran 55 50] 1]
set wpt1 [DboTclHelper_sMakeCPoint $wx1 $wy1]
set wpt2 [DboTclHelper_sMakeCPoint $wx2 $wy2]
puts "WIRE=( ${wx1} ${wy1} ) -> ( ${wx2} ${wy2} )"
set lWire [$lPage NewWireScalar $lStatus $wpt1 $wpt2]
puts "WIRE failed=[expr {[$lStatus Failed]?1:0}]  WIRE=<w: $lWire>"

# === Save to disk via SaveDesignAs so we can independently verify ===
catch { $lPage MarkModified }
catch { $lSchematic MarkModified }
catch { $lSession MarkAllLibForSave $lLib }
set outPath "C:/TEMP-B~1/kilo/author/HEADLESSAUTH.DSN"
set csOut [DboTclHelper_sMakeCString $outPath]
set savedok 0
if {[catch { $lSession SaveDesignAs $lDesign $csOut 1 } esv]} {
  puts "SAVEDAS_ERR: $esv"
  if {[catch { $lSession SaveDesignAs $lDesign $csOut } esv2]} {
    puts "SAVEDAS_ERR2: [string range $esv2 0 200]"
  }
}
if {![$lStatus Failed]} { set savedok 1 }
puts "SAVEDOK=<ok: $savedok> failed=[expr {[$lStatus Failed]?1:0}]"
set fsize -1
if {[file exists $outPath]} { set fsize [file size $outPath] }
puts "OUTSIZE=<size: $fsize>"
puts "PATH=$outPath"

# Cleanup
catch { $lSession RemoveDesign $lDesign }
catch { delete_DboSession $lSession }
catch { delete_DboState $lStatus }
puts "DONE"
exit 0
