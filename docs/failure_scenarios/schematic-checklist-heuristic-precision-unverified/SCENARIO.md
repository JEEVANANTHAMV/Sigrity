# schematic-checklist-heuristic-precision-unverified

`run_schematic_checklist` (sigrity_mcp/domains/cad/schematic_checklist_tools.py) is a rule engine (decoupling caps, pull-up/pull-down resistors, floating clock nets, reset-circuit presence, test-point coverage) over real `report.exe -v net`/`-v bom` CSV output. Its **parsing** layer is grounded in real report files and unit-tested, but whether the five **heuristics themselves** are precise enough for a real production board — without false positives — is unverified. status_category: `unreliable_intermittent` (per the manifest's classification) — i.e. it works (parses, runs, produces exactly the findings its own rules state it checked), but the *accuracy of the findings against a real design* is not an established fact.

## What went wrong (i.e. what is *not* confirmed)

Per `README.md` lines 476-485 (the `built_untested`/honest-limitation section): "this one's *parsing* is grounded in real report files this suite itself produced on this machine and is covered by unit tests against that real CSV shape — **what's unverified is only whether the five heuristics themselves (REFDES-prefix/net-name pattern matching) are precise enough for a real production board without false positives; they are deliberately coarse and every finding says exactly what pattern triggered it.**"

`schematic_checklist_tools.py`'s own module docstring (lines 29-32) says the same thing in-module: "These are **coarse, net-level heuristics, not a full per-IC power-pin-map checker** (this suite has no per-component pin-function data, only which REFDES.PIN is on which net) — each finding says exactly what was checked so a reviewer can judge it, per this project's usual 'don't fabricate confidence' discipline."

## Why it's built this way (what IS verified, for contrast)

- **Parsing is real, grounded in real artifacts**: `parse_net_report`/`parse_bom_report` key off the actual 2-line title-header + CSV shape of `report.exe -v net`/`-v bom` output, and the module docstring quotes the real, verbatim shape it was built against (real `GND` net with real pin list, real `BOM` header row with real `CAP300`/`RES400` rows, from real files under `runs/allegro_report-*/net_rep.rpt`/`bom_rep.rpt`).
- **Why it can't be a real per-pin checker**: `report.exe -v net`/`-v bom` (Allegro's report engine, confirmed live) only gives net-to-REFDES.PIN connectivity and a BOM — it has no per-component pin-*function* data (which specific pin of which IC is a power pin, a clock input, etc.). The five rules therefore necessarily work off REFDES prefix letter conventions (C/R/L/D/Q/U/J/SW/Y/TP/...) plus regex patterns on *net names* — the same coarse, convention-based signals a human EDA engineer might use as a quick screen, but with no way to look inside an IC's own datasheet pin map.
- The rules and their regexes, for reference (schematic_checklist_tools.py lines 45-53): `_GROUND_NAMES` (GND/0/AGND/DGND/VSS/GROUND/PGND), `_POWER_NET_RE` (`^[+-]?\d+(\.\d+)?V\d*$`), `_POWER_KEYWORD_RE` (VCC/VDD/VBAT/VPWR/^PWR/_PWR$), `_RESET_RE` (RESET|RST), `_CLOCK_RE` (CLK|CLOCK|OSC|XTAL), `_PULLABLE_RE` (RESET|RST|ENABLE|_EN$|^EN_|_CS$|^CS_|SDA|SCL), `_TEST_POINT_RE` (`^TP\d*$`).

## Evidence

- `sigrity_mcp/domains/cad/schematic_checklist_tools.py` — full module (lines 1-266), especially the module docstring (lines 1-33) and each `_check_*` function's own finding message, which states explicitly what pattern triggered it (e.g. decoupling's message names the exact net and says "check for a missing decoupling/bypass cap", not a definitive "this is a bug").
- `README.md` lines 476-485 — the "unverified precision" statement, verbatim.
- `core/tool_status.py` — `allegro_report` is `confirmed_live` (the input-report producer), while `run_schematic_checklist` itself has no separate `TOOL_STATUS` entry (it's a pure in-suite rule engine over an already-confirmed-live tool's output, so it doesn't have its own license/live-execution status in that registry — its "unverified" flag is specifically about heuristic precision, not about whether it even runs).

## Affected code

- `sigrity_mcp/domains/cad/schematic_checklist_tools.py` — `_check_decoupling`, `_check_pull_up_down`, `_check_clocks`, `_check_resets`, `_check_test_points` (the five heuristics with unverified real-world precision), and `parse_net_report`/`parse_bom_report` (the parsing layer, which IS verified).
