"""Allegro PCB Editor automation — SKILL-scripted, session-based.

Confirmed live on this machine: `allegro.exe -s script.scr <board_file>` loads the given
board and replays `script.scr`'s lines against Allegro's `Command:` prompt. A
`skill <expr>` line hands one SKILL expression to the AXL-SKILL interpreter; a bare
`quit` line exits the application afterward. Both confirmed working end-to-end — a real
board loaded, a real SKILL query (`axlCurrentDesign`) executed and its result written to
a file, then a clean process exit, all within ~20 seconds.

UPDATE: the mutation call (`axlDBCreateNet`, via `allegro_create_net`) was re-tested
after the user resolved a machine-wide licensing issue, and now completes cleanly in
~5.6 seconds against a real board (returncode 0) — the earlier ">2 minutes, never
finished" result really was a license/queue-related block, not a bug in the SKILL call
or session mechanics. Only `allegro_create_net` was independently re-confirmed this way;
`allegro_create_component`/`allegro_create_board_outline`/`allegro_create_stackup`/
`allegro_save_design`/`allegro_run_drc` share the same session mechanics and `axl*` API
family but were not each individually re-run — likely also fixed, but still flagged
per-tool as unverified below until confirmed one by one.

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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.create("allegro")
    return {"session_id": session.session_id}


@mcp.tool
async def allegro_create_net(session_id: str, net_name: str, net_type: Optional[_NET_TYPES] = None) -> dict:
    """Create a net in the open Allegro board (CONFIRMED LIVE — see module docstring).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDBCreateNet {skill_str(net_name)})"))
    return {"session_id": session_id, "net_name": net_name, "net_type": net_type}


@mcp.tool
async def allegro_create_component(
    session_id: str,
    ref_des: str,
    device_name: str,
    package: Optional[str] = None,
    value: Optional[str] = None,
) -> dict:
    """Create a component placeholder in the open Allegro board (UNVERIFIED live — see module docstring).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [skill_str(ref_des), skill_str(device_name)]
    if package is not None:
        args.append(skill_str(package))
    if value is not None:
        args.append(skill_str(value))
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDBCreateComponent {' '.join(args)})"))
    return {"session_id": session_id, "ref_des": ref_des, "device_name": device_name}


@mcp.tool
async def allegro_create_board_outline(session_id: str, points: list[list[float]]) -> dict:
    """Create the board outline shape from a closed polygon of [x, y] points (UNVERIFIED live — see module docstring).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    point_list = " ".join(f"(list {p[0]} {p[1]})" for p in points)
    expr = f'(axlDBCreateShape (list {point_list}) nil "BOARD GEOMETRY/OUTLINE")'
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
async def allegro_run_drc(session_id: str, batch_mode: bool = False) -> dict:
    """Queue a design-rule-check update (UNVERIFIED live — see module docstring).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDRCUpdate {'t' if batch_mode else 'nil'})"))
    return {"session_id": session_id, "batch_mode": batch_mode}


@mcp.tool
async def allegro_save_design(session_id: str, output_file: Optional[str] = None) -> dict:
    """Queue saving the current Allegro board (UNVERIFIED live — see module docstring).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    expr = "(axlSaveDesign)" if output_file is None else f"(axlSaveDesign {skill_path(output_file)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "output_file": output_file}


@mcp.tool
async def allegro_run_session(session_id: str, board_file: str) -> dict:
    """Write out the session's accumulated SKILL macro and launch Allegro against a real board as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, "quit")
    clear_stale_design_lock(board_file)
    record = await run_session(
        session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="macro.scr",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
