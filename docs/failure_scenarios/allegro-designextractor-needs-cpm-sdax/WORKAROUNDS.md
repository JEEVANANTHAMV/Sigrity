# Workarounds: designextractor Requires a .cpm/.sdax Project

## Verified Workaround

For direct `.brd` database extraction (BOM, nets, components, pins, test points, DRC, geometry), use **`run_allegro_extracta`** (`extracta.exe`) instead of `run_allegro_design_extractor`. extracta accepts a `.brd` directly and is `confirmed_live` end-to-end on this machine (real non-empty extracted data for the built-in views, `returncode=0`).

Evidence: `sigrity_mcp/core/tool_status.py:631-632` — "For direct .brd database extraction, use `allegro_extracta` (extracta.exe) instead."

`run_allegro_design_extractor` should only be used when a real, populated `.cpm`/`.sdax` **project file** exists as the input. If a pipeline genuinely needs the designextractor JSON/parastitic dump (or Elasticsearch push via `-u`), the precondition is a real project file — not a board file.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Use `run_allegro_extracta` for `.brd` extraction | worked (extracta is `confirmed_live`) | `sigrity_mcp/core/tool_status.py:631-632` |
| 2 | Pass a raw `.brd` to `designextractor.exe -p` | didnt_work — immediate usage-banner re-print (rejected at arg parsing) | `sigrity_mcp/core/tool_status.py:629-630` |
| 3 | Use one of the shipped `.cpm` templates under `share/cdssetup/pcbdw/workspaces/` | didnt_work — those are unfilled `@project@.cpm` templates, not real projects | `sigrity_mcp/domains/cad/allegro_extraction_tools.py:15-17` |

## Prevention

1. Do **not** pass a `.brd` to `run_allegro_design_extractor`; it will only re-print the usage banner. Reserve this tool for real `.cpm`/`.sdax` project files.
2. If the goal is to dump design data from a `.brd`, use `run_allegro_extracta` (headless, `confirmed_live`) — it is the right tool for `.brd`-level database extraction.
3. If a real designextractor run is genuinely needed, stage a **populated** `.cpm`/`.sdax` project (the shipped `share/cdssetup/pcbdw/workspaces/` files are unfilled templates and will not satisfy the tool) before invoking it.
4. Until a real project file is run through this tool successfully, treat `run_allegro_design_extractor` as `built_untested`/`known_blocked` — the wrapper's argument building is correct (it emits `-p <project_file>` plus optional `-o`/`-f`/`-u`/`-c`), but a full successful extraction has not been confirmed on this machine.

## Remaining Gaps

No real, populated `.cpm`/`.sdax` project instance was found on this machine to test `run_allegro_design_extractor` end-to-end. So:
- The `.brd`-input rejection is confirmed (the blocker itself is well-understood).
- The **successful** designextractor path (real project → JSON dump, optional Elasticsearch push) remains unexecuted here; the tool is `known_blocked` with respect to the common `.brd`-only case and `built_untested` with respect to the real-project case.
- The only in-suite route for `.brd` extraction is `run_allegro_extracta`; designextractor's JSON/Elasticsearch-specific capabilities have no confirmed in-suite substitute for a `.brd`.
