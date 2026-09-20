"""Shared helper for a real, demonstrated failure class in Allegro's family of
standalone `tools/bin` CLIs (dxf2a, a2dxf, ipc2581_in, idf_out, idx_out, generate_sim_variant,
create_sym, ...  — several share near-identical "Standard command line arguments"/"Legend"
`-help` footers, strongly suggesting a shared internal argument-parsing library).

Every `submit_job`-based tool runs with a fresh per-job scratch directory as its process
cwd, not the MCP server's own cwd. A caller-supplied *relative* path to a required input
file that doesn't resolve from THAT directory doesn't make these tools fail cleanly —
confirmed live (twice, for dxf2a and a2dxf, while building allegro_import_tools.py) they
instead fall back to an interactive re-prompt loop reading from a stdin that's never
connected, generating output fast enough to hit this suite's 200MB job-log watchdog
(`core/config.py`'s `max_log_bytes`) within seconds. Resolving every path argument to
absolute (relative to the MCP server's own cwd) before building argv closes off the most
common cause of this.
"""

from __future__ import annotations

from pathlib import Path


def resolve_path(path: str) -> str:
    """Absolute-ify a path relative to the caller's (server's) cwd, not a job's scratch cwd.

    Purely lexical (Path.resolve() doesn't require the target to already exist), so this
    is safe to apply to output paths that don't exist yet too.
    """
    return str(Path(path).resolve())
