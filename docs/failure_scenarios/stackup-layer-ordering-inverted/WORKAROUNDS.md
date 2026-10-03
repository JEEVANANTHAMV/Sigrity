# Workarounds: Stackup Layer Ordering Inverted by 'bottom' Queuing

## Verified Workaround

Queue layers in top-to-bottom order (index 0 = physical top) — do NOT reverse the list. The tool `generate_multilayer_stackup` queues each layer via `axlXSectionCreate(nil 'bottom <defstruct>)` in the same order the caller passes them, and each successive `'bottom` insert lands adjacent to the board's real outer BOTTOM layer, pushing earlier inserts up. This is the exact opposite of the literal reading of `axlXSectionCreate.txt`'s doc tip.

Confirmed live 4 times against fresh copies of the real sample board, each independently verified by `run_allegro_report(..., report_code="x-section")` read-back.

Evidence: `.forjinn/skills/sigrity-cad/SKILL.md:211-222` (Task 6, ORDERING GOTCHA + Verified artifact).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Queue layers top-to-bottom (index 0 = top), use `'bottom` endpoint | worked | `sigrity_mcp/core/tool_status.py:193-197`; SKILL.md Task 6 |
| 2 | Queue layers bottom-to-top (literal reading of `axlXSectionCreate.txt` doc tip) | didnt_work — produced inverted order | `sigrity_mcp/core/tool_status.py:195-196`; SKILL.md Task 6 ORDERING GOTCHA |
| 3 | Use `'top` or `'afterBottom` endpoint instead | not_usable — restricted by Allegro to unnamed dielectric/MASK layers for PCB designs | `.forjinn/skills/sigrity-cad/SKILL.md:221-222` |

## Prevention

1. When using `generate_multilayer_stackup`, always pass `layers` in top-to-bottom order (index 0 = physical top). The tool's docstring and SKILL.md both state this explicitly.
2. After any stackup authoring run, ALWAYS verify with an independent `run_allegro_report(..., report_code="x-section")` read-back — never trust `state:"succeeded"` alone. SKILL return values never surface in the job log.
3. If using the raw `axlXSectionCreate(nil 'bottom <defstruct>)` SKILL call directly (outside the tool wrapper), queue in the same top-to-bottom order, not the doc-tip's bottom-to-top order.

## Remaining Gaps

None. The ordering behavior is fully characterized and the workaround is confirmed live. The residual risk is a caller who reads Cadence's vendored `axlXSectionCreate.txt` doc tip in isolation (without the live-verification evidence recorded here) and reverses the list. The tool wrapper's docstring and SKILL.md now both warn about this explicitly, and the `x-section` report read-back is the reliable verify step.
