# Workarounds: axlDBCreateModuleInstance Returns nil (axlGetParam nil)

## Verified Workaround

**No confirmed in-suite workaround exists yet** (`verified_workaround: None`). The blocker is a board/library-path content precondition, not a wrapper bug, so the remedy is to change the precondition — but that fix has **not** been confirmed end-to-end on this machine.

The known direction for a fix: call `allegro_place_module_instance` with a `module_def_name` that **does** resolve as a library-loadable module definition on the current board/library-path configuration (i.e. a name for which `axlGetParam("library:<module_def_name>")` returns non-nil). Per the tool's own module note: "Not yet confirmed working end-to-end against a module_def_name that does resolve this way." Until such a name is found and a real placed instance is read back, `allegro_place_module_instance` should be treated as `built_untested`/not-yet-working end-to-end for module creation.

Evidence: `sigrity_mcp/domains/cad/allegro_geometry_tools.py:53-54` — "Not yet confirmed working end-to-end against a module_def_name that does resolve this way — `allegro_get_module_instance_location` (read-only) remains `built_untested`."

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Use `module_def_name="CAP300"` (a symbol real board components already use) | didnt_work — `axlDBCreateModuleInstance` returned nil; `axlGetParam("library:CAP300")` also nil | `sigrity_mcp/domains/cad/allegro_geometry_tools.py:46-52` |
| 2 | Read the SKILL return value from the job log to confirm the nil | didnt_work (diagnosis only) — SKILL return values never surface in the job log; a return-value-capture file (SKILL `outfile`/`fprintf`) was required to observe the nil | `sigrity_mcp/domains/cad/allegro_geometry_tools.py:38-42` |
| 3 | Retry with a `module_def_name` known to resolve as a library module | unconfirmed — not yet demonstrated end-to-end on this board | `sigrity_mcp/domains/cad/allegro_geometry_tools.py:53-54` |

## What to Do to Unlock This (the precondition to satisfy)

The blocker is that the footprint cannot be resolved as a **library module** on the current board/library-path configuration. To make `allegro_place_module_instance` succeed:

1. Confirm the **library path** is set so the footprint's library is actually loadable in the session (a board can reference a footprint by name in its own design database while that name is not reachable through `axlGetParam("library:<name>")` if the owning library isn't on the resolvable path for this mechanism).
2. Pick a `module_def_name` for which `axlGetParam("library:<module_def_name>")` returns a real (non-nil) module definition. Verify this **before** calling `allegro_place_module_instance` (queue an `axlGetParam` query and capture its result via SKILL `outfile`/`fprintf`, since SKILL return values never surface in the job log).
3. Call `allegro_place_module_instance` only with a confirmed-resolvable name, then **verify with a read-back**: after `allegro_save_design` + `allegro_run_session`, use `allegro_get_module_instance_location(session_id, instance_name)` (read-only, currently `built_untested`) or an independent `report.exe -v bom`/`-v cmp` re-read to confirm the instance actually landed on the board. Do not trust the tool's return value or the job log (the log only shows the Allegro banner).

Note on the parallel path: `run_allegro_placement` (auto-placement) does **not** substitute for this — it is itself blocked on this board by the separate "No Package Keepin" precondition, and even where it works it places *existing* components rather than creating new module instances at explicit coordinates.

## Prevention

1. Treat `allegro_place_module_instance` as `built_untested` end-to-end until a module-creation success is captured against a resolvable `module_def_name` on a real board.
2. Do **not** confuse "a name the board's components already use" with "a name that resolves as a library module for `axlDBCreateModuleInstance`" — on this board those are different things (the name is referenced in the design DB but not independently library-loadable via `axlGetParam`).
3. Always verify module placement with an independent read-back (`allegro_get_module_instance_location` or `report.exe`), not by the tool return value or the job log (SKILL returns never appear in the job log — this is a project-wide constraint).
4. When this tool is retried, isolate the library-path variable explicitly: first prove `axlGetParam("library:<name>")` is non-nil in a fresh session, then attempt the place call, so a future nil is unambiguously a library-resolution failure rather than a session/path issue.

## Remaining Gaps

- No confirmed `module_def_name` that resolves as a library module on a real board has been found and verified end-to-end — so `allegro_place_module_instance` remains unproven in practice on this machine.
- `allegro_get_module_instance_location` (read-only) is implemented from the vendored doc but `built_untested`; it cannot be meaningfully tested until a placed instance exists, which the nil-precondition currently prevents.
- The exact board/library-path condition under which a footprint becomes independently resolvable via `axlGetParam("library:<name>")` (vs. being merely referenced in the design DB) is not isolated in the source — it is hypothesized to be a library-path/load configuration issue, not a naming issue.
- No in-suite tool wraps the "set/confirm the resolvable library path for module resolution" step; that is a board/session configuration the caller must establish.
