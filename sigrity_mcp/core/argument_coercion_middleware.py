"""Applies `argument_coercion.coerce_json_string_arguments` to every tool call, once,
for all tools registered on the shared `mcp` instance.

Where this plugs in
--------------------
FastMCP's `FunctionTool.run()` validates `arguments` with pydantic *before* the
tool's own body ever runs (`fastmcp/tools/function_tool.py` in the installed
`fastmcp==4.0.4` package — checked directly, not from memory). There is no
documented hook on `FunctionTool`/`@mcp.tool` itself to pre-process arguments
before that validation. There IS a supported, documented extension point one
layer up: `fastmcp.server.middleware.Middleware.on_call_tool`, which runs for
every `tools/call` request *before* `FastMCP.call_tool()` resolves and invokes
the target `FunctionTool` (see `FastMCP.call_tool()` in
`fastmcp/server/server.py`: the middleware chain wraps
`tool._run(arguments)`, not the other way around). Mutating
`context.message.arguments` here is documented/relied-upon FastMCP behavior
(`fastmcp/server/low_level.py`'s `_forward_ctx` explicitly folds middleware
edits to `context.message` back into what the handler receives), so this is a
real, supported mechanism — not a monkeypatch of FastMCP internals.

Registering ONE instance of this middleware (see `sigrity_mcp/mcp_app.py`)
therefore fixes every tool that takes a `list[...]`/`dict[...]`-typed
parameter in one place, with no change required to any of the ~200 individual
`@mcp.tool` functions across `sigrity_mcp/domains/**`.
"""

from __future__ import annotations

import mcp_types
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from sigrity_mcp.core.argument_coercion import coerce_json_string_arguments


class JsonStringArgumentCoercionMiddleware(Middleware):
    """Pre-parses JSON/Python-literal-encoded string arguments before tool validation.

    Looks up the target tool's input schema (`Tool.parameters`) to decide,
    per field, whether a string value is a legitimate literal or a
    stringified list/dict that should be parsed back to native Python before
    FastMCP's pydantic validation runs. See `argument_coercion.py` for the
    actual decision logic.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        arguments = context.message.arguments
        fastmcp_context = context.fastmcp_context

        if arguments and fastmcp_context is not None:
            tool = await fastmcp_context.fastmcp.get_tool(context.message.name)
            if tool is not None:
                coerced = coerce_json_string_arguments(arguments, tool.parameters)
                if coerced is not arguments:
                    # `CallToolRequestParams` is a plain (non-frozen) pydantic
                    # model; assigning the attribute directly (no
                    # `validate_assignment`) is how FastMCP's own
                    # `_forward_ctx` documents folding a middleware's edits
                    # back into what the handler/tool body receives.
                    context.message.arguments = coerced

        return await call_next(context)
