# Workarounds: TOP/BOTTOM Name Collision Causes Silent No-Op

## Verified Workaround

Drop the "TOP"/"BOTTOM"-named entries from the `layers` list before calling `generate_multilayer_stackup`. The board's physical outer layers already exist with their own pre-existing names and attributes; the stackup authoring tool only needs to create the INTERNAL layers. This is the recommended approach and is what the 18-layer definition effectively does (the 16 internal layers land correctly; the TOP/BOTTOM entries are silently skipped, which is fine if you intended them to stay as-is).

Evidence: `.forjinn/skills/sigrity-cad/SKILL.md:229-231` — "Either drop \"TOP\"/\"BOTTOM\"-named entries from `layers` (the physical outer layers already exist) or separately drive `axlXSectionGet(nil \"TOP\")` + `axlXSectionModify` + `axlXSectionSet` to actually change them (not wrapped by any tool yet)."

If you MUST change the outer layers' attributes (thickness, material), the only known path is to separately drive `axlXSectionGet(nil "TOP")` + `axlXSectionModify` + `axlXSectionSet` — this is NOT wrapped by any tool in this suite yet (manual SKILL scripting required).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Drop "TOP"/"BOTTOM"-named entries from `layers` list | worked — internal layers land correctly, outer layers keep pre-existing defaults | `sigrity_mcp/core/tool_status.py:198-203`; SKILL.md Task 6 |
| 2 | Keep "TOP"/"BOTTOM" entries and expect them to modify the existing outer layers | didnt_work — silent no-op, no change, no error | `sigrity_mcp/core/tool_status.py:198-203`; SKILL.md Task 6 TOP/BOTTOM NAME-COLLISION GOTCHA |
| 3 | `axlXSectionGet(nil "TOP")` + `axlXSectionModify` + `axlXSectionSet` to modify existing outer layers | known path, not wrapped by any tool yet (manual SKILL) | SKILL.md:230-231 |

## Prevention

1. Before calling `generate_multilayer_stackup`, check if your `layers` list contains entries named "TOP" or "BOTTOM". If yes, decide: (a) drop them (outer layers stay as board defaults), or (b) hand-write the `axlXSectionGet`/`axlXSectionModify`/`axlXSectionSet` SKILL calls in the same session after the stackup creation.
2. Always verify with an independent `run_allegro_report(..., report_code="x-section")` read-back and **compare the reported TOP/BOTTOM attributes against your intended input values**. A silent no-op is invisible in the job log and only detectable by content-matching the report against your intent.
3. When defining a multi-layer stackup definition function (like `build_18layer_rigid_flex_stackup_definition()`), document which layers are "created by the tool" vs "left as board defaults" so the caller knows what to expect in the `x-section` report.

## Remaining Gaps

- There is no tool wrapper for `axlXSectionGet` + `axlXSectionModify` + `axlXSectionSet` to modify existing outer layers. A caller who needs to change TOP/BOTTOM thickness/material must hand-write the SKILL calls.
- The silent no-op behavior means a caller who accidentally includes "TOP"/"BOTTOM" entries in their `layers` list will get a board with the wrong outer-layer attributes and no error to warn them. The only defense is the `x-section` report read-back with content comparison.
