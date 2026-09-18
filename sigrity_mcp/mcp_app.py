"""The single shared FastMCP application instance.

Every domain module (`sigrity_mcp.domains.*`) imports `mcp` from here and registers its
tools on it with `@mcp.tool`. `sigrity_mcp.server` imports all domain modules for their
side effects and exposes the fully-populated app.
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP(
    name="sigrity-mcp",
    instructions=(
        "Tools for driving a local Cadence Sigrity 2024.0 install (Power Integrity, "
        "Signal Integrity, interconnect extraction, in-design analysis, and the unified "
        "Sigrity X platform) through its Tcl batch-automation interface. Long-running "
        "simulations/extractions are launched as background jobs: a 'run_*' tool returns "
        "a job_id immediately, then use get_job_status / wait_for_job / tail_job_log to "
        "track it and list_job_files / read_* tools to retrieve results. All file paths "
        "passed to tools must be absolute paths already reachable on this machine."
    ),
)
