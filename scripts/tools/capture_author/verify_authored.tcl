# verify_authored.tcl - INDEPENDENT RE-EXTRACTION of the headless-authored .dsn
# Reuses the EXACT working read path from work_extract.tcl (the proven tool).
# Opens HEADLESSAUTH.DSN (written by step3_author.tcl with NO Capture.exe) and
# walks page -> part-inst -> pins, printing parts + pins + nets. This proves the
# authored objects actually landed in a valid, readable .dsn.
proc isnull {o} { if {$o eq "" || $o eq "0" || $o eq "NULL"} { return 1 }; return 0 }
proc cstrval {h} {
  if {[isnull $h]} { return "" }
  if {![string match "*CString*" $h]} { return "" }
  if {[catch {DboTclHelper_sGetConstCharPtr $h} v]} { return "" }
  if {$v eq "" || $v eq "NULL" || $v eq "0"} { return "" }
  return $v
}
proc dbstr {getter obj status} {
  if {[isnull $obj]} { return "" }
  if {[catch {set h [eval [list $getter $obj $status]]} e]} { return "" }
  return [cstrval $h]
}

load C:/Cadence/SPB_22.1/tools/bin/orDb_Dll_Tcl64.dll DboTclWriteBasic
set lStatus   [DboState]
set lSession  [DboTclHelper_sCreateSession]
set lPath     [DboTclHelper_sMakeCString C:/TEMP-B~1/kilo/author/HEADLESSAUTH.DSN]
set lDesign   [$lSession GetDesignAndSchematics $lPath $lStatus]
if {[$lStatus Failed]} {
  set cs [DboTclHelper_sMakeCString ""]
  $lStatus Message $cs
  puts "EXTRACT_ERROR: [cstrval $cs]"
  exit 1
}
set designName [dbstr DboDesign_sGetName $lDesign $lStatus]
puts "VERIFY_DESIGN=<name: $designName>"

set rootSch [DboDesign_GetRootSchematic $lDesign $lStatus]
puts "ROOTSCH=<sch: $rootSch>"
catch { DboSchematic_ReadAllPages $rootSch }
puts "READALLPAGES=done"

set total_parts 0
set total_pins  0
array set PARTS {}
array set NET_SEEN {}
array set NET_MEMBERS {}

set pageIter [DboSchematic_NewPagesIter $rootSch $lStatus]
if {[isnull $pageIter]} { puts "PAGES_ITER=null" } else {
  while {1} {
    set page [DboSchematicPagesIter_NextPage $pageIter $lStatus]
    if {[isnull $page]} { break }
    # Count wires on this page
    set wireIt ""
    if {![catch { set wireIt [DboPage_NewWiresIter $page $lStatus] } ew]} {
      set wcnt 0
      set w [DboPageWiresIter_NextWire $wireIt $lStatus]
      while {![isnull $w]} { incr wcnt; set w [DboPageWiresIter_NextWire $wireIt $lStatus]; if {$wcnt>5000} break }
      puts "PAGEWIRES=<wires: $wcnt>"
    }
    if {[catch { set partIter [DboPage_NewPartInstsIter $page $lStatus] } epg]} {
      puts "PARTITER_ERR: $epg"; continue
    }
    while {1} {
      set part [DboPagePartInstsIter_NextPartInst $partIter $lStatus]
      if {[isnull $part]} { break }
      incr total_parts
      set ref [dbstr DboPartInst_sGetReference $part $lStatus]
      set PARTS($ref) 1
      puts "  PART=<ref: $ref>"
      # pins
      if {[catch { set pinIter [DboPartInst_NewPinsIter $part $lStatus] } pe]} {
        puts "    PINITER_ERR: $pe"; continue
      }
      while {1} {
        set pin [DboPartInstPinsIter_NextPin $pinIter $lStatus]
        if {[isnull $pin]} { break }
        incr total_pins
        set pinNum [dbstr DboPortInst_sGetPinNumber $pin $lStatus]
        set netNm  [dbstr DboPortInst_sGetNetName  $pin $lStatus]
        if {$pinNum ne ""} {
          puts "    PIN=<ref: $ref>.<pin: $pinNum> net=<$netNm>"
          if {$netNm ne ""} {
            if {![info exists NET_SEEN($netNm)]} { set NET_SEEN($netNm) 1; set NET_MEMBERS($netNm) "" }
            append NET_MEMBERS($netNm) "${ref}.${pinNum} "
          }
        }
      }
    }
  }
}

puts "VERIFY_SUMMARY design=$designName parts=$total_parts pins=$total_pins nets=[llength [array names NET_SEEN]]"
foreach n [lsort [array names NET_MEMBERS]] {
  puts "  NET=<net: $n> members: [string trim $NET_MEMBERS($n)]"
}
catch {delete_DboSession $lSession}
catch {delete_DboState $lStatus}
puts "VERIFY_DONE"
exit 0
