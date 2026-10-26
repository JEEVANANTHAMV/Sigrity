"""Allegro PCB Editor automation — SKILL-scripted, session-based.

Confirmed live on this machine: `allegro.exe -s script.scr <board_file>` loads the given
board and replays `script.scr`'s lines against Allegro's `Command:` prompt. A
`skill <expr>` line hands one SKILL expression to the AXL-SKILL interpreter; a bare
`quit` line exits the application afterward. Both confirmed working end-to-end — a real
board loaded, a real SKILL query (`axlCurrentDesign`) executed and its result written to
a file, then a clean process exit, all within ~20 seconds.

UPDATE 2026-10-11: each `axl*` mutation call was independently re-run live in a single
SKILL session and the saved .brd was re-read with extracta (bypassing SKILL), so
persistence — not just "state=succeeded" — is what's claimed. Confirmed WORKING this way:
`allegro_create_net` (axlDBCreateNet persisted pre-save), `allegro_create_stackup`
(axlXSectionCreate — new layer visible in the LAYER report, board went 2->3 layers),
`allegro_run_drc` (axlDRCUpdate "No DRC errors detected", rc 0), and `allegro_save_design`
(axlSaveDesign "fillin yes" — board file grew and the net/layer persisted on re-open).
Two calls were found MIS-WRITTEN and corrected against that live run:
- `allegro_create_board_outline`: the old form passed a flat point list to
  axlDBCreateShape, which rejects it ("Object should be either an r_path or an o_polygon").
  It now builds a real r_path (`axlPathStart`, same as allegro_create_copper_shape). The
  API works; the shipped default was wrong.
- `allegro_create_component`: axlDBCreateComponent reached the board fine but failed with
  ERROR(SPMHNX-9): Unable to find device file for 'MYDEVICE' because the example used an
  arbitrary string; device_name must be a REAL installed device/part name. Corrected the
  docstring + return note; prefer allegro_place_module_instance for a real placement.
Note the one-time "Product Choices" dialog is real on this machine and the DismissWatcher
attached by run_session for tool="allegro" is what dismisses it — a raw subprocess with no
watcher hangs on it.

Usage pattern: start_allegro_session -> compose tools -> allegro_run_session(session_id,
board_file). Note `board_file` is supplied at RUN time, not composition time — Allegro
takes it as `allegro.exe`'s own positional argument (which loads the design before the
script runs), unlike Sigrity's `sigrity::open document` Tcl command.

CONSOLIDATED (compact-tool-surface pass): this file, allegro_geometry_tools.py, and
allegro_constraint_tools.py all compose into the SAME Allegro SKILL session (one
`start_allegro_session` -> many compose calls across all three files -> one
`allegro_run_session`), so their 22 individual "compose" functions are now driven through
ONE cross-file dispatcher tool, `allegro_configure(session_id, operations)`, defined here
(each item is `{"op": "<short-name>", **kwargs}`, `short-name` = the function name with
the `allegro_` prefix stripped). Grouped by what they do: net/component/board-level ops
(`create_net, create_nets, create_component, create_board_outline, create_route_keepin,
create_stackup, set_variable, run_drc, save_design` — from this file), geometry ops (`create_trace,
create_via, create_simple_padstack, place_module_instance, assign_net, delete_connect,
create_copper_shape, create_film, get_module_instance_location, get_net_length` — from
allegro_geometry_tools.py), and constraint ops (`set_spacing_constraint,
set_physical_constraint, create_ecset, delete_ecset, set_electrical_constraint,
get_electrical_constraint, set_electrical_check_mode, get_net_constraint, list_ecsets,
design_value_set` — from allegro_constraint_tools.py). Every operation's underlying validation/SKILL-quoting is
UNCHANGED — this only changes how many separate tool calls an agent needs, not what each
operation does or how safely it's built. `start_allegro_session` and `allegro_run_session`
are unaffected and remain individually exposed. See `allegro_configure`'s own docstring
for the full op list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional, Union

from sigrity_mcp.core.skillscript import skill_path, skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp
from sigrity_mcp.domains.cad.allegro_geometry_tools import (
    closed_outline_path_expr,
    allegro_assign_net,
    allegro_create_copper_shape,
    allegro_create_film,
    allegro_create_keepout,
    allegro_create_package_keepin,
    allegro_create_simple_padstack,
    allegro_create_trace,
    allegro_create_via,
    allegro_delete_connect,
    allegro_get_module_instance_location,
    allegro_get_net_length,
    allegro_import_package,
    allegro_list_packages,
    allegro_place_module_instance,
)
from sigrity_mcp.domains.cad.allegro_constraint_tools import (
    allegro_create_ecset,
    allegro_delete_ecset,
    allegro_design_value_set,
    allegro_get_electrical_constraint,
    allegro_get_net_constraint,
    allegro_list_ecsets,
    allegro_set_electrical_check_mode,
    allegro_set_electrical_constraint,
    allegro_set_physical_constraint,
    allegro_set_spacing_constraint,
)

_NET_TYPES = Literal["Signal", "Power", "Ground"]


def _skill_line(expr: str) -> str:
    return f"skill {expr}"


def _xsection_position_arg(position: Union[str, int]) -> str:
    """Render the `g_option` position argument of `axlXSectionCreate`/`axlXSectionSet`.

    Per the vendored SKILL doc (`share/pcb/examples/skill/DOC/FUNCS/axlXSectionCreate.txt`
    on this machine): the 3 endpoint symbols are quoted SKILL symbols (`'top`/`'bottom`/
    `'afterBottom`); anything else is either a t_etchSubclass name (insert above that
    already-existing named layer — a plain SKILL string) or a numeric x_position (insert
    above that stackup position ordinal — a bare number). `'top`/`'afterBottom` are
    documented as restricted to unnamed dielectric/MASK layers for PCB designs — use
    `'bottom` (or an explicit named-layer anchor) for named CONDUCTOR/PLANE layers.
    """
    if isinstance(position, str) and position in ("top", "bottom", "afterBottom"):
        return f"'{position}"
    if isinstance(position, (int, float)):
        return str(position)
    return skill_str(position)


def _make_axlxsection(
    name: Optional[str],
    layer_type: Optional[str],
    material: Optional[str],
    thickness_mil: Optional[float],
) -> str:
    """Build a `make_axlXSection(...)` defstruct expression from the subset of real,
    settable xsection attributes this suite exposes (see `axlXSectionGet.txt`'s
    attribute table: name/layerType/material/thickness are all `Modify: Yes`).
    """
    attrs: list[str] = []
    if name is not None:
        attrs += ["?name", skill_str(name)]
    if layer_type is not None:
        attrs += ["?layerType", skill_str(layer_type)]
    if material is not None:
        attrs += ["?material", skill_str(material)]
    if thickness_mil is not None:
        attrs += ["?thickness", str(thickness_mil)]
    return f"(make_axlXSection {' '.join(attrs)})" if attrs else "(make_axlXSection)"


@mcp.tool
async def start_allegro_session() -> dict:
    """Begin a new Allegro SKILL automation session.
Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.create("allegro")
    return {"session_id": session.session_id}


