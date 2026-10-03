# allegro_create_trace with Bare Layer Name Silently Returns Nil

**Slug**: `createtrace-bare-layer-name-silent-nil`
**Tool(s) affected**: `allegro_create_trace` (allegro_geometry_tools.py)
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

When `allegro_create_trace` was called with a bare layer name (e.g., `layer="TOP"`), the underlying SKILL call `axlDBCreatePath(path "TOP" "net_name")` silently returned **nil** — no path was created at all (0 segments, `Missing Connections: 1` on an otherwise-clean board) — even though the call raised no error and the job exited rc 0. The trace simply did not exist. The failure was invisible in the job log (SKILL return values never surface there). The same points/net on the same board, when the layer was passed as the full class/subclass string `"ETCH/TOP"`, produced a real connected path.

This was a real bug in the tool's original implementation: it passed the caller's bare layer name straight to `axlDBCreatePath`'s `t_layer` argument. The vendored `axlDBCreatePath.txt` doc's own worked example uses the full class/subclass string (`axlDBCreatePath(path "ETCH/TOP" "gnd")` — note "ETCH/TOP", not bare "TOP"), the same convention `allegro_create_copper_shape` already builds correctly for shapes (`"BOUNDARY/<layer>"`/`"ETCH/<layer>"`).

## Root Cause

`axlDBCreatePath` requires a full class/subclass string (e.g., `"ETCH/TOP"`) for its `t_layer` argument, not a bare layer name (e.g., `"TOP"`). A bare layer name is not a valid layer specification for this SKILL function — it silently fails (returns nil) rather than raising an error. The original `allegro_create_trace` implementation did not prepend the required class prefix, so every call with a bare layer name produced a nil return and no path.

This instance is now FIXED: the tool builds `"ETCH/<layer>"` automatically via the `_etch_layer_arg` helper (same convention `allegro_create_copper_shape` uses). It is tolerant of a caller who already passes a full class/subclass string (containing `/`) — only bare names get `"ETCH/"` prepended.

## Evidence

- `sigrity_mcp/core/tool_status.py:316-322` — "TWO ADDITIONAL REAL, PREVIOUSLY-UNDISCOVERED BUGS were found and FIXED in the existing (confirmed_live) `allegro_create_trace` tool while exercising this live rip-up-and-refix cycle: (a) it passed the caller's bare layer name (e.g. `\"TOP\"`) straight to `axlDBCreatePath`'s t_layer argument; the vendored `axlDBCreatePath.txt` doc's own worked example uses the full class/subclass string (`\"ETCH/TOP\"`) -- live-reproduced the bare form silently creating NOTHING (nil return, 0 segments, `Missing Connections: 1` on an otherwise-clean board) even though the job still exited rc 0; fixed by building `\"ETCH/<layer>\"` automatically (same convention `allegro_create_copper_shape` already used correctly for shapes)."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:115-137` (`_etch_layer_arg` docstring) — "BUG FIX (found live 2026-10-02, via this project's own routing-capability investigation): the original implementation passed the caller's bare layer name (e.g. `\"TOP\"`) straight through as `t_layer`. The vendored `axlDBCreatePath.txt` doc's own worked example uses the full class/subclass string instead (`axlDBCreatePath(path \"ETCH/TOP\" \"gnd\")` — note \"ETCH/TOP\", not bare \"TOP\"), the same convention `allegro_create_copper_shape` already builds correctly for shapes. LIVE-REPRODUCED on the real Fault-Detector sample: calling this tool with the old bare-`\"TOP\"` behavior against a real ripped-up net, then saving/running/independently re-verifying via `run_allegro_report(..., report_code=\"sum\")`, showed `axlDBCreatePath` silently returning nil — NO path was created at all (0 segments on either pin, `Missing Connections: 1`), even though the call itself raised no error and the job still exited rc 0. Switching to the real `\"ETCH/<layer>\"` form fixed it."
- `.forjinn/skills/sigrity-cad/SKILL.md:449-452` (Task 9, bug 1) — "**Layer string**: passed the bare layer name (`\"TOP\"`) straight to `axlDBCreatePath`'s `t_layer` arg. The vendored doc's own example uses `\"ETCH/TOP\"`. Bare `\"TOP\"` silently created NOTHING (nil return, 0 segments, `Missing Connections: 1`) even on `rc 0`. Now fixed: builds `\"ETCH/<layer>\"` automatically (same as `allegro_create_copper_shape`)."

## Pipeline Impact

Affects any trace-creation pipeline that uses `allegro_create_trace` with a bare layer name (the common case — callers pass `"TOP"`, `"BOTTOM"`, `"L3_SIG1"`, etc., not `"ETCH/TOP"`). Before the fix, every such call silently created nothing. After the fix, the tool automatically builds the correct class/subclass string. The failure mode is dangerous because the job exits rc 0 and `state` is "succeeded" — the only way to detect the nil return is to independently verify via `run_allegro_report(report_code="sum")` (`Missing Connections` should be 0 for a successful trace) or `run_allegro_report(report_code="drc")` (the targeted violation should clear).
