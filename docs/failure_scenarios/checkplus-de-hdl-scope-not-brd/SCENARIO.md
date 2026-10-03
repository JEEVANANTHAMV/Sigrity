# checkplus Is the DE-HDL Schematic Rules Checker, Not an Allegro `.brd` Checker

**Slug**: `checkplus-de-hdl-scope-not-brd`
**Tool(s) affected**: `run_allegro_checkplus` (wraps `checkplus.exe`, `sigrity_mcp/domains/cad/allegro_drc_tools.py`)
**Status category**: `known_blocked`
**Pipeline stage**: design / rule-check (constraint verification)

## Symptom

`checkplus.exe` launches cleanly (it fetches a license, prints real, readable
diagnostics, no dialog, no crash) but can never complete a meaningful check against
anything in this suite's Allegro PCB flow. Two distinct failure signatures were
observed:

1. **The `-proj` path-resolution failure** (observed first, while the tool was still
   believed to be a general Allegro rule checker). Pass `-proj` a bare directory
   (`tools/checkplus_exp/concept/examples/physical`, a real shipped example project that
   has its own `cp.dat`), and checkplus reports:
   ```
   **Error! [5038] Project File '<value>' does not exist
   **Warning! [5015] Missing '<cwd>/checkplus/cp.dat'
   ```
   Passing a raw `.brd` instead of a directory fails the same way. The `[5015]` warning
   looks for `cp.dat` in a fixed `<cwd>/checkplus/cp.dat` location and **ignores the
   `-proj` value entirely** for that particular check — even when the directory being
   pointed at already contains a `cp.dat`. The initial read of this was that `-proj`
   resolves through some CDS project-registration convention ("not a plain filesystem
   path") that was never isolated from the doc tree.

2. **The scope correction** (the actual root cause, found later). checkplus is not an
   Allegro physical-PCB rules checker at all. Its own shipped documentation chapter is
   titled **"Setting Up Allegro Design Entry HDL Rules Checker"** — it is the rules
   checker for **Design Entry HDL / Concept-HDL**, a separate, *legacy Cadence schematic*
   tool. Its `-proj` argument is a **DE-HDL project reference**, not anything resolvable
   from an Allegro `.brd` or a plain directory path. This fully explains the `[5038]`
   "Project File does not exist" result: we were handing it the wrong *kind* of project
   by construction, not merely the wrong *path format*.

Net effect: the tool is real and runs, but it is aimed at the wrong domain. It checks
DE-HDL schematic design rules, whereas this suite's PCB work revolves around Allegro
`.brd` boards produced by a **Capture-based** schematic flow (Capture, *not* DE-HDL).
Even if the correct `-proj` reference format were discovered, the tool would not check
an Allegro PCB layout.

## Root Cause

Two independent facts, the second subsuming the first:

- **`-proj` is a project reference, not a filesystem path.** The `[5015]` warning reading
  from a hard-coded `<cwd>/checkplus/cp.dat` (and ignoring `-proj` for that check) plus
  the `[5038]` "Project File does not exist" for both a bare directory and a raw `.brd`
  show that checkplus resolves `-proj` through a Cadence project-registration
  convention — the same family `designextractor.exe` expects a `.cpm`/`.sdax` project
  for — rather than a simple directory-or-file path. The exact convention is not
  recoverable at implementation level from the shipped `doc/checkplus/` tree (which
  describes the check *rules*, not the path/reference format).

- **The tool is simply aimed at DE-HDL, not Allegro PCB.** The authoritative scope
  statement is checkplus's own docs: `doc/checkplus/chap2.html` is titled "Setting Up
  Allegro Design Entry HDL Rules Checker". The word "Allegro" in the title is a naming
  historical artifact; the rules being checked belong to the DE-HDL / Concept-HDL
  *schematic* design entry tool, a different and legacy product line. Allegro `.brd`
  physical design rules are checked elsewhere (see WORKAROUNDS.md).

Because this suite's schematics come from **Capture** (not DE-HDL), there is no DE-HDL
project in this flow for checkplus to consume at all — so the tool is likely inapplicable
independent of the unresolved `-proj` format question.

## Evidence

- `sigrity_mcp/core/tool_status.py:591-599` — first (path-resolution) note: "Attempted
  live against a real shipped example project (tools/checkplus_exp/concept/examples/
  physical, which has its own cp.dat) — failed both as a bare directory path and would
  also fail as a raw .brd: checkplus prints `**Error! [5038] Project File '<value>'
  does not exist` and a `**Warning! [5015] Missing '<cwd>/checkplus/cp.dat'` that
  ignores -proj's value for that specific check. This means -proj resolves through some
  CDS project-registration convention (not a plain filesystem path)... Not a license or
  launch problem — the tool runs and prints real, readable diagnostics — but the correct
  project_file value for it is still unconfirmed."
- `sigrity_mcp/core/tool_status.py:792-800` — second (scope-correction) note:
  "`doc/checkplus/chap2.html`'s own title is 'Setting Up Allegro Design Entry HDL Rules
  Checker' — checkplus is a rules checker for Design Entry HDL / Concept-HDL (a
  separate, legacy Cadence SCHEMATIC tool), not for Allegro PCB `.brd` physical layouts
  at all. Its `-proj` argument is a DE-HDL project reference, not anything resolvable
  from a `.brd` or a plain directory path — this fully explains the earlier 'Project
  File does not exist' result and means this tool is likely not applicable to a
  Capture-based (not DE-HDL-based) design flow at all, independent of the
  project-reference-format question."
