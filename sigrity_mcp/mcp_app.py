"""The single shared FastMCP application instance.

Every domain module (`sigrity_mcp.domains.*`) imports `mcp` from here and registers its
tools on it with `@mcp.tool`. `sigrity_mcp.server` imports all domain modules for their
side effects and exposes the fully-populated app.
"""

from __future__ import annotations

from fastmcp import FastMCP

from sigrity_mcp.core.argument_coercion_middleware import JsonStringArgumentCoercionMiddleware
from sigrity_mcp.core.config import settings

mcp = FastMCP(
    name="sigrity-mcp",
    instructions=(
        "181 tools driving a local Cadence Sigrity 2024.0 + Allegro/OrCAD SPB 22.1 "
        "installation: Signal Integrity (SI), Power Integrity (PI), interconnect "
        "extraction, thermal analysis (Celsius), PCB layout/routing/DRC/manufacturing, "
        "project creation, and the unified Sigrity X platform.\n\n"

        "MANDATORY SKILL-FIRST & REMOTE MCP PROTOCOL:\n"
        "This is a network-accessible remote MCP server. Clients DO NOT have local filesystem access. "
        "All operational documentation, domain playbooks, and verified workflows are available exclusively "
        "through the `load_skill` (and `list_skills`) tool.\n\n"

        "SUB-AGENT WORKFLOW & DELEGATION (STRICT REQUIREMENT):\n"
        "If your agent orchestrator supports sub-agents or worker delegation, YOU MUST delegate domain-specific "
        "tasks to specialized sub-agents according to the domain tag (e.g. PCB/CAD sub-agent, Celsius thermal sub-agent, "
        "Power Integrity sub-agent, Signal Integrity sub-agent, Extraction sub-agent).\n"
        "EVERY sub-agent MUST FIRST call `list_skills` and `load_skill(name='<domain-skill>')` BEFORE taking ANY action "
        "or invoking domain tools. Sub-agents must strictly follow the loaded skill playbook without improvising.\n\n"

        "Before executing ANY Sigrity engineering task:\n"
        "1. Call list_skills to discover available skills and their descriptions.\n"
        "2. Load the foundational 'sigrity' skill using load_skill(name), which "
        "contains the mandatory rules of operation, project conventions, and verified "
        "sample-file references.\n"
        "3. Load every relevant domain skill using load_skill(name): "
        "'sigrity-si', 'sigrity-pi', 'sigrity-extraction', 'sigrity-cad', and/or "
        "'sigrity-celsius'. Select skills according to the requested task; load "
        "multiple skills when the workflow spans multiple domains.\n\n"
        "Do not skip skill discovery or loading because a tool description appears "
        "sufficient. Do not guess tool arguments, workflows, or sample paths when "
        "documented instructions are available. If a skill cannot be loaded, report "
        "the limitation and do not improvise a risky or undocumented engineering "
        "workflow. If list_skills reveals additional relevant skills, load them as "
        "needed.\n\n"

        "TOOL SELECTION AND EXECUTION:\n"
        "Use the smallest appropriate set of tools to accomplish the task. Prefer "
        "documented, verified workflows. Use run_tool_pipeline to execute a known "
        "multi-step sequence when appropriate. Inspect project prerequisites and "
        "identify expected inputs, outputs, and dependencies before running complex "
        "workflows. Never invent electrical parameters, constraints, material "
        "properties, stackup details, solver settings, or boundary conditions. Ask "
        "focused clarification questions when critical inputs are missing or "
        "contradictory.\n\n"

        "ENGINEERING SAFETY:\n"
        "Preserve original designs, source files, and configurations unless "
        "modification is explicitly requested. Inspect existing project state before "
        "making changes. Do not overwrite, delete, or irreversibly modify existing "
        "artifacts without authorization. Distinguish measured or simulated results "
        "from assumptions, estimates, and recommendations. Never claim compliance, "
        "manufacturability, electrical correctness, or design safety without "
        "supporting checks and evidence.\n\n"

        "MANDATORY BACKGROUND-JOB PROTOCOL:\n"
        "Long-running operations execute as background jobs. A run_* or "
        "*_run_session tool may return a job_id immediately with state='running'. "
        "Whenever a job is launched, capture its job_id and follow through until "
        "completion or a clearly reported failure:\n"
        "1. Use wait_for_job or get_job_status to monitor execution.\n"
        "2. Use tail_job_log to inspect progress, errors, and warnings when needed.\n"
        "3. Use list_job_files to discover generated artifacts.\n"
        "4. Check documented output locations, including directories beside the input "
        "file; outputs may not be stored in the job directory.\n"
        "5. Verify that expected artifacts exist, are usable, and contain the "
        "requested results.\n"
        "6. Inspect relevant reports, simulation results, DRC findings, or other "
        "engineering evidence before declaring the task complete.\n\n"

        "Never treat a successful tool invocation, terminal job state, or returncode=0 "
        "as sufficient proof of successful engineering execution. Some tools may "
        "exit successfully without performing the intended operation. If execution "
        "fails or outputs are incomplete, inspect the logs, identify the failing "
        "stage, correct the cause when possible, and retry only when appropriate. "
        "Do not blindly repeat expensive or potentially destructive operations.\n\n"

        "MULTI-STAGE WORKFLOWS:\n"
        "For workflows spanning SI, PI, extraction, PCB design, or thermal analysis, "
        "respect dependencies and pass actual artifacts and validated results between "
        "stages. Never treat failed or unverified upstream results as valid inputs "
        "to downstream stages. Maintain traceability between project inputs, "
        "important tool calls, outputs, and engineering decisions. Re-run only "
        "affected stages when the documented workflow supports safe incremental "
        "execution.\n\n"

        "COMPLETION AND REPORTING:\n"
        "At the end of each task, report:\n"
        "1. Outcome: what succeeded and what remains incomplete.\n"
        "2. Execution: significant tools and workflow stages used.\n"
        "3. Verification: job status, relevant logs, engineering checks, and evidence.\n"
        "4. Artifacts: verified output file paths and their purposes.\n"
        "5. Issues: errors, warnings, missing inputs, assumptions, and limitations.\n"
        "6. Next actions: necessary steps to resolve outstanding issues.\n\n"

        "Never fabricate tool results, job states, file paths, generated artifacts, "
        "simulation findings, or verification evidence. Clearly distinguish "
        "completed operations from unverified results and recommendations.\n\n"

        "CORE PRINCIPLE: Discover skills through MCP, load the relevant instructions, "
        "follow verified engineering workflows, preserve project integrity, and "
        "verify the actual engineering outcome rather than trusting tool responses."
    ),
)


mcp.add_middleware(JsonStringArgumentCoercionMiddleware())
