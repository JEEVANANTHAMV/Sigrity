"""XtractIM — 2.5D/3D package/PCB parasitic (PG/EPA) extraction.

Two confirmed, independent invocation modes:

(a) Primary/simple mode — a pre-built XML "ExtractorWorkspace" file, no Tcl involved:
    `XtractIM -b "<workspace.xml>" ["<new_spd_override.spd>"]`

(b) Session/Tcl mode, `sigrity::` namespace, confirmed verbatim sample:
    sigrity::open document {!}
    sigrity::open document -attach {@spd} {!}
    sigrity::update net selected 0 -all {!}
    sigrity::update net selected 1 {@GND} {!}
    sigrity::update net color {000128128} {@GND} {!}
    sigrity::update Mode {EPA} {!}
    sigrity::update PackageType -d {0} -b {0} -a {1} {!}
    sigrity::update Circuits -d {U1} -b {BGA1} -c {C1} {C2} {!}
    sigrity::add Layer {bump} -above {Signal$M1} -circuit {U1} {!}
    sigrity::update layer thickness 1.0000e-006 {Bump01} {!}
    sigrity::update PGAnalysis -i {1} -b {0} -freq {2} -g {0} -d {1} -l {1} -p {2} -x {1} -y {1} -all {!}
    sigrity::process shape {!}
    sigrity::save -workspace {@workspace} {!}
    sigrity::apply OutputACR {1}
    sigrity::begin simulation {!}

Unlike Clarity3D, XtractIM's Tcl lines DO use the `{!}` end-of-statement terminator
token, matching PowerSI's convention — this module includes it everywhere the confirmed
sample does.

Usage pattern for mode (b): start_xtractim_session -> zero or more xtractim_* "compose"
tools (each just appends a Tcl line, no process launched) -> xtractim_run_session
(writes the accumulated script and actually launches XtractIM once). Use
preview_tcl_session/close_tcl_session (sigrity_mcp.domains.platform.session_tools) to
inspect or discard a session, and the job-control tools (get_job_status, tail_job_log,
list_job_files, read_job_output_file) to track/retrieve the run.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_xtractim_workspace(workspace_xml: str, spd_override: Optional[str] = None) -> dict:
    """Run XtractIM against a pre-built "ExtractorWorkspace" XML file, as a background job.

    This is XtractIM's simple, no-Tcl invocation mode — the workspace XML (produced
    interactively or hand-authored beforehand) already fully describes nets, package
    type, circuits, and analysis options. Runs `XtractIM -b "<workspace_xml>" ["<spd_override>"]`;
    `spd_override` optionally re-points the extraction at a different `.spd` layout than
    the one recorded in the workspace file.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = ["-b", workspace_xml]
    if spd_override:
        args.append(spd_override)
    record = await submit_job(tool="xtractim", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def start_xtractim_session(spd_file: str) -> dict:
    """Begin a new XtractIM Tcl automation session by opening a layout (.spd) document.

    Returns a session_id — pass it to every other xtractim_* tool below to keep adding
    steps (net selection, package type, circuits, analysis options, ...) to the same
    macro, then finish with xtractim_run_session. Nothing is executed yet; this only
    records:
        sigrity::open document {!}
        sigrity::open document -attach {<spd_file>} {!}
    """
    session = tcl_sessions.create("xtractim")
    sid = session.session_id
    tcl_sessions.add_line(sid, "sigrity::open document {!}")
    tcl_sessions.add_line(sid, f"sigrity::open document -attach {tcl_path(spd_file)} {{!}}")
    return {"session_id": sid, "spd_file": spd_file}


@mcp.tool
async def xtractim_select_net(session_id: str, net_name: Optional[str] = None, selected: bool = True) -> dict:
    """Select or deselect one net by name, or every net at once when `net_name` is omitted.

    Appends `sigrity::update net selected {<0|1>} {<net_name>} {!}` for a named net
    (matching the confirmed sample `sigrity::update net selected 1 {@GND} {!}`), or
    `sigrity::update net selected {<0|1>} -all {!}` when `net_name` is None (matching
    the confirmed sample `sigrity::update net selected 0 -all {!}`, typically used to
    deselect everything before selecting specific nets of interest).
    """
    flag = 1 if selected else 0
    if net_name is None:
        tcl_sessions.add_line(session_id, f"sigrity::update net selected {flag} -all {{!}}")
    else:
        tcl_sessions.add_line(session_id, f"sigrity::update net selected {flag} {tcl_str(net_name)} {{!}}")
    return {"session_id": session_id, "net_name": net_name, "selected": selected}


@mcp.tool
async def xtractim_set_mode(session_id: str, mode: Literal["EPA"] = "EPA") -> dict:
    """Set the XtractIM analysis mode for this session (currently only 'EPA' — Electrical Package Analysis — is confirmed).

    Appends `sigrity::update Mode {<mode>} {!}`.
    """
    tcl_sessions.add_line(session_id, f"sigrity::update Mode {tcl_str(mode)} {{!}}")
    return {"session_id": session_id, "mode": mode}


@mcp.tool
async def xtractim_set_package_type(session_id: str, die: int = 0, board: int = 0, assembly: int = 1) -> dict:
    """Set which package layers (die/board/assembly) participate in the extraction, as 0/1 flags.

    Appends `sigrity::update PackageType -d {<die>} -b {<board>} -a {<assembly>} {!}`
    (matching the confirmed sample `sigrity::update PackageType -d {0} -b {0} -a {1} {!}`).
    """
    tcl_sessions.add_line(
        session_id, f"sigrity::update PackageType -d {{{die}}} -b {{{board}}} -a {{{assembly}}} {{!}}"
    )
    return {"session_id": session_id, "die": die, "board": board, "assembly": assembly}


@mcp.tool
async def xtractim_set_circuits(
    session_id: str,
    die_ref_des: str,
    board_ref_des: str,
    component_ref_des_list: list[str],
) -> dict:
    """Assign the die/board reference designators and the component(s) to extract for this circuit.

    Appends `sigrity::update Circuits -d {<die_ref_des>} -b {<board_ref_des>} -c {<c1>} {<c2>} ... {!}`
    (matching the confirmed sample
    `sigrity::update Circuits -d {U1} -b {BGA1} -c {C1} {C2} {!}`).
    """
    parts = [
        "sigrity::update Circuits",
        f"-d {tcl_str(die_ref_des)}",
        f"-b {tcl_str(board_ref_des)}",
        "-c",
        *(tcl_str(c) for c in component_ref_des_list),
        "{!}",
    ]
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {
        "session_id": session_id,
        "die_ref_des": die_ref_des,
        "board_ref_des": board_ref_des,
        "component_ref_des_list": component_ref_des_list,
    }


@mcp.tool
async def xtractim_set_pg_analysis_options(
    session_id: str,
    inductance: bool = True,
    dcr: bool = True,
    loop_inductance: bool = True,
    per_pin_mode: int = 2,
    frequency_mode: int = 2,
) -> dict:
    """Configure power/ground (PG) analysis options: which quantities to extract and at what resolution.

    Booleans map to 0/1. Appends
    `sigrity::update PGAnalysis -i {<0|1>} -d {<0|1>} -l {<0|1>} -p {<per_pin_mode>} -freq {<frequency_mode>} -all {!}`.
    This is a reduced subset of the confirmed full sample line (which also carries
    `-b`/`-g`/`-x`/`-y` flags not exposed here) — `dcr` maps to `-d` (DC resistance) and
    `loop_inductance` maps to `-l`.
    """
    i_flag = 1 if inductance else 0
    d_flag = 1 if dcr else 0
    l_flag = 1 if loop_inductance else 0
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::update PGAnalysis -i {{{i_flag}}} -d {{{d_flag}}} -l {{{l_flag}}} "
            f"-p {{{per_pin_mode}}} -freq {{{frequency_mode}}} -all {{!}}"
        ),
    )
    return {
        "session_id": session_id,
        "inductance": inductance,
        "dcr": dcr,
        "loop_inductance": loop_inductance,
        "per_pin_mode": per_pin_mode,
        "frequency_mode": frequency_mode,
    }


