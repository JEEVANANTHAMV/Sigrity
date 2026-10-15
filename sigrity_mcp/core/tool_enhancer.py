"""Tool enhancement, tagging, and MCP instructions for Sigrity MCP.

- Enforces tags on all 200+ tools based on domain.
- Ensures tool descriptions reference direct MCP `load_skill('<name>')` calls.
- Defines strict system instructions directing calling models to use sub-agents and
  ensuring sub-agents load skills before taking action.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

DOMAIN_TAG_MAP: dict[str, tuple[set[str], str]] = {
    "cad": ({"cad", "sigrity-cad", "pcb-layout"}, "sigrity-cad"),
    "si": ({"si", "sigrity-si", "signal-integrity"}, "sigrity-si"),
    "pi": ({"pi", "sigrity-pi", "power-integrity"}, "sigrity-pi"),
    "extraction": ({"extraction", "sigrity-extraction", "interconnect-extraction"}, "sigrity-extraction"),
    "thermal": ({"thermal", "sigrity-celsius", "celsius"}, "sigrity-celsius"),
    "aurora": ({"aurora", "sigrity-aurora", "design-sync"}, "sigrity"),
    "sourcing": ({"sourcing", "components"}, "sigrity"),
    "platform": ({"platform", "skills", "jobs"}, "sigrity"),
}

STRICT_SERVER_INSTRUCTIONS = (
    "Sigrity MCP Server (200+ tools for Cadence Sigrity 2024.0 and Allegro/OrCAD SPB 22.1 EDA).\n\n"

    "CRITICAL ARCHITECTURE NOTICE:\n"
    "This is a network-accessible remote MCP server. Clients DO NOT have local filesystem access "
    "to this machine. All operational playbooks, rules of operation, and verified sample files "
    "are accessible exclusively through MCP tools (`load_skill` and `list_skills`).\n\n"

    "SUB-AGENT WORKFLOW & DELEGATION PROTOCOL (MANDATORY):\n"
    "1. SUB-AGENT USAGE: If your agent environment or orchestrator supports sub-agents, delegation, or "
    "specialized workers (e.g. Claude Code subagents, DeepAgents, LangChain/LangGraph, AutoGen, CrewAI), "
    "YOU MUST DELEGATE domain-specific tasks to dedicated sub-agents according to the domain:\n"
    "   - CAD/PCB Sub-Agent: Allegro/OrCAD placement, routing, DRC, Gerber, SKILL scripting (`sigrity-cad` tag)\n"
    "   - Thermal Sub-Agent: Celsius 2D, 3D, CFD electrothermal & thermal-stress simulations (`sigrity-celsius` tag)\n"
    "   - Power Integrity Sub-Agent: PowerDC IR-drop, XcitePI parasitic extraction, OptimizePI PDN (`sigrity-pi` tag)\n"
    "   - Signal Integrity Sub-Agent: PowerSI S-parameter extraction, BroadbandSPICE fitting (`sigrity-si` tag)\n"
    "   - Extraction Sub-Agent: Clarity3D, XtractIM, T2B 3D EM interconnect extraction (`sigrity-extraction` tag)\n\n"

    "2. STRICT SUB-AGENT SKILL PROTOCOL:\n"
    "   BEFORE executing ANY domain tools or actions, EVERY agent and sub-agent MUST FIRST:\n"
    "   a. Call `list_skills` to discover available domain skills.\n"
    "   b. Call `load_skill(name='sigrity')` for fundamental rules, project conventions, and background-job patterns.\n"
    "   c. Call `load_skill(name='<domain-skill>')` (e.g. 'sigrity-cad', 'sigrity-celsius', 'sigrity-pi', "
    "'sigrity-si', 'sigrity-extraction') to obtain the verified execution playbook, parameter rules, and pitfalls.\n"
    "   Sub-agents MUST NOT call domain tools without first loading the corresponding domain skill.\n\n"

    "3. BACKGROUND-JOB PROTOCOL:\n"
    "   EDA simulations and solvers run asynchronously. Tools returning a `job_id` with state='running' MUST be "
    "monitored using `wait_for_job` or `get_job_status`, inspected with `tail_job_log` / `list_job_files`, and verified "
    "by inspecting output artifacts before reporting task completion.\n\n"

    "4. ENGINEERING INTEGRITY:\n"
    "   Never invent parameters, solver settings, or boundary conditions. If an expected input is missing, load the domain skill "
    "or ask focused questions. Do not fabricate results or trust returncode=0 without verifying report artifacts."
)


def enrich_and_tag_tools(mcp_app: FastMCP) -> int:
    """Tag all tools by domain and ensure skill references point to load_skill calls."""
    skill_regex = re.compile(
        r"(?:[Ss]ee\s+)?`?\.forjinn/skills/([a-zA-Z0-9_-]+)(?:/SKILL\.md)?`?(?:\s+for\s+the\s+full\s+verified\s+playbook[^.\n]*)?",
        re.IGNORECASE,
    )

    tools: list[Any] = []
    if hasattr(mcp_app, "local_provider") and hasattr(mcp_app.local_provider, "_components"):
        for key, comp in mcp_app.local_provider._components.items():
            if key.startswith("tool:"):
                tools.append(comp)

    updated_count = 0
    for t in tools:
        fn = getattr(t, "fn", None)
        mod = getattr(fn, "__module__", "") if fn else ""
        parts = mod.split(".")
        domain = parts[2] if len(parts) > 2 and parts[2] in DOMAIN_TAG_MAP else "platform"
        domain_tags, default_skill = DOMAIN_TAG_MAP.get(domain, ({"general"}, "sigrity"))

        # Assign tags to tool
        t.tags = set(domain_tags)

        # Ensure descriptions reference load_skill
        desc = getattr(t, "description", None)
        if desc and ".forjinn/skills" in desc:
            def _repl(match: re.Match[str]) -> str:
                skill_name = match.group(1) if match.group(1) else default_skill
                return f"Call load_skill('{skill_name}') for the verified playbook, workflow parameters, and examples."

            t.description = skill_regex.sub(_repl, desc).strip()
            updated_count += 1

    # Update server instructions to strict sub-agent instructions
    mcp_app.instructions = STRICT_SERVER_INSTRUCTIONS
    return updated_count
