# LLM Serializes List/Dict Arguments as JSON Strings → Pydantic `list_type`/`dict_type` Failure

**Slug**: `json-arg-coercion-middleware`
**Tool(s) affected**: **every** `@mcp.tool` with a `list[...]`/`dict[...]`-typed parameter (~26 tools audited); originally surfaced by `generate_multilayer_stackup`'s `layers` and by `run_tool_pipeline`'s `steps`
**Status category**: `tool_bug_fixed` (per manifest row 107) — a wrapper-level bug, now fixed suite-wide by one middleware
**Pipeline stage**: platform (transport/wire-serialization layer, applies to all tools)

## Symptom

Some calling models (observed live: **`qwen3-max` served via vLLM**, calling through the forji-desk app) emit a `list`/`dict`-typed tool argument as a **JSON-encoded *string*** instead of a native JSON array/object — e.g. they send `steps` as the *string* `'[{"tool": "...", ...}]'` rather than a real array. FastMCP 4.0.4's `FunctionTool.run()` validates the incoming arguments with pydantic and **does not attempt to parse string-encoded structures first**, so a **syntactically well-formed** tool call was being **rejected** with a pydantic `list_type`/`dict_type` `ValidationError` — purely because of how the model serialized the argument on the wire, not because the call was actually wrong.

Concretely, any one of the ~26 exposed tools (e.g. `generate_multilayer_stackup(layers="[...]")`, `run_tool_pipeline(steps="[...]")`, `powerdc_add_vrm`, `xtractim_set_circuits`, `evaluate_bom_sourcing_policy`) would fail validation if the calling model stringified its argument, even when the JSON content was perfectly valid.

## Root Cause

- **FastMCP's wire handling**: FastMCP 4.0.4's `FunctionTool.run()` validates `arguments` via `TypeAdapter.validate_python(..., strict=...)` and does **not** call the legacy `mcp.server.mcpserver` `FuncMetadata.pre_parse_json` path — so a string that encodes a list/dict is handed to pydantic as a string and fails a non-string field (checked directly against the installed `fastmcp==4.0.4` package, not from memory).
- **The calling model's serialization quirk**: certain open-weight models (qwen3-max via vLLM in the observed case) emit list/dict arguments as JSON *strings*. This is a real, observed property of model tool-call emission, not a harness artifact.
- **Not unique to one tool**: an audit of `sigrity_mcp/domains/**` found **26 `@mcp.tool`-registered functions** with at least one `list[...]`/`dict[...]` (or `Union[str, list[...]]`)-typed parameter, *all equally exposed* — which is why the fix had to be suite-wide, not a per-tool patch.

## How the fix works (the middleware)

The fix is a **single FastMCP `Middleware.on_call_tool`** registered once on the shared `mcp` instance (see `sigrity_mcp/mcp_app.py` and `sigrity_mcp/core/argument_coercion_middleware.py`). It runs for **every** `tools/call` request *before* `FastMCP.call_tool()` resolves and invokes the target `FunctionTool` (the middleware chain wraps `tool._run(arguments)`), and it mutates `context.message.arguments` (documented/relied-upon FastMCP behavior — `_forward_ctx` folds middleware edits back into what the handler receives). Per field, it decides:

- **Is this field's schema one that *definitely doesn't accept a plain string*?** If yes, a string value for it is "almost certainly a JSON/Python-literal-encoded complex value."
- **Can the string be parsed** (JSON, falling back to `ast.literal_eval` for Python-repr-style single-quoted literals) **into a `list`/`dict`?** Only then is it replaced with the parsed native value.

