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

`allegro_create_copper_shape` (`axlDBCreateShape`) closes a real, high-leverage gap found
in a later pass: `generate_multilayer_stackup`/`allegro_create_stackup`
(`rigid_flex_stackup_tools.py`/`allegro_tools.py`) author layer STRUCTURE (name/type/
material/thickness via `axlXSectionCreate`) but never create any actual copper geometry —
a "PLANE"-typed layer from those tools is a cross-section definition only, zero copper
poured onto it. This was the suspected root cause of PowerDC `pdcVRM` binds failing with
"The net pair ... is not specified" against boards built purely from
`generate_multilayer_stackup` (nothing physical on the plane layer to attach to). The
vendored `axlDBCreateOpenShape.txt` doc is explicit that the same `axlDBCreateShape`
call becomes a real connectivity-driven dynamic "plane pour" (not a fixed polygon) simply
by using class `BOUNDARY` instead of `ETCH` in the layer string (`"BOUNDARY/<layer>"` vs
`"ETCH/<layer>"`) — confirmed against the real worked example
`share/pcb/examples/skill/dbcreate/axldbctshp.il` (`dbc_shp_t2`: a solid-filled
`"ETCH/TOP"` shape assigned to net `"GND"`). See `allegro_create_copper_shape`'s own
docstring for the live before/after PowerDC test and its result.
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
    """Create a routed trace (a \"path\"/cline) on a given etch layer and net, within the current Allegro SKILL session.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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


def _closed_path_expr(points: list[list[float]]) -> str:
    """Build an r_path SKILL expression (`axlPathStart`) from a boundary point list,
    auto-closing it if the caller didn't repeat the first point as the last one.

    Per the vendored doc (`axlDBCreateOpenShape.txt` NOTE): "A path starts at startPoint
    and a segment is created for each segment in the pathList. If the path does not end
    at the startPoint IT IS considered AN ERROR" -- the same restriction applies to
    `axlDBCreateShape`, which takes the same arguments.
    """
    pts = [list(p) for p in points]
    if pts and (pts[0][0] != pts[-1][0] or pts[0][1] != pts[-1][1]):
        pts.append(pts[0])
    return f"(axlPathStart {_point_list(pts)})"


@mcp.tool
async def allegro_create_copper_shape(
    session_id: str,
    layer: str,
    net_name: str,
    points: list[list[float]],
    dynamic: bool = True,
) -> dict:
    """Pour a real, solid-filled copper shape onto a cross-section layer and assign it to
    a net (`axlDBCreateShape`), within the current Allegro SKILL session.

    This is the real fix for the gap `generate_multilayer_stackup`/`allegro_create_stackup`
    leave open (see this module's docstring): those tools author layer STRUCTURE via
    `axlXSectionCreate` but never create actual copper — a "PLANE"-typed layer is a bare
    cross-section definition with nothing physical on it. This tool creates the actual
    shape/pour and binds it to a net in one real SKILL call.

    `layer` is the BARE xsection/etch layer name (e.g. `"L2_GND"`, matching the `name` you
    gave `generate_multilayer_stackup`/`allegro_create_stackup`) — NOT a full
    class/subclass string. This tool builds the class/subclass itself from `dynamic`:
      - `dynamic=True` (default): `"BOUNDARY/<layer>"` — per the vendored doc
        (`axlDBCreateOpenShape.txt`: "A static shape is created if you create shape on
        class ETCH, dynamic shapes are created if class is BOUNDARY ... The same rule
        also applies to axlDBCreateShape"), this is a real connectivity-driven "plane
        pour" that conforms to its net and re-floods on update (`axlDBDynamicShapes`) —
        what PCB designers mean by a "copper pour"/"plane shape", not a fixed polygon.
        LIVE-CONFIRMED on a real board (see this tool's own module and
        `.forjinn/skills/sigrity-cad/SKILL.md`): `axlDBGetShapes("BOUNDARY/<layer>")`
        read back a real non-nil shape dbid after this call + save + run.
      - `dynamic=False`: `"ETCH/<layer>"` — a plain static filled copper shape (e.g. for
        a CONDUCTOR/signal layer where a fixed polygon is actually what's wanted).

    `points`: an explicit closed boundary as `[[x, y], ...]` in board (design) units —
    auto-closed if you omit the repeated first/last point (see `_closed_path_expr`).
    REQUIRED, deliberately with NO auto-derive-from-board-outline default: an earlier
    design considered defaulting to `(car (axlPolyFromDB (car (axlDBGetShapes "BOARD
    GEOMETRY/OUTLINE"))))` ("pour the whole board outline" with no coordinates needed) but
    this was LIVE-TESTED and DISPROVEN against a real board (the Fault-Detector sample):
    `axlDBGetShapes("BOARD GEOMETRY/OUTLINE")` returned `nil` — a real board's physical
    outline is typically drawn as plain LINE/ARC segments, not a "shape" database object,
    so there is nothing for `axlDBGetShapes` to find there (confirmed: this board has 157
    real shapes total, all of them `PACKAGE GEOMETRY/*` component silkscreen/assembly/
    place-bound outlines — zero `BOARD GEOMETRY/*` shapes of any kind). A components-
    bounding-box fallback (`axlDBGetExtents(axlDBGetDesign()->components nil)`) was also
    tried live and returned a degenerate `((0.0 0.0) (0.0 0.0))` box, so it isn't a
    reliable substitute either. Rather than ship a default that silently pours nothing,
    this tool requires an explicit boundary — pass your own board outline coordinates
    (e.g. from your own design records, or from converting the outline's LINE segments via
    `axlDBComposeShapesFromLines` first, not wrapped by this tool) or any sub-region
    polygon you want poured.

    The shape is always solid-filled (`l_r_fill = t`) — an unfilled "pour" isn't real
    copper. Voids/keepouts are NOT handled by this minimal-scope tool; for anything beyond
    "cover this boundary solid on one layer/net", hand-write SKILL from the real worked
    example `share/pcb/examples/skill/dbcreate/axldbctshp.il` instead.

    VERIFY, don't trust this tool's return value: SKILL return values never surface here
    (see this module's docstring) — after `allegro_save_design` + `allegro_run_session`,
    independently confirm the shape landed (a captured `axlDBGetShapes("<class>/<layer>")`
    query is the reliable check; CONFIRMED LIVE this way 3 independent times, including a
    SECOND, fully separate Allegro process re-opening the saved board from disk — see
    `.forjinn/skills/sigrity-cad/SKILL.md` Task 7). This tool was originally built to test
    whether missing plane copper was blocking PowerDC `pdcVRM` net-pair binds — it was
    NOT: the exact same PowerDC error reproduced before and after pouring real,
    independently-verified copper (see `core.tool_status`'s `powerdc` note and
    `.forjinn/skills/sigrity-cad/SKILL.md` Task 7 for the full investigation). So this
    tool is confirmed to do what it says (pour real, net-bound copper) — just don't
    expect that alone to fix a `pdcVRM` net-pair failure.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if len(points) < 3:
        raise ValueError("An explicit shape boundary needs at least 3 points.")
    path_expr = _closed_path_expr(points)
    boundary_source = "explicit points"

    class_name = "BOUNDARY" if dynamic else "ETCH"
    skill_layer = f"{class_name}/{layer}"
    expr = f"(axlDBCreateShape {path_expr} t {skill_str(skill_layer)} {skill_str(net_name)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {
        "session_id": session_id,
        "layer": layer,
        "skill_layer": skill_layer,
        "net_name": net_name,
        "dynamic": dynamic,
        "boundary_source": boundary_source,
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    expr = f'(axlGetModuleInstanceLocation (car (axlSelectByName "GROUP" {skill_str(instance_name)})))'
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "instance_name": instance_name}
