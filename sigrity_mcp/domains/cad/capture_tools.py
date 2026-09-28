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
if hasattr(ctypes, "WINFUNCTYPE") and hasattr(ctypes, "wintypes"):
    _WIN_WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
else:
    _WIN_WNDENUMPROC = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_long)


def _win32_user32():
    """Return the live user32 module handle. Factored out so tests (and future
    non-Windows CI environments) can swap in a fake rather than monkey-patching the
    real stdlib ``ctypes`` module globally."""
    if hasattr(ctypes, "windll"):
        return ctypes.windll.user32
    return None


@mcp.tool
async def start_capture_session(project_file: str) -> dict:
    """Begin a new OrCAD Capture automation session by opening a project (.opj).
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    clear_stale_design_lock(project_file)
    session = tcl_sessions.create("capture")
    tcl_sessions.add_line(session.session_id, f"Open {str(project_file).replace(chr(92), '/')}")
    return {"session_id": session.session_id, "project_file": project_file}


@mcp.tool
async def capture_select_page(
    session_id: str, design: str, schematic_folder: str, page: str
) -> dict:
    """Select a design/schematic page so subsequent placement acts on a real page.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    line = f"PlacePart {x} {y} {tcl_str(library_file)} {tcl_str(part_name)} {tcl_str(package)} FALSE"
    tcl_sessions.add_line(session_id, line)
    return {"session_id": session_id, "part_name": part_name, "x": x, "y": y}


@mcp.tool
async def capture_place_wire(session_id: str, x1: float, y1: float, x2: float, y2: float) -> dict:
    """Place a wire segment between two page coordinates. Appends `PlaceWire {x1} {y1} {x2} {y2}`.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, f"PlacePin {x} {y} {tcl_str(pin_name)} {tcl_str(pin_type)} FALSE")
    return {"session_id": session_id, "pin_name": pin_name}


@mcp.tool
async def capture_set_property(session_id: str, property_name: str, value: str) -> dict:
    """Set a property on the currently-selected object(s). Appends `SetProperty {property_name} {value}`.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
    """Auto-dismiss Capture's modal \"Capture Custom Launch\" recovery dialog.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    top = _find_window("Capture Custom Launch")
    if top is None:
        return {"found": False, "clicked": False, "note": "No 'Capture Custom Launch' dialog currently open."}
    clicked = _click_button_in_window(top, button)
    return {"found": True, "clicked": clicked, "dialog_title_hint": "Capture Custom Launch", "button": button}


@mcp.tool
async def capture_annotate(session_id: str) -> dict:
    """Queue reference-designator annotation for the open design.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, 'Menu "Tools::Annotate"')
    return {"session_id": session_id}


@mcp.tool
async def capture_check_design_rules(session_id: str) -> dict:
    """Queue Capture's electrical/design rules check (ERC) for the open design.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, 'Menu "PCB::Design Rules Check"')
    return {"session_id": session_id}


@mcp.tool
async def capture_create_netlist(session_id: str) -> dict:
    """Queue netlist creation for the open design, for handoff to PCB layout.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, 'Menu "Tools::Create Netlist"')
    return {"session_id": session_id}


@mcp.tool
async def capture_save(session_id: str) -> dict:
    """Queue saving the open design. Appends `Menu \"File::Save\"`.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    tcl_sessions.add_line(session_id, 'Menu "File::Save"')
    return {"session_id": session_id}


@mcp.tool
async def capture_run_session(session_id: str, product: str = "OrCAD Capture") -> dict:
    """Write out the session's accumulated Tcl macro and launch Capture against it as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
