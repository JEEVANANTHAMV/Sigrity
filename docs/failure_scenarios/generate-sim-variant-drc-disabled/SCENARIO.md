# generate-sim-variant-drc-disabled

- **tool**: `generate_sim_variant` (`generate_sim_variant.exe`; logical tool `generate_sim_variant`)
- **status_category**: `precondition_error` (the tool is correct and confirmed live; the "DRC is off" state of the produced variant is deliberate, not a defect)
- **verified_workaround**: YES — verify a variant with `report.exe` re-read (its own note), and do NOT re-enable/run DRC against a variant expecting a clean result

## What went wrong (the trap)

`generate_sim_variant` creates a **new derivative Allegro design** for SI what-if analysis by over/undersizing trace widths and/or dielectric thicknesses from a master board. Per the tool's own `-help`: **on-line DRC is deliberately disabled in the resulting variant design** — its elements may legitimately violate spacing against their oversized/undersized neighbors. A caller who runs DRC (or re-enables it) on the variant and sees violations will misread them as a produced-defect or tool bug. They are the expected, intended consequence of the geometric what-if, not a failure.

The tool itself works: the live run produced a genuine, distinct, valid derivative board.

## Evidence

- `core/tool_status.py` (`generate_sim_variant` note): "CONFIRMED LIVE: genuinely creates a NEW derivative Allegro design for SI what-if analysis (over/undersizing trace widths and/or dielectric thicknesses from a master board) ... `generate_sim_variant -c \"1.0\" -d \"1.0\" -o variant_out.brd <master.brd>` (percentage oversize on both clines and dielectrics) against a real sample board produced a real, distinct 918KB new .brd -- independently confirmed valid (not a corrupt/stub copy) by re-reading it with report.exe (81 packages, 191 drills, 163 connections, matching the master's real content). NOTE from the tool's own -help: on-line DRC is deliberately disabled in the resulting variant design (elements may legitimately violate spacing against their oversized neighbors) -- don't re-enable/run DRC against a variant expecting a clean result."

## Symptoms a caller observes

- A valid, content-matching derivative `.brd` is produced (not a corrupt/stub)
- If DRC is run against it, spacing violations appear that are an artifact of the what-if geometry, not a real design error
- On-line DRC is not active on the variant
