# Workarounds — schematic-checklist-heuristic-precision-unverified

## No single "fix" exists — the design is deliberately conservative

`verified_workaround: None` here means there is no confirmed way to make the five heuristics *provably precise* on a real production board without false positives — that would require per-IC pin-function data (a pin map/datasheet check), which this suite explicitly does not have (`schematic_checklist_tools.py` docstring: "this suite has no per-component pin-function data, only which REFDES.PIN is on which net").

What the suite does instead is bound the risk so a bad heuristic result can't be silently mistaken for a confident, authoritative signoff:

## 1. Every finding self-describes what triggered it

Per `README.md` lines 484-485 and the module docstring, "each finding says exactly what was checked so a reviewer can judge it." Look at the actual finding messages (schematic_checklist_tools.py):

- `decoupling`: "Power net '{net}' has no capacitor (REFDES prefix 'C') attached anywhere in this report — **check for a missing decoupling/bypass cap.**" — framed as a check-for-possibility, not a verdict.
- `pull_up_down`: "Signal net '{net}' (matches a pull-up/pull-down-candidate name pattern) has no resistor (REFDES prefix 'R') bridging it to a ground/power net in this report — **verify a pull-up/pull-down is present if this signal needs a defined idle state.**"
- `clocks`: "Clock/oscillator net '{net}' has fewer than 2 connections ({n}) — **looks floating/unterminated.**"
- `resets`: "Reset net '{net}' has no resistor or capacitor attached in this report — **verify the reset circuit (pull resistor / RC delay / supervisor) is actually present.**"
- `test_points`: if no `TP<n>` REFDES is found: "confirm this design genuinely has no dedicated test points, **or that this org uses a different test-point naming convention** than 'TP<n>'."

## 2. Severity is deliberately downgraded to match confidence

Note the `severity` field values used per rule (schematic_checklist_tools.py): `decoupling` → `warning`, `pull_up_down` → `info`, `clocks` → `error` (the one case with a hard physical lower bound: a clock net with <2 connections is, by connectivity counting alone, unambiguously under-connected — this is the one rule where the check doesn't need pin-function data at all), `resets` → `warning`, `test_points` → `info`. The rules that are genuinely pattern-matching guesses (pull-up/down, reset, test-point naming) are rated `info`/`warning`, not `error`.

## 3. What to do when consuming the output

- **Treat the findings as a screening pass / reviewer checklist, not as a signoff.** A human reviewer should verify each flagged net against the actual design intent/datasheet before acting — the tool's own messages are written to be handed directly to that reviewer.
- For the rules that depend on *naming conventions* (`pull_up_down`, `resets`, `test_points`), a false positive is most likely when the design uses naming that doesn't match the built-in regexes (`_PULLABLE_RE`, `_RESET_RE`, `_TEST_POINT_RE`) — e.g. a reset net named `SYS_RESTART` instead of anything containing `RESET`/`RST`, or a test point named `TP1.5`/`TEST_POINT_1` instead of bare `TP<n>`. If the design's naming conventions differ from the built-in patterns, expect the relevant rule to flag nothing (false negative) or, where a *different* pattern is used, to flag an unrelated net (false positive). There is no parameter on `run_schematic_checklist` to override these regexes — the patterns are module-level constants (`schematic_checklist_tools.py` lines 45-51).
- For `test_points` specifically: if a BOM isn't provided, the rule is skipped outright (severity `skipped`, schematic_checklist_tools.py lines 241-249) rather than guessing — provide `bom_report_file` if test-point coverage actually matters for the checklist run.

## What does NOT resolve this scenario

- There is no additional confirmed-live tool in this suite that would make the check *precise* (no per-IC pin-map data source is available on this machine per the module's own stated limitation).
- Re-running the checklist more, or against more nets, doesn't fix precision — the limitation is structural (no pin-function data), not statistical.
