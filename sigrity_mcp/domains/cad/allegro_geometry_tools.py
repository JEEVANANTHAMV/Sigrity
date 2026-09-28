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
