# interchange-translators-license-gated-workaround

`con2xml.exe`, `cap2xml.exe`, `dml2con.exe`, and `apd2con.exe` (the schematic/netlist ⇄ XML/DML/Concept-HDL interchange translators in `sigrity_mcp/domains/cad/interchange_tools.py`) all fail at their own **internal license check, before argument parsing even begins** — with "No Product License selected... Translation cancelled" — on this machine. status_category: `known_blocked` (licensing, not an implementation gap). **Per the project's scope note, the pure FlexNet license failure itself is out of scope for a fix — this folder documents only the confirmed, in-suite WORKAROUND paths that avoid needing these four tools at all.**

## What went wrong (for context only, not the subject of this fix)

`interchange_tools.py`'s module docstring (lines 1-20) records: running any of the four with `-help` fails with `"No Product License selected... Translation cancelled"` rather than printing a usage banner — the license gate fires before argument parsing gets far enough to print help, so the exact flag syntax for all four could not even be confirmed from this machine the way every other new tool in this domain was. `core/tool_status.py`'s per-tool notes (con2xml lines 636-648, cap2xml 649-654, dml2con 655-660, apd2con 661-667) confirm each one individually against real sample files, including the specific sample used and the exact exit code observed:

- `con2xml` — fails at license check against `share/pcb/translators/altium_proj_template/worklib/top/sch_1/top.con`; **exit code 0** on failure ("do not treat a 0 return code as success for this tool").
- `cap2xml` — same failure against the real `Fault-Detector.opj` sample project; **exit code 0** on failure.
- `dml2con` — same failure against `share/pcb/signal/templates/hspice_bbox_template.dml`; **exit code 2**.
- `apd2con` — same failure (**exit code 2**), and doubly blocked: "no `.apd` sample file exists anywhere in the install either, so even a working license would need an APD design obtained separately to exercise this tool."

`README.md` Known Gaps (lines 755-759) groups these squarely under "**Needs a Cadence license grant** (the tool itself is real, confirmed CLI, and fails specifically with a license-selection message before doing any work)". `SCENARIOS.md`'s own scope note (lines 24-27) is explicit that this is why the license block itself is not the target of a fix here: "Pure FlexNet license scenarios are excluded per the project's scope note. License-gated tools (con2xml/cap2xml/dml2con/apd2con) appear only to document their WORKAROUND path (use copyproject/xcon2project/PowerSI BRD-bridge instead)."

## The point of this folder

Since the license gate cannot be fixed in-suite (it's a FlexNet/entitlement issue on this machine, not a code bug), this scenario documents **the confirmed-working alternative paths in this codebase that accomplish the same end goals** (get a schematic/Capture design or netlist into a form downstream Sigrity tools can actually consume) without ever invoking these four blocked translators.

## Affected code

- `sigrity_mcp/domains/cad/interchange_tools.py` — `run_con2xml`/`run_cap2xml`/`run_dml2con`/`run_apd2con` (all four, confirmed license-blocked; every tool in this module is `known_blocked` in `core/tool_status.py`).
