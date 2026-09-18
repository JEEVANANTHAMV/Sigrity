"""Domain 4 (Sigrity Aurora / In-Design Analysis) tools.

See the package docstring in `sigrity_mcp/domains/aurora/__init__.py` for the full
research finding this domain is built on: Aurora runs inside Allegro/OrCAD X, not as a
standalone Sigrity Suite tool, and no Allegro/OrCAD install exists on this machine.
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
    tool here to run. Aurora is Cadence's real-time SI/PI/power-aware checking flow
    that runs *inside* Allegro/OrCAD X PCB Editor during layout, using Sigrity's
    simulation engines as a linked library. It has no standalone executable, and no
    Allegro/OrCAD install exists on this machine (confirmed: zero Aurora-named files
    anywhere under the Sigrity Suite install, despite "Sigrity Aurora" appearing as a
    licensed product *bundle name* in this machine's install manifest — that bundle
    entry describes what the license covers if Allegro/OrCAD were also installed, not
    a tool present here). No public documentation of an Aurora-specific SKILL/Tcl
    scripting surface was found either, so even a hypothetical future Allegro install
    couldn't be safely automated from what's confirmed today.

    What IS honestly available: every check Aurora performs in-design has a
    post-layout equivalent already implemented in this suite's other domains — see
    get_in_design_analysis_alternatives for the specific mapping.
    """
    return {
        "aurora_available": False,
        "reason": (
            "Sigrity Aurora runs inside Allegro/OrCAD X PCB Editor, not as a standalone "
            "Sigrity Suite executable. No Allegro/OrCAD install is present on this "
            "machine, and no public Aurora-specific SKILL/Tcl automation surface was "
            "found during research, so this suite cannot launch, configure, or query "
            "Aurora sessions without fabricating a capability it doesn't have."
        ),
        "confirmed_by": [
            "Zero Aurora-named executables/DLLs anywhere under C:\\Cadence\\Sigrity2024.0",
            "This machine's install manifest lists 'Sigrity Aurora' only as a licensed "
            "product *bundle name* (what an Allegro/OrCAD license would unlock), not an "
            "installed component",
            "Cadence installation-guide text: Aurora/SystemSI/SystemPI/Topology Explorer "
            "flows run 'from the Cadence OrCAD and Allegro 22.10 base or later release'",
        ],
        "see_also": "get_in_design_analysis_alternatives",
    }


@mcp.tool
async def get_in_design_analysis_alternatives() -> dict:
    """List the standalone-tool equivalents in this suite for each kind of check Sigrity Aurora performs in-design.

    Aurora's value is doing these checks live, inside the layout editor, as routing
    happens. This suite can't reproduce that interactivity without Allegro/OrCAD
    installed — but it can run the same underlying analysis after the fact (or on a
    pre-layout stackup/topology) using PowerSI, PowerDC, Clarity3D, and XtractIM, which
    are all confirmed real and working in this environment.
    """
    return {"alternatives": _ALTERNATIVES}
