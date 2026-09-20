"""CelsiusCFD automation — computational-fluid-dynamics thermal simulation, Tcl-scripted, session-based.

CONFIRMED LIVE end-to-end on this machine against a real Cadence sample project
(`share/PostInstallationCheck/celsiuscfd/pcb_pkg_sav.3dth` + `pcb_pkg_sav.tcl`):
`CelsiusCFD.exe -tcl pcb_pkg_sav.tcl` exited 0 and produced a real result — "Starting
the steady-state simulation" / "CelsiusECSolver is completed" / "CFD network file (.cfd)
is generated!" in the engine log. The `sigrity::` sequence this module generates is
transcribed directly from that confirmed-working sample: `sigrity::configure version
-version {5}`, `sigrity::open file -file {<project>}`, an optional `sigrity::update
CFDSolverOptions -SolverCPUPercentage {n}`, `sigrity::begin simulation
-fileName {<project>}`, `sigrity::end simulation -fileName {<project>}`,
`sigrity::close exe`.

IMPORTANT: Celsius3D (the sibling structural/thermal-stress solver, same product
family) was confirmed via both direct testing and the multi-model eval harness to hang
indefinitely when re-run against a project directory that already has a prior run's
result folder — very likely a GUI overwrite-confirmation dialog. CelsiusCFD was not
independently re-tested this exact way, but treat it as likely subject to the same
risk until proven otherwise: always run against a fresh copy of the project directory,
never re-run in place.

Same scope note as celsius3d_tools.py: `start_celsiuscfd_session` expects a `.3dth`
project that already has its CFD setup (geometry, materials, boundary conditions)
configured — this automates *running* an existing project, not authoring one from bare
geometry, since no additional CelsiusCFD Tcl setup vocabulary was found documented
anywhere in the shipped doc tree beyond this confirmed sequence.
"""

from __future__ import annotations

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
async def start_celsiuscfd_session(project_file: str) -> dict:
    """Begin a new CelsiusCFD automation session by opening a `.3dth` CFD-thermal project.

    Returns a session_id — pass it to celsiuscfd_set_solver_cpu_percentage (optional)
    and celsiuscfd_run_session. Nothing runs yet; this records the confirmed preamble
    `sigrity::configure version -version {5}` then `sigrity::open file
    -file {<project_file>}`, transcribed from the real working sample
    `share/PostInstallationCheck/celsiuscfd/pcb_pkg_sav.tcl`.
    """
    session = tcl_sessions.create("celsiuscfd")
    tcl_sessions.add_line(session.session_id, "sigrity::configure version -version {5}")
    tcl_sessions.add_line(session.session_id, f"sigrity::open file -file {tcl_path(project_file)}")
    return {"session_id": session.session_id, "project_file": project_file}


@mcp.tool
async def celsiuscfd_set_solver_cpu_percentage(session_id: str, cpu_percentage: int) -> dict:
    """Set what percentage of available CPU the CFD solver is allowed to use.

    Appends `sigrity::update CFDSolverOptions -SolverCPUPercentage {<cpu_percentage>}`,
    confirmed against the real working sample (which used `{1}` — a deliberately small
    value for a fast post-install smoke test, not necessarily a recommended production
    setting). This is the only CelsiusCFD-specific solver-configuration Tcl command
    confirmed on this machine.
    """
    tcl_sessions.add_line(
        session_id, f"sigrity::update CFDSolverOptions -SolverCPUPercentage {{{cpu_percentage}}}"
    )
    return {"session_id": session_id, "cpu_percentage": cpu_percentage}


@mcp.tool
async def celsiuscfd_run_session(session_id: str, project_file: str, clean_prior_results: bool = True) -> dict:
    """Write out the session's accumulated Tcl macro and launch CelsiusCFD against it as a background job.

    `project_file` must be the same `.3dth` path passed to start_celsiuscfd_session.
    Appends `sigrity::begin simulation -fileName {<project_file>}`, `sigrity::end
    simulation -fileName {<project_file>}`, then `sigrity::close exe`, matching the
    confirmed working sample exactly, then runs `CelsiusCFD.exe -tcl <macro.tcl>` (no
    `-b` flag needed — confirmed live without it).
    When `clean_prior_results` is True (default), prior CFD output directories
    are cleared before launching to prevent interactive overwrite dialogs.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    if clean_prior_results:
        _clear_prior_celsius_results(project_file)

    path = tcl_path(project_file)
    tcl_sessions.add_line(session_id, f"sigrity::begin simulation -fileName {path}")
    tcl_sessions.add_line(session_id, f"sigrity::end simulation -fileName {path}")
    tcl_sessions.add_line(session_id, "sigrity::close exe")
    record = await run_session(session_id, tool="celsiuscfd", tcl_arg_flag="-tcl")
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