@mcp.tool
async def xtractim_process_and_save(session_id: str, workspace_file: str) -> dict:
    """Process the current shape/setup and save the accumulated setup as a workspace file.

    Appends `sigrity::process shape {!}` then `sigrity::save -workspace {<workspace_file>} {!}`.
    """
    tcl_sessions.add_line(session_id, "sigrity::process shape {!}")
    tcl_sessions.add_line(session_id, f"sigrity::save -workspace {tcl_path(workspace_file)} {{!}}")
    return {"session_id": session_id, "workspace_file": workspace_file}


@mcp.tool
async def xtractim_run_session(session_id: str) -> dict:
    """Write out the session's accumulated Tcl macro and launch XtractIM against it as a background job.

    Appends `sigrity::apply OutputACR {1}` then `sigrity::begin simulation {!}` (matching
    the confirmed sample's tail exactly, note the first line's lack of a `{!}` terminator
    is intentional/as-observed), then runs `XtractIM -b -tcl <macro.tcl>`.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    tcl_sessions.add_line(session_id, "sigrity::apply OutputACR {1}")
    tcl_sessions.add_line(session_id, "sigrity::begin simulation {!}")
    record = await run_session(
        session_id,
        tool="xtractim",
        tcl_arg_flag="-tcl",
        build_args=["-b"],
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
