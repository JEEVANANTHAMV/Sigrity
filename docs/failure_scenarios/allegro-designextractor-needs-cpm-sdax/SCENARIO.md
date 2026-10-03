# designextractor Requires a .cpm/.sdax Project — Rejects Raw .brd

**Slug**: `allegro-designextractor-needs-cpm-sdax`
**Tool(s) affected**: `run_allegro_design_extractor` (`sigrity_mcp/domains/cad/allegro_extraction_tools.py`)
**Status category**: `known_blocked`
**Pipeline stage**: design / extraction

## Symptom

`run_allegro_design_extractor` (`designextractor.exe`) cannot be driven against a raw Allegro `.brd` file. Passing a `.brd` as the `-p/--proj` argument is rejected **immediately** at argument-parsing time — the tool re-prints its full usage banner and exits rather than doing any extraction. The tool's own `-help` banner documents `-p/--proj <file>` as the required project input.

This is distinct from the sibling `run_allegro_extracta` tool (which *does* accept a `.brd` directly and is `confirmed_live`). `designextractor` is a different extraction engine that reads Allegro's design **project** database/connectivity representation, and it genuinely requires a populated `.cpm`/`.sdax` project file — not a board design file.

## Root Cause

`designextractor.exe` is not a `.brd` consumer. Its `-p/--proj` parameter is validated against a project-file type (`.cpm`/`.sdax`), and a raw `.brd` fails that validation before any processing begins, producing the bare usage-banner re-print. This is a genuine product precondition (the tool was never designed to ingest a `.brd`), not a wrapper bug and not a license problem: the tool launches, parses arguments, and rejects the wrong input type with real diagnostics.

## Evidence

- `sigrity_mcp/core/tool_status.py:629-632` — `allegro_designextractor` note: "Attempted live: passing a raw .brd is confirmed rejected outright (immediate usage-banner re-print) — designextractor genuinely requires a populated .cpm/.sdax project file per its own -help text. For direct .brd database extraction, use `allegro_extracta` (extracta.exe) instead."
- `sigrity_mcp/core/tool_status.py:63` — `"allegro_designextractor": "known_blocked"` in the `TOOL_STATUS` registry.
- `sigrity_mcp/domains/cad/allegro_extraction_tools.py:3-19` — module docstring: "IMPORTANT, confirmed live: `-p/--proj` genuinely requires a `.cpm`/`.sdax` project file — running it against a raw `.brd` (as this suite's other CAD tools take directly) failed immediately with argument-parsing rejection, re-printing the usage banner. No populated `.cpm`/`.sdax` project instance was found on this machine to test end-to-end (the ones shipped under `share/cdssetup/pcbdw/workspaces/` are unfilled `@project@.cpm` templates, not real projects) — treat `run_allegro_design_extractor` as `built_untested` until run against a real `.cpm`/`.sdax` file. Do not pass a `.brd` file to this tool."
- `sigrity_mcp/domains/cad/allegro_extraction_tools.py:39` — the wrapper passes the supplied path straight through as `-p <project_file>`.
- `sigrity_mcp/domains/cad/allegro_extraction_tools.py:6-7` — designintent of the tool: "a standalone tool that dumps a design's connectivity/parasitic data to JSON, optionally pushing it straight to an Elasticsearch endpoint via `-u`. Distinct from Sigrity's own extraction tools (Clarity3D/XtractIM, Domain 3) — this reads Allegro's own design database/connectivity representation."

## Pipeline Impact

`run_allegro_design_extractor` **cannot** be used in any pipeline whose available design artifact is a bare `.brd` (which is the common case across this suite — most CAD tools take `.brd` directly). Any flow that wanted `designextractor`'s JSON connectivity/parasitic dump (optionally pushed to Elasticsearch via `-u`) from a board file is blocked unless a real `.cpm`/`.sdax` project file is staged first. Until a real project file is available, the `run_allegro_design_extractor` end-to-end path on this machine is `known_blocked`/`built_untested` (the argument shape is confirmed; a full successful run against a real project has never been executed here).
