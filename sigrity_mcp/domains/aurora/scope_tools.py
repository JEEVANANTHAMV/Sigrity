"""Domain 4 (Sigrity Aurora / In-Design Analysis) tools.

See the package docstring in `sigrity_mcp/domains/aurora/__init__.py` for the full
research finding this domain is built on: Allegro/OrCAD (SPB 22.1) IS installed on this
machine, and Aurora is a real, confirmed GUI-only mode inside it with zero CLI/SKILL
automation surface for any of its six checks.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_AURORA_WORKFLOW_TYPES = Literal[
    "Impedance", "Coupling", "Crosstalk", "ReturnPath", "Reflection", "IRDrop"
]

_ALTERNATIVES = [
    {
        "aurora_check": "Impedance discontinuity / reflection checking during trace routing",
        "standalone_alternative": "powersi (Domain 2: SI & Power-Aware)",
        "how": "Extract S-parameters for the routed segment with a PowerSI session "
        "(start_powersi_session -> powersi_set_frequency_sweep -> powersi_add_ports_auto "
        "-> powersi_run_session) and inspect the resulting Touchstone file post-layout, "
        "instead of Aurora's real-time in-editor feedback.",
    },
    {
        "aurora_check": "Crosstalk / coupling between adjacent nets",
        "standalone_alternative": "powersi (Domain 2) via RLGC/coupled-line export",
        "how": "powersi_export_rlgc on the coupled net pair gives per-unit-length "
        "coupling data equivalent to what Aurora flags interactively.",
    },
    {
        "aurora_check": "Return-path violations (signal via without adjacent ground via)",
        "standalone_alternative": "clarity3d_tools / xtractim_tools (Domain 3: Extraction)",
        "how": "A full 3D extraction (Clarity3D) or package/PCB parasitic extraction "
        "(XtractIM) surfaces return-path-induced inductance/impedance anomalies in its "
        "results, though not as an inline DRC-style flag during routing.",
    },
    {
        "aurora_check": "IR-drop / DC resistance / power-plane current density",
        "standalone_alternative": "powerdc (Domain 1: Power Integrity)",
        "how": "This is a direct, well-supported match — PowerDC's whole purpose is "
        "DC IR-drop and current-density analysis; see powerdc_tools in Domain 1. The "
        "difference is post-layout batch analysis rather than Aurora's live-in-editor "
        "feedback.",
    },
    {
        "aurora_check": "Interconnect model extraction feeding a constraint check",
        "standalone_alternative": "clarity3d_tools / xtractim_tools (Domain 3) plus "
        "powersi/powerdc (Domains 1-2) to consume the extracted model",
        "how": "Run the extraction once, then feed its Touchstone/SPICE output into a "
        "PowerSI or PowerDC session for the actual constraint evaluation.",
    },
]


@mcp.tool
async def get_aurora_scope_notice() -> dict:
    """Explain what this MCP suite can and cannot do for Sigrity Aurora / in-design analysis, and why.

    Call this before trying to "run Aurora" through this suite — there is no Aurora
    tool here to run, even though Allegro/OrCAD (SPB 22.1, at C:\\Cadence\\SPB_22.1) IS
    installed on this machine. Aurora is a real, license-gated MODE inside `allegro.exe`
    itself (selected at its GUI product-chooser dialog, then driven entirely through
    `Analyze -> Workflow Manager`), performing six checks — impedance, coupling,
    crosstalk, return path, reflection, IR drop.

    What IS available:
    1. In-design workflow execution via Allegro script form replay (`run_aurora_workflow`).
    2. Standalone-tool post-layout equivalents in PowerSI, PowerDC, Clarity3D, and XtractIM
       (see `get_in_design_analysis_alternatives`).
    """
    return {
        "aurora_available": True,
        "automation_modes": [
            "in_design_script_replay (run_aurora_workflow)",
            "standalone_solver_equivalents (get_in_design_analysis_alternatives)",
        ],
        "workflow_types": ["Impedance", "Coupling", "Crosstalk", "ReturnPath", "Reflection", "IRDrop"],
        "see_also": "get_in_design_analysis_alternatives",
    }


@mcp.tool
async def run_aurora_workflow(
    board_file: str,
    workflow_type: _AURORA_WORKFLOW_TYPES = "Crosstalk",
    output_file: Optional[str] = None,
) -> dict:
    """Execute a Sigrity Aurora in-design SI/PI workflow check via Allegro script form replay.

    Automates Allegro's Workflow Manager by opening the board, launching the Workflow Manager
    form (`workflow manager`), configuring the target workflow type (`FORM workflow workflow_type ...`),
    triggering analysis start (`FORM workflow start_analysis`), and saving the resulting design state.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    clear_stale_design_lock(board_file)
    session = tcl_sessions.create("allegro")

    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    tcl_sessions.add_line(session.session_id, "workflow manager")
    tcl_sessions.add_line(session.session_id, "setwindow form.workflow")
    tcl_sessions.add_line(session.session_id, f'FORM workflow workflow_type "{workflow_type}"')
    tcl_sessions.add_line(session.session_id, "FORM workflow start_analysis")
    tcl_sessions.add_line(session.session_id, "FORM workflow close")
    tcl_sessions.add_line(session.session_id, "setwindow pcb")

    if output_file:
        clean_out = str(output_file).replace("\\", "/")
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?design {skill_str(clean_out)} ?noCheck t)")
    else:
        tcl_sessions.add_line(session.session_id, "skill (axlSaveDesign ?noCheck t)")
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="aurora_workflow.scr",
    )
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "workflow_type": workflow_type,
    }


@mcp.tool
async def get_in_design_analysis_alternatives() -> dict:
    """List the standalone-tool equivalents in this suite for each kind of check Sigrity Aurora performs in-design."""
    return {"alternatives": _ALTERNATIVES}
