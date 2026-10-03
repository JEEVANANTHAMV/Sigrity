# Workarounds: checkplus Is the DE-HDL Schematic Rules Checker, Not an Allegro `.brd` Checker

## Verified Workaround (in-suite, live-verified)

**For PCB (`.brd`) design-rule checking, use `run_allegro_batch_drc` instead of
`run_allegro_checkplus`.**

`run_allegro_batch_drc` (`sigrity_mcp/domains/cad/allegro_drc_tools.py:40-51`, wrapping
`batch_drc.exe`) is the confirmed, live-verified headless DRC path for Allegro boards:

- `sigrity_mcp/core/tool_status.py:565-566` — "`allegro_batch_drc`: Confirmed live
  against a real .brd sample on this machine: `batch_drc.exe -nographic <board>` exited
  0 with 'Batch DRC checking done.'"
- `sigrity_mcp/core/tool_status.py:50` — status map: `"allegro_batch_drc":
  "confirmed_live"`.
- `README.md:68-69` — "Confirmed live, standalone CLI ... `run_allegro_batch_drc`
  (`batch_drc.exe -nographic`, confirmed: 'Batch DRC checking done.')."
- `.forjinn/skills/sigrity-cad/SKILL.md:33-49` — verified playbook: submit
  `run_allegro_batch_drc(board_file=...)`, poll, read `batch_drc.log` for the "DRC
  update completed" evidence. Note `batch_drc.log` is where the real DRC result text
  lands (see the sibling scenario `batch-drc-launcher-exits-early-state-lie` for the
  launcher's state-lying caveat).

So the rule: **if the goal is "run DRC against my Allegro board," call
`run_allegro_batch_drc`, never `run_allegro_checkplus`.** `checkplus` checks DE-HDL
schematic rules, a different domain, and will not validate a `.brd`.

## Workarounds Tried (with outcomes)

| # | What was tried | Outcome | Evidence |
|---|----------------|---------|----------|
| 1 | `run_allegro_batch_drc` for `.brd` DRC | **worked** — the correct, confirmed-live path for PCB design rules | `sigrity_mcp/core/tool_status.py:565-566` |
| 2 | `run_allegro_checkplus -proj <bare directory>` (shipped example with its own `cp.dat`) | **failed** — `**Error! [5038] Project File '<value>' does not exist` + `**Warning! [5015] Missing '<cwd>/checkplus/cp.dat'` (the `[5015]` check ignores `-proj` entirely) | `sigrity_mcp/core/tool_status.py:591-599`; `allegro_drc_tools.py:17-29` |
| 3 | `run_allegro_checkplus -proj <raw .brd>` | **failed** — same `[5038]` signature; a `.brd` is not a valid checkplus project reference | `sigrity_mcp/core/tool_status.py:591-594` ("would also fail as a raw .brd") |
| 4 | Discover the exact `-proj` project-registration convention from the doc tree | **not isolated** — `doc/checkplus/` describes the check rules, not the path/reference format in enough detail; even if found, the tool targets the wrong domain | `allegro_drc_tools.py:25-29`; `sigrity_mcp/core/tool_status.py:792-800` |

## Applicability to this suite's Capture-based flow

**Very likely inapplicable — do not try to rescue it.**

- This suite's schematics are **Capture-based, not DE-HDL-based** (see the
  `CAD/Capture & schematic` scenario group in SCENARIOS.md). checkplus checks rules for
  **Design Entry HDL / Concept-HDL**, a separate legacy Cadence *schematic* product.
  There is therefore no DE-HDL project in this flow for checkplus to consume, regardless
  of what `-proj` format it wants.
- This conclusion is independent of the unresolved `-proj` format question: the scope
  correction holds either way. Even a "correctly" formatted reference would point at a
  DE-HDL schematic design, not an Allegro PCB layout.
- `sigrity_mcp/core/tool_status.py:792-800` states it directly: "this tool is likely not
  applicable to a Capture-based (not DE-HDL-based) design flow at all, independent of the
  project-reference-format question."

Practical recommendation: treat `run_allegro_checkplus` as out-of-scope for this suite's
PCB work. Keep it wrapped (it is harmless and self-documenting), but route all `.brd`
design-rule checking to `run_allegro_batch_drc`. Do not invest further in isolating the
`-proj` DE-HDL project-reference convention for a flow that has no DE-HDL projects.

## Remaining Gaps

- The exact `-proj` DE-HDL project-reference format is still **unconfirmed** — it was
  never isolated from the doc tree. This is now a low-priority gap because the tool is
  out of scope for the Capture-based flow, not because the format is expected to be
  discovered and used.
- No live, successful `checkplus.exe` run exists on this machine (every attempt ended in
  `[5038]`). It is therefore effectively `built_untested` in a functional sense, even
  though the wrapper is implemented and the CLI is confirmed to launch and fetch a
  license.
- `run_allegro_checkplus` remains registered with status `known_blocked`
  (`sigrity_mcp/core/tool_status.py:60`) and is not referenced by any verified SKILL
  task; the only verified DRC task in `sigrity-cad/SKILL.md` is `run_allegro_batch_drc`.
