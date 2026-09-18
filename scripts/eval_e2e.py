"""Phase E: multi-model end-to-end evaluation harness.

Runs a fixed set of realistic, complex end-to-end tasks against one or more
OpenAI-compatible endpoints, using fastmcp's in-process Client against our real server
(sigrity_mcp.server.mcp) exactly as scripts/test_llm_e2e.py does, but:
  - tracks per-task metrics (wall-clock time, turn count, tool-call count, which tools,
    any tool-call errors, whether a final answer was produced) instead of just printing
    a transcript
  - runs the same task across multiple endpoints/models for a side-by-side comparison
  - writes a JSON report to disk for later analysis / prompt-tuning iteration

Usage:
    python scripts/eval_e2e.py
"""

import asyncio
import io
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)

import httpx
from fastmcp import Client
from openai import AsyncOpenAI

from sigrity_mcp.server import mcp

ENDPOINTS = [
    {"name": "node-5", "base_url": "http://172.16.34.5:8000/v1", "model": "qwen3-max"},
    {"name": "node-11", "base_url": "http://172.16.34.11:8000/v1", "model": "qwen3-max"},
]

MAX_TURNS = 20
TOOL_TIMEOUT_SECONDS = 180


@dataclass
class ToolCallRecord:
    turn: int
    name: str
    args: dict
    ok: bool
    error: Optional[str] = None
    result_preview: str = ""


@dataclass
class TaskResult:
    endpoint: str
    task_name: str
    started_at: float
    ended_at: float = 0.0
    turns_used: int = 0
    tool_calls: list = field(default_factory=list)
    final_answer: Optional[str] = None
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return round(self.ended_at - self.started_at, 1)

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)

    @property
    def tool_error_count(self) -> int:
        return sum(1 for t in self.tool_calls if not t["ok"])

    @property
    def unique_tools_used(self) -> list:
        seen = []
        for t in self.tool_calls:
            if t["name"] not in seen:
                seen.append(t["name"])
        return seen


def mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema},
    }


async def run_task(endpoint: dict, task_name: str, system_prompt: str, user_prompt: str) -> TaskResult:
    result = TaskResult(endpoint=endpoint["name"], task_name=task_name, started_at=time.time())
    http_client = httpx.AsyncClient(trust_env=False, timeout=120.0)
    oai = AsyncOpenAI(base_url=endpoint["base_url"], api_key="not-needed", http_client=http_client)

    try:
        async with Client(mcp) as client:
            mcp_tools = await client.list_tools()
            openai_tools = [mcp_tool_to_openai(t) for t in mcp_tools]
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            for turn in range(MAX_TURNS):
                result.turns_used = turn + 1
                response = await oai.chat.completions.create(
                    model=endpoint["model"],
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    timeout=180.0,
                )
                choice = response.choices[0]
                messages.append(choice.message.model_dump(exclude_none=True))

                if not choice.message.tool_calls:
                    result.final_answer = choice.message.content
                    break

                for tool_call in choice.message.tool_calls:
                    name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    call_record: dict[str, Any] = {"turn": turn, "name": name, "args": args, "ok": True}
                    try:
                        call_result = await asyncio.wait_for(
                            client.call_tool(name, args), timeout=TOOL_TIMEOUT_SECONDS
                        )
                        payload = call_result.content[0].text if call_result.content else "{}"
                    except Exception as exc:  # noqa: BLE001
                        # str(exc) is empty for e.g. asyncio.TimeoutError -- always
                        # include the exception type so a timeout is distinguishable
                        # from a real tool error at a glance.
                        error_text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                        payload = json.dumps({"error": error_text})
                        call_record["ok"] = False
                        call_record["error"] = error_text
                    call_record["result_preview"] = payload[:200]
                    result.tool_calls.append(call_record)
                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": payload})
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.ended_at = time.time()
        await http_client.aclose()

    return result


