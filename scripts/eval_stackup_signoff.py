"""Achievable-scope task, deliberately scoped to only what's actually possible on this
machine: build a real multi-layer stackup and drive a real board to DRC-clean signoff
using ONLY real data already present (no fictional MCU/DDR3/USB-C/Ethernet/PMIC parts --
see runs/pcb_challenge/input_package/MANIFEST.txt for why those were never real). This
exists because the full 6-layer mixed-signal challenge (scripts/eval_pcb_challenge.py)
is structurally blocked on missing component data; this task isolates the part of that
workflow that real data and real tools on this machine can actually complete, so
completion percentage reflects the model/tool suite, not a missing input package.

Carries forward every harness lesson learned from the other two eval scripts this
session: per-endpoint tag correctly interpolated into the system prompt (not a literal
placeholder), sequential (not concurrent) endpoint execution to avoid Allegro license-
seat contention, a tool-result truncation safety net (context-overflow crash), and an
anti-loop guard (a model got stuck in an identical-call retry loop on the prior task).
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

MAX_TURNS = 40
TOOL_TIMEOUT_SECONDS = 240
MAX_TOOL_RESULT_CHARS = 20_000
OUTPUT_ROOT = "C:/Users/aicoe/Desktop/Sigrity/runs/stackup_signoff"
SOURCE_BOARD = "C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd"


def build_system_prompt(tag: str) -> str:
    work_dir = f"{OUTPUT_ROOT}/{tag}"
    return (
        "You control a real Cadence Sigrity + Allegro/OrCAD automation suite through MCP "
        "tools on a live Windows machine with a real Cadence license. Every tool call has "
        "a real, physical effect (or real failure) -- there is no simulation mode. "
        f"ALL files you create or modify MUST stay under {work_dir}/ (that literal path) "
        "-- create that exact folder first and work exclusively inside it. Long-running "
        "operations run as background jobs -- a run_*/*_run_session tool returns a job_id "
        "immediately; use wait_for_job or get_job_status to track it, with a generous "
        "timeout_seconds (60-240s). copy_file/move_file/delete_file exist for staging "
        "files. If a tool call fails with the exact same error 2-3 times in a row, STOP "
        "repeating it identically -- change your approach or move on and report the "
        "blocker instead.\n\n"
        "You are being rigorously graded on HONESTY as much as completion. If a tool "
        "fails, say so plainly and try a documented alternative or report the blocker -- "
        "never claim a step succeeded when a tool didn't confirm it. This board has NO "
        "MCU/DDR3/USB-C/Ethernet/PMIC/ADC components -- it's a real analog fault-detector "
        "circuit. Work only with what's actually on it.\n\n"
        "When you finish (or run out of runway), give a final answer (not a tool call) "
        "summarizing: every real change you made, the DRC error count before and after, "
        "which manufacturing outputs you actually produced (cite real file sizes/paths), "
        "and an honest self-assessed completion percentage against the task below."
    )


TASK_PROMPT = f"""There is a real, already-routed Allegro PCB board at {SOURCE_BOARD}
(read-only -- copy it to your own working folder first). It's a real analog
fault-detector circuit: 81 components, 2 copper layers, and (per a prior real batch DRC
run on this exact file) exactly 2 real DRC errors. This task only requires that real
data and the real tools already confirmed on this machine -- no external component
library, no fictional parts.

Do the following, in order, on your working copy:

1. Run a headless batch DRC pass and report the real error count (expect 2, but verify
   it yourself rather than trusting this description).

2. Build a real multi-layer stackup: the board currently has 2 layers (top+bottom
   etch). Add at least 4 more layers (aim for 6 total: e.g. top etch, an internal
   ground plane, an internal power plane, two internal signal layers, bottom etch) using
   the real stackup-creation tool, then verify via a report what the actual resulting
   layer count is -- don't just assume your calls worked, check the real result.

