"""Interactive Swagger UI documentation and testing endpoints for Sigrity MCP.

Provides:
- `/docs`: Full interactive Swagger UI with "Try it out" & "Execute" for all 200+ tools.
- `/openapi.json`: OpenAPI 3.0.3 specification covering all registered tools.
- `/tools/{tool_name}`: POST endpoint to invoke and test tools directly from Swagger UI or curl.
- `/api/tools`: JSON list of all tools and schemas.
- `/api/tools/{tool_name}`: Tool metadata and parameters.
- `/`: Convenient redirect to `/docs`.
- `/favicon.svg` and `/favicon.ico`: Embedded SVG icon.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

if TYPE_CHECKING:
    from fastmcp import FastMCP

DOMAIN_TITLES = {
    "cad": "CAD & PCB Layout (Allegro/OrCAD SPB 22.1)",
    "si": "Signal Integrity (PowerSI / BroadbandSPICE)",
    "pi": "Power Integrity (PowerDC / XcitePI / OptimizePI)",
    "extraction": "Interconnect Extraction (Clarity 3D / XtractIM / T2B)",
    "thermal": "Thermal Analysis (Celsius 2D / 3D / CFD)",
    "aurora": "Design Sync (Allegro Aurora)",
    "sourcing": "Component Sourcing",
    "platform": "Platform, Skills & Job Utilities",
    "general": "General Utilities",
}

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#0f172a"/>
  <rect x="14" y="14" width="36" height="36" rx="6" fill="#3b82f6" stroke="#60a5fa" stroke-width="2"/>
  <circle cx="24" cy="24" r="3" fill="#ffffff"/>
  <circle cx="40" cy="24" r="3" fill="#ffffff"/>
  <circle cx="32" cy="32" r="4" fill="#93c5fd"/>
  <circle cx="24" cy="40" r="3" fill="#ffffff"/>
  <circle cx="40" cy="40" r="3" fill="#ffffff"/>
  <line x1="8" y1="24" x2="14" y2="24" stroke="#60a5fa" stroke-width="2"/>
  <line x1="8" y1="40" x2="14" y2="40" stroke="#60a5fa" stroke-width="2"/>
  <line x1="50" y1="24" x2="56" y2="24" stroke="#60a5fa" stroke-width="2"/>
  <line x1="50" y1="40" x2="56" y2="40" stroke="#60a5fa" stroke-width="2"/>
  <line x1="24" y1="8" x2="24" y2="14" stroke="#60a5fa" stroke-width="2"/>
  <line x1="40" y1="8" x2="40" y2="14" stroke="#60a5fa" stroke-width="2"/>
  <line x1="24" y1="50" x2="24" y2="56" stroke="#60a5fa" stroke-width="2"/>
  <line x1="40" y1="50" x2="40" y2="56" stroke="#60a5fa" stroke-width="2"/>
</svg>"""

