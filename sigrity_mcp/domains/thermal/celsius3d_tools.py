"""Celsius3D automation — 3D electrothermal/thermal-stress simulation, Tcl-scripted, session-based.

CONFIRMED LIVE end-to-end on this machine against a real Cadence sample project
(`share/PostInstallationCheck/celsius3d/case.3dth` + `case.tcl`): `Celsius3D.exe -tcl
case.tcl` exited 0 and produced a real result set — "Stress engine started and completed
successfully!" in the engine log, and real numeric displacement/strain/stress values in
`case_Result_Summary.dat`/`.json`. The exact four-line `sigrity::` sequence this module
generates is transcribed directly from that confirmed-working sample, not guessed:
`sigrity::configure version -version {5}`, `sigrity::open file -file {<project>}`,
`sigrity::begin simulation -fileName {<project>}`, `sigrity::end simulation
-fileName {<project>}`, `sigrity::close exe`.

IMPORTANT, confirmed live and re-tested multiple times on this machine (Sigrity
2024.0): re-running `celsius3d_run_session` against a project directory that already
contains a prior run's result folder (e.g. `<name>_SS_W/`) leaves the `Celsius3D.exe`
process running indefinitely after the simulation has actually completed — the job
appears to "hang with an empty log". Root cause, confirmed by direct window-tree
inspection (pywin32, see core/win32gui_helper.py): the simulation itself COMPLETEs and
writes the full result set (~20-30 s, identical to a fresh run), but afterwards the
process stays alive and idle (CPU frozen, main Qt workbench window open, NO modal
dialog with a clickable button in its window tree) — an "Unsaved Project" Qt
QMainWindow appears as a second visible top-level window (class
`Qt5159QWindowIcon`, empty window text, zero visible/enabled children in EnumWindows),
but it is not a classic Win32 dialog — WM_CLOSE / synthetic Enter / BN_CLICKED to any
child do not dismiss it, and there is no Yes/No button window to find. This is NOT a
GUI overwrite-confirmation prompt in the Win32-dialog sense; it is a post-completion
exit stall. It also happens on the very FIRST run of a "fresh" project (observed:
simulation written, process idle-exit-stalled) — it is not strictly a
re-run/overwrite-specific bug, even though re-runs reliably exhibit it. The
JobManager's `wait(timeout)` then times out, `tail_job_log` shows only the "legacy
command line syntax" banner (Celsius3D writes little/nothing to stdout), and the job is
either still reported "running" or gets killed on hard timeout.

CONFIRMED WORKAROUND (use this always): run against a FRESH copy of the project — copy
`.3dth` + `.tcl` into a new directory and delete/never-reuse any existing
`<name>_SS_W/` result folder — and additionally, because the process does not reliably
self-exit even after completion, have the caller (or a JobManager side-task) treat
"SR3d.dat + case_Result_Summary.dat have appeared with reasonable size" as the real
completion signal rather than "process exited", and/or poll
`win32gui_helper.find_process_windows(pid)` / `find_dialogs(pid)` and dismiss the
Unsaved-Project window (it does not close cleanly by message posting today, so the
pragmatic close is to `kill` the Celsius3D.exe process once the result files exist —
the work is done by then). `core/win32gui_helper.py` is the reusable pywin32 helper
for exactly this: poll the process's window tree, read dialog titles/classes, and drive
dismissal (WM_COMMAND BN_CLICKED to a Yes/OK/Confirm child, VK_RETURN/VK_SPACE, WM_CLOSE)
— it is wired for any Cadence tool that pops a real dialog; for Celsius3D specifically
it confirms the post-completion-idle-stall diagnosis but the actual close still requires
killing the process once the result set is on disk.

SCOPE NOTE: unlike PowerDC/PowerSI (which have many `sigrity::set`/`sigrity::add`
compose tools for building up a simulation from scratch), no additional Celsius3D-
specific Tcl setup vocabulary (materials, boundary conditions, power maps, mesh
settings) was found documented anywhere in the shipped doc tree beyond this confirmed
open/run/close sequence. In practice this means `start_celsius3d_session` expects a
`.3dth` project file that already has its thermal setup (materials, sources, boundary
conditions) configured — via `CelsiusStudio.exe`'s GUI, or IMPORTANT and confirmed
during Domain 1 development, PowerDC's own thermal/electro-thermal features
(`powerdc_mark_thermal_component`, `powerdc_set_power_dissipation`) — this tool only
automates *running* an already-built Celsius3D project, not authoring one from bare
geometry. Extend this module if a real project surfaces additional confirmed
`sigrity::` commands.
"""

from __future__ import annotations

import os
import pathlib
import shutil

from sigrity_mcp.core.tclscript import tcl_path
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp


def _clear_prior_celsius_results(project_file: str) -> None:
    """Remove any existing result folders matching <case>_* to prevent modal overwrite prompts."""
    try:
        p = pathlib.Path(project_file)
        if p.parent.exists():
            stem = p.stem
            for item in p.parent.glob(f"{stem}_*"):
                if item.is_dir() and item.name.endswith(("_SS_W", "_Result", "_CFD", "_EC", "_Results")):
                    shutil.rmtree(item, ignore_errors=True)
    except Exception:
        pass


@mcp.tool
async def start_celsius3d_session(project_file: str) -> dict:
    """Begin a new Celsius3D automation session by opening a `.3dth` thermal project.
See `.forjinn/skills/sigrity-celsius/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    session = tcl_sessions.create("celsius3d")
    tcl_sessions.add_line(session.session_id, "sigrity::configure version -version {5}")
    tcl_sessions.add_line(session.session_id, f"sigrity::open file -file {tcl_path(project_file)}")
    return {"session_id": session.session_id, "project_file": project_file}


@mcp.tool
async def celsius3d_run_session(session_id: str, project_file: str, clean_prior_results: bool = True) -> dict:
    """Write out the session's accumulated Tcl macro and launch Celsius3D against it as a background job.
See `.forjinn/skills/sigrity-celsius/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if clean_prior_results:
        _clear_prior_celsius_results(project_file)

    path = tcl_path(project_file)
    tcl_sessions.add_line(session_id, f"sigrity::begin simulation -fileName {path}")
    tcl_sessions.add_line(session_id, f"sigrity::end simulation -fileName {path}")
    tcl_sessions.add_line(session_id, "sigrity::close exe")
    record = await run_session(session_id, tool="celsius3d", tcl_arg_flag="-tcl")
    project_dir = os.path.dirname(os.path.abspath(project_file))
    stem = os.path.splitext(os.path.basename(project_file))[0]
    results_dir = os.path.join(project_dir, f"{stem}_SS_W")
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "results_dir": results_dir,
        "note": (
            "Celsius3D does NOT reliably self-exit after a successful solve -- it idles "
            "with an 'Unsaved Project' Qt window that cannot be dismissed by message "
            "posting. Do NOT gate on state=='succeeded' or returncode; the process may "
            "never self-exit even on success. The real completion signal is SR3d.dat + "
            "case_Result_Summary.dat/.json present at real size in results_dir (next to "
            "project_file, NOT in job_dir). Once those exist at real size, it is safe to "
            "force-kill the now-idle Celsius3D.exe process (pid on this record) -- the "
            "work is already on disk. This stall can happen even on a completely fresh, "
            "never-run project dir, so clean_prior_results=True is necessary but not "
            "sufficient to avoid it."
        ),
    }
