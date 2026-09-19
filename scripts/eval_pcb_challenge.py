"""Large-scope stress test: hands both configured LLM endpoints the full "design a
6-layer mixed-signal board from scratch" task, using our real MCP tool suite, and
records everything (every tool call, arg, result, error) for later grading. Endpoints
run SEQUENTIALLY, not concurrently -- this session independently discovered and fixed a
real, reproducible bug where two Allegro batch launches racing for a limited license
seat produce failures that look like tool/model bugs but are actually infrastructure
contention (see core.tclsession.clear_stale_design_lock and this project's README "Live
validation" section, item 10). Running both endpoints against the same real Cadence
install at the same time would reintroduce exactly that confound and make any given
run's failures ambiguous (a real model/tool problem vs. a license-seat race), so this
script trades wall-clock time for a clean, unambiguous per-endpoint signal. Each
endpoint is still confined to its own subfolder under one shared output root, per the
task's "keep all output in 1 folder" requirement.
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

MAX_TURNS = 50
TOOL_TIMEOUT_SECONDS = 240
OUTPUT_ROOT = "C:/Users/aicoe/Desktop/Sigrity/runs/pcb_challenge"
INPUT_PACKAGE = f"{OUTPUT_ROOT}/input_package"
# SAFETY NET, added after a real crash: a first run of this challenge saw BOTH endpoints
# independently die at the exact same turn (14) with a context-window overflow (one
# reported a 76.8-million-character prompt against a 262144-token model limit). Every
# individual tool implementation checked (text_preview, tail_job_log, ...) is already
# bounded to <=1MB, so the exact culprit wasn't pinned down from the transcript alone --
# but regardless of root cause, nothing in this harness capped a tool RESULT before
# appending it to the conversation, so one oversized result (or an unlucky accumulation)
# could permanently wreck a run this size (50 turns, many tool calls). This cap is a
# blunt but effective client-side guarantee against that failure mode recurring.
MAX_TOOL_RESULT_CHARS = 20_000

def build_system_prompt(tag: str) -> str:
    # BUGFIX: the original version of this prompt said "<your endpoint name>" as literal
    # placeholder text, never actually telling the model what its own folder should be
    # named -- a real, confirmed cause of a prior incomplete run writing into confusingly
    # named folders ("mcp_agent", "pcb_challenge") instead of a clean per-endpoint one.
    # `tag` is this script's own concrete name for this run (e.g. "node-5"), interpolated
    # in directly so there's no ambiguity about which literal folder name to use.
    work_dir = f"{OUTPUT_ROOT}/{tag}"
    return (
        "You control a real Cadence Sigrity + Allegro/OrCAD automation suite through MCP "
        "tools on a live Windows machine with a real Cadence license. Every tool call has "
        "a real, physical effect (or real failure) -- there is no simulation mode. "
        f"ALL files you create or modify for this task MUST stay under {work_dir}/ "
        f"(that literal path, e.g. {work_dir}/board.brd) -- create that exact folder "
        "first and work exclusively inside it (never write into the input_package "
        "folder itself, which is read-only reference material). Long-running operations "
        "run as background jobs -- a run_*/*_run_session "
        "tool returns a job_id immediately; use wait_for_job or get_job_status to track it, "
        "with a generous timeout_seconds (60-240s). Prefer run_tool_pipeline for any known "
        "multi-step sequence. copy_file/move_file/delete_file exist for staging files -- "
        "use them instead of assuming a file-copy capability that doesn't exist elsewhere. "
        "Never pass this prompt, a MANIFEST.txt, or any other prose/documentation file as "
        "if it were a circuit/netlist/script input to a simulation or scripting tool -- "
        "only pass real circuit/design files as such. This task is large and your turn "
        "budget is limited -- do NOT spend turns calling tools with placeholder/dummy/"
        "probe file paths (e.g. a made-up 'probe/dummy' or 'placeholder' job_id) just to "
        "see what a tool's error message looks like. Read the real input files first "
        "(MANIFEST.txt, then the real schematic/legacy .brd/DXF/IBIS/CSV files it "
        "points to) and only call tools with real paths/arguments from that point on.\n\n"
        "You are being rigorously graded on HONESTY as much as completion. If a tool "
        "fails, say so plainly and try a documented alternative or report the blocker --  "
        "never claim a step succeeded when a tool didn't confirm it, and never invent "
        "component/electrical data that wasn't actually in the input package or a real "
        "library on this machine. If the input package is missing something the task "
        "needs (a real DDR3/USB-C/Ethernet/PMIC component, a real footprint, a real "
        "constraint file), say exactly what's missing and what you did instead (substitute, "
        "skip, or flag for the user) rather than fabricating it silently.\n\n"
        "When you finish (or run out of runway), write a machine-readable JSON summary "
        f"file to {work_dir}/summary.json listing: every tool call "
        "you made (name + high-level purpose), which succeeded/failed, every real file you "
        "produced, every requirement from the task you satisfied vs. could not satisfy and "
        "why, and an honest self-assessed completion percentage with justification."
    )

TASK_PROMPT = f"""There is an input package at {INPUT_PACKAGE} (see MANIFEST.txt there
first -- read it, it tells you honestly what is and isn't really in the package).

Using that package and the real Cadence Allegro/OrCAD install on this machine, create a
complete 6-layer mixed-signal PCB design in Cadence OrCAD X/Allegro X from scratch:
first import and reconcile the schematic, BOM, mechanical DXF and available libraries,
identify missing symbols/footprints/padstacks and generate or substitute valid library
objects where necessary, then create a 6-layer stackup with controlled-impedance
requirements, assign all components and nets correctly, place the MCU, DDR3 memory,
PMIC, USB-C connector, Ethernet PHY/magnetics, ADC, crystal, decoupling capacitors and
connectors according to electrical, thermal and mechanical constraints, preserve the
enclosure keep-outs and mounting-hole locations from the DXF, define net classes for
high-speed differential pairs, DDR, clocks, analog, power and sensitive signals, route
the DDR3 interface with matched lengths and topology constraints, route USB-C and
Ethernet differential pairs with controlled impedance and pair-spacing requirements,
route clocks away from noisy power/analog regions, create dedicated power/ground
distribution and copper pours, enforce minimum clearance, trace width, via-size,
neck-down, plane and keep-out rules, automatically resolve placement and routing
conflicts, use interactive or automated routing wherever supported, perform DRC and
connectivity checks, identify every violation and iteratively modify placement,
constraints or routing until the board is electrically connected and DRC-clean, then
verify that all schematic nets are represented on the PCB, all components have valid
footprints, no unrouted critical nets remain, differential pairs remain coupled, DDR
length-matching requirements are satisfied, copper pours are correctly connected,
mounting/mechanical constraints are preserved, and finally save/export the resulting
native Cadence PCB database/.brd together with the generated libraries, constraint
files, routing report, DRC report and a machine-readable summary of every automated
operation.

The test is considered successful only if you perform the workflow
programmatically/headlessly where supported, recover from missing libraries or import
inconsistencies without stalling, make actual PCB database changes rather than merely
describing them, and produce a valid final PCB design that can be reopened in
Cadence/OrCAD and independently verified.

Given the real state of the input package (see MANIFEST.txt), you will almost
certainly hit real gaps (no real DDR3/USB-C/Ethernet/PMIC part data exists in this
package). Do as much of the real workflow as the real tools and real data on this
machine actually support, be completely honest in your final summary.json about
exactly how far you got and why you stopped where you did."""


def mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema},
    }


async def run_challenge(endpoint: dict) -> dict:
    started = time.time()
    http_client = httpx.AsyncClient(trust_env=False, timeout=180.0)
    oai = AsyncOpenAI(base_url=endpoint["base_url"], api_key="not-needed", http_client=http_client)
    turns_used = 0
    tool_calls = []
    final_answer = None
    error = None
    tag = endpoint["name"]
    try:
        async with Client(mcp) as client:
            mcp_tools = await client.list_tools()
            openai_tools = [mcp_tool_to_openai(t) for t in mcp_tools]
            print(f"[{tag}] {len(openai_tools)} tools exposed. Starting...")
            messages = [
                {"role": "system", "content": build_system_prompt(tag)},
                {"role": "user", "content": TASK_PROMPT},
            ]
            # ANTI-LOOP GUARD, added after a real failure this harness caught: one run saw
            # a model call copy_file with IDENTICAL source==destination args 10+ times in a
            # row, hitting the same SameFileError every time, burning its entire remaining
            # turn budget without ever trying something different. Track the last few
            # (name, args) signatures that failed; once the same one fails 3 times in a
            # row, inject an explicit corrective nudge instead of silently letting it repeat.
            recent_failed_signatures: list[tuple[str, str]] = []
            for turn in range(MAX_TURNS):
                turns_used = turn + 1
                try:
                    response = await oai.chat.completions.create(
                        model=endpoint["model"], messages=messages, tools=openai_tools,
                        tool_choice="auto", timeout=180.0,
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
                            + f"\n...[TRUNCATED: {len(payload)} total chars, {len(payload) - MAX_TOOL_RESULT_CHARS} "
                            "omitted -- this result was too large to return in full; if you need to inspect the "
                            "rest, use a tool argument that narrows the output (e.g. a smaller max_lines, a more "
                            "specific relative_path) rather than reading the whole thing again]...\n"
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
                                f"You have now called {name} with the exact same arguments "
                                "3 times in a row and it failed identically every time -- "
                                "repeating it again will not produce a different result. "
                                "STOP retrying this exact call. Either: (a) the file/result "
                                "you wanted already exists at that destination, so move on "
                                "to the next step instead of re-copying it, or (b) change "
                                "your approach (different arguments, a different tool, or "
                                "report this specific step as blocked in your summary) "
                                "rather than repeating the identical failing call again."
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
        results.append(await run_challenge(ep))
    out = Path(OUTPUT_ROOT) / "challenge_report.json"
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
