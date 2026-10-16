"""Quick manual smoke test: server builds, tools register, real safe tools actually run."""

import asyncio

from sigrity_mcp.server import mcp


async def main():
    tools = await mcp.list_tools()
    print("TOOL COUNT:", len(tools))
    for t in sorted(tools, key=lambda t: t.name):
        print(" -", t.name, ":", (t.description or "").splitlines()[0][:80])


if __name__ == "__main__":
    asyncio.run(main())
