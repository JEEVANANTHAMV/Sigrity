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

IMPORTANT, confirmed via both direct manual re-testing and two independent LLM-driven
end-to-end runs (`scripts/eval_e2e.py`'s `thermal_celsius3d_signoff` task, against both
configured endpoints): re-running `celsius3d_run_session` against a project directory
that already contains a prior run's result folder (e.g. `<name>_SS_W/`) HANGS
indefinitely with an empty log — confirmed by a direct `timeout 20 Celsius3D.exe -tcl
case.tcl` against an already-simulated sample project (exit 124, no output beyond the
"legacy command line syntax" banner), and independently by both LLM test runs
discovering and correctly reporting the same hang (rather than fabricating success)
after `wait_for_job` timed out and `tail_job_log` showed no progress. The real,
first-time run against a fresh copy of the same project completed in ~20-30 seconds —
so this is very likely Celsius3D popping a GUI overwrite-confirmation dialog when it
detects existing output from a prior run, the same class of issue as the "Product
Choices" dialog that initially blocked `allegro.exe`/`Capture.exe`. Workaround: always
run against a fresh copy of the project directory (delete any prior `<name>_SS_W/`-style
result folder, or copy the project to a new location) before calling
celsius3d_run_session — do not re-run against the same project path twice in place.

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

from sigrity_mcp.core.tclscript import tcl_path
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def start_celsius3d_session(project_file: str) -> dict:
    """Begin a new Celsius3D automation session by opening a `.3dth` thermal project.

    Returns a session_id — pass it to celsius3d_run_session to execute. Nothing runs
    yet; this records the confirmed preamble `sigrity::configure version -version {5}`
    then `sigrity::open file -file {<project_file>}`, transcribed from the real working
    sample `share/PostInstallationCheck/celsius3d/case.tcl`.
    """
    session = tcl_sessions.create("celsius3d")
    tcl_sessions.add_line(session.session_id, "sigrity::configure version -version {5}")
    tcl_sessions.add_line(session.session_id, f"sigrity::open file -file {tcl_path(project_file)}")
    return {"session_id": session.session_id, "project_file": project_file}


@mcp.tool
async def celsius3d_run_session(session_id: str, project_file: str) -> dict:
    """Write out the session's accumulated Tcl macro and launch Celsius3D against it as a background job.

    `project_file` must be the same `.3dth` path passed to start_celsius3d_session
    (Celsius3D's confirmed Tcl commands take the project path again at both
    begin/end-simulation, not just at open). Appends `sigrity::begin simulation
    -fileName {<project_file>}`, `sigrity::end simulation -fileName {<project_file>}`,
    then `sigrity::close exe`, matching the confirmed working sample exactly, then runs
    `Celsius3D.exe -tcl <macro.tcl>` (no `-b` flag needed — confirmed live without it).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log —
    a real electrothermal/stress solve on a moderate design took under 30 seconds in
    testing, but larger meshes will take longer.
    """
    path = tcl_path(project_file)
    tcl_sessions.add_line(session_id, f"sigrity::begin simulation -fileName {path}")
    tcl_sessions.add_line(session_id, f"sigrity::end simulation -fileName {path}")
    tcl_sessions.add_line(session_id, "sigrity::close exe")
    record = await run_session(session_id, tool="celsius3d", tcl_arg_flag="-tcl")
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
