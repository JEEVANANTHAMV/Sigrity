"""Coerce JSON/Python-literal-encoded string arguments for non-string tool parameters.

Why this exists
----------------
Some MCP clients / calling models (observed live: ``qwen3-max`` served via vLLM,
calling through the real forji-desk app) emit a ``list``/``dict``-typed tool
argument as a JSON-encoded *string* (e.g. ``'[{"name": "L2_GND", ...}]'``)
instead of a native JSON array/object. FastMCP 4.0.4's ``FunctionTool.run()``
validates incoming ``arguments`` with pydantic's
``TypeAdapter.validate_python(..., strict=...)`` and does not attempt to parse
string-encoded structures first — unlike the legacy ``mcp.server.mcpserver``
code path's ``FuncMetadata.pre_parse_json``, which FastMCP's own
``FunctionTool.run()`` does not call (checked directly against the installed
``fastmcp==4.0.4`` package under ``.venv``; see the `on_call_tool` note below
for exactly where this module plugs in instead). The net effect: a
syntactically well-formed tool call is rejected with a pydantic
``list_type``/``dict_type`` ``ValidationError`` purely because of how the
calling model serialized its arguments on the wire — not because the call
itself was wrong.

This is NOT unique to one tool. An audit of ``sigrity_mcp/domains/**`` found
26 `@mcp.tool`-registered functions with at least one ``list[...]``/``dict[...]``
(or ``Union[str, list[...]]``)-typed parameter, all equally exposed — e.g.
``generate_multilayer_stackup`` (the tool that originally surfaced this),
``powerdc_add_vrm``, ``xtractim_set_circuits``, ``run_tool_pipeline``,
``evaluate_bom_sourcing_policy``, and others. See
``sigrity_mcp/core/argument_coercion_middleware.py`` for how this helper is
wired in once, for every tool, via FastMCP's middleware chain rather than
patched into each tool individually.

Only arguments whose JSON schema definitely does *not* accept a plain string
are candidates for coercion (so a tool parameter that legitimately accepts
either a string or a list, e.g. ``Union[str, list[str]]``, is left alone — a
string value there is already valid as-is and must not be reinterpreted).
Among those candidates, a string value is replaced with its parsed form only
when parsing succeeds AND produces a ``list``/``dict`` — a plain scalar
(``"5"``, ``"true"``, ``"null"``) is left untouched, since that is far more
likely to be a literal the caller intended than a JSON-encoded container.
"""

from __future__ import annotations

import ast
import json
from typing import Any


def _field_rejects_plain_string(field_schema: Any) -> bool:
    """True if this JSON-schema fragment definitely does not accept a plain string.

    Used to decide whether a *string* value arriving for this field is almost
    certainly a JSON/Python-literal-encoded complex value rather than a
    legitimate literal string.

    Conservative by design: anything this can't classify (a bare ``$ref``, an
    empty/absent schema, an ``anyOf``/``oneOf`` branch that itself allows a
    plain string) is treated as "leave it alone" (returns ``False``), so this
    never mangles a parameter that was always meant to accept text.
    """
    if not isinstance(field_schema, dict):
        return False

    ftype = field_schema.get("type")
    if isinstance(ftype, str):
        return ftype != "string"
    if isinstance(ftype, list):
        # JSON Schema's list-of-types form, e.g. ["string", "null"].
        return "string" not in ftype

    for key in ("anyOf", "oneOf"):
        branches = field_schema.get(key)
        if isinstance(branches, list) and branches:
            # A field like `Union[str, list[str]]` produces an `anyOf` with a
            # plain `{"type": "string"}` branch alongside the array branch —
            # a string value is already valid for it, so only flag this field
            # as string-rejecting if EVERY branch rejects a plain string.
            return all(
                _field_rejects_plain_string(branch)
                for branch in branches
                if isinstance(branch, dict)
            )

    # No "type"/"anyOf"/"oneOf" info at all (e.g. a bare `$ref` to a named
    # model, or an unconstrained field) — can't prove a string is wrong here.
    return False


def _non_string_field_names(input_schema: dict[str, Any] | None) -> set[str]:
    """Names of top-level properties whose schema rejects a plain string value."""
    if not input_schema or not isinstance(input_schema, dict):
        return set()
    props = input_schema.get("properties")
    if not isinstance(props, dict):
        return set()
    return {
        name
        for name, field_schema in props.items()
        if _field_rejects_plain_string(field_schema)
    }


def _try_parse_structured(value: str) -> tuple[Any, bool]:
    """Try to parse `value` as JSON, falling back to a Python-literal (``ast.literal_eval``).

    The fallback covers calling models that emit Python-repr-style strings
    (single-quoted dicts/lists) instead of JSON — a variant of the same
    stringified-argument quirk. Returns ``(parsed, True)`` only when parsing
    succeeds AND the result is a ``list``/``dict``; a parsed scalar (int,
    float, bool, None, or even another string) is reported as a non-match
    so an actual literal string argument is never silently rewritten.
    """
    try:
        parsed = json.loads(value)
    except (ValueError, RecursionError):
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError, RecursionError, TypeError, MemoryError):
            return None, False

    if isinstance(parsed, (list, dict)):
        return parsed, True
    return None, False


def coerce_json_string_arguments(
    arguments: dict[str, Any], input_schema: dict[str, Any] | None
) -> dict[str, Any]:
    """Return a copy of `arguments` with string-encoded list/dict values parsed back
    into native Python objects, for fields whose schema cannot accept a plain string.

    `arguments` is never mutated in place; the original dict is returned
    unchanged (same object) when nothing needed coercion, so callers can use
    an identity check to skip reassigning it.
    """
    non_string_fields = _non_string_field_names(input_schema)
    if not non_string_fields:
        return arguments

    coerced: dict[str, Any] | None = None
    for key in non_string_fields:
        if key not in arguments:
            continue
        value = arguments[key]
        if not isinstance(value, str):
            continue
        parsed, matched = _try_parse_structured(value)
        if not matched:
            continue
        if coerced is None:
            coerced = dict(arguments)
        coerced[key] = parsed

    return arguments if coerced is None else coerced
