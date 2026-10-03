"""Domain 4 (Sigrity Aurora / In-Design Analysis) tools.

See the package docstring in `sigrity_mcp/domains/aurora/__init__.py` for the original
research finding this domain is built on: Allegro/OrCAD (SPB 22.1) IS installed on this
machine, and Aurora itself is a real, license-gated GUI-only mode inside it.

UPDATED FINDING (supersedes the "zero automation surface" conclusion above): Aurora's
six checks are driven through `allegro.exe`'s Workflow Manager form, and Allegro's own
batch-script replay mechanism (`FORM ...` commands inside a `-s script.scr` run — the
same mechanism `allegro_placement_tools.py`'s Z-Router automation uses) can drive that
same form headlessly. `run_aurora_workflow` below wraps it. The standalone-tool
equivalents (`get_in_design_analysis_alternatives`) remain useful when you want
post-layout batch numbers instead of Aurora's in-editor checks.
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
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
    """Execute a Sigrity Aurora in-design SI/PI workflow check via Allegro script form replay, as a background job.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
        tcl_sessions.add_line(session.session_id, f'skill (axlSaveDesign ?design {skill_str(clean_out)} ?mode {skill_str("nocheck")})')
    else:
        tcl_sessions.add_line(session.session_id, f'skill (axlSaveDesign ?mode {skill_str("nocheck")})')
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="aurora_workflow.scr",
    )
    result_ext = {
        "Impedance": ".impida", "Coupling": ".cplida", "Crosstalk": ".xtalkida",
        "ReturnPath": ".rpida", "Reflection": ".rfltida", "IRDrop": ".irida",
    }.get(workflow_type)
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "workflow_type": workflow_type,
        "expected_result_file_ext": result_ext,
        "note": (
            "run_aurora_workflow is built_untested: the Aurora-specific FORM field names "
            "(workflow_type, start_analysis, form.workflow) are a best-effort "
            "transcription from the doc set, never confirmed end-to-end against a real "
            "board to show the check ran and wrote its result file. Do NOT gate on "
            "state=='succeeded' or returncode -- a clean board save does not mean the "
            "Aurora check worked. The only proof the check produced a result is the "
            f"presence of the proprietary Aurora result file ({result_ext}) at real size "
            "next to the board; absence means treat the Aurora step as a silent no-op. "
            "For decision-critical signoff, prefer the confirmed standalone equivalents "
            "from get_in_design_analysis_alternatives instead."
        ),
    }


@mcp.tool
async def get_in_design_analysis_alternatives() -> dict:
    """List the standalone-tool equivalents in this suite for each kind of check Sigrity Aurora performs in-design.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    return {"alternatives": _ALTERNATIVES}