async def allegro_create_net(session_id: str, net_name: str, net_type: Optional[_NET_TYPES] = None) -> dict:
    """Create a net in the open Allegro board (CONFIRMED LIVE — see module docstring).

    `axlDBCreateNet` on an already-existing net name is a no-op, so this is idempotent.
    For a batch of nets, prefer `allegro_create_nets` (one queued SKILL line per net,
    one round-trip for the whole set) to avoid the per-net round-trip cost that the
    single-net tool incurs when called in a loop.
    Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDBCreateNet {skill_str(net_name)})"))
    return {"session_id": session_id, "net_name": net_name, "net_type": net_type, "idempotent": True}


async def allegro_create_nets(
    session_id: str,
    net_names: list[str],
    net_type: Optional[_NET_TYPES] = None,
) -> dict:
    """Create MULTIPLE nets in one call — batch alternative to looping `allegro_create_net`.

    Queues one `axlDBCreateNet` SKILL line per name into the current session (same
    mutation path as the single-net tool, so the result is idempotent for already-present
    names). `net_type` is applied to any name that accepts it (it is silently ignored
    for a net already created without one); omit it to keep nets at Allegro's default
    type. Call load_skill('sigrity-cad') for the full verified playbook."""
    if not net_names:
        raise ValueError("net_names must be a non-empty list")
    for net_name in net_names:
        tcl_sessions.add_line(session_id, _skill_line(f"(axlDBCreateNet {skill_str(net_name)})"))
    return {"session_id": session_id, "created": len(net_names), "net_names": list(net_names), "net_type": net_type}


async def allegro_create_component(
    session_id: str,
    ref_des: str,
    device_name: str,
    package: Optional[str] = None,
    value: Optional[str] = None,
) -> dict:
    """Create a component in the open Allegro board.

    FIX / root-cause (2026-10-11 live test): the session mechanics are FINE and confirmed
    working (a net/stackup/save in the same session all persisted), but the ORIGINAL
    example in the tests/prompt used an arbitrary string for `device_name` — Allegro
    case-folds it (e.g. "MyDevice" -> "MYDEVICE") and then fails with
    `ERROR(SPMHNX-9): Unable to find device file for 'MYDEVICE'`, creating nothing.
    `axlDBCreateComponent` requires `device_name` to be a REAL, installed device/part name
    (resolvable by `axlGetParam("library:<name>")` in this board's library path) — the
    same requirement `axlDBCreateModuleInstance` has (see `allegro_place_module_instance`).
    Pass an actually-installed part (e.g. one of the .olb/.psm you staged into
    `C:\\Cadence\\SPB_22.1\\tools\\capture\\library` + `pcbdw_lib`), not a made-up name.
    For a real placement at a coordinate, prefer `allegro_place_module_instance`.
    Call load_skill('sigrity-cad') for the full verified playbook."""
    args = [skill_str(ref_des), skill_str(device_name)]
    if package is not None:
        args.append(skill_str(package))
    if value is not None:
        args.append(skill_str(value))
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDBCreateComponent {' '.join(args)})"))
    return {
        "session_id": session_id,
        "ref_des": ref_des,
        "device_name": device_name,
        "note": (
            "device_name MUST be a real installed device/part name (Allegro case-folds it "
            "and looks it up as a device file). A made-up name fails with "
            "ERROR(SPMHNX-9): Unable to find device file. Use an installed .psm/.olb part, "
            "or place via allegro_place_module_instance."
        ),
    }


async def allegro_create_board_outline(session_id: str, points: list[list[float]]) -> dict:
    """Create the board outline shape from a closed polygon of [x, y] points.

    FIXED (2026-10-11 live root-cause): the original form passed a *flat* point list
    (`(list (list x y) ...)`) to `axlDBCreateShape`, which rejects it with
    `WARNING (axlDBCreateOpenShape): Object should be either an r_path or an o_polygon`
    and creates nothing. `axlDBCreateShape`'s first argument must be a real `r_path`
    (or `o_polygon`) SKILL object — the same construction `allegro_create_copper_shape`
    already uses (`axlPathStart` from a closed point list). Now the outline is built as a
    proper `r_path` via `closed_outline_path_expr` and left unclosed-on-purpose is NOT an
    option: the path is auto-closed (first point repeated as last) per the SKILL doc's
    "a path that does not end at its start point is an ERROR" rule.

    THIS OP WORKS — CONFIRMED LIVE AGAIN 2026-10-25 against a real client BRS build, by a
    standalone readback bypassing the LLM entirely (`axlDBGetShapes("BOARD GEOMETRY/OUTLINE")`
    returned a real shape, `(car shapes)->bBox` = `((0.0 0.0) (2362.2 2362.2))`, exactly the
    60mm board requested). Do NOT trust `run_allegro_report(..., report_code="sum")`'s
    "Layout area (sq in)" / "Router Keepin" fields to verify this op — a real BRS run drew
    this conclusion backwards and reported the outline as broken. Those two report fields
    read `axlDBGetDesign()->keepinRoute` (layer `ROUTE KEEPIN/ALL`), which is a COMPLETELY
    SEPARATE shape from `BOARD GEOMETRY/OUTLINE` and stays nil until `create_route_keepin`
    (below) is called — they report 0.00 / (0,0)-(0,0) even when the real outline exists and
    is the right size. To verify this op for real, capture a readback via SKILL's own
    `outfile`/`fprintf` in the same session (the same technique this module's
    `allegro_get_net_length` docstring describes), e.g. `(let ((f (outfile "verify.txt" "w"))
    (shapes (axlDBGetShapes "BOARD GEOMETRY/OUTLINE"))) (fprintf f "count=%d bbox=%L\\n"
    (length shapes) (when shapes (car shapes)->bBox)) (close f))`, then read that file.

    NOT IDEMPOTENT: calling this op again (e.g. after a report falsely suggested the first
    call failed) does NOT replace the existing outline — it draws an ADDITIONAL overlapping
    shape on top of it (confirmed: 2 retries on the same board left 3 outline shapes on
    disk). If you need to redo an outline, delete the old shape first rather than re-calling
    this blindly on suspected failure.

    If you actually need the board to report a nonzero "Layout area" / have a routable
    boundary Allegro's placement, routing, and report tools recognize, also call
    `create_route_keepin` (same points, typically the same or inset polygon) — the physical
    outline and the route keepin are two independent concepts in Allegro and this op only
    creates the former.
    Call load_skill('sigrity-cad') for the full verified playbook."""
    if len(points) < 3:
        raise ValueError("A board outline needs at least 3 points.")
    path_expr = closed_outline_path_expr(points)
    # Bind the r_path to a var, then hand it to axlDBCreateShape (which needs a real
    # r_path object, not a flat list).
    #
    # CONFIRMED BUG FIX (was SPMHDB-185 'Filled SHAPE may not exist on layer
    # BOARD GEOMETRY/OUTLINE'): the second arg is l_r_fill, and
    # 'BOARD GEOMETRY/OUTLINE' is an UNFILLED-ONLY class. Passing `t` (solid fill)
    # is rejected and the outline never persists. The correct value is `nil`
    # (unfilled), verified headlessly in C:\TEMP-B~1\kilo\outline_fix\final_test.py
    # (board grew, axlDBGetShapes readback returned bBox ((0 0) (2362.2 2362.2))
    # area 5579989.0 = 60mm², round-tripped through disk). The r_path itself is
    # auto-closed by closed_outline_path_expr; the fill flag is separate.
    expr = f'(let ((g_outline {path_expr})) (axlDBCreateShape g_outline nil "BOARD GEOMETRY/OUTLINE"))'
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "point_count": len(points)}


async def allegro_create_route_keepin(session_id: str, points: list[list[float]]) -> dict:
    """Create the ROUTE KEEPIN boundary from a closed polygon of [x, y] points — the
    shape Allegro's placement/routing tools and `run_allegro_report(report_code="sum")`'s
    "Layout area" / "Router Keepin" fields actually read (`axlDBGetDesign()->keepinRoute`),
    as DISTINCT from the cosmetic `create_board_outline` shape (`BOARD GEOMETRY/OUTLINE`).

    ADDED 2026-10-25 (real root-cause, real client BRS build): `create_board_outline`
    was live-verified to genuinely work (see that op's docstring), but a report pulled
    AFTER calling only `create_board_outline` still showed "Layout area (sq in): 0.00" and
    "Router Keepin (in): (0.0000,0.0000) by (0.0000,0.0000)" — read as "the outline failed".
    It didn't fail; nothing had populated `ROUTE KEEPIN/ALL` yet, because no tool did. Per
    the vendored `axlDbidDoc.txt` ("DESIGN Attributes"): `keepinRoute` = "Route shape/rect
    keepin, nil if none (layer ROUTE KEEPIN/ALL)" — a field entirely separate from
    `designOutline` (layer `BOARD GEOMETRY/DESIGN_OUTLINE`, also separate from
    `BOARD GEOMETRY/OUTLINE`) and from `create_board_outline`'s shape. In the normal Allegro
    workflow these usually share the same polygon (draw the physical edge, then define the
    routable area to match it) — call this op with the same `points` as
    `create_board_outline` right after it, in the same session, unless you deliberately want
    a smaller routable area inset from the physical edge.

    Same construction as `create_board_outline` (`axlPathStart` -> `axlDBCreateShape`,
    unfilled) on `"ROUTE KEEPIN/ALL"` instead of `"BOARD GEOMETRY/OUTLINE"`. Not idempotent
    for the same reason noted on that op — do not re-call this speculatively if a report
    still shows a zero area; verify via a captured `outfile`/`fprintf` readback instead.
    Call load_skill('sigrity-cad') for the full verified playbook."""
    if len(points) < 3:
        raise ValueError("A route keepin needs at least 3 points.")
    path_expr = closed_outline_path_expr(points)
    expr = f'(let ((g_keepin {path_expr})) (axlDBCreateShape g_keepin nil "ROUTE KEEPIN/ALL"))'
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "point_count": len(points)}


async def allegro_create_stackup(
    session_id: str,
    position: Union[Literal["top", "bottom", "afterBottom"], str, int] = "bottom",
    name: Optional[str] = None,
    layer_type: Optional[str] = None,
    material: Optional[str] = None,
    thickness_mil: Optional[float] = None,
) -> dict:
    """Queue ONE real cross-section stackup layer (`axlXSectionCreate`), within the current Allegro SKILL session.

    UPGRADED from the original bare `(axlXSectionCreate nil 'position)` form (which only
    ever inserted one unnamed, default-material/thickness DIELECTRIC layer): now builds a
    real `make_axlXSection(?name ... ?layerType ... ?material ... ?thickness ...)`
    defstruct so `name`/`layer_type`/`material`/`thickness_mil` are genuinely authored —
    these are exactly the attributes the vendored `axlXSectionGet.txt` doc marks
    `Modify: Yes`, confirmed against the real example script
    `share/pcb/examples/skill/dbcreate/xsection.il` on this machine. There is NO SKILL
    attribute for an electrical "reference plane" (searched `axlXSectionGet`'s full
    attribute table and every `axlCNS*`/`axlCns*` Constraint-Manager function on this
    install) — a signal layer's reference plane is inferred by Allegro from stackup
    ADJACENCY to a PLANE layer, not a settable field, so this tool has nothing to set for
    that concept; order your layers so the intended plane is physically adjacent instead.

    `position` accepts the 3 SKILL endpoint symbols (`"top"`/`"bottom"`/`"afterBottom"` —
    NOTE: `"top"`/`"afterBottom"` are restricted by Allegro to unnamed dielectric/MASK
    layers for PCB designs; use `"bottom"` for named CONDUCTOR/PLANE layers), OR the name
    of an already-existing named layer to insert above it (t_etchSubclass), OR a numeric
    stackup position ordinal (x_position) to insert above. For composing more than one
    layer in the correct top-to-bottom order in a single session, prefer
    `generate_multilayer_stackup` (in `rigid_flex_stackup_tools.py`), which applies
    Cadence's own documented ordering convention automatically.
Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    defstruct = _make_axlxsection(name, layer_type, material, thickness_mil)
    expr = f"(axlXSectionCreate nil {_xsection_position_arg(position)} {defstruct})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {
        "session_id": session_id,
        "position": position,
        "name": name,
        "layer_type": layer_type,
        "material": material,
        "thickness_mil": thickness_mil,
    }


async def allegro_set_variable(session_id: str, name: str, value: str) -> dict:
    """Queue a session-scope Allegro variable set (`axlSetVariable`) before `axlDBCreateComponent` runs in the same session.

    Sets ONE Allegro environment variable for THIS session only (per the vendored
    `axlSetVariable.txt` doc: variable settings "only apply to current session. They
    are not saved to user's local env file," and batch operations launched from
    Allegro do NOT see the change). Use it to point the session's device-library
    paths at the directories that actually contain the part files on disk — the
    typical names are `DEVPATH` (.pdra device/part definitions), `PSMPATH` (.psm
    package symbols), `PADPATH` (.pad pad libraries), and `STEPPATH` (.step 3-D
    models): queue one `allegro_set_variable` line per path BEFORE
    `allegro_create_component`, and the .pdra/.psm/.pad/.step files become
    discoverable, fixing SPMHNX-9 ("Unable to find device file") caused by the
    paths not covering where the files physically live.

    The value is always emitted in axlSetVariable's *list* form with exactly one
    element — `(axlSetVariable "NAME" '("value"))` — so the type is unambiguous
    even for a single path (the doc's own list-mode example:
    `axlSetVariable("psmpath" '("." "symbols"))`); to APPEND to an existing path
    rather than replace it, read the current value back with
    `axlGetVariableList` first and pass the combined, slash-joined list.
    Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlSetVariable {skill_str(name)} '({skill_str(value)}))"))
    return {"session_id": session_id, "name": name, "value": value}


async def allegro_run_drc(session_id: str, batch_mode: bool = False) -> dict:
    """Queue a design-rule-check update (UNVERIFIED live — see module docstring).
Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDRCUpdate {'t' if batch_mode else 'nil'})"))
    return {"session_id": session_id, "batch_mode": batch_mode}