This is **conservative by design** and never mangles legitimate text:
- A field that `Union[str, list[str]]` (e.g. `ref_des` in several PI tools) is **left alone** — a string there is already valid and must not be reinterpreted (`_field_rejects_plain_string` returns `False` for a `string`-allowing branch).
- A bare `$ref`/absent schema / unconstrained field is left alone (can't prove a string is wrong).
- A string that parses to a **scalar** (`"5"`, `"true"`, `"null"`) is left untouched — far more likely a literal the caller intended than a JSON-encoded container (`_try_parse_structured` requires the parse to be a `list`/`dict`).

## Evidence

- `sigrity_mcp/core/argument_coercion.py:1-39` (module docstring) — the full mechanism and scope: "Some MCP clients / calling models (observed live: `qwen3-max` served via vLLM, calling through the real forji-desk app) emit a `list`/`dict`-typed tool argument as a JSON-encoded *string* ... FastMCP 4.0.4's `FunctionTool.run()` validates ... does not attempt to parse string-encoded structures first ... The net effect: a syntactically well-formed tool call is rejected with a pydantic `list_type`/`dict_type` `ValidationError` purely because of how the calling model serialized its arguments on the wire." Plus: "An audit of `sigrity_mcp/domains/**` found **26** `@mcp.tool`-registered functions with at least one `list[...]`/`dict[...]` ... e.g. `generate_multilayer_stackup` (the tool that originally surfaced this), `powerdc_add_vrm`, `xtractim_set_circuits`, `run_tool_pipeline`, `evaluate_bom_sourcing_policy`, and others."
- `sigrity_mcp/core/argument_coercion.py:31-38` — the conservative rule: "Only arguments whose JSON schema definitely does *not* accept a plain string are candidates ... a tool parameter that legitimately accepts either a string or a list, e.g. `Union[str, list[str]]`, is left alone."
- `sigrity_mcp/core/argument_coercion.py:48-85` (`_field_rejects_plain_string`) — the per-field schema classification (string type, JSON-Schema list-of-types, `anyOf`/`oneOf`, bare `$ref` → leave alone).
- `sigrity_mcp/core/argument_coercion.py:102-122` (`_try_parse_structured`) — JSON parse with `ast.literal_eval` fallback; returns a match only when the parse is a `list`/`dict` (scalars never coersed).
- `sigrity_mcp/core/argument_coercion.py:125-153` (`coerce_json_string_arguments`) — copies `arguments` and rewrites only matched fields; returns the same object unchanged when nothing matched (identity check).
- `sigrity_mcp/core/argument_coercion_middleware.py:1-25` (module docstring) — *where it plugs in* (one layer up at `Middleware.on_call_tool`: "the middleware chain wraps `tool._run(arguments)`, not the other way around"; mutating `context.message.arguments` is documented FastMCP behavior) and *why one instance suffices* ("Registering ONE instance ... fixes every tool that takes a `list[...]`/`dict[...]`-typed parameter in one place, with no change required to any of the ~200 individual `@mcp.tool` functions").
- `sigrity_mcp/core/argument_coercion_middleware.py:36-66` (`on_call_tool`) — the actual wiring: looks up the tool (`fastmcp_context.fastmcp.get_tool(context.message.name)`), calls `coerce_json_string_arguments(arguments, tool.parameters)`, and reassigns `context.message.arguments = coerced` only when the identity changed.
- `.forjinn/skills/sigrity/SKILL.md:106-115` — the operator-facing note: "FIXED — `list`/`dict` arguments sent as JSON strings now work ... transparently parsed back to a native list/dict for every tool in this suite before validation, instead of failing with a pydantic `list_type`/`dict_type` error. See `sigrity_mcp/core/argument_coercion_middleware.py` ... A parameter that legitimately accepts either a string or a list (`Union[str, list[str]]`, e.g. `ref_des` in several PI tools) is unaffected either way."

## Pipeline Impact

Before the fix, any flow using one of the 26 exposed tools — **including the `run_tool_pipeline`'s own `steps` argument, the backbone of the suite's recommended one-call sequencing** (SKILL.md:69-95) — was at risk of a hard `list_type`/`dict_type` validation failure whenever the calling model stringified that argument. Since qwen3-max (the exact model the eval harness, `scripts/eval_e2e.py:34-36`, runs) is the observed offender, the eval and any qwen3-max-driven production use were directly exposed. The middleware removes that class of failure suite-wide with no per-tool change, which is what made the 12/12 eval run reliable.