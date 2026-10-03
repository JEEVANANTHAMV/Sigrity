# Workarounds: JSON-String-Encoded list/dict Arguments

## Verified Fix (in-suite — `tool_bug_fixed`, suite-wide)

**A single FastMCP middleware, registered once, transparently re-parses JSON/Python-literal string arguments back into native `list`/`dict` for every tool before FastMCP's pydantic validation.** No per-tool change.

- **Mechanism**: `JsonStringArgumentCoercionMiddleware.on_call_tool` (argument_coercion_middleware.py:46-66) runs on every `tools/call`, looks up the tool's input schema (`tool.parameters`), and calls `coerce_json_string_arguments(arguments, tool.parameters)`; if anything changed it reassigns `context.message.arguments`. FastMCP's middleware chain wraps `tool._run(arguments)`, so the handler/tool body sees the coerced values.
- **Decision logic** (argument_coercion.py): only fields whose schema **definitely rejects a plain string** are candidates; among those, a string value is replaced only when it **parses (JSON, or `ast.literal_eval` fallback) into a `list`/`dict`**. Scalars and string-allowing fields (`Union[str, list[...]]`) are untouched.
- **Scope**: covers all ~26 exposed tools (incl. `generate_multilayer_stackup`, `run_tool_pipeline`, `powerdc_add_vrm`, `xtractim_set_circuits`, `evaluate_bom_sourcing_policy`).
- **Operator confirmation**: SKILL.md:106-115 states it plainly ("FIXED — `list`/`dict` arguments sent as JSON strings now work ... for every tool in this suite").

Manifest row 107 marks this `verified_workaround: YES (argument_coercion_middleware)`.

## What this does / doesn't fix

- **Fixes**: the `list_type`/`dict_type` `ValidationError` for string-encoded containers, for *every* tool, with a conservative guard that can't corrupt valid string args or `Union[str, list[...]]` args.
- **Does not fix / does not affect**:
  - A field that legitimately takes a string and a caller *meant* a string — left alone (correct).
  - A field that *only* accepts a string and a model stringifies a container that should have been a string — out of scope (schema says string, so it's a valid string).
  - Malformed JSON that doesn't parse to a list/dict — left as a string (pydantic will then reject it with the original error, which is correct: it *is* malformed).
  - The calling model's underlying quirk (still emits strings) — the middleware *absorbs* it rather than stopping the model; that's the intended trade-off.

## Why this design (and the alternatives rejected)

| Alternative | Why not |
|---|---|
| Patch each of the 26 tools to parse its own args | Fragile, repetitive, easy to miss a new tool; the middleware does it once for all ~200 tools at the wire layer |
| Monkeypatch FastMCP `FunctionTool.run()` / rely on legacy `pre_parse_json` | Not a supported hook in FastMCP 4.0.4; `FunctionTool.run` does not call `pre_parse_json`; monkeypatching internals is brittle |
| Always parse any string arg | Would corrupt legitimate string arguments; the conservative field-schema + list/dict-only rule (argument_coercion.py:31-38, 102-122) avoids that |

## Workarounds / the fix, as a table (with outcomes)

| # | Behavior | Outcome | Evidence |
|---|----------|---------|----------|
| 1 | (pre-fix) model sends `steps`/`layers` as a JSON *string* → FastMCP pydantic | **`list_type`/`dict_type` `ValidationError`** on a well-formed call | argument_coercion.py:1-19 |
| 2 | (pre-fix) a caller works around by JSON-decoding client-side | **unreliable** — depends on the calling model/client; doesn't help the in-process eval or other clients | — |
| 3 | **Middleware auto-coerces string→native for string-rejecting fields that parse to list/dict** | **works suite-wide; transparent to all tools and all callers** | argument_coercion_middleware.py:46-66; SKILL.md:106-115 |
| 4 | Conservative guard (string-allowing / scalar / bare-$ref left alone) | **prevents corrupting legit strings & `Union[str,list]` fields** | argument_coercion.py:48-85, 102-122 |

## Prevention

1. **Keep the single middleware registered on the shared `mcp` instance** (`sigrity_mcp/mcp_app.py`). Do **not** remove it or replace it with per-tool patches; it is the one place the wire-serialization quirk is absorbed.
2. **When adding a tool with a `list[...]`/`dict[...]` arg, no change is needed** — the middleware covers it automatically (that is the point of the design). Just make sure the arg is genuinely typed `list`/`dict`, not `str`, if you want the benefit.
3. **For `Union[str, list[...]]` fields, accept that they are deliberately not coerced** — callers can send a real string there and it stays a string. Don't "fix" coercion into these fields.
4. If a new calling model exposes a *different* stringification quirk (e.g. always double-encoding), extend `_try_parse_structured`'s parse fallback — don't scatter parsing across tools.

## Remaining Gaps

The fix is conservative and intentionally narrow: it only absorbs **string → native container** for **string-rejecting** fields that **parse to a list/dict**. It does not change the calling model's emission, does not touch scalar/string fields, and relies on the tool's JSON schema being present (`get_tool(...).parameters`); a tool whose parameters are unavailable (`tool is None`) is skipped. It is robust for the observed qwen3-max/vLLM case and the 26 audited tools, but any *new* serialization quirk beyond "stringified JSON/Python literal" would need a corresponding extension to the parse fallback.