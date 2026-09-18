"""OrCAD Capture schematic-capture automation — Tcl-scripted, session-based.

Confirmed live on this machine: a bare `Capture.exe` launch (no arguments) opens
normally. What is NOT reliably confirmed: batch script execution via
`Capture.exe -product=<name> script.tcl` (the form Cadence's own docs document,
doc/orctclsample). Repeated attempts on this machine were inconsistent — sometimes
opening Capture's own default/tutorial project instead of running the given script,
sometimes exiting immediately with no output, and at least once triggering a "Capture
Custom Launch" recovery dialog (which Cadence's docs say "is displayed only after
Capture fails at launching for the first time" — i.e. a crash-recovery prompt, not a
license chooser). The exact cause (a Tcl syntax issue in the probe scripts used, a
version-specific CLI quirk, or something else) was not isolated.

So unlike allegro_tools.py (where the session/run mechanics are confirmed, only
specific creation calls are unverified), here the run mechanics themselves are
unverified. This module is built from Cadence's documented Tcl API and real sample
scripts (doc/orctclsample, doc/orctclcap) — a solid transcription, but treat every tool
below as built_untested until `capture_run_session`'s batch invocation is independently
confirmed working on this machine.

Usage pattern: start_capture_session -> compose tools -> capture_run_session. The script
itself must call Menu "File::Close"/"File::Exit" to terminate — Capture does not
auto-exit after running a batch script, per the confirmed working example in
doc/orctclsample.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.tclscript import tcl_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def start_capture_session(project_file: str) -> dict:
    """Begin a new OrCAD Capture automation session by opening a project (.opj).

    Returns a session_id — pass it to every other capture_* tool below, then finish
    with capture_run_session. Nothing is executed yet; this records
    `Open <project_file>` (a bare path, forward slashes, no quoting — matching the
    confirmed real sample `Open d:/Sample_Scripts/Sample-19/Sample-19.opj` exactly,
    since `Open` is a Capture-specific proc rather than a standard Tcl command and its
    argument-parsing conventions are not independently confirmed to accept brace/quote
    quoting the way genuine Tcl commands do).
    """
    session = tcl_sessions.create("capture")
    tcl_sessions.add_line(session.session_id, f"Open {str(project_file).replace(chr(92), '/')}")
    return {"session_id": session.session_id, "project_file": project_file}


@mcp.tool
async def capture_place_part(
    session_id: str,
    x: float,
    y: float,
    library_file: str,
    part_name: str,
    package: str = "",
) -> dict:
    """Place a part from a library at an absolute page coordinate.

    Appends `PlacePart {x} {y} {library_file} {part_name} {package} FALSE`, the
    confirmed non-interactive placement call (as opposed to `PlacePartEx`, the
    interactive/mouse-driven variant) from doc/orctclsample.
    """
    line = f"PlacePart {x} {y} {tcl_str(library_file)} {tcl_str(part_name)} {tcl_str(package)} FALSE"
    tcl_sessions.add_line(session_id, line)
    return {"session_id": session_id, "part_name": part_name, "x": x, "y": y}


@mcp.tool
async def capture_place_wire(session_id: str, x1: float, y1: float, x2: float, y2: float) -> dict:
    """Place a wire segment between two page coordinates. Appends `PlaceWire {x1} {y1} {x2} {y2}`."""
    tcl_sessions.add_line(session_id, f"PlaceWire {x1} {y1} {x2} {y2}")
    return {"session_id": session_id, "from": [x1, y1], "to": [x2, y2]}


@mcp.tool
async def capture_place_pin(
    session_id: str,
    x: float,
    y: float,
    pin_name: str,
    pin_type: str = "Passive",
) -> dict:
    """Place a pin at a page coordinate (for symbol/mechanical-drawing construction).

    Appends `PlacePin {x} {y} {pin_name} {pin_type} FALSE`, matching the confirmed
    sample `PlacePin x y "pinName" "Passive" FALSE`.
    """
    tcl_sessions.add_line(session_id, f"PlacePin {x} {y} {tcl_str(pin_name)} {tcl_str(pin_type)} FALSE")
    return {"session_id": session_id, "pin_name": pin_name}


@mcp.tool
async def capture_set_property(session_id: str, property_name: str, value: str) -> dict:
    """Set a property on the currently-selected object(s). Appends `SetProperty {property_name} {value}`."""
    tcl_sessions.add_line(session_id, f"SetProperty {tcl_str(property_name)} {tcl_str(value)}")
    return {"session_id": session_id, "property_name": property_name, "value": value}


@mcp.tool
async def capture_annotate(session_id: str) -> dict:
    """Queue reference-designator annotation for the open design.

    Appends `Menu "Tools::Annotate"` — confirmed "Available from: Tools menu" in
    doc/cap_ref/Project_manager_command_reference.html.
    """
    tcl_sessions.add_line(session_id, 'Menu "Tools::Annotate"')
    return {"session_id": session_id}


@mcp.tool
async def capture_create_netlist(session_id: str) -> dict:
    """Queue netlist creation for the open design, for handoff to PCB layout.

    Appends `Menu "Tools::Create Netlist"` — confirmed "Available from: Tools menu" in
    doc/cap_ref/Project_manager_command_reference.html. Opens Capture's tabbed
    "Create Netlist" dialog in an interactive session; in batch mode this queues the
    same underlying command, but the exact output-format selection (Allegro/PSpice/...)
    normally made in that dialog is NOT independently confirmed to have a scriptable
    override — you may need a companion `DialogBox`-style settings file (see the
    CIS-BOM-from-command-line pattern in doc/orctclcap) to select a format headlessly.
    """
    tcl_sessions.add_line(session_id, 'Menu "Tools::Create Netlist"')
    return {"session_id": session_id}


@mcp.tool
async def capture_save(session_id: str) -> dict:
    """Queue saving the open design. Appends `Menu "File::Save"`."""
    tcl_sessions.add_line(session_id, 'Menu "File::Save"')
    return {"session_id": session_id}


@mcp.tool
async def capture_run_session(session_id: str, product: str = "OrCAD Capture") -> dict:
    """Write out the session's accumulated Tcl macro and launch Capture against it as a background job.

    UNVERIFIED — see module docstring: this exact batch invocation was not reliably
    reproduced on this machine across several attempts. Appends `Menu "File::Close"`
    then `Menu "File::Exit"` (required — Capture does not auto-exit after a batch
    script per Cadence's own confirmed example) before running
    `Capture.exe -product=<product> <macro.tcl>` (the script path is a bare positional
    argument, no preceding flag, per doc/cap_ug's documented switches — this project's
    core.process.submit_job supports that via tcl_arg_flag=None).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log,
    and treat a job that runs far longer than a Sigrity Tcl job (which typically
    completes in seconds) as a signal something is stuck, not necessarily still working.
    """
    tcl_sessions.add_line(session_id, 'Menu "File::Close"')
    tcl_sessions.add_line(session_id, 'Menu "File::Exit"')
    record = await run_session(
        session_id,
        tool="capture",
        tcl_arg_flag=None,
        build_args=[f"-product={product}"],
        script_filename="macro.tcl",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