async def allegro_save_design(session_id: str, output_file: Optional[str] = None) -> dict:
    """Queue saving the current Allegro board (CONFIRMED LIVE — see module docstring).

    Saves the board **already open in the session** (i.e. the board passed to
    `allegro_run_session`). `axlSaveDesign` takes NO path argument in SKILL — passing
    one is rejected with 'extra arguments or keyword missing' (confirmed in the
    `decisive` and `brs_verify_now` `.jrl` journals). Therefore `output_file` is
    accepted for API symmetry / log-only purposes and is NOT forwarded to SKILL;
    the board file is whatever was opened on the command line. Always verify the
    target `.brd` actually grew after `allegro_run_session` returns `succeeded`
    (see that tool's note — `axlSaveDesign` errors land in the `.jrl`, not run.log).
    Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line("(axlSaveDesign)"))
    note = {"session_id": session_id, "output_file": output_file}
    if output_file is not None:
        note["note"] = (
            "axlSaveDesign saves the board already open in the session (the one "
            "passed to allegro_run_session). The output_file argument is NOT "
            "forwarded to SKILL; it is recorded here for logging only. Confirm the "
            "board's byte size increased after the run."
        )
    return note


_CONFIGURE_OPS = {
    # net / component / board-level ops (this file)
    "create_net": allegro_create_net,
    "create_nets": allegro_create_nets,
    "create_component": allegro_create_component,
    "create_board_outline": allegro_create_board_outline,
    "create_route_keepin": allegro_create_route_keepin,
    "create_stackup": allegro_create_stackup,
    "set_variable": allegro_set_variable,
    "run_drc": allegro_run_drc,
    "save_design": allegro_save_design,
    # geometry ops (allegro_geometry_tools.py)
    "create_trace": allegro_create_trace,
    "create_via": allegro_create_via,
    "create_simple_padstack": allegro_create_simple_padstack,
    "place_module_instance": allegro_place_module_instance,
    "assign_net": allegro_assign_net,
    "delete_connect": allegro_delete_connect,
    "create_copper_shape": allegro_create_copper_shape,
    "create_film": allegro_create_film,
    "create_package_keepin": allegro_create_package_keepin,
    "create_keepout": allegro_create_keepout,
    "list_packages": allegro_list_packages,
    "import_package": allegro_import_package,
    "get_module_instance_location": allegro_get_module_instance_location,
    "get_net_length": allegro_get_net_length,
    # constraint ops (allegro_constraint_tools.py)
    "set_spacing_constraint": allegro_set_spacing_constraint,
    "set_physical_constraint": allegro_set_physical_constraint,
    "create_ecset": allegro_create_ecset,
    "delete_ecset": allegro_delete_ecset,
    "set_electrical_constraint": allegro_set_electrical_constraint,
    "get_electrical_constraint": allegro_get_electrical_constraint,
    "set_electrical_check_mode": allegro_set_electrical_check_mode,
    "get_net_constraint": allegro_get_net_constraint,
    "list_ecsets": allegro_list_ecsets,
    "design_value_set": allegro_design_value_set,
}


@mcp.tool
async def allegro_configure(session_id: str, operations: list[dict]) -> dict:
    """Apply a list of Allegro session-configuration operations in one call (replaces
    calling the 22 individual compose tools spread across allegro_tools.py,
    allegro_geometry_tools.py, and allegro_constraint_tools.py one at a time).

    All three modules compose into the SAME Allegro SKILL session (one
    `start_allegro_session` -> many `allegro_configure` calls -> one `allegro_run_session`),
    so this single dispatcher spans all three files rather than each file getting its own.

    Each item in `operations` is `{"op": "<name>", **kwargs}`. `kwargs` are EXACTLY that
    operation's own parameters below (everything except `session_id`, which is threaded through
    automatically) — these are the real Python keyword-argument names, read off the actual
    function signatures; a key not listed here for a given op WILL raise `ValueError` naming the
    exact index/op/bad-kwarg, it will never be silently accepted or ignored. This list is the
    ONLY place these kwargs are documented to you — the individual `allegro_*` functions this
    dispatches to are not separately exposed as callable tools, so their own docstrings are not
    visible to you; do not guess a field name that isn't in this exact list, and do not invent an
    op name or extra kwarg no matter how plausible it sounds (there is no `top_layer` field
    anywhere below, for example — a padstack's layer kwarg is `pad_layer`).

    - `create_net(net_name, net_type=None)`
    - `create_nets(net_names, net_type=None)`  — `net_names` is a list of strings
    - `create_component(ref_des, device_name, package=None, value=None)`
    - `create_board_outline(points)`  — `points` is a list of `[x, y]` pairs. Draws the
      COSMETIC physical outline (`BOARD GEOMETRY/OUTLINE`) only — `run_allegro_report`'s
      "Layout area" / "Router Keepin" fields read a DIFFERENT shape and will show 0.00 /
      (0,0)-(0,0) until `create_route_keepin` is also called; that is not a sign this op
      failed. Not idempotent — do not re-call it speculatively (see its own docstring for
      how to verify for real).
    - `create_route_keepin(points)`  — same `points` shape as `create_board_outline`
      (usually the identical polygon); draws the ROUTABLE boundary (`ROUTE KEEPIN/ALL`)
      that placement/routing/reports actually use. Call right after `create_board_outline`
      in the same session unless a smaller inset routable area is wanted.
    - `create_stackup(position="bottom", name=None, layer_type=None, material=None, thickness_mil=None)`
    - `set_variable(name, value)`
    - `run_drc(batch_mode=False)`
    - `save_design(output_file=None)`  — note: `axlSaveDesign` takes no path argument; `output_file` is for this tool's own bookkeeping only
    - `create_trace(points, layer, net_name, width)`  — `width` is required
    - `create_via(padstack_name, x, y, net_name=None, rotation=0.0, mirror=False)`
    - `create_simple_padstack(name, pad_layer, pad_width, pad_height, pad_figure="RECTANGLE", drill_diameter=None)`
      — `pad_layer` (NOT `top_layer`/`layer`) is the only layer kwarg; omit `drill_diameter`
      entirely for an SMT pad with no drill (do not pass `drill_x`/`drill_y`/`drill`/`drill_size`
      — a round drill takes one scalar, `drill_diameter`, and nothing else)
    - `place_module_instance(instance_name, module_def_name, x, y, rotation=0.0, logic_from_schematic=False, mirror=False)`
    - `assign_net(object_type, object_name, net_name, ripup=False, ignore_fixed=False)`
    - `delete_connect(object_type, object_name, ripup=True)`  — DESTRUCTIVE: removes the connection, not reversible within the session
    - `create_copper_shape(layer, net_name, points, dynamic=True)`
    - `create_film(film_name, layers, negative=False, mirrored=False)`
    - `create_package_keepin(points)`
    - `create_keepout(points)`
    - `list_packages(package_dir=None)`
    - `import_package(package_dir, placements, device_dir=None)`
    - `get_module_instance_location(instance_name)`
    - `get_net_length(net_name)`
    - `set_spacing_constraint(constraint, value, cset=None, layer=None)`
    - `set_physical_constraint(constraint, value, cset=None, layer=None)`
    - `create_ecset(name, copy_from=None)`
    - `delete_ecset(name)`
    - `set_electrical_constraint(ecset, check, value)`
    - `get_electrical_constraint(ecset, check)`
    - `set_electrical_check_mode(check, mode)`
    - `get_net_constraint(net_name, constraint_name)`
    - `list_ecsets(domain="electrical")`
    - `design_value_set(check, value)`

    Operations are applied in list order, since later ones (e.g. assigning a net to a pin just
    created) can depend on earlier ones.

    Example: `operations=[{"op": "create_net", "net_name": "GND"},
    {"op": "create_trace", "points": [[0, 0], [100, 0]], "layer": "TOP",
    "net_name": "GND", "width": 5.0},
    {"op": "create_simple_padstack", "name": "M3_MOUNT", "pad_layer": "TOP",
    "pad_width": 125.98, "pad_height": 125.98, "pad_figure": "ROUND", "drill_diameter": 125.98},
    {"op": "set_spacing_constraint", "constraint": "LINE_TO_LINE", "value": 5.0}]`.
    Pass `operations` as a real JSON array value, not as a JSON-encoded string.
    Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    results = []
    for i, raw_op in enumerate(operations):
        op = dict(raw_op)
        name = op.pop("op", None)
        fn = _CONFIGURE_OPS.get(name)
        if fn is None:
            raise ValueError(
                f"operations[{i}]: unknown op {name!r}. Valid ops: {sorted(_CONFIGURE_OPS)}"
            )
        try:
            result = await fn(session_id, **op)
        except TypeError as e:
            raise ValueError(f"operations[{i}] (op={name!r}): {e}") from e
        results.append({"op": name, **result})
    return {"session_id": session_id, "operations_applied": len(results), "results": results}


@mcp.tool
async def allegro_run_session(session_id: str, board_file: str) -> dict:
    """Write out the session's accumulated SKILL macro and launch Allegro against a real board as a background job.

    Multi-arg constraint calls queued via `tcl_sessions.add_il` are NOT written as bare
    `.scr` lines — Allegro 22.1's `-s` command-replay parser (the `lineread` top-level
    reader) corrupts any `skill <expr>` line whose form has more than one top-level
    whitespace-separated token (it keeps only the first, so e.g.
    `axlCNSSetSpacing(nil nil 'line_line 5)` re-parses to `axlCNSGetSpacing(nil nil
    'line_line)` -> "not a function" / silent no-op; confirmed live 2026-10-18, 4
    independent repros). Those calls are instead written to `auto_il.il` in the board's
    directory (the design-dir-relative path convention `load`/`outfile` use) and invoked
    as the documented `skill (load "...")` + `skill <func>` single-token pair. See
    `allegro_constraint_tools.py`'s module docstring for the full evidence + rule-name
    ground truth.
    Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.get(session_id)
    has_il = bool(session.il_lines)
    if has_il:
        il_path = Path(board_file).parent / "auto_il.il"
        il_path.write_text("\n\n".join(session.il_lines) + "\n", encoding="utf-8")
        il_abs = str(il_path).replace("\\", "/")
        # Load the .il once (it defines all queued defuns), then call each by its
        # single-token name in queue order. Each emitted line is a 1-token `skill (...)`
        # form, which the lineread parser handles correctly.
        session = tcl_sessions.add_line(session_id, f'skill (load "{il_abs}")')
        for func_name in session.il_func_names:
            session = tcl_sessions.add_line(session_id, f"skill ({func_name})")
    session = tcl_sessions.add_line(session_id, "quit")
    has_save = any("axlSaveDesign" in line for line in session.script._lines)
    clear_stale_design_lock(board_file)
    record = await run_session(
        session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="macro.scr",
    )
    result = {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
    if has_save:
        result["note"] = (
            "SKILL-level errors (e.g. an unrecognized axlSaveDesign keyword) are logged "
            "to Allegro's own .jrl journal next to the board file, NOT to run.log -- a "
            "state='succeeded' result is not proof the queued save actually executed. "
            "Verify the expected output file genuinely changed (size/mtime, or an "
            "independent report.exe read-back) before trusting this result."
        )
    if has_il:
        il_note = (
            "Multi-arg constraint calls ran via a loaded auto_il.il in the board's "
            "directory (a bare .scr line cannot carry a multi-token SKILL form on this "
            "22.1 build). Each call's return value (t/nil) is captured to a "
            "design-dir cns_<id>.txt file, NOT returned to this process -- verify a set "
            "by reading that file or re-querying via the matching axlCNS*Get* function / "
            "report.exe."
        )
        result["note"] = (result.get("note", "") + " " + il_note).strip()
    return result
