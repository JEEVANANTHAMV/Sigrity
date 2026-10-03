# Workarounds: allegro_create_trace with No Width Creates Zero-Width Copper

## Verified Workaround

The bug is FIXED in the current code. `allegro_create_trace` now has a REQUIRED `width` parameter (no silent default). Always pass a real width (e.g., this board's own actual `5.0` mil, read from `run_allegro_report(..., report_code="sum")`'s "Trace Width By Layer" table). Passing a real `width` produced a normal, DRC-clean trace with no neck-width violations.

There is deliberately no silent default here — always read the board's real existing trace width for the layer/net you're routing on rather than guessing.

Evidence: `sigrity_mcp/domains/cad/allegro_geometry_tools.py:174-176` — "There is deliberately no silent default here — always read the board's real existing trace width for the layer/net you're routing on rather than guessing."

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Pass a real `width` (e.g., `width=5.0` read from the board's "Trace Width By Layer" report) | worked — normal, DRC-clean trace | `sigrity_mcp/core/tool_status.py:328-329`; SKILL.md Task 9 |
| 2 | Omit `width` (old implementation: `axlPathStart(points)` with no second arg) | didnt_work — zero-width copper, real DRC violations | `sigrity_mcp/core/tool_status.py:323-328`; SKILL.md Task 9 |
| 3 | "Inherit the board's/net's default trace width" (assumption when omitting `width`) | didnt_work — Allegro does NOT inherit; width defaults to 0 | `axlPathStart.txt` doc (vendored); `allegro_geometry_tools.py:162-165` |

## Prevention

1. Use the current `allegro_create_trace` (with the fix). Always pass a real `width` value. Do not pass `width=0.0` unless you intentionally want zero-width copper (which will violate DRC).
2. Read the board's real existing trace width from `run_allegro_report(..., report_code="sum")`'s "Trace Width By Layer" table before choosing a width. Do not guess.
3. After trace creation, verify with `run_allegro_batch_drc` + `run_allegro_report(report_code="drc")` → no "Minimum Neck Width" or near-zero-clearance violations on the new trace. If a zero-width trace is suspected, query `axlDBGetConnect`'s segment/width attributes via a SKILL `outfile`/`fprintf` capture.
4. If you are using a vendored or older copy of this tool suite, check that `width` is a required parameter in `allegro_create_trace`'s signature and that `axlPathStart` is called with the width as its second argument.

## Remaining Gaps

None. The bug is fixed in code and re-verified live. The residual risk is a caller using an older/unpatched copy of the tool suite, or a caller who passes an intentionally wrong width value (e.g., `width=0.5` mil when the board's minimum is 5 mil) — the tool does not validate the width against the board's DRC rules; it passes whatever value the caller provides straight through to `axlPathStart`.
