# axlDBCreateModuleInstance Returns nil — axlGetParam("library:<name>") Can't Resolve the Footprint

**Slug**: `module-instance-axlget-param-nil`
**Tool(s) affected**: `allegro_place_module_instance` (`sigrity_mcp/domains/cad/allegro_geometry_tools.py`), `allegro_get_module_instance_location` (same file, read-only counterpart)
**Status category**: `precondition_error`
**Pipeline stage**: placement / design (component footprint placement)

## Symptom

`allegro_place_module_instance` (which emits a real `axlDBCreateModuleInstance` SKILL call to place a component footprint at an explicit coordinate/rotation) returns `nil` — no module instance is created — even for a symbol name that the board's components *already use*. In the live test, `axlDBCreateModuleInstance` returned `nil` for `module_def_name="CAP300"`, a symbol name `report.exe -v bom` confirms real components on the board already use. The companion read-only query `axlGetParam("library:CAP300")` **also** returns `nil` for the same name.

So the footprint `CAP300` is referenced by name inside the loaded design, yet it is **not independently resolvable as a library-loadable module definition** via `axlGetParam`/`axlDBCreateModuleInstance` on this board/library-path configuration.

## Root Cause

A board/library-path precondition is unmet, not a wrapper bug. `axlDBCreateModuleInstance` (component placement at an explicit coordinate) needs to be able to resolve the `module_def_name` as a loadable module definition from the library path. On this board/library configuration, the footprints already placed in the design are referenced in the design database but are **not reachable** as standalone library module definitions through `axlGetParam("library:<name>")`. Because the resolution step returns `nil`, `axlDBCreateModuleInstance` has nothing to instantiate and returns `nil`. The tool is implemented correctly (verified against the vendored `axlDBCreateModuleInstance` doc and the return-value-capture test); the failure is that the specific `module_def_name` cannot be resolved as a library module on this board.

## Evidence

- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:13-17` — "`axlDBCreateModuleInstance` (component placement at an explicit coordinate/rotation) is the most directly useful one for closing the gap between 'create a component placeholder' (`allegro_create_component`, unplaced) and a real placement flow — it's a distinct, lower-level AXL interface from `axlDBCreateComponent`, confirmed via its own doc page to take an explicit origin coordinate and rotation."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:44-54` — module docstring STATUS UPDATE: "`allegro_place_module_instance` is CONFIRMED IMPLEMENTED CORRECTLY but hit a real board-content precondition, the same "board-authoring gap, not a wrapper bug" class of finding already documented elsewhere in this suite (see `allegro_placement`'s "No Package Keepin" note): the same return-value-capture test showed `axlDBCreateModuleInstance` returning nil for `module_def_name=\"CAP300\"` — a symbol name real components on the board already use (confirmed via `report.exe -v bom`) — because `axlGetParam(\"library:CAP300\")` also returns nil, i.e. that footprint isn't independently resolvable as a library-loadable module definition via this mechanism on this board/library-path configuration, even though it's referenced by name in the design already. Not yet confirmed working end-to-end against a module_def_name that does resolve this way — `allegro_get_module_instance_location` (read-only) remains `built_untested`."
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:238-265` — `allegro_place_module_instance` builds the real call: `(axlDBCreateModuleInstance <instance_name> <module_def_name> (list x y) <rotation> <logic_method> nil <mirror>)`. The `module_def_name` is the argument that must resolve as a library module; when it doesn't, the call returns nil (SKILL return values never surface in the job log, so this is only visible via the return-value-capture file).
- `sigrity_mcp/domains/cad/allegro_geometry_tools.py:473-479` — `allegro_get_module_instance_location` (the read-only query for an already-placed instance) is implemented from the vendored doc but remains `built_untested` (it depends on a successfully-placed instance existing to read back, which the nil-precondition prevents).

## Pipeline Impact

Headless *placement of a new module instance* at explicit coordinates is blocked for any `module_def_name` that cannot be resolved as a library module on the current board/library-path configuration. This is the same "board-authoring gap, not a wrapper bug" class as the `allegro_placement` "No Package Keepin" blocker: the tool and the AXL call are correct, but a board/library precondition is unmet. Consequences:

- Any pipeline that wants to *add* a component footprint at a coordinate (rather than work with components already on the board) cannot rely on `allegro_place_module_instance` unless a resolvable `module_def_name` is available.
- The read-back helper `allegro_get_module_instance_location` is effectively untested as a real flow because it depends on a placed instance existing (which the nil return prevents here).
- A workaround in the suite's own placement flow (`run_allegro_placement`) does **not** cure this: auto-placement also failed on this board (No Package Keepin), and its success depends on different board content than the library-resolution precondition blocking `axlDBCreateModuleInstance`.
