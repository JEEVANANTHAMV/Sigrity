"""A single tool that executes a declarative sequence of other tool calls.

Why this exists: a realistic end-to-end flow (open a design, configure a session
across several calls, run it, wait, read results) is 6-10 individual tool calls that
an LLM caller has to get in the right order with the right session_id/job_id threaded
between them. With 90+ tools across five domains, that's a lot of surface area for a
caller to misalign — one wrong argument or skipped step and the whole flow silently
does the wrong thing. `run_tool_pipeline` lets a caller submit the whole sequence as
one structured list and get one aggregated result back, with automatic `${...}`
placeholder substitution so step N can reference step N-1's output without the caller
manually copying values between calls.

This does not replace the individual tools — a caller who wants to inspect an
intermediate result before deciding the next step should still call tools one at a
time. Use this when the sequence is already known upfront.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastmcp import Client

from sigrity_mcp.core.pipeline import PlaceholderError, resolve
from sigrity_mcp.mcp_app import mcp

MAX_STEPS = 50


@mcp.tool
async def run_tool_pipeline(steps: list[dict], stop_on_error: bool = True) -> dict:
    """Run a sequence of MCP tool calls in one shot, threading results between steps automatically.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if len(steps) > MAX_STEPS:
        return {"error": f"Pipeline has {len(steps)} steps, exceeding the {MAX_STEPS}-step limit."}

    context: dict[str, Any] = {}
    results: list[dict] = []

    async with Client(mcp) as client:
        for index, step in enumerate(steps):
            tool_name = step.get("tool")
            if not tool_name:
                results.append({"index": index, "error": "step is missing the required 'tool' key"})
                if stop_on_error:
                    break
                continue
            if tool_name == "run_tool_pipeline":
                results.append({"index": index, "tool": tool_name, "error": "pipelines cannot call themselves"})
                if stop_on_error:
                    break
                continue

            raw_args = step.get("args") or {}
            try:
                resolved_args = resolve(raw_args, context)
            except PlaceholderError as exc:
                results.append(
                    {"index": index, "tool": tool_name, "error": f"unresolved placeholder: '${{{exc.args[0]}}}'"}
                )
                if stop_on_error:
                    break
                continue

            try:
                call_result = await client.call_tool(tool_name, resolved_args)
                payload = json.loads(call_result.content[0].text) if call_result.content else {}
            except Exception as exc:  # noqa: BLE001 - deliberately broad: any tool-call failure is a step result, not a crash
                results.append(
                    {"index": index, "tool": tool_name, "args": resolved_args, "error": str(exc)}
                )
                if stop_on_error:
                    break
                continue

            entry: dict[str, Any] = {"index": index, "tool": tool_name, "args": resolved_args, "result": payload}
            results.append(entry)
            save_as: Optional[str] = step.get("save_as")
            if save_as:
                context[save_as] = payload

    succeeded = sum(1 for r in results if "error" not in r)
    return {
        "step_count": len(steps),
        "executed_count": len(results),
        "succeeded_count": succeeded,
        "failed_count": len(results) - succeeded,
        "results": results,
    }