SWAGGER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} - Swagger UI</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    html {{ box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }}
    *, *:before, *:after {{ box-sizing: inherit; }}
    body {{
      margin: 0;
      background: #f8fafc;
      color: #0f172a;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .topbar-header {{
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      color: #fff;
      padding: 16px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    .topbar-brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 20px;
      font-weight: 700;
      color: #f8fafc;
      text-decoration: none;
    }}
    .topbar-badge {{
      background: #3b82f6;
      color: #fff;
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 9999px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .topbar-links {{
      display: flex;
      gap: 16px;
      align-items: center;
    }}
    .topbar-link {{
      color: #94a3b8;
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 6px;
      transition: all 0.2s;
    }}
    .topbar-link:hover {{
      color: #f8fafc;
      background: rgba(255, 255, 255, 0.1);
    }}
    .swagger-ui .topbar {{ display: none; }}
    .swagger-ui .info {{
      margin: 25px 0 20px 0;
    }}
    .swagger-ui .info .title {{
      font-size: 28px;
      color: #0f172a;
    }}
    .swagger-ui .opblock.opblock-post {{
      background: rgba(16, 185, 129, 0.05);
      border-color: #10b981;
    }}
    .swagger-ui .opblock.opblock-post .opblock-summary-method {{
      background: #10b981;
    }}
    .swagger-ui .opblock .opblock-summary-path {{
      font-weight: 600;
    }}
    .swagger-ui .btn.execute {{
      background-color: #2563eb;
      border-color: #2563eb;
      color: #fff;
    }}
    .swagger-ui .btn.execute:hover {{
      background-color: #1d4ed8;
      border-color: #1d4ed8;
    }}
  </style>
</head>
<body>
  <header class="topbar-header">
    <a href="/docs" class="topbar-brand">
      <svg width="28" height="28" viewBox="0 0 64 64" fill="none">
        <rect width="64" height="64" rx="14" fill="#3b82f6"/>
        <circle cx="24" cy="24" r="4" fill="#ffffff"/>
        <circle cx="40" cy="24" r="4" fill="#ffffff"/>
        <circle cx="32" cy="32" r="5" fill="#dbeafe"/>
        <circle cx="24" cy="40" r="4" fill="#ffffff"/>
        <circle cx="40" cy="40" r="4" fill="#ffffff"/>
      </svg>
      <span>{title}</span>
      <span class="topbar-badge">{version}</span>
    </a>
    <div class="topbar-links">
      <a href="{mcp_path}" class="topbar-link" target="_blank">🔌 MCP Endpoint ({mcp_path})</a>
      <a href="/openapi.json" class="topbar-link" target="_blank">📄 OpenAPI JSON</a>
      <a href="https://raw.githubusercontent.com/user/repo/main/README.md" class="topbar-link" target="_blank">📖 README</a>
    </div>
  </header>

  <div id="swagger-ui"></div>

  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {{
      window.ui = SwaggerUIBundle({{
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        displayRequestDuration: true,
        docExpansion: "list",
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        tryItOutEnabled: true,
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 1
      }});
    }};
  </script>
</body>
</html>
"""


def get_all_tools(mcp_app: FastMCP) -> list[Any]:
    """Extract all registered tools from the FastMCP application."""
    tools = []
    if hasattr(mcp_app, "local_provider") and hasattr(mcp_app.local_provider, "_components"):
        for key, comp in mcp_app.local_provider._components.items():
            if key.startswith("tool:"):
                tools.append(comp)
    return tools


def get_tool_domain_tag(tool: Any) -> str:
    """Determine the domain category and friendly tag for a tool."""
    fn = getattr(tool, "fn", None)
    mod = getattr(fn, "__module__", "") if fn else ""
    parts = mod.split(".")
    domain = parts[2] if len(parts) > 2 and parts[2] in DOMAIN_TITLES else "general"
    return DOMAIN_TITLES.get(domain, domain.capitalize())


def build_openapi_schema(
    mcp_app: FastMCP,
    title: str = "Sigrity MCP",
    version: str = "0.1.0",
    description: str = "API documentation and live testing console for Cadence Sigrity 2024.0 and Allegro/OrCAD SPB 22.1 MCP tools.",
    base_url: str = "http://localhost:8765",
) -> dict[str, Any]:
    """Generate OpenAPI 3.0.3 specification covering all registered tools."""
    tools = get_all_tools(mcp_app)

    tags_map: dict[str, str] = {}
    paths: dict[str, Any] = {}

    for t in sorted(tools, key=lambda x: x.name):
        tag = get_tool_domain_tag(t)
        tags_map[tag] = f"Tools for {tag}"

        raw_params = getattr(t, "parameters", {}) or {}
        # Ensure schema structure
        if isinstance(raw_params, dict) and raw_params.get("properties"):
            body_schema = raw_params
        else:
            body_schema = {
                "type": "object",
                "properties": {},
                "description": "No parameters required",
            }

        summary = getattr(t, "title", None) or t.name.replace("_", " ").title()
        # Add tool tags
        tool_tags = list(getattr(t, "tags", [])) if getattr(t, "tags", None) else []
        all_tags = [tag] + [t for t in tool_tags if t != tag]

        # POST /tools/{tool_name} to execute the tool
        paths[f"/tools/{t.name}"] = {
            "post": {
                "summary": summary,
                "description": getattr(t, "description", None) or f"Execute the {t.name} tool.",
                "operationId": f"call_{t.name}",
                "tags": all_tags,
                "requestBody": {
                    "description": f"Parameters for {t.name}",
                    "required": bool(raw_params.get("required")),
                    "content": {
                        "application/json": {
                            "schema": body_schema,
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Tool executed successfully",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "is_error": {"type": "boolean"},
                                        "content": {"type": "string"},
                                        "structured_content": {"type": "object"},
                                        "tool": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "400": {
                        "description": "Tool execution or validation error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "is_error": {"type": "boolean"},
                                        "error": {"type": "string"},
                                        "tool": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "500": {
                        "description": "Internal server error during execution",
                    },
                },
            },
            "get": {
                "summary": f"Get schema for {t.name}",
                "description": f"Retrieve tool metadata, parameters schema, and description for {t.name}.",
                "operationId": f"info_{t.name}",
                "tags": [tag],
                "responses": {
                    "200": {
                        "description": "Tool schema information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "parameters": {"type": "object"},
                                        "tag": {"type": "string"},
                                    },
                                }
                            }
                        },
                    }
                },
            },
        }

    tag_list = [{"name": tag, "description": desc} for tag, desc in sorted(tags_map.items())]

    return {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": version,
            "description": description,
        },
        "servers": [
            {"url": "/", "description": "Current Sigrity MCP Server"},
        ],
        "tags": tag_list,
        "paths": paths,
    }


def setup_swagger_docs(
    mcp_app: FastMCP,
    title: str = "Sigrity MCP",
    version: str = "0.1.0",
    description: str = (
        "Interactive testing console and documentation for 200+ Cadence Sigrity 2024.0 "
        "and Allegro/OrCAD SPB 22.1 MCP tools."
    ),
    mcp_path: str = "/mcp",
) -> None:
    """Register Swagger UI, OpenAPI schema, and live tool testing endpoints on FastMCP."""
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }

    # 1. Swagger UI at /docs
    @mcp_app.custom_route("/docs", methods=["GET"])
    async def docs_endpoint(_request: Request) -> Response:
        html = SWAGGER_HTML_TEMPLATE.format(
            title=title,
            version=version,
            mcp_path=mcp_path,
        )
        return HTMLResponse(content=html, headers=cors_headers)

    # 2. OpenAPI schema at /openapi.json
    @mcp_app.custom_route("/openapi.json", methods=["GET", "OPTIONS"])
    async def openapi_endpoint(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response("", headers=cors_headers)
        base_url = str(request.base_url).rstrip("/")
        schema = build_openapi_schema(
            mcp_app=mcp_app,
            title=title,
            version=version,
            description=description,
            base_url=base_url,
        )
        return JSONResponse(schema, headers=cors_headers)

    # 3. Live Tool Execution & Inspection at /tools/{tool_name}
    @mcp_app.custom_route("/tools/{tool_name}", methods=["POST", "GET", "OPTIONS"])
    async def tool_execution_endpoint(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response("", headers=cors_headers)

        tool_name = request.path_params.get("tool_name", "")

        # Find tool
        tools_by_name = {t.name: t for t in get_all_tools(mcp_app)}
        if tool_name not in tools_by_name:
            return JSONResponse(
                {"success": False, "is_error": True, "error": f"Tool '{tool_name}' not found", "tool": tool_name},
                status_code=404,
                headers=cors_headers,
            )

        tool = tools_by_name[tool_name]

        # GET returns tool inspection/schema
        if request.method == "GET":
            return JSONResponse(
                {
                    "name": tool.name,
                    "title": getattr(tool, "title", None) or tool.name,
                    "description": getattr(tool, "description", ""),
                    "parameters": getattr(tool, "parameters", {}),
                    "tags": list(getattr(tool, "tags", [])) if getattr(tool, "tags", None) else [get_tool_domain_tag(tool)],
                    "domain": get_tool_domain_tag(tool),
                },
                headers=cors_headers,
            )

        # POST executes the tool
        try:
            body_bytes = await request.body()
            arguments = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            if not isinstance(arguments, dict):
                arguments = {}
        except Exception as e:
            return JSONResponse(
                {"success": False, "is_error": True, "error": f"Invalid JSON payload: {e}", "tool": tool_name},
                status_code=400,
                headers=cors_headers,
            )

        try:
            res = await mcp_app.call_tool(tool_name, arguments)
            content_text = ""
            if res.content:
                content_text = "\n".join(
                    c.text for c in res.content if hasattr(c, "text") and c.text is not None
                )

            # Try parsing content_text if structured_content is missing
            structured = res.structured_content
            if structured is None and content_text:
                try:
                    structured = json.loads(content_text)
                except Exception:
                    structured = None

            status_code = 400 if res.is_error else 200
            return JSONResponse(
                {
                    "success": not res.is_error,
                    "is_error": res.is_error,
                    "tool": tool_name,
                    "content": content_text,
                    "structured_content": structured,
                },
                status_code=status_code,
                headers=cors_headers,
            )
        except Exception as exc:
            return JSONResponse(
                {
                    "success": False,
                    "is_error": True,
                    "tool": tool_name,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                status_code=500,
                headers=cors_headers,
            )

    # 4. /api/tools endpoint (list all tools)
    @mcp_app.custom_route("/api/tools", methods=["GET", "OPTIONS"])
    async def api_tools_list(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response("", headers=cors_headers)
        tools = get_all_tools(mcp_app)
        registry = {}
        for t in tools:
            registry[t.name] = {
                "name": t.name,
                "title": getattr(t, "title", None) or t.name,
                "description": getattr(t, "description", ""),
                "parameters": getattr(t, "parameters", {}),
                "tags": list(getattr(t, "tags", [])) if getattr(t, "tags", None) else [get_tool_domain_tag(t)],
                "domain": get_tool_domain_tag(t),
            }
        return JSONResponse(
            {
                "server": mcp_app.name,
                "total_tools": len(tools),
                "tools": registry,
            },
            headers=cors_headers,
        )

    # 5. /api/tools/{tool_name} alias
    @mcp_app.custom_route("/api/tools/{tool_name}", methods=["GET", "POST", "OPTIONS"])
    async def api_tool_alias(request: Request) -> Response:
        return await tool_execution_endpoint(request)

    # 6. Root redirect to /docs
    @mcp_app.custom_route("/", methods=["GET"])
    async def root_redirect(_request: Request) -> Response:
        return RedirectResponse(url="/docs", status_code=307)

    # 7. Favicon SVG & ICO
    @mcp_app.custom_route("/favicon.svg", methods=["GET"])
    async def favicon_svg(_request: Request) -> Response:
        return Response(
            content=FAVICON_SVG,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @mcp_app.custom_route("/favicon.ico", methods=["GET"])
    async def favicon_ico(_request: Request) -> Response:
        return Response(
            content=FAVICON_SVG,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )
