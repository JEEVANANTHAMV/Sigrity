"""End-to-end test: a real LLM (local qwen3-max) drives our MCP tools via OpenAI-style
tool calling, using fastmcp's in-process Client against the actual server object.

The local model endpoint is a LAN address and must bypass the corporate HTTP(S) proxy
(which returns a 407 auth page for it) -- hence `trust_env=False` on the httpx client.
"""

import asyncio
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx
from fastmcp import Client
from openai import AsyncOpenAI

from sigrity_mcp.server import mcp

BASE_URL = "http://LAN_MODEL_HOST:8000/v1"
MODEL = "qwen3-max"


def mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


async def run_conversation(client: Client, oai: AsyncOpenAI, user_prompt: str, max_turns: int = 6) -> None:
    mcp_tools = await client.list_tools()
    openai_tools = [mcp_tool_to_openai(t) for t in mcp_tools]
    print(f"[{len(openai_tools)} tools exposed to the model]\n")

    messages = [
        {
            "role": "system",
            "content": (
                "You control a Cadence Sigrity automation suite through MCP tools. "
                "Use the tools to answer the user's question. Call tools as needed, "
                "then give a concise final answer citing what the tools returned."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    for turn in range(max_turns):
        response = await oai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
        )
        choice = response.choices[0]
        messages.append(choice.message.model_dump(exclude_none=True))

        if not choice.message.tool_calls:
            print("=== FINAL ANSWER ===")
            print(choice.message.content)
            return

        for tool_call in choice.message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"[turn {turn}] model calls {name}({args})")
            result = await client.call_tool(name, args)
            payload = result.content[0].text if result.content else "{}"
            print(f"  -> {payload[:300]}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": payload,
                }
            )

    print("=== MAX TURNS REACHED ===")


async def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "What Sigrity tools are installed on this machine, and is the FlexNet "
        "license server currently reachable? Also tell me this machine's FlexNet host ID."
    )
    http_client = httpx.AsyncClient(trust_env=False)
    oai = AsyncOpenAI(base_url=BASE_URL, api_key="not-needed", http_client=http_client)
    async with Client(mcp) as client:
        await run_conversation(client, oai, prompt)


if __name__ == "__main__":
    asyncio.run(main())
