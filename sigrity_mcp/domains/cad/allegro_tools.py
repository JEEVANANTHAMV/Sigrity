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

from typing import Literal, Optional

from sigrity_mcp.core.skillscript import skill_path, skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_NET_TYPES = Literal["Signal", "Power", "Ground"]


def _skill_line(expr: str) -> str:
    return f"skill {expr}"


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
async def allegro_create_stackup(session_id: str, position: Literal["top", "bottom", "afterBottom"] = "top") -> dict:
    """Create a single, simple layer stackup cross-section (UNVERIFIED live — see module docstring).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, _skill_line(f"(axlXSectionCreate nil '{position})"))
    return {"session_id": session_id, "position": position}


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
