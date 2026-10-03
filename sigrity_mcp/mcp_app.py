"""The single shared FastMCP application instance.

Every domain module (`sigrity_mcp.domains.*`) imports `mcp` from here and registers its
tools on it with `@mcp.tool`. `sigrity_mcp.server` imports all domain modules for their
side effects and exposes the fully-populated app.
"""

from __future__ import annotations

from fastmcp import FastMCP

from sigrity_mcp.core.argument_coercion_middleware import JsonStringArgumentCoercionMiddleware

mcp = FastMCP(
    name="sigrity-mcp",
    instructions=(
        "181 tools driving a local Cadence Sigrity 2024.0 + Allegro/OrCAD SPB 22.1 "
        "install: Power Integrity, Signal Integrity, interconnect extraction, thermal "
        "(Celsius), PCB layout/routing/DRC/manufacturing, project creation, and the "
        "unified Sigrity X platform.\n\n"
        "READ-THOSE-FIRST PROTOCOL: each tool's description is intentionally short "
        "(one line + a pointer). The full verified playbook, exact minimal call "
        "sequences, pitfalls, real sample paths, and live examples live in the skill "
        "files under `.forjinn/skills/`. If you can read this machine's filesystem "
        "(e.g. Claude Code), start by reading `.forjinn/skills/sigrity/SKILL.md` "
        "(foundation: the 3 inviolable rule-of-thumb + real sample file table), then "
        "`sigrity-si`, `sigrity-pi`, `sigrity-extraction`, `sigrity-cad`, or "
        "`sigrity-celsius` for your domain. If you cannot (a remote client connected "
        "over http/sse with no filesystem access to this machine), call the "
        "`list_skills` tool instead to see the same names+descriptions, then "
        "`load_skill(name)` for the domain(s) your task needs — identical content, "
        "served over MCP itself rather than a file path. Tool descriptions point to "
        "the exact relevant skill file either way.\n\n"
        "MODEL: long-running work is a background job. A `run_*`/`*_run_session` tool "
        "returns a `job_id` immediately (state='running') — then you must follow with "
        "`wait_for_job`/`get_job_status`, and `tail_job_log`/`list_job_files` to "
        "verify. Never trust `state`/`returncode` alone — some tools exit 0 while "
        "doing nothing, and output usually lands next to the input file (not the job "
        "dir). Use `run_tool_pipeline` to chain a known multi-step flow in one call."
    ),
)

# Some calling models (observed live with qwen3-max via vLLM) emit a list/dict-typed
# tool argument as a JSON-encoded string instead of a native JSON array/object; FastMCP's
# strict pydantic argument validation rejects that outright. This middleware pre-parses
# such arguments for every tool call before validation runs -- see
# sigrity_mcp/core/argument_coercion_middleware.py for the full rationale and exactly
# which FastMCP extension point this uses.
mcp.add_middleware(JsonStringArgumentCoercionMiddleware())