SYSTEM_PROMPT = (
    "You control a Cadence Sigrity + Allegro/OrCAD automation suite through MCP tools, "
    "covering everything from PCB layout (Allegro) and schematic capture (OrCAD Capture) "
    "through Power Integrity, Signal Integrity, Interconnect Extraction, and license/job "
    "management. Long-running operations run as background jobs — a run_*/*_run_session "
    "tool returns a job_id immediately; use wait_for_job or get_job_status to track it, "
    "and cancel_job if something is taking far longer than expected (more than ~60-90 "
    "seconds for a simple query, or a few minutes for a real simulation).\n\n"
    "Efficiency rules, follow strictly:\n"
    "- You already know every available tool and what it does from your tool list — do "
    "NOT call discovery/inventory tools (list_sigrity_tools, list_allegro_tools, "
    "get_install_info, get_cds_environment_info, list_all_jobs) unless the user's "
    "question is specifically about installation, licensing, or an unknown job's status. "
    "Go straight to the tool the task actually needs.\n"
    "- Prefer run_tool_pipeline to execute a whole known sequence of steps in ONE call "
    "instead of one call per step — this is almost always the right choice for any task "
    "with more than 2 steps. Use ${step_name.field} to reference an earlier step's saved "
    "result.\n"
    "- When waiting on a job, pass a generously long timeout_seconds to wait_for_job "
    "(60-180s) so you resolve it in one call instead of polling repeatedly.\n"
    "- Don't call preview_tcl_session or list_job_files just to double-check yourself "
    "unless something actually went wrong — trust a tool's own returned result.\n\n"
    "When you're done, give a concise final answer citing what the tools actually "
    "returned — don't claim success a tool didn't confirm."
)

_SAMPLE_BRD = (
    "C:/Cadence/SPB_22.1/tools/capture/samples/PCB-Layout/Fault-Detector/allegro/"
    "fault-detector_allegro_routed.brd"
)

TASKS = [
    {
        "name": "brd_to_powersi_signoff",
        "user_prompt": (
            f"There's a real Allegro board file at {_SAMPLE_BRD} (read-only, don't try "
            "to modify it in place — any output files should go elsewhere, e.g. "
            "C:/Users/aicoe/Desktop/Sigrity/runs/). Open it directly in a PowerSI "
            "session, save it as a native .spd file at C:/Users/aicoe/Desktop/Sigrity/"
            "runs/eval_board.spd, auto-generate ports for every component, set a "
            "frequency sweep from 1e6 to 1e9 Hz, and run the extraction. Check on the "
            "job and tell me whether it succeeded and what the PowerSI process actually "
            "reported in its log."
        ),
    },
    {
        "name": "allegro_report_and_check",
        "user_prompt": (
            f"Using the real board file at {_SAMPLE_BRD} directly (it's read-only, "
            "these operations don't modify it), generate an Allegro summary drawing "
            "report AND run a database integrity check-only pass on it. Tell me the "
            "board's component count, DRC error count, and whether the integrity check "
            "found any warnings or errors."
        ),
    },
    {
        "name": "aurora_scope_and_alternative",
        "user_prompt": (
            "I want to run a live in-design Sigrity Aurora check for crosstalk on a board "
            "while I'm routing it. Can this MCP suite do that? If not, tell me exactly why "
            "not and what I should use instead, using the actual tools available."
        ),
    },
]


async def main() -> None:
    all_results: list[TaskResult] = []
    for task in TASKS:
        for endpoint in ENDPOINTS:
            print(f"\n=== {task['name']} @ {endpoint['name']} ===")
            res = await run_task(endpoint, task["name"], SYSTEM_PROMPT, task["user_prompt"])
            all_results.append(res)
            print(
                f"  duration={res.duration_seconds}s turns={res.turns_used} "
                f"tool_calls={res.tool_call_count} tool_errors={res.tool_error_count} "
                f"tools={res.unique_tools_used}"
            )
            if res.error:
                print(f"  HARNESS ERROR: {res.error}")
            if res.final_answer:
                print(f"  final_answer: {res.final_answer[:300]}")
            else:
                print("  NO FINAL ANSWER (ran out of turns or errored)")

    report_path = Path(__file__).parent.parent / "runs" / "eval_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps([asdict(r) for r in all_results], indent=2, default=str), encoding="utf-8"
    )
    print(f"\nFull report written to {report_path}")

    print("\n=== SUMMARY ===")
    for r in all_results:
        status = "OK" if r.final_answer and not r.error else "INCOMPLETE"
        print(
            f"{r.task_name:30s} {r.endpoint:10s} {status:10s} "
            f"{r.duration_seconds:6.1f}s  turns={r.turns_used:2d}  "
            f"calls={r.tool_call_count:2d}  errors={r.tool_error_count}"
        )


if __name__ == "__main__":
    asyncio.run(main())
