"""Builds the full sigrity-mcp server by importing every domain package for its tool
registrations, then exposes the shared `mcp` FastMCP instance to run.
"""

from __future__ import annotations

from sigrity_mcp.mcp_app import mcp

# Each import below registers that domain's @mcp.tool functions as a side effect.
from sigrity_mcp.domains import aurora, extraction, pi, platform, si  # noqa: E402,F401

__all__ = ["mcp"]
