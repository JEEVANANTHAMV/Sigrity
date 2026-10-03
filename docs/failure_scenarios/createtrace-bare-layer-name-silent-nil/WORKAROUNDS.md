# Workarounds: allegro_create_trace with Bare Layer Name Silently Returns Nil

## Verified Workaround

The bug is FIXED in the current code. `allegro_create_trace` now automatically builds `"ETCH/<layer>"` via `_etch_layer_arg` (allegro_geometry_tools.py:115-137). Pass the bare layer name (e.g., `layer="TOP"`) — the tool prepends `"ETCH/"` automatically. If you already have a full class/subclass string (containing `/`), pass it directly — it is used as-is.

Re-verified live: the same points/net on the same board produced a real connected path with the `"ETCH/<layer>"` form, independently confirmed by `Missing Connections: 0`, the new path appearing in a pin's `axlDBGetConnect` traversal, and the targeted DRC violation clearing with no new ones.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Pass bare layer name (`layer="TOP"`) to current `allegro_create_trace` | worked — tool auto-builds `"ETCH/TOP"` | `allegro_geometry_tools.py:115-137`; `sigrity_mcp/core/tool_status.py:316-322` |
| 2 | Pass full class/subclass string (`layer="ETCH/TOP"`) to current `allegro_create_trace` | worked — used as-is | `allegro_geometry_tools.py:135-137` |
| 3 | Old implementation: bare layer name passed straight to `axlDBCreatePath` | didnt_work — nil return, 0 segments, `Missing Connections: 1`, rc 0 | `sigrity_mcp/core/tool_status.py:316-322`; SKILL.md Task 9 |

## Prevention

1. Use the current `allegro_create_trace` (with the fix). Pass the bare layer name or the full class/subclass string — both work.
2. ALWAYS verify trace creation with an independent read: `run_allegro_report(report_code="sum")` → `Missing Connections: 0` (or the expected count), and `run_allegro_report(report_code="drc")` → the targeted violation cleared. Do not trust `state:"succeeded"` or rc 0.
3. If you are using a vendored or older copy of this tool suite, check that `_etch_layer_arg` exists in `allegro_geometry_tools.py` and that `allegro_create_trace` calls it. The fix is in code, not in configuration.

## Remaining Gaps

None. The bug is fixed in code and re-verified live. The residual risk is a caller using an older/unpatched copy of the tool suite. The fix is documented in the tool's own docstring (`_etch_layer_arg`) and in SKILL.md Task 9.