- `sigrity_mcp/core/tool_status.py:60` — status map: `"allegro_checkplus":
  "known_blocked"`.
- `README.md:69-73` — initial finding: "`run_allegro_checkplus` (`checkplus.exe`) is a
  real, license-fetching standalone constraint/rule checker, but its `-proj` argument
  resolves through some CDS project-registration convention rather than a plain
  filesystem path (confirmed via real `**Error! [5038]`/`**Warning! [5015]` diagnostics
  against a real shipped example project) — not yet confirmed end-to-end."
- `README.md:828-832` — scope correction: "`checkplus.exe` — SCOPE CORRECTION: its own
  doc chapter is titled 'Setting Up Allegro **Design Entry HDL** Rules Checker' — it's a
  rules checker for a different, legacy Cadence *schematic* tool (DE-HDL/Concept-HDL),
  not for Allegro PCB `.brd` layouts at all. Likely not applicable to this suite's
  Capture-based flow regardless of what reference format `-proj` needs."
- `sigrity_mcp/domains/cad/allegro_drc_tools.py:9-15` — `checkplus.exe -help` banner,
  confirmed live: `checkplus -help|-h|-version|{-proj <file> [-verbose ...]
  [-compiledfiledir <dir>] [-max_messages <n>] [-I <path>] [-r <env_file>]
  [-r <rule_file> [names]]}`.
- `sigrity_mcp/domains/cad/allegro_drc_tools.py:17-29` — wrapper docstring: "IMPORTANT,
  confirmed live: `-proj` does NOT take a raw `.brd` path or a bare directory path — both
  were tried against this machine's real sample projects
  (`tools/checkplus_exp/concept/examples/physical`, a real shipped example with its own
  `cp.dat`) and both failed with `**Error! [5038]` ... plus a `**Warning! [5015]` ...
  meaning checkplus resolves `-proj` through some CDS project-registration convention
  (likely tied to a `.cpm`/project-manager entry, the same family `designextractor.exe`
  expects `.cpm`/`.sdax` for), not a simple filesystem path."
- `sigrity_mcp/domains/cad/allegro_drc_tools.py:54-77` — `run_allegro_checkplus` builds
  `["-proj", project_file]` and submits `tool="allegro_checkplus"`.

## Pipeline Impact

This is a **scope mismatch, not a blocker of an active step.** No part of the suite's
verified PCB pipeline depends on `run_allegro_checkplus`; it exists only as a plausible
"constraint/rule checker" alongside `run_allegro_batch_drc`. The realistic impact is:

- Any pipeline step that reaches for `run_allegro_checkplus` expecting it to validate an
  Allegro `.brd` board's physical design rules will always fail (with `[5038]`) and never
  produce a meaningful result — and that failure will look like a project-path bug,
  not a domain bug, unless the DE-HDL scope is known.
- It should not be mistaken for the DRC step. PCB design-rule checking for `.brd` boards
  is done by `run_allegro_batch_drc` (see WORKAROUNDS.md), which is the confirmed,
  live-verified path.
- Since the suite's schematics are Capture-based (not DE-HDL-based), there is likely no
  DE-HDL project to feed it even if the `-proj` format were solved, so it is very
  probably dead weight for this flow rather than a recoverable tool.
