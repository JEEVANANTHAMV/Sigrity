"""XcitePI automation — chip/package power integrity, decap placement, and IO model extraction.

Confirmed real batch invocation (via Cadence's own `postInstallCheck.pl` script, not the
user guide): `XcitePI.exe -b -tcl <script.tcl>`. Unlike PowerSI/PowerDC/OptimizePI,
XcitePI's Tcl commands use FLAT function names rather than a `sigrity::` namespace
(e.g. `xpi_new_design`, `xpi_open_file`, `xpi_start`, ...) — transcribed from the real
sample script `share/PostInstallationCheck/xcitepi/demo_decap.tcl`.

Usage pattern: start_xcitepi_session -> one or more xcitepi_* "compose" tools (each just
appends a Tcl line, no process launched) -> xcitepi_run_session (writes the accumulated
script, appends `xpi_start`/`xpi_close_design`/`xpi_exit`, and actually launches XcitePI
once). Use preview_tcl_session/close_tcl_session (sigrity_mcp.domains.platform.session_tools)
to inspect or discard a session, and the job-control tools (get_job_status,
tail_job_log, list_job_files, read_job_output_file) to track/retrieve the run started by
xcitepi_run_session.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_FEATURES = Literal["TD", "FD", "PME", "IOME", "PP"]
_SPICE_STYLE = Literal["pin", "net"]
_SPICE_EXTRACTION = Literal["r", "rc", "all"]
_REPORT_SCOPE = Literal["decap", "circuit", "all"]


@mcp.tool
async def start_xcitepi_session(feature: _FEATURES, tech_file: str) -> dict:
    """Begin a new XcitePI automation session by selecting an analysis feature and loading a technology file.

    `feature` selects XcitePI's working mode: 'TD' (time domain), 'FD' (frequency
    domain), 'PME' (power model extraction), 'IOME' (IO model extraction — the decap/
    SPICE-model flow shown in the confirmed sample script), or 'PP' (post-processing).
    Returns a session_id — pass it to every other xcitepi_* tool below, then finish with
    xcitepi_run_session. Nothing is executed yet; this records
    `xpi_set_feature {<feature>}` followed by `xpi_set_tech_file {<tech_file>}`.
    """
    session = tcl_sessions.create("xcitepi")
    tcl_sessions.add_line(session.session_id, f"xpi_set_feature {tcl_str(feature)}")
    tcl_sessions.add_line(session.session_id, f"xpi_set_tech_file {tcl_path(tech_file)}")
    return {"session_id": session.session_id, "feature": feature, "tech_file": tech_file}


@mcp.tool
async def xcitepi_open_layout(session_id: str, layout_file: str, map_file: Optional[str] = None) -> dict:
    """Open a layout (e.g. a GDS file) into the current XcitePI session, optionally with a companion pin/net map file.

    Appends `xpi_open_file {<layout_file>} [{<map_file>}]`, matching the confirmed sample
    `xpi_open_file {demo_decap.gds} {demo1.map}`.
    """
    parts = [f"xpi_open_file {tcl_path(layout_file)}"]
    if map_file is not None:
        parts.append(tcl_path(map_file))
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "layout_file": layout_file, "map_file": map_file}


@mcp.tool
async def xcitepi_save_design(session_id: str, xpi_file: str) -> dict:
    """Save the current XcitePI design to a `.xpi` project file.

    Appends `xpi_save_design {<xpi_file>}`. The confirmed sample script calls this twice
    (once right after opening the layout, again after configuring SPICE output) — call
    this tool again at whatever point in your macro you want a checkpoint saved.
    """
    tcl_sessions.add_line(session_id, f"xpi_save_design {tcl_path(xpi_file)}")
    return {"session_id": session_id, "xpi_file": xpi_file}


@mcp.tool
async def xcitepi_set_spice_output(
    session_id: str,
    output_file: str,
    style: _SPICE_STYLE = "pin",
    extraction: _SPICE_EXTRACTION = "rc",
) -> dict:
    """Configure where and how XcitePI writes its extracted SPICE model.

    `style` selects `-pin` (per-pin, the confirmed sample's choice) or `-net` (per-net)
    SPICE output. `extraction` selects the model's parasitic content: 'r' (resistance
    only), 'rc' (resistance+capacitance, default), or 'all'. Appends
    `xpi_set_spice_output_path {<output_file>}` followed by
    `xpi_set_spice_option -<style> -<extraction>`.
    """
    tcl_sessions.add_line(session_id, f"xpi_set_spice_output_path {tcl_path(output_file)}")
    tcl_sessions.add_line(session_id, f"xpi_set_spice_option -{style} -{extraction}")
    return {"session_id": session_id, "output_file": output_file, "style": style, "extraction": extraction}


@mcp.tool
async def xcitepi_generate_report(session_id: str, output_file: str, scope: _REPORT_SCOPE = "all") -> dict:
    """Queue a decap/circuit report once the extraction has run.

    `scope` selects 'decap' (decap placement/values only), 'circuit' (circuit-level
    results only), or 'all' (default, both). Appends `xpi_report -<scope> -output {<output_file>}`.
    """
    tcl_sessions.add_line(session_id, f"xpi_report -{scope} -output {tcl_path(output_file)}")
    return {"session_id": session_id, "output_file": output_file, "scope": scope}


@mcp.tool
async def xcitepi_save_iome_result(session_id: str, result_file: str) -> dict:
    """Queue saving the IO-model-extraction (IOME) result to a file, matching the confirmed sample's `xpi_save_iome_result {demo_decap}` step.

    Appends `xpi_save_iome_result {<result_file>}`. Only meaningful when the session was
    started with feature='IOME'.
    """
    tcl_sessions.add_line(session_id, f"xpi_save_iome_result {tcl_path(result_file)}")
    return {"session_id": session_id, "result_file": result_file}


@mcp.tool
async def xcitepi_run_session(session_id: str) -> dict:
    """Write out the session's accumulated Tcl macro and launch XcitePI against it as a background job.

    Before running, this appends `xpi_start` (runs the extraction — confirmed via the
    real sample script), then `xpi_close_design` and `xpi_exit` as the macro's final
    lines, matching the confirmed sample script's ending sequence. Runs
    `XcitePI.exe -b -tcl <macro.tcl>`. Returns a job_id immediately; poll it with
    get_job_status/wait_for_job.
    """
    tcl_sessions.add_line(session_id, "xpi_start")
    tcl_sessions.add_line(session_id, "xpi_close_design")
    tcl_sessions.add_line(session_id, "xpi_exit")
    record = await run_session(session_id, tool="xcitepi", tcl_arg_flag="-tcl", build_args=["-b"])
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
    }
