"""Domain 4 (Sigrity Aurora / In-Design Analysis) tools.

See the package docstring in `sigrity_mcp/domains/aurora/__init__.py` for the full
research finding this domain is built on: Allegro/OrCAD (SPB 22.1) IS installed on this
machine, and Aurora is a real, confirmed GUI-only mode inside it with zero CLI/SKILL
automation surface for any of its six checks.
"""

from __future__ import annotations

from sigrity_mcp.mcp_app import mcp

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
    crosstalk, return path, reflection, IR drop — each menu/dialog-driven with zero CLI
    or SKILL automation surface found anywhere in Allegro's own SKILL function reference
    or narrative docs. Automating it would mean scripting mouse clicks through a GUI,
    which this suite doesn't do for any tool.

    One name-collision worth knowing about: `C:\\Cadence\\SPB_22.1\\tools\\bin\\aurora.exe`
    looks like it should be this feature, but is a same-name-different-product false
    lead — a launcher for Allegro Design Workbench (a PDM/design-collaboration tool),
    confirmed via its own config folder and a full-tree grep finding zero references to
    it from anywhere in Allegro's SI/PI-analysis code paths.

    What IS honestly available: every check Aurora performs in-design has a
    post-layout equivalent already implemented in this suite's other domains — see
    get_in_design_analysis_alternatives for the specific mapping.
    """
    return {
        "aurora_available": False,
        "reason": (
            "Sigrity Aurora is a real, license-gated GUI mode inside allegro.exe (Allegro/"
            "OrCAD SPB 22.1, which IS installed on this machine), with zero documented "
            "CLI or SKILL automation surface for any of its six checks — every workflow "
            "is menu/dialog-driven only, confirmed by searching Allegro's complete SKILL "
            "function reference (840 files) and narrative SKILL user guide for any "
            "Aurora/Workflow-Manager-related command and finding none."
        ),
        "confirmed_by": [
            "doc/sigrity_aurora and doc/algroroute/chap13.html (Allegro's own docs) "
            "describe every Aurora workflow as wizard/dialog-driven: net-selection "
            "dialogs, per-workflow Analysis Options dialogs, a 'Start Analysis' button",
            "Zero hits for 'aurora'/'WorkflowManager' anywhere in "
            "share/pcb/examples/skill/DOC/FUNCS/ (Allegro's complete SKILL function "
            "reference) or doc/algroskill (the narrative SKILL user guide)",
            "aurora.exe (tools/bin) is confirmed to be an unrelated Allegro Design "
            "Workbench/PDM launcher, not the SI/PI analysis feature — a same-name "
            "false lead, not evidence Aurora is scriptable",
            "allegrosigritypi.exe/allegrosigritysi.exe are confirmed plain GUI "
            "product-launchers into Allegro (pre-selecting a license tier), not "
            "independently batch-scriptable — no -b/-tcl-style flag exists for either",
        ],
        "see_also": "get_in_design_analysis_alternatives",
    }


@mcp.tool
async def get_in_design_analysis_alternatives() -> dict:
    """List the standalone-tool equivalents in this suite for each kind of check Sigrity Aurora performs in-design.

    Aurora's value is doing these checks live, inside the layout editor, as routing
    happens — that interactivity is GUI-only with no scripting hook, so this suite can't
    reproduce it even though Allegro/OrCAD is installed here. What it can do is run the
    same underlying analysis after the fact (or on a pre-layout stackup/topology) using
    PowerSI, PowerDC, Clarity3D, and XtractIM, which are all confirmed real and working
    in this environment.
    """
    return {"alternatives": _ALTERNATIVES}
