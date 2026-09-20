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

RE-TESTED THIS PASS (see `core/tool_status.py`'s `capture` note for the full write-up):
the `known_blocked` status is real and was further root-caused to a specific,
project-agnostic, machine-level defect in this Capture install's own `Open <project>`
code path — not a wrapper-layer bug: a minimal Open+Close+Exit-only script against a
*different*, simpler shipped sample project (FullAdder.opj) hangs identically (0-byte
log, no `.lck` file ever written into the project directory, 100% CPU spin, zero
windows of any kind), while `Capture.exe -version` still works cleanly. The "Capture
Custom Launch" recovery dialog seen along the way is a *separate*, distinct failure
mode (a genuine prior-session crash-dump recovery prompt, confirmed from its own
`errorlog.xml`/`crashdump.dmp` pair) and is handled by
`capture_handle_custom_launch_dialog` below, which is a real, live-verified fix for
that specific, narrower problem even though it does not fix the main `Open`-step hang.
Actually authoring a real, populated schematic end-to-end on this machine is still
blocked on the Capture-level defect above; nothing in this module's Python code is a
workaround for that.

Usage pattern: start_capture_session -> compose tools -> capture_run_session. The script
itself must call Menu "File::Close"/"File::Exit" to terminate — Capture does not
auto-exit after running a batch script, per the confirmed working example in
doc/orctclsample.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from typing import Optional

from sigrity_mcp.core.tclscript import tcl_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

# Windows modal auto-dismiss, used only by capture_handle_custom_launch_dialog below.
_WIN_WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def _win32_user32():
    """Return the live user32 module handle. Factored out so tests (and future
    non-Windows CI environments) can swap in a fake rather than monkey-patching the
    real stdlib ``ctypes`` module globally."""
    return ctypes.windll.user32


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
    Also removes a stale `<project_file>.lck` sibling file if one exists — a live-caught
    real cause of some of this tool's documented non-determinism: a batch run that was
    killed rather than exiting cleanly leaves its lock behind, and the next open then
    blocks on a modal "already open/locked" dialog with no console output at all
    (indistinguishable from a hang until a human clicks through it). This alone may not
    fully explain every non-deterministic run documented in this module's docstring, but
    removes one confirmed, reproducible cause of it.
    """
    clear_stale_design_lock(project_file)
    session = tcl_sessions.create("capture")
    tcl_sessions.add_line(session.session_id, f"Open {str(project_file).replace(chr(92), '/')}")
    return {"session_id": session.session_id, "project_file": project_file}


@mcp.tool
async def capture_select_page(
    session_id: str, design: str, schematic_folder: str, page: str
) -> dict:
    """Select a design/schematic page so subsequent placement acts on a real page.

    Opens the project, the active schematic view still points at the project root, and
    `PlacePart`/`PlaceWire`/`PlacePin` have no page to act on — a live-confirmed cause of
    a run that opens, then never does any of the queued work. These two commands switch
    the active context to the target schematic page first:

        SelectPMItem "<design>"
        OPage "<schematic_folder>" "<page>"

    Both are taken verbatim from Cadence's own confirmed working sample
    (doc/orctclsample, Sample-19.tcl: `SelectPMItem "./Sample-19.dsn"` +
    `OPage "SCHEMATIC1" "PAGE1"`). `design` is the design's project-model path (e.g.
    `./fault-detector.dsn`, or `SCHEMATIC1/PAGE_1` for a nested page); `schematic_folder`
    is the design's root schematic folder name; `page` is the page inside it. Pass the
    same values on repeat if you place on the same page; selecting a second page works
    the same way for multi-page designs.
    """
    tcl_sessions.add_line(session_id, f'SelectPMItem {tcl_str(design)}')
    tcl_sessions.add_line(session_id, f'OPage {tcl_str(schematic_folder)} {tcl_str(page)}')
    return {"session_id": session_id, "design": design, "page": f"{schematic_folder}/{page}"}


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


def _find_window(title_hint: str) -> Optional[int]:
    """Return the hwnd of a top-level window whose title contains `title_hint`, else None."""
    user32 = _win32_user32()
    user32.EnumWindows.argtypes = [_WIN_WNDENUMPROC, wt.LPARAM]
    user32.EnumWindows.restype = wt.BOOL
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    found: list[int] = []

    def _cb(hwnd, _l):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if buf.value and title_hint in buf.value:
            found.append(hwnd)
        return True

    user32.EnumWindows(_WIN_WNDENUMPROC(_cb), 0)
    return found[0] if found else None


def _click_button_in_window(top_hwnd: int, button_text: str) -> bool:
    """Find a child Button of `top_hwnd` whose caption matches `button_text` and click it."""
    user32 = _win32_user32()
    user32.EnumChildWindows.argtypes = [wt.HWND, _WIN_WNDENUMPROC, wt.LPARAM]
    user32.EnumChildWindows.restype = wt.BOOL
    user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
    hits: list[int] = []

    def _cb(hwnd, _l):
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cls, 128)
        if cls.value != "Button":
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value.strip() == button_text:
            hits.append(hwnd)
        return True

    cbref = _WIN_WNDENUMPROC(_cb)
    user32.EnumChildWindows(wt.HWND(top_hwnd), cbref, 0)
    if not hits:
        return False
    btn = hits[0]
    # BM_CLICK (0x00F5) — sends a clean WM_COMMAND without requiring the dialog's
    # own message loop to be idle, unlike PostMessage(BM_CLICK) on a frozen thread.
    user32.SendMessageW(wt.HWND(btn), 0x00F5, 0, 0)
    return True


@mcp.tool
async def capture_handle_custom_launch_dialog(button: str = "No") -> dict:
    """Auto-dismiss Capture's modal "Capture Custom Launch" recovery dialog.

    Captured live from a real stuck batch run: after Capture's process has failed to
    launch cleanly in a prior session, the next launch presents this exact dialog
    ("Capture has detected that it did not launch properly in the previous session.
    Click 'YES' to launch Capture with the following settings? / Click 'NO' will
    launch Capture in default mode.") with a Yes/No pair of buttons, and sits there
    indefinitely — no CLI flag skips it, and it is invisible in the job's own run.log
    (a stuck job's log stays 0 bytes). This finds the dialog by its exact title and
    sends a real `BM_CLICK` (Windows message 0x00F5) to the matching button, which
    is equivalent to a human click and returns immediately (it goes through the
    window's own message pump, not the job's console). `button` is `"No"` (default —
    launch in default mode, what a human choosing "just get on with it" would click)
    or `"Yes"` (launch in the custom/safe mode the dialog's list box describes). Returns
    `{found: bool, clicked: bool}` — a caller that just launched a capture job and got
    back no log output after a reasonable wait should call this and re-check, rather
    than assuming the job is permanently hung.
    """
    top = _find_window("Capture Custom Launch")
    if top is None:
        return {"found": False, "clicked": False, "note": "No 'Capture Custom Launch' dialog currently open."}
    clicked = _click_button_in_window(top, button)
    return {"found": True, "clicked": clicked, "dialog_title_hint": "Capture Custom Launch", "button": button}


@mcp.tool
async def capture_annotate(session_id: str) -> dict:
    """Queue reference-designator annotation for the open design.

    Appends `Menu "Tools::Annotate"` — confirmed "Available from: Tools menu" in
    doc/cap_ref/Project_manager_command_reference.html.
    """
    tcl_sessions.add_line(session_id, 'Menu "Tools::Annotate"')
    return {"session_id": session_id}


@mcp.tool
async def capture_check_design_rules(session_id: str) -> dict:
    """Queue Capture's electrical/design rules check (ERC) for the open design.

    Appends `Menu "PCB::Design Rules Check"`. Confirmed from
    doc/cap_ref/Project_manager_command_reference.html's own "Design Rules Check
    command" entry: "Available from: PCB menu" (distinct from Annotate/Create Netlist
    above, which are both "Available from: Tools menu") — "Use this command to check a
    design for violations of design rules... Design Rules Check uses the decision
    matrix located in the ERC Matrix tab in the Design Rules Check dialog box." This is
    genuinely Capture's ERC equivalent (electrical rule checking against a
    user-configurable matrix), not merely a naming coincidence with Allegro's PCB-side
    DRC.

    UNCONFIRMED live, same caveat as every other capture_* tool: the exact `Menu
    "PCB::Design Rules Check"` string is built by the same "<Available-from
    menu>::<command name>" convention already confirmed working for
    `Menu "Tools::Annotate"`/`Menu "Tools::Create Netlist"` above, but this specific
    menu path itself was not independently found spelled out as a literal Tcl macro
    line anywhere in the doc tree — treat it as a well-grounded inference, not a
    transcribed example, until run live. The doc doesn't say ERC results are
    scriptably readable afterward either; per the same page, violations are placed as
    DRC markers on the schematic pages themselves ("Browse DRC Markers" on the Edit
    menu) rather than written to a plain-text report — inspect the saved design (or a
    netlist error log) rather than expecting a summary file back from this tool.
    """
    tcl_sessions.add_line(session_id, 'Menu "PCB::Design Rules Check"')
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


async def auto_dismiss_recovery_dialog_if_stuck(job_id: str, check_after_seconds: float = 15.0) -> Optional[str]:
    """Poll one already-submitted Capture job; if it's still running with an empty log
    and a real "Capture Custom Launch" modal dialog is present, click it ("No") and
    return a note for the result. Returns None when no intervention was needed.

    Kept separate from capture_run_session (which must stay a fast, fire-and-forget
    launcher) so callers that already block on a job — like generate_schematic_from_spec —
    can opt in without every capture tool call gaining an unconditional delay.
    """
    import pathlib

    from sigrity_mcp.core.jobs import job_manager

    record = await job_manager.wait(job_id, timeout=check_after_seconds)
    if record.state != "running":
        return None
    log = pathlib.Path(record.job_dir) / "run.log"
    if log.is_file() and log.stat().st_size > 0:
        return None
    top = _find_window("Capture Custom Launch")
    if top is None:
        return None
    clicked = _click_button_in_window(top, "No")
    if clicked:
        return (
            "Job appeared stuck with an empty log; a real 'Capture Custom Launch' "
            "recovery dialog was found and auto-dismissed (clicked 'No' — see "
            "capture_handle_custom_launch_dialog). The original job_id continues; "
            "re-check it with wait_for_job/tail_job_log rather than relaunching."
        )
    return f"A 'Capture Custom Launch' dialog is present but its buttons could not be clicked (found={top is not None}) — see capture_handle_custom_launch_dialog for a manual click."