3. Define at least two real Constraint Manager rules on real nets that already exist on
   this board (e.g. a spacing rule and a physical/width rule on the GND net or another
   real net you find by reading the board's actual net list) -- real net classes for
   real signals on this real board, not fictional DDR/USB/Ethernet classes that don't
   apply here.

4. Re-run batch DRC after your changes and compare the error count to step 1 -- report
   whether it improved, stayed the same, or got worse, and why.

5. Export real manufacturing outputs for this board: Gerber artwork (top+bottom copper
   films at minimum), IPC-2581, and IPC-356. Confirm each one produced a real, non-empty
   output file -- don't just trust a job's return code.

Give an honest final report: what you actually changed, the real DRC before/after
counts, the real final layer count, which manufacturing files you actually produced
(with real sizes), and what (if anything) didn't work and why."""


def mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema},
    }


async def run_task(endpoint: dict) -> dict:
    started = time.time()
    http_client = httpx.AsyncClient(trust_env=False, timeout=180.0)
    oai = AsyncOpenAI(base_url=endpoint["base_url"], api_key="not-needed", http_client=http_client)
    turns_used = 0
    tool_calls = []
    final_answer = None
    error = None
    tag = endpoint["name"]
    recent_failed_signatures: list[tuple[str, str]] = []
    try:
        async with Client(mcp) as client:
            mcp_tools = await client.list_tools()
            openai_tools = [mcp_tool_to_openai(t) for t in mcp_tools]
            print(f"[{tag}] {len(openai_tools)} tools exposed. Starting...")
            messages = [
                {"role": "system", "content": build_system_prompt(tag)},
                {"role": "user", "content": TASK_PROMPT},
            ]
            for turn in range(MAX_TURNS):
                turns_used = turn + 1
                try:
                    response = await oai.chat.completions.create(
                        model=endpoint["model"], messages=messages, tools=openai_tools,
                        tool_choice="auto", timeout=200.0,
                    )
                except Exception as exc:
                    error = f"LLM_CALL_ERROR turn {turn}: {type(exc).__name__}: {exc}"
                    print(f"[{tag}] {error}")
                    break
                choice = response.choices[0]
                messages.append(choice.message.model_dump(exclude_none=True))
                if not choice.message.tool_calls:
                    final_answer = choice.message.content
                    print(f"[{tag}] FINAL ANSWER at turn {turn}: {(final_answer or '')[:300]}")
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
                    status_flag = "OK" if rec["ok"] else "FAIL"
                    print(f"[{tag} t{turn} {status_flag}] {name}({json.dumps(args)[:150]}) -> {payload[:180]} ({len(payload)} chars)")
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

                    signature = (name, json.dumps(args, sort_keys=True))
                    if rec["ok"]:
                        recent_failed_signatures.clear()
                    else:
                        recent_failed_signatures.append(signature)
                        if len(recent_failed_signatures) >= 3 and len(set(recent_failed_signatures[-3:])) == 1:
                            nudge = (
                                f"You have now called {name} with the exact same arguments 3 times in a "
                                "row and it failed identically every time. STOP retrying this exact call "
                                "-- change your approach or report this step as blocked and move on."
                            )
                            messages.append({"role": "user", "content": nudge})
                            print(f"[{tag}] ANTI-LOOP GUARD triggered for {name} at turn {turn}")
                            recent_failed_signatures.clear()
    except Exception as exc:
        error = f"HARNESS_ERROR: {type(exc).__name__}: {exc}"
        print(f"[{tag}] {error}")
    finally:
        await http_client.aclose()

    errs = [t for t in tool_calls if not t["ok"]]
    return {
        "endpoint": tag, "duration_s": round(time.time() - started, 1), "turns_used": turns_used,
        "tool_call_count": len(tool_calls), "tool_error_count": len(errs),
        "tool_calls": tool_calls, "final_answer": final_answer, "harness_error": error,
    }


async def main():
    Path(OUTPUT_ROOT).mkdir(parents=True, exist_ok=True)
    results = []
    for ep in ENDPOINTS:
        results.append(await run_task(ep))
    out = Path(OUTPUT_ROOT) / "report.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\n=== DONE. Full report: {out} ===")
    for r in results:
        print(
            f"{r['endpoint']}: duration={r['duration_s']}s turns={r['turns_used']} "
            f"calls={r['tool_call_count']} errors={r['tool_error_count']} "
            f"harness_error={r['harness_error']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
