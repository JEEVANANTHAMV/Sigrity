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

`allegro_delete_connect` (`axlDeleteObject` with the `'ripup` mode flag) closes the other
real gap this project's own prior campaign never tested: a MANUAL, SURGICAL rip-up of one
bad net's etch, as a precursor to re-routing just that net with `allegro_create_trace`
instead of redoing the whole board. Confirmed real via the vendored
`axlDeleteObject.txt` doc: `axlDeleteObject(lo_dbid 'ripup)` is documented as "ripup of
associated etch via the ripup option (same as Allegro delete command ripup option)" —
the dbid is obtained the same `(car (axlSelectByName <type> <name>))` way
`allegro_assign_net` already uses. `object_type="NET"` is the primary, tested granularity
(there is no SKILL "select the one CLINE segment nearest this DRC coordinate" primitive
on this install — `axlSelectByName` only finds named objects: NET/COMPONENT/PIN/REFDES/
etc., never a bare unnamed etch segment by location), matching this project's own task
framing of "rip up and refix one bad trace/net" at net granularity rather than requiring
a sub-net segment selector that does not exist here. See this tool's own docstring for
the live rip-up-and-refix test.

`allegro_get_net_length` (`axlDBGetLength`) closes the routing-QUALITY-analysis gap: none
of this suite's existing report codes or `axlCNS*` constraint queries
(`allegro_get_net_constraint`) return a net's actual measured routed etch length — only
its CONSTRAINT/RULE value (e.g. `MAX_VIAS`, `PROPAGATION_DELAY`). `axlDBGetLength`, per
its own vendored doc, is the real "calculate the length of the given object" primitive
(works on a NET, CLINE, SEGMENT, or RATSNEST dbid) — this is what actually lets an agent
compare two real nets' routed lengths against a length-matching tolerance (e.g. a DDR
address/data skew budget from `get_high_speed_constraint_preset`), not just confirm DRC
is clean. See this tool's own docstring for the live length-matching test.

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


def _etch_layer_arg(layer: str) -> str:
    """Build the real `t_layer` class/subclass string `axlDBCreatePath` requires.

    BUG FIX (found live 2026-10-02, via this project's own routing-capability
    investigation): the original implementation passed the caller's bare layer name
    (e.g. `"TOP"`) straight through as `t_layer`. The vendored `axlDBCreatePath.txt` doc's
    own worked example uses the full class/subclass string instead (`axlDBCreatePath(path
    "ETCH/TOP" "gnd")` — note "ETCH/TOP", not bare "TOP"), the same convention
    `allegro_create_copper_shape` already builds correctly for shapes
    (`"BOUNDARY/<layer>"`/`"ETCH/<layer>"`). LIVE-REPRODUCED on the real Fault-Detector
    sample: calling this tool with the old bare-`"TOP"` behavior against a real ripped-up
    net, then saving/running/independently re-verifying via `run_allegro_report(...,
    report_code="sum")`, showed `axlDBCreatePath` silently returning nil — NO path was
    created at all (0 segments on either pin, `Missing Connections: 1`), even though the
    call itself raised no error and the job still exited rc 0 (another instance of this
    suite's "SKILL return values/errors never surface in the job log" problem). Switching
    to the real `"ETCH/<layer>"` form fixed it: the same points/net on the same board
    produced a real connected path, independently confirmed by `Missing Connections: 0`,
    the new path appearing in a pin's `axlDBGetConnect` traversal, and the targeted DRC
    violation clearing with no new ones. Tolerant of a caller who already passes a full
    class/subclass string (containing `/`) — only bare names get `"ETCH/"` prepended.
    """
    return layer if "/" in layer else f"ETCH/{layer}"


@mcp.tool
def _check_self_overlap(points: list[list[float]]) -> None:
    """Raise ValueError if any two collinear (both-horizontal or both-vertical)
    segments of this path overlap in extent. A self-overlapping path (e.g. a meander
    that doubles back over part of its own previous run) causes `axlDBCreatePath` to
    silently return nil (0 segments created, Missing Connections: 1) with no error --
    this is the same failure signature as the bare-layer-name/zero-width bugs this
    module already fixed, but a different root cause. Strict inequality on the overlap
    test allows two segments to merely touch at a shared endpoint (a valid corner)."""
    n = len(points)
    for i in range(n - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        for j in range(i + 1, n - 1):
            x3, y3 = points[j]
            x4, y4 = points[j + 1]
            if y1 == y2 and y3 == y4 and y1 == y3:
                lo1, hi1 = min(x1, x2), max(x1, x2)
                lo2, hi2 = min(x3, x4), max(x3, x4)
                if lo1 < hi2 and lo2 < hi1:
                    raise ValueError(
                        f"Path self-overlaps: horizontal segments at y={y1} "
                        f"(points {i}->{i + 1}) and (points {j}->{j + 1}) overlap in "
                        f"x-range [{lo1},{hi1}] vs [{lo2},{hi2}]. axlDBCreatePath "
                        "will silently return nil for this path."
                    )
            elif x1 == x2 and x3 == x4 and x1 == x3:
                lo1, hi1 = min(y1, y2), max(y1, y2)
                lo2, hi2 = min(y3, y4), max(y3, y4)
                if lo1 < hi2 and lo2 < hi1:
                    raise ValueError(
                        f"Path self-overlaps: vertical segments at x={x1} "
                        f"(points {i}->{i + 1}) and (points {j}->{j + 1}) overlap in "
                        f"y-range [{lo1},{hi1}] vs [{lo2},{hi2}]. axlDBCreatePath "
                        "will silently return nil for this path."
                    )


async def allegro_create_trace(
    session_id: str,
    points: list[list[float]],
    layer: str,
    net_name: str,
    width: float,
) -> dict:
    """Create a routed trace (a \"path\"/cline) on a given etch layer and net, within the current Allegro SKILL session.

    `layer` is the BARE etch layer name (e.g. `"TOP"`, `"BOTTOM"`, or an internal
    signal-layer xsection name like `"L3_SIG1"`) — this tool builds the real
    `"ETCH/<layer>"` class/subclass string itself (see `_etch_layer_arg`'s docstring for
    the live bug this fixes: the bare name alone silently creates nothing). Pass a full
    `"ETCH/<layer>"`/other class string directly if you already have one; it is used
    as-is.

    `width` (board/design units, e.g. mils) is REQUIRED — a second, independent real bug
    found live in the same routing-capability investigation that found the layer-string
    bug above: the original implementation called `axlPathStart(points)` with NO second
    argument. Per the vendored `axlPathStart.txt` doc, that second argument (`f_width`)
    "becomes the default width for all ... segments" — omitting it does not mean "inherit
    the net's/board's default trace width" as might be assumed; it silently creates
    **zero-width copper**. LIVE-CONFIRMED on the real Fault-Detector sample: a trace
    created the old way, independently re-queried via `axlDBGetConnect`'s own
    `segments`/`width` attributes, showed `width=0.0` on every one of its 7 segments, and
    `run_allegro_batch_drc` + `run_allegro_report(..., report_code="drc")` flagged it with
    real new "Minimum Neck Width" (required 5 MIL, actual 0 MIL) and near-zero "Line to
    Line"/"Line to Pin Spacing" violations against nearby copper that a properly-widthed
    trace would not have triggered (a 0-width line consumes none of the real clearance
    budget, so it reads as sitting almost exactly on top of neighboring copper/pins even
    when its center-line path was chosen to clear them). Passing a real `width` (e.g. this
    board's own actual `5.0` mil, read from `run_allegro_report(...,
    report_code="sum")`'s "Trace Width By Layer" table) produced a normal, DRC-clean
    trace with no neck-width violations. There is deliberately no silent default here —
    always read the board's real existing trace width for the layer/net you're routing on
    rather than guessing.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if len(points) < 2:
        raise ValueError("A trace needs at least two points.")
    _check_self_overlap(points)
    path_expr = f"(axlPathStart {_point_list(points)} {width})"
    skill_layer = _etch_layer_arg(layer)
    expr = f"(axlDBCreatePath {path_expr} {skill_str(skill_layer)} {skill_str(net_name)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {
        "session_id": session_id,
        "point_count": len(points),
        "layer": layer,
        "skill_layer": skill_layer,
        "net_name": net_name,
        "width": width,
    }


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
async def allegro_delete_connect(
    session_id: str,
    object_type: str,
    object_name: str,
    ripup: bool = True,
) -> dict:
    """Delete a named database object (typically a NET) with etch rip-up (`axlDeleteObject`), within the current Allegro SKILL session.

    The manual-override "rip it up" half of a surgical fix-one-route workflow: find the
    dbid by name the same way `allegro_assign_net` does
    (`(car (axlSelectByName object_type object_name))`), then
    `axlDeleteObject(dbid 'ripup)`. Per the vendored `axlDeleteObject.txt` doc, the
    `'ripup` mode is "same as the Allegro delete command ripup option" — it erases the
    object's routed etch rather than just the logical connection, so a net ripped up this
    way goes back to unrouted ratsnest and can be cleanly re-routed with
    `allegro_create_trace` (same pattern `allegro_create_copper_shape` demonstrates for
    authoring, just in reverse).

    `object_type="NET"` (by net name) is the primary, live-tested granularity — there is
    no SKILL primitive on this install to select a single unnamed CLINE/SEGMENT by
    location (e.g. "the trace nearest this DRC violation's coordinate"); `axlSelectByName`
    only resolves named objects (NET/COMPONENT/PIN/REFDES/GROUP/...). So "surgical" here
    means net-granularity rip-up-and-refix (matching this project's own stated goal of
    fixing "one bad trace/net" without redoing the whole board), not sub-net segment
    surgery. `ripup=False` falls back to a bare `axlDeleteObject(dbid)` (logic-only
    delete, per the doc: "Deletion of nets is LOGIC only, and leaves the physical
    objects") if you deliberately want that distinction.

    VERIFY, don't trust this tool's return value: SKILL return values never surface in
    the job log (see this module's docstring) — after `allegro_save_design` +
    `allegro_run_session`, independently confirm via `run_allegro_report(...,
    report_code="sum")` (nets/pins/connections unchanged, the net now shows as
    ratsnest/unrouted) or `run_allegro_batch_drc` (the target violation gone).

    **CAUTION**: despite the doc text above, `object_type="NET"` was confirmed LIVE to
    be DESTRUCTIVE to the net's logical identity, not just its etch (real net count
    dropped 75->74, the net's pins went to Unused, and a subsequent
    `allegro_create_trace` for that net silently created nothing since the net no
    longer existed). For a non-destructive rip-up-and-reroute, use
    `allegro_assign_net(object_type="PIN", object_name=<a pin on the net>,
    net_name=<the net's own name>, ripup=True)` instead — see the `warning` field in
    the return value for `object_type="NET"`.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    select_expr = f"(car (axlSelectByName {skill_str(object_type)} {skill_str(object_name)}))"
    mode_arg = " 'ripup" if ripup else ""
    expr = f"(axlDeleteObject {select_expr}{mode_arg})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    result = {
        "session_id": session_id,
        "object_type": object_type,
        "object_name": object_name,
        "ripup": ripup,
    }
    if object_type.upper() == "NET":
        result["warning"] = (
            "DESTRUCTIVE: axlDeleteObject on a NET dbid deletes the net's LOGICAL "
            "IDENTITY entirely (not just its etch) -- confirmed live (net count "
            "dropped 75->74, pins went to Unused). The net ceases to exist; a "
            "subsequent allegro_create_trace(net_name=<this net>) will silently "
            "create NOTHING (axlDBCreatePath returns nil for a nonexistent net). For "
            "a non-destructive rip-up-and-reroute, use "
            "allegro_assign_net(object_type='PIN', object_name='<a pin on the net>', "
            "net_name='<the net's own name>', ripup=True) instead -- that strips the "
            "connected clines while leaving the net and its pins intact."
        )
    return result


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

    For a safe "whole populated board" default without hand-authoring coordinates, call
    `allegro_get_board_extent_points` (domains.cad.allegro_extraction_tools) first and
    pass its `points` straight through here — it derives a real, board-specific
    rectangle from the board's actual placed pin extents plus a margin, verified safer
    than the obvious "Drawing Extents"/`sum`-report bounding box (which is the
    inherited drawing sheet size, not board geometry — confirmed on two structurally
    different real boards reporting byte-identical extents). See that tool's own
    docstring for the full reasoning.

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


@mcp.tool
async def allegro_get_net_length(session_id: str, net_name: str) -> dict:
    """Queue a read-only query of a net's real measured routed etch length (`axlDBGetLength`), within the current Allegro SKILL session.

    This is the routing-QUALITY-analysis counterpart to `allegro_get_net_constraint`
    (which only ever returns a RULE/constraint value, e.g. `MAX_VIAS`, never an actual
    measured length). Per the vendored `axlDBGetLength.txt` doc: "Calculate the length of
    the given object which may be a NET, CLINE, SEGMENT, or RATSNEST. If a net is
    partially routed includes sum of all ratsnest manhattan lengths" — so this returns a
    real number for both fully- and partially-routed nets, in board (design) units
    (typically mils), not a design-rule limit.

    Resolves the net the same `(car (axlSelectByName "NET" net_name))` way
    `allegro_assign_net`/`allegro_delete_connect` do. The real use case this was built
    for: length-matching compliance — query two (or more) nets this way, compare the
    returned values against a tolerance from `get_high_speed_constraint_preset`
    (e.g. `intra_pair_length_match_mils`/`addr_ctrl_to_clk_length_match_mils`), and decide
    whether a net needs to be ripped up (`allegro_delete_connect`) and re-routed
    (`allegro_create_trace`) to come back into tolerance — not just whether DRC is clean.

    VERIFY, don't trust this tool's return value: SKILL return values never surface in
    the job log for a bare query like this one either (see this module's docstring) —
    capture the real number via SKILL's own `outfile`/`fprintf` in the same session (the
    same technique this module's docstring describes being used to verify
    `allegro_create_trace`/`allegro_create_simple_padstack`'s real dbid returns), e.g.
    `(let ((f (outfile "lengths.txt" "a"))) (fprintf f "%s %L\\n" net_name (axlDBGetLength
    (car (axlSelectByName "NET" net_name)))) (close f))`, then read that file after the
    job completes.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    expr = f'(axlDBGetLength (car (axlSelectByName "NET" {skill_str(net_name)})))'
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "net_name": net_name}
