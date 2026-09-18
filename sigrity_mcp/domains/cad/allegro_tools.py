"""Allegro PCB Editor automation — SKILL-scripted, session-based.

Confirmed live on this machine: `allegro.exe -s script.scr <board_file>` loads the given
board and replays `script.scr`'s lines against Allegro's `Command:` prompt. A
`skill <expr>` line hands one SKILL expression to the AXL-SKILL interpreter; a bare
`quit` line exits the application afterward. Both confirmed working end-to-end — a real
board loaded, a real SKILL query (`axlCurrentDesign`) executed and its result written to
a file, then a clean process exit, all within ~20 seconds.

What is NOT yet confirmed: an actual database *mutation* call (`axlDBCreateNet`) did not
complete within two minutes in the same session shape that the query call completed in
under twenty seconds — cause unconfirmed (a hidden confirmation dialog, a genuinely slow
first-mutation cost, or something else). So while this module implements the documented
`axl*` creation API (net/component/board-outline/stackup/DRC), per-tool docstrings below
flag creation calls specifically as unverified, distinct from the confirmed session/query
mechanics themselves. Treat `allegro_run_session`'s `board_file` load and any read-only
SKILL query as reliable; treat any `axlDBCreate*`/`axlSaveDesign`/`axlDRCUpdate` call as
best-effort until independently confirmed.

Usage pattern: start_allegro_session -> compose tools -> allegro_run_session(session_id,
board_file). Note `board_file` is supplied at RUN time, not composition time — Allegro
takes it as `allegro.exe`'s own positional argument (which loads the design before the
script runs), unlike Sigrity's `sigrity::open document` Tcl command.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.skillscript import skill_path, skill_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_NET_TYPES = Literal["Signal", "Power", "Ground"]


def _skill_line(expr: str) -> str:
    return f"skill {expr}"


@mcp.tool
async def start_allegro_session() -> dict:
    """Begin a new Allegro SKILL automation session.

    Returns a session_id — pass it to every other allegro_* tool below to keep adding
    SKILL steps to the same macro, then finish with allegro_run_session(session_id,
    board_file). Nothing is executed yet, and no design file needs to be given until you
    run the session: Allegro loads the board as `allegro.exe`'s own command-line
    argument (which happens before the script replays), not via a SKILL command inside
    the script the way Sigrity's `sigrity::open document` works.
    """
    session = tcl_sessions.create("allegro")
    return {"session_id": session.session_id}


@mcp.tool
async def allegro_create_net(session_id: str, net_name: str, net_type: Optional[_NET_TYPES] = None) -> dict:
    """Create a net in the open Allegro board (UNVERIFIED live — see module docstring).

    Appends `skill (axlDBCreateNet {net_name})`. `net_type` is accepted for future use
    but not yet wired to a specific SKILL property call — pass it for documentation
    purposes only until this is confirmed against a real board.
    """
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

    Appends `skill (axlDBCreateComponent {ref_des} {device_name} [{package}] [{value}])`
    per the confirmed AXL-SKILL function signature
    `axlDBCreateComponent(s_refDes s_deviceName [s_package] [s_value] [s_tolerance])`.
    """
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

    `points` should form a closed polygon (first and last point the same, or the loop is
    implied) in the board's native units. Appends a SKILL point-list literal and calls
    `axlDBCreateShape`, matching the confirmed real example in
    share/pcb/examples/skill/dbcreate/xsection.il (`axlDBCreateShape(polygon nil
    "BOARD GEOMETRY/OUTLINE")`) — this tool always targets that same layer.
    """
    point_list = " ".join(f"(list {p[0]} {p[1]})" for p in points)
    expr = f'(axlDBCreateShape (list {point_list}) nil "BOARD GEOMETRY/OUTLINE")'
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "point_count": len(points)}


@mcp.tool
async def allegro_create_stackup(session_id: str, position: Literal["top", "bottom", "afterBottom"] = "top") -> dict:
    """Create a single, simple layer stackup cross-section (UNVERIFIED live — see module docstring).

    IMPORTANT confirmed limitation from Allegro's own SKILL documentation: multi-stackup
    (rigid-flex) creation is explicitly NOT fully supported via SKILL in this version
    ("Currently not possible to create/manage multiple stackups via Skill... This
    restriction will be removed in a future release") — this tool only supports the
    single-stackup case. Appends `skill (axlXSectionCreate nil '{position})`, the
    confirmed `axlXSectionCreate(nil g_option [g_xsectionDefStruct])` signature with a
    position symbol rather than a full cross-section definition struct (which needs a
    per-layer material/thickness table this tool doesn't attempt to construct — for a
    real stackup, adapt share/pcb/examples/skill/dbcreate/xsection.il's `SimpleCreate()`
    directly instead of relying on this tool alone).
    """
    tcl_sessions.add_line(session_id, _skill_line(f"(axlXSectionCreate nil '{position})"))
    return {"session_id": session_id, "position": position}


@mcp.tool
async def allegro_run_drc(session_id: str, batch_mode: bool = False) -> dict:
    """Queue a design-rule-check update (UNVERIFIED live — see module docstring).

    Appends `skill (axlDRCUpdate {nil|t})`. `batch_mode=False` (default, `nil`) runs
    interactive-style checks only; `True` (`t`) runs "on and batch checks" — Allegro's
    own SKILL docs flag this batch mode as "being phased out," so prefer the default
    unless you specifically need it.
    """
    tcl_sessions.add_line(session_id, _skill_line(f"(axlDRCUpdate {'t' if batch_mode else 'nil'})"))
    return {"session_id": session_id, "batch_mode": batch_mode}


@mcp.tool
async def allegro_save_design(session_id: str, output_file: Optional[str] = None) -> dict:
    """Queue saving the current Allegro board (UNVERIFIED live — see module docstring).

    Appends `skill (axlSaveDesign [{output_file}])` per the confirmed
    `axlSaveDesign(?design t_design ?mode t_option ...)` signature — without
    `output_file`, saves back to the board that was opened.
    """
    expr = "(axlSaveDesign)" if output_file is None else f"(axlSaveDesign {skill_path(output_file)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "output_file": output_file}


@mcp.tool
async def allegro_run_session(session_id: str, board_file: str) -> dict:
    """Write out the session's accumulated SKILL macro and launch Allegro against a real board as a background job.

    `board_file` is required here (not at start_allegro_session) because Allegro takes
    it as `allegro.exe`'s own positional command-line argument, loaded before the script
    replays — confirmed live: the design was already accessible to SKILL queries with no
    explicit "open" command needed in the script itself.
    Appends a bare `quit` line (confirmed to cleanly exit Allegro afterward — not a SKILL
    call, a native Allegro command-prompt command) before running
    `allegro.exe -s <macro.scr> <board_file>`.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job. Allegro can
    take 15-20+ seconds just to load a real board before your script's lines even start
    running, so don't assume "still running" after a short wait means something is wrong.
    """
    tcl_sessions.add_line(session_id, "quit")
    record = await run_session(
        session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="macro.scr",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
