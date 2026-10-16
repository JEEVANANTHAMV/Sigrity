"""Manufacturing-signoff eval: exercises this pass's fixes (Gerber artwork pipeline,
confirmed net assignment) plus the existing IPC-2581/IPC-356/DRC tools as one realistic,
multi-step, industry-standard PCB manufacturing signoff flow, through both configured
LLM endpoints -- to see whether the models pick the right tools in the right order for a
real end-to-end CAD-to-manufacturing task, not just isolated single-tool calls, and
report real results honestly rather than trusting a bare "job succeeded".
"""

import asyncio
import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)

import httpx
from fastmcp import Client
from openai import AsyncOpenAI

from sigrity_mcp.server import mcp

ENDPOINTS = [
    {"name": "node-5", "base_url": "http://172.16.34.5:8000/v1", "model": "qwen3-max"},
    {"name": "node-11", "base_url": "http://172.16.34.11:8000/v1", "model": "qwen3-max"},
]

MAX_TURNS = 25
TOOL_TIMEOUT_SECONDS = 180
# See the identical constant in scripts/eval_pcb_challenge.py for why this exists: a
# sibling eval run saw both endpoints independently blow through the model's context
# window (one hit 76.8M characters) with no single tool result capped before being
# appended to conversation history. This run didn't hit it, but the same unbounded
# accumulation risk applies here too.
MAX_TOOL_RESULT_CHARS = 20_000

SYSTEM_PROMPT = (
    "You control a Cadence Sigrity + Allegro/OrCAD automation suite through MCP tools. "
    "Long-running operations run as background jobs -- a run_*/*_run_session tool "
    "returns a job_id immediately; use wait_for_job or get_job_status to track it. "
    "Prefer run_tool_pipeline for multi-step sequences using ${step_name.field} "
    "placeholders. Give a concise final answer citing what the tools actually "
    "returned -- don't claim success a tool didn't confirm, and don't hide a real "
    "failure. Some tools return a job that exits nonzero with warnings that are not "
    "fatal errors (e.g. run_allegro_generate_artwork) -- read the log/output content, "
    "not just the return code, before deciding whether something failed."
)

_BOARD = "C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd"

TASK = {
    "name": "manufacturing_signoff_pipeline",
    "user_prompt": (
        f"I need a real, industry-standard PCB manufacturing signoff package for the "
        f"board at {_BOARD} (read-only -- copy it to a fresh location under "
        "C:/Users/aicoe/Desktop/Sigrity/runs/ first, e.g. "
        "C:/Users/aicoe/Desktop/Sigrity/runs/eval_mfg/board.brd, and work on that copy). "
        "Do all of the following against your copy, in a sensible order, and use real "
        "Allegro/Cadence tools for each step (not just claim they're done):\n"
        "1. Run a headless batch DRC pass and report the real error/warning counts.\n"
        "2. Define Gerber artwork film records for the top and bottom copper layers "
        "(ETCH/TOP and ETCH/BOTTOM), save the design, then generate the actual Gerber "
        "artwork files for those films.\n"
        "3. Export the board to IPC-2581 (unified fab/assembly/test data) and IPC-356 "
        "(bare-board electrical test netlist) formats -- both real industry-standard "
        "manufacturing data formats.\n"
        "4. Report a final manufacturing-signoff summary: for each of the four "
        "deliverables (DRC pass, Gerber artwork, IPC-2581, IPC-356), state clearly "
        "whether it actually succeeded and cite what the tool/job output really said, "
        "including the real DRC error/warning counts and confirmation that real output "
        "files (not just a zero exit code) were produced for each export."
    ),
}


def mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema},
    }


async def run_task(endpoint, task_name, user_prompt):
    started = time.time()
    http_client = httpx.AsyncClient(trust_env=False, timeout=180.0)
    oai = AsyncOpenAI(base_url=endpoint["base_url"], api_key="not-needed", http_client=http_client)
    turns_used = 0
    tool_calls = []
    final_answer = None
    error = None
    try:
        async with Client(mcp) as client:
            mcp_tools = await client.list_tools()
            openai_tools = [mcp_tool_to_openai(t) for t in mcp_tools]
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            for turn in range(MAX_TURNS):
                turns_used = turn + 1
                response = await oai.chat.completions.create(
                    model=endpoint["model"], messages=messages, tools=openai_tools,
                    tool_choice="auto", timeout=240.0,
                )
                choice = response.choices[0]
                messages.append(choice.message.model_dump(exclude_none=True))
                if not choice.message.tool_calls:
                    final_answer = choice.message.content
                    break
                for tc in choice.message.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    rec = {"turn": turn, "name": name, "args": args, "ok": True}
                    try:
                        result = await asyncio.wait_for(client.call_tool(name, args), timeout=TOOL_TIMEOUT_SECONDS)
                        payload = result.content[0].text if result.content else "{}"
                    except Exception as exc:
                        error_text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                        payload = json.dumps({"error": error_text})
                        rec["ok"] = False
                        rec["error"] = error_text
                    rec["result_preview"] = payload[:300]
                    rec["result_chars"] = len(payload)
                    tool_calls.append(rec)
                    print(f"  [{endpoint['name']}/{task_name} turn {turn}] {name}({args}) -> {payload[:200]}")
                    sent_payload = payload
                    if len(payload) > MAX_TOOL_RESULT_CHARS:
                        half = MAX_TOOL_RESULT_CHARS // 2
                        sent_payload = (
                            payload[:half]
                            + f"\n...[TRUNCATED: {len(payload)} total chars, "
                            f"{len(payload) - MAX_TOOL_RESULT_CHARS} omitted]...\n"
                            + payload[-half:]
                        )
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": sent_payload})
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        await http_client.aclose()
    return {
        "endpoint": endpoint["name"], "task_name": task_name, "duration_s": round(time.time() - started, 1),
        "turns_used": turns_used, "tool_calls": tool_calls, "final_answer": final_answer, "error": error,
    }


async def main():
    results = []
    for endpoint in ENDPOINTS:
        print(f"\n=== {TASK['name']} @ {endpoint['name']} ===")
        res = await run_task(endpoint, TASK["name"], TASK["user_prompt"])
        results.append(res)
        errs = sum(1 for t in res["tool_calls"] if not t["ok"])
        tools_used = [t["name"] for t in res["tool_calls"]]
        print(f"  duration={res['duration_s']}s turns={res['turns_used']} calls={len(res['tool_calls'])} tool_errors={errs}")
        print(f"  tools called in order: {tools_used}")
        print(f"  final_answer: {(res['final_answer'] or '')[:800]}")
        if res["error"]:
            print(f"  HARNESS ERROR: {res['error']}")

    out = Path("C:/Users/aicoe/Desktop/Sigrity/runs/eval_manufacturing_report.json")
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    asyncio.run(main())
