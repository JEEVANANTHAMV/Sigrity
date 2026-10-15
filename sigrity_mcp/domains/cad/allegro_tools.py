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
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from sigrity_mcp.core.skillscript import skill_path, skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp
from sigrity_mcp.domains.cad.allegro_geometry_tools import closed_outline_path_expr

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


@mcp.tool
async def allegro_create_net(session_id: str, net_name: str, net_type: Optional[_NET_TYPES] = None) -> dict:
    """Create a net in the open Allegro board (CONFIRMED LIVE — see module docstring).

    `axlDBCreateNet` on an already-existing net name is a no-op, so this is idempotent.
    For a batch of nets, prefer `allegro_create_nets` (one queued SKILL line per net,
    one round-trip for the whole set) to avoid the per-net round-trip cost that the
    single-net tool incurs when called in a loop.
    Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDBCreateNet {skill_str(net_name)})"))
    return {"session_id": session_id, "net_name": net_name, "net_type": net_type, "idempotent": True}


@mcp.tool
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


@mcp.tool
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


@mcp.tool
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


@mcp.tool
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


@mcp.tool
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


@mcp.tool
async def allegro_run_drc(session_id: str, batch_mode: bool = False) -> dict:
    """Queue a design-rule-check update (UNVERIFIED live — see module docstring).
Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDRCUpdate {'t' if batch_mode else 'nil'})"))
    return {"session_id": session_id, "batch_mode": batch_mode}


@mcp.tool
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


@mcp.tool
async def allegro_run_session(session_id: str, board_file: str) -> dict:
    """Write out the session's accumulated SKILL macro and launch Allegro against a real board as a background job.
Call load_skill('sigrity-cad') for the full verified playbook, pitfalls, and a live example."""
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
    return result
