"""Entry point for the Sigrity MCP server.

Defaults to `stdio` (for a same-machine launcher like Claude Code's mcp.json — the
existing setup keeps working unchanged). Pass `--transport http` or `--transport sse`
to serve over the network instead, so a remote client (a deepagents/LangChain agent on
another machine, for example) can connect via `MultiServerMCPClient`. See the README's
"Connecting a remote MCP client" section for a worked example, and
`.forjinn/skills/` (via the `list_skills`/`load_skill` tools) for how such a client
discovers the domain playbooks without any filesystem access to this machine.
"""

from __future__ import annotations

import argparse

from sigrity_mcp.core.config import settings
from sigrity_mcp.server import mcp


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Sigrity MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default=settings.mcp_transport,
        help="MCP transport. 'stdio' (default) for a local same-machine launcher; "
        "'http' (Streamable HTTP) or 'sse' for a remote/network client. "
        "Env override: SIGRITY_MCP_TRANSPORT.",
    )
    parser.add_argument(
        "--host",
        default=settings.mcp_host,
        help="Bind address for http/sse transport (default: %(default)s). Use 0.0.0.0 "
        "to accept connections from other machines. Env override: SIGRITY_MCP_HOST.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.mcp_port,
        help="Bind port for http/sse transport (default: %(default)s). "
        "Env override: SIGRITY_MCP_PORT.",
    )
    parser.add_argument(
        "--path",
        default=settings.mcp_path,
        help="URL path for the MCP endpoint under http/sse transport "
        "(default: %(default)s), i.e. http://<host>:<port><path>. "
        "Env override: SIGRITY_MCP_PATH.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, path=args.path)


if __name__ == "__main__":
    main()
