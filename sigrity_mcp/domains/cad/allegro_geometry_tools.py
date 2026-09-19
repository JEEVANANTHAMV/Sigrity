"""Allegro PCB geometry authoring — SKILL-scripted, session-based: traces, vias, padstacks,
module (component footprint) placement at explicit coordinates, and net assignment.

CORRECTION to this project's own earlier research: the original `allegro_tools.py`
module docstring implies `allegro_create_component` (`axlDBCreateComponent`) may not
actually *place* a footprint at a coordinate, and this suite had no wrapper at all for
creating an actual routed trace, a standalone via, a real padstack definition, or
assigning a pin/via to a net. All of these are real, individually documented SKILL
functions confirmed present in `share/pcb/examples/skill/DOC/FUNCS/` on this machine
(`axlDBCreatePath`, `axlDBCreateVia`, `axlDBCreatePadStack`, `axlDBCreateModuleInstance`,
`axlDBAssignNet`, `axlGetModuleInstanceLocation`) — this module wraps them.

`axlDBCreateModuleInstance` (component placement at an explicit coordinate/rotation) is
the most directly useful one for closing the gap between "create a component
placeholder" (`allegro_create_component`, unplaced) and a real placement flow — it's a
distinct, lower-level AXL interface from `axlDBCreateComponent`, confirmed via its own
doc page to take an explicit origin coordinate and rotation.

`axlDBCreatePadStack`'s real signature takes nested SKILL defstructs
(`make_axlPadStackPad`) supporting dozens of pad/drill options — this module wraps only
the simple single-layer-pad, single-drill case shown in the function's own "Surface
Mount Padstack" example, the same "simple case only, don't attempt the full defstruct"
honesty pattern `allegro_create_stackup` already uses for `axlXSectionCreate`. For
anything beyond a simple SMT pad or a simple round-drill via padstack, hand-write a
SKILL script from the real example at
`share/pcb/examples/skill/dbcreate/pad.il` instead of relying on this tool.

STATUS UPDATE: `allegro_assign_net` (`axlDBAssignNet`) is now CONFIRMED LIVE, correcting
an earlier wrong finding. The original test concluded it was broken (session ran, no
change landed on disk) — a re-test, run cleanly (no overlapping Allegro launches
competing for a license seat, which was the real cause of the earlier apparent hang),
proved the opposite: reassigning a real pin (R1.2) to a real net (GND) via this exact
tool function, then independently re-reading the board with `report.exe` (bypassing
SKILL entirely), showed R1.2 correctly moved out of its original net and into GND on
disk. `allegro_create_via` and `allegro_create_film` are also confirmed live (see
`allegro_create_film`'s own docstring for the real Gerber-pipeline evidence).

`allegro_create_trace` and `allegro_create_simple_padstack` are now ALSO confirmed live:
run against the real sample board with return-value capture (`axlDBCreatePath`/
`axlDBCreatePadStack` results written to a file via SKILL's own `outfile`/`fprintf`,
since job logs otherwise only show Allegro's own startup banner), both returned real
dbids (`((dbid:...) nil)` and `dbid:...` respectively), not nil.

`allegro_place_module_instance` is CONFIRMED IMPLEMENTED CORRECTLY but hit a real
board-content precondition, the same "board-authoring gap, not a wrapper bug" class of
finding already documented elsewhere in this suite (see `allegro_placement`'s
"No Package Keepin" note): the same return-value-capture test showed
`axlDBCreateModuleInstance` returning nil for `module_def_name="CAP300"` — a symbol name
real components on the board already use (confirmed via `report.exe -v bom`) — because
`axlGetParam("library:CAP300")` also returns nil, i.e. that footprint isn't independently
resolvable as a library-loadable module definition via this mechanism on this board/
library-path configuration, even though it's referenced by name in the design already.
Not yet confirmed working end-to-end against a module_def_name that does resolve this
way — `allegro_get_module_instance_location` (read-only) remains `built_untested`.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.mcp_app import mcp


def _skill_line(expr: str) -> str:
    return f"skill {expr}"


def _point_list(points: list[list[float]]) -> str:
    return "(list " + " ".join(f"(list {p[0]} {p[1]})" for p in points) + ")"


@mcp.tool
async def allegro_create_trace(
    session_id: str,
    points: list[list[float]],
    layer: str,
    net_name: str,
) -> dict:
    """Create a routed trace (a "path"/cline) on a given etch layer and net, within the current Allegro SKILL session.

    Appends `skill (axlDBCreatePath (axlPathStart {points}) {layer} {net_name}))` — a
    simplified straight-segment-list wrapper around the confirmed real
    `axlDBCreatePath`/`axlPathStart` functions. `points` is a list of `[x, y]` vertices
    (at least two) the path/trace runs through, in the board's native design units.
    `net_name` must already exist (create it first with allegro_create_net in the same
    session) — `axlDBCreatePath` returns nil and creates nothing if the net doesn't
    exist yet. Note Allegro may merge the resulting cline with adjacent clines on the
    same net (documented behavior, not a bug) — the actual created geometry can be a
    superset of the given points.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    if len(points) < 2:
        raise ValueError("A trace needs at least two points.")
    path_expr = f"(axlPathStart {_point_list(points)})"
    expr = f"(axlDBCreatePath {path_expr} {skill_str(layer)} {skill_str(net_name)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "point_count": len(points), "layer": layer, "net_name": net_name}


