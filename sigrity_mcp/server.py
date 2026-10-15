"""Builds the full sigrity-mcp server by importing every domain package for its tool
registrations, then exposes the shared `mcp` FastMCP instance to run.
"""

from __future__ import annotations

from sigrity_mcp.core.tool_enhancer import enrich_and_tag_tools
from sigrity_mcp.mcp_app import mcp

# Each import below registers that domain's @mcp.tool functions as a side effect.
from sigrity_mcp.domains import aurora, cad, extraction, pi, platform, si, sourcing, thermal  # noqa: E402,F401

# Enrich tools with tags and sanitize descriptions for remote MCP clients
enrich_and_tag_tools(mcp)

__all__ = ["mcp"]


if __name__ == "__main__":
    mcp.run(transport="stdio")
