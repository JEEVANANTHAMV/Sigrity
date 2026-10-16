"""Tests for the JSON/Python-literal string-argument coercion fix.

Background: some calling models (observed live: qwen3-max via vLLM, through the real
forji-desk app) emit a `list`/`dict`-typed tool argument as a JSON-encoded string
(e.g. `'[{"name": ...}]'`) instead of a native JSON array/object. FastMCP 4.0.4's
`FunctionTool.run()` validates `arguments` with strict pydantic `TypeAdapter` validation
and does not pre-parse such strings (checked directly against the installed
`fastmcp==4.0.4` package -- unlike the legacy `mcp.server.mcpserver` code path's
`FuncMetadata.pre_parse_json`, which FastMCP does not call). The fix lives in:
  - sigrity_mcp/core/argument_coercion.py (the pure coercion logic)
  - sigrity_mcp/core/argument_coercion_middleware.py (wires it into every tool call
    via FastMCP's documented `Middleware.on_call_tool` hook)
  - sigrity_mcp/mcp_app.py (registers the middleware once on the shared `mcp` instance)

See tests/test_cad_rigid_flex_stackup_tools.py::
test_generate_multilayer_stackup_accepts_layers_as_json_string_through_mcp for the
original failing tool's reproduction. This file covers the coercion logic directly,
plus two more of the 26 tools found (by audit) to have the same list/dict-typed
parameter shape, confirming the fix is not special-cased to one tool.
"""

import json

import pytest

from sigrity_mcp.core.argument_coercion import coerce_json_string_arguments
from sigrity_mcp.domains.extraction.xtractim_tools import start_xtractim_session
from sigrity_mcp.server import mcp


# ---------------------------------------------------------------------------
# Pure-function tests for coerce_json_string_arguments
# ---------------------------------------------------------------------------


def test_coerce_parses_json_string_list_field():
    schema = {"properties": {"layers": {"type": "array", "items": {"type": "object"}}}}
    args = {"layers": json.dumps([{"name": "A"}, {"name": "B"}])}
    result = coerce_json_string_arguments(args, schema)
    assert result["layers"] == [{"name": "A"}, {"name": "B"}]


def test_coerce_parses_json_string_dict_field():
    schema = {"properties": {"opts": {"type": "object"}}}
    args = {"opts": json.dumps({"a": 1, "b": 2})}
    result = coerce_json_string_arguments(args, schema)
    assert result["opts"] == {"a": 1, "b": 2}


def test_coerce_falls_back_to_python_literal_syntax():
    """Some models emit Python-repr (single-quoted) strings instead of JSON for the
    same stringified-argument quirk; json.loads alone would reject these."""
    schema = {"properties": {"layers": {"type": "array"}}}
    args = {"layers": "[{'name': 'A'}]"}
    result = coerce_json_string_arguments(args, schema)
    assert result["layers"] == [{"name": "A"}]


def test_coerce_leaves_plain_scalar_strings_untouched():
    """A string value that happens to parse as JSON but produces a scalar (not a
    list/dict) is left alone -- it's far more likely to be a literal than an
    encoded container."""
    schema = {"properties": {"count": {"type": "integer"}}}
    args = {"count": "5"}
    result = coerce_json_string_arguments(args, schema)
    assert result["count"] == "5"
    assert result is args  # no copy made when nothing changes


def test_coerce_leaves_already_valid_fields_alone():
    schema = {"properties": {"layers": {"type": "array"}}}
    args = {"layers": [{"name": "A"}]}
    result = coerce_json_string_arguments(args, schema)
    assert result is args


def test_coerce_does_not_touch_fields_that_already_accept_a_plain_string():
    """A `Union[str, list[str]]` field's JSON schema is an `anyOf` including a plain
    `string` branch -- a string value is already valid there, so it must not be
    reinterpreted (a literal ref-des string could coincidentally look JSON-ish)."""
    schema = {
        "properties": {
            "ref_des": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}
        }
    }
    args = {"ref_des": "U1"}
    result = coerce_json_string_arguments(args, schema)
    assert result["ref_des"] == "U1"
    assert result is args


def test_coerce_handles_missing_or_unknown_schema_gracefully():
    args = {"layers": "not json"}
    assert coerce_json_string_arguments(args, None) is args
    assert coerce_json_string_arguments(args, {}) is args


# ---------------------------------------------------------------------------
# Middleware integration tests -- confirm the fix applies cleanly to OTHER
# audited tools with list/dict-typed parameters, not just generate_multilayer_stackup.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xtractim_set_circuits_accepts_list_field_as_json_string():
    """xtractim_set_circuits(component_ref_des_list: list[str]) is one of the other
    tools found (by audit) with a plain list-typed parameter -- confirms the
    middleware fix is not special-cased to generate_multilayer_stackup."""
    session = await start_xtractim_session(spd_file="dummy.spd")
    sid = session["session_id"]

    args = {
        "session_id": sid,
        "die_ref_des": "U1",
        "board_ref_des": "BGA1",
        "component_ref_des_list": json.dumps(["C1", "C2", "C3"]),
    }
    result = await mcp.call_tool("xtractim_set_circuits", args)

    assert result.is_error is False
    assert result.structured_content["component_ref_des_list"] == ["C1", "C2", "C3"]


@pytest.mark.asyncio
async def test_run_tool_pipeline_accepts_steps_as_json_string():
    """run_tool_pipeline(steps: list[dict]) is another of the 26 audited tools with
    a list/dict-typed parameter -- confirms the fix generalizes beyond CAD tools."""
    steps = [
        {
            "tool": "get_high_speed_constraint_preset",
            "args": {"interface_type": "DDR5"},
        }
    ]
    args = {"steps": json.dumps(steps)}

    result = await mcp.call_tool("run_tool_pipeline", args)

    assert result.is_error is False
    assert result.structured_content["results"][0]["result"]["interface"] == "DDR5"