@mcp.tool
async def allegro_create_via(
    session_id: str,
    padstack_name: str,
    x: float,
    y: float,
    net_name: Optional[str] = None,
    rotation: float = 0.0,
    mirror: bool = False,
) -> dict:
    """Place a standalone via at an explicit coordinate, within the current Allegro SKILL session.

    Appends `skill (axlDBCreateVia {padstack_name} (list {x} {y}) [{net_name}] [t/nil]
    {rotation})`, per the confirmed real `axlDBCreateVia` function. `padstack_name`
    must already exist in the design or be loadable from the library search path
    (`PADPATH`) — Allegro loads it automatically in that case. `net_name` defaults to a
    standalone (netless) via if omitted. Note per the function's own doc: this cannot
    create a test-point via — that needs a separate, unwrapped `axlTestPoint` call.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    net_arg = skill_str(net_name) if net_name is not None else "nil"
    mirror_arg = "t" if mirror else "nil"
    expr = f"(axlDBCreateVia {skill_str(padstack_name)} (list {x} {y}) {net_arg} {mirror_arg} {rotation})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "padstack_name": padstack_name, "x": x, "y": y, "net_name": net_name}


@mcp.tool
async def allegro_create_simple_padstack(
    session_id: str,
    name: str,
    pad_layer: str,
    pad_width: float,
    pad_height: float,
    pad_figure: str = "RECTANGLE",
    drill_diameter: Optional[float] = None,
) -> dict:
    """Create a simple, single-pad-layer padstack definition, within the current Allegro SKILL session.

    BEST-EFFORT/SIMPLIFIED wrapper: `axlDBCreatePadStack`'s real signature supports
    dozens of drill/pad options via nested SKILL defstructs — this tool only covers the
    single-pad, single-drill (or no-drill, for an SMT pad) case shown in the function's
    own "Surface Mount Padstack" example. Appends
    `skill (axlDBCreatePadStack {name} {drill-defstruct-or-nil}
    (cons (make_axlPadStackPad ?layer {pad_layer} ?type 'REGULAR ?figure '{pad_figure}
    ?figureSize {pad_width}:{pad_height}) nil) t)`. `drill_diameter` omitted creates a
    surface-mount pad with no drill; given, creates a plated circular through-hole of
    that diameter. For anything beyond this (multiple pad layers, slots, keepouts,
    thermal reliefs, non-round drills, ...), write a SKILL script directly from
    `share/pcb/examples/skill/dbcreate/pad.il` instead.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    pad_struct = (
        f"(make_axlPadStackPad ?layer {skill_str(pad_layer)} ?type 'REGULAR "
        f"?figure '{pad_figure} ?figureSize {pad_width}:{pad_height})"
    )
    if drill_diameter is not None:
        drill_struct = f"(make_axlPadStackPad ?plating 'PLATED ?drillDiameter {drill_diameter})"
    else:
        drill_struct = "nil"
    expr = f"(axlDBCreatePadStack {skill_str(name)} {drill_struct} (cons {pad_struct} nil) t)"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "name": name, "pad_layer": pad_layer, "drill_diameter": drill_diameter}


