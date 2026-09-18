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

    Each entry in `steps` is a dict:
      - "tool" (required): the exact name of another tool in this server (e.g.
        "start_powersi_session"). Must not be "run_tool_pipeline" itself — pipelines
        cannot nest.
      - "args" (optional): the arguments to call it with, as you would normally. Any
        string value of the exact form "${name.path}" is replaced with the value at
        that path in an earlier step's saved result before the call is made (e.g.
        "${open_session.session_id}"); a placeholder embedded in a larger string like
        "note-${open_session.session_id}" is stringified in place instead. A reference
        to a step that hasn't run yet, or wasn't saved, is a pipeline error.
      - "save_as" (optional): a name to store this step's result dict under, so later
        steps can reference it via "${that_name.field}". Skip this for steps whose
        result nothing downstream needs.

    Example — compose and run a complete PowerSI extraction in one call:
        steps = [
          {"tool": "start_powersi_session", "args": {"spd_file": "C:/d/board.spd"}, "save_as": "s"},
          {"tool": "powersi_set_mode", "args": {"session_id": "${s.session_id}", "mode": "extraction"}},
          {"tool": "powersi_set_frequency_sweep", "args": {"session_id": "${s.session_id}", "start": "1e6", "end": "1e9"}},
          {"tool": "powersi_add_ports_auto", "args": {"session_id": "${s.session_id}"}},
          {"tool": "powersi_run_session", "args": {"session_id": "${s.session_id}"}, "save_as": "run"},
          {"tool": "wait_for_job", "args": {"job_id": "${run.job_id}", "timeout_seconds": 120}},
        ]

    `stop_on_error=True` (default) halts on the first failing step, leaving later steps
    unexecuted — check the returned `results` list to see exactly how far it got and
    why. Set False to keep going and collect every step's outcome regardless (useful
    for a diagnostic dry-run across independent steps, not for a flow where later steps
    genuinely depend on earlier ones succeeding).

    At most 50 steps per call. Returns step_count/executed_count/succeeded_count/
    failed_count plus the full per-step `results` list (each with its resolved args and
    either a `result` or an `error` key).
    """
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
