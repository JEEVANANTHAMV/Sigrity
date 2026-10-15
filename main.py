"""Entry point for the Sigrity MCP server.

Defaults to `stdio` (for a same-machine launcher like Claude Code's mcp.json — the
existing setup keeps working unchanged). Pass `--transport http` or `--transport sse`
to serve over the network instead, so a remote client (a deepagents/LangChain agent on
another machine, for example) can connect via `MultiServerMCPClient`. See the README's
"Connecting a remote MCP client" section for a worked example, and
the `load_skill` (and `list_skills`) tools for how such a client
discovers the domain playbooks without any filesystem access to this machine.
"""

import argparse

from sigrity_mcp.core.config import settings
from sigrity_mcp.core.swagger import setup_swagger_docs
from sigrity_mcp.core.tool_enhancer import STRICT_SERVER_INSTRUCTIONS, enrich_and_tag_tools
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
    parser.add_argument(
        "--docs",
        dest="enable_docs",
        action="store_true",
        default=True,
        help="Enable Swagger UI documentation and live tool testing at /docs (default: True).",
    )
    parser.add_argument(
        "--no-docs",
        dest="enable_docs",
        action="store_false",
        help="Disable Swagger UI documentation.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    
    # Ensure all tools have domain tags, sanitized MCP-compliant descriptions,
    # and strict sub-agent instructions for remote clients.
    enrich_and_tag_tools(mcp)
    mcp.instructions = STRICT_SERVER_INSTRUCTIONS

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        if args.enable_docs:
            setup_swagger_docs(
                mcp_app=mcp,
                title="Sigrity MCP",
                version="0.1.0",
                description=(
                    "Interactive documentation and testing console for 200+ Cadence Sigrity 2024.0 "
                    "and Allegro/OrCAD SPB 22.1 MCP tools."
                ),
                mcp_path=args.path,
            )
            display_host = "localhost" if args.host == "0.0.0.0" else args.host
            print(f"\n========================================================")
            print(f" Sigrity MCP Server with Swagger UI Live Testing")
            print(f"========================================================")
            print(f" • Swagger UI Docs:  http://{display_host}:{args.port}/docs")
            print(f" • OpenAPI Spec:     http://{display_host}:{args.port}/openapi.json")
            print(f" • MCP Endpoint:     http://{display_host}:{args.port}{args.path}")
            print(f" • Sub-Agent Policy: STRICT - Sub-agents must call load_skill()")
            print(f"========================================================\n")
        mcp.run(transport=args.transport, host=args.host, port=args.port, path=args.path)


if __name__ == "__main__":
    main()