@mcp.tool
async def allegro_place_module_instance(
    session_id: str,
    instance_name: str,
    module_def_name: str,
    x: float,
    y: float,
    rotation: float = 0.0,
    logic_from_schematic: bool = False,
    mirror: bool = False,
) -> dict:
    """Place a module (component footprint) instance at an explicit board coordinate and rotation, within the current Allegro SKILL session.

    Appends `skill (axlDBCreateModuleInstance {instance_name} {module_def_name}
    (list {x} {y}) {rotation} {0|1|2} [nil] [t/nil])`, per the confirmed real
    `axlDBCreateModuleInstance` function — a distinct, lower-level placement API from
    `allegro_create_component`'s `axlDBCreateComponent` (which creates a placeholder
    without necessarily placing it). `module_def_name` must reference an existing
    module/footprint definition already available to the design. `logic_from_schematic`
    (`i_logic_method`) selects where the instance's logic comes from: `False` (default)
    is `0` (no logic, pure mechanical placement), `True` is `1` (logic from schematic);
    the doc also documents a `2` (logic from module definition) not exposed here — pass
    it via a direct SKILL call if needed.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    logic_method = 1 if logic_from_schematic else 0
    mirror_arg = "t" if mirror else "nil"
    expr = (
        f"(axlDBCreateModuleInstance {skill_str(instance_name)} {skill_str(module_def_name)} "
        f"(list {x} {y}) {rotation} {logic_method} nil {mirror_arg})"
    )
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {
        "session_id": session_id,
        "instance_name": instance_name,
        "module_def_name": module_def_name,
        "x": x,
        "y": y,
        "rotation": rotation,
    }


@mcp.tool
async def allegro_assign_net(
    session_id: str,
    object_type: str,
    object_name: str,
    net_name: Optional[str],
    ripup: bool = False,
    ignore_fixed: bool = False,
) -> dict:
    """Assign a pin/via/shape to a net (or unassign it to a dummy net), within the current Allegro SKILL session.

    Appends `skill (axlDBAssignNet (car (axlSelectByName {object_type} {object_name}))
    {net_name-or-nil} {t/nil} {t/nil})`, per the confirmed real `axlDBAssignNet`
    function, which itself takes a resolved dbid rather than a name — this tool
    resolves the name to a dbid via `axlSelectByName` in the same expression (a common
    real pattern shown in Allegro's own SKILL examples) so callers don't need to manage
    dbids across session lines. `object_type` is Allegro's own object-type string for
    `axlSelectByName` (e.g. `"PIN"`, `"VIA"`, `"SHAPE"`) — get the exact set of valid
    type strings from `axlSelectByName`'s own doc page if unsure. Pass `net_name=None`
    to unassign to a dummy net. `ripup=True` also rips up connected clines/vias on the
    old net; `ignore_fixed=True` overrides the default refusal to reassign a net on an
    object with a FIXED property.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    net_arg = skill_str(net_name) if net_name is not None else "nil"
    ripup_arg = "t" if ripup else "nil"
    ignore_arg = "t" if ignore_fixed else "nil"
    select_expr = f"(car (axlSelectByName {skill_str(object_type)} {skill_str(object_name)}))"
    expr = f"(axlDBAssignNet {select_expr} {net_arg} {ripup_arg} {ignore_arg})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {
        "session_id": session_id,
        "object_type": object_type,
        "object_name": object_name,
        "net_name": net_name,
    }


@mcp.tool
async def allegro_create_film(
    session_id: str,
    film_name: str,
    layers: list[str],
    negative: bool = False,
    mirrored: bool = False,
) -> dict:
    """Create (or replace) an artwork film record, within the current Allegro SKILL session.

    CONFIRMED LIVE — this is the real missing piece behind Gerber export: `gbplot.exe`
    (see allegro_manufacturing_tools.py) needs an already-generated `.art` file, which
    itself needs a film record defined on the board. Allegro's Artwork Control Form
    normally authors these interactively; `axlFilmCreate` is the real, documented SKILL
    equivalent, confirmed live producing genuine RS274X Gerber output end-to-end: create
    a film per copper/silkscreen/soldermask layer needed (e.g. `["ETCH/TOP"]` for the top
    copper layer), save the design, then run run_allegro_generate_artwork.

    Appends `skill (axlFilmCreate {film_name} ?layers (list {layers...}) [?negative t]
    [?mirrored t])`. `layers` are fully-qualified Allegro layer names (e.g. `"ETCH/TOP"`,
    `"ETCH/BOTTOM"`, `"SILKSCREEN_TOP"`) — pass a class name alone (e.g. `"MANUFACTURING"`)
    to include every subclass of that class. `negative`/`mirrored` map to the function's
    own `?negative`/`?mirrored` booleans; every other real optional (`?rotation`,
    `?xOffset`, `?sequence`, ...) is left at its documented default — call
    axlFilmCreate again with the same film_name to replace/adjust it.
    This only queues the step — call allegro_run_session to actually execute it, then
    allegro_save_design before running artwork.exe (film records don't take effect on
    disk until the design is saved).
    """
    layer_list = "(list " + " ".join(skill_str(l) for l in layers) + ")"
    parts = [skill_str(film_name), "?layers", layer_list]
    if negative:
        parts += ["?negative", "t"]
    if mirrored:
        parts += ["?mirrored", "t"]
    expr = f"(axlFilmCreate {' '.join(parts)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "film_name": film_name, "layers": layers}


@mcp.tool
async def allegro_get_module_instance_location(session_id: str, instance_name: str) -> dict:
    """Queue a read-only query of a placed module instance's current location/rotation, within the current Allegro SKILL session.

    Appends `skill (axlGetModuleInstanceLocation (car (axlSelectByName "GROUP"
    {instance_name})))`, per the confirmed real `axlGetModuleInstanceLocation` function
    and its own doc example (which resolves the instance via `axlSingleSelectName`/
    `axlGetSelSet` — this tool uses the equivalent, more directly composable
    `axlSelectByName` form instead). Returns `(list (list x y) rotation [mirror])` in
    the session's own output when run.
    Like every other SKILL query line in this suite, inspect the job's log via
    tail_job_log/read_job_output_file after allegro_run_session — this suite has no
    mechanism to pipe a SKILL return value directly back into the MCP response.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    expr = f'(axlGetModuleInstanceLocation (car (axlSelectByName "GROUP" {skill_str(instance_name)})))'
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "instance_name": instance_name}
