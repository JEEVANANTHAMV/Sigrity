"""Exercises run_tool_pipeline against real, lightweight registered tools (no Sigrity
process launch needed) to prove the in-process Client wiring and placeholder threading
actually work end-to-end, not just the substitution logic in isolation.
"""

import pytest

import sigrity_mcp.server  # noqa: F401 - ensures every domain is registered on `mcp`,
# independent of whatever other test files pytest happens to have already imported;
# run_tool_pipeline dispatches through a real Client(mcp) call, unlike most tests here
# which call tool functions directly as plain Python, so it actually needs this.
from sigrity_mcp.domains.platform.pipeline_tools import run_tool_pipeline


@pytest.mark.asyncio
async def test_pipeline_runs_steps_in_order_and_threads_results():
    steps = [
        {"tool": "get_aurora_scope_notice", "args": {}, "save_as": "notice"},
        {
            "tool": "get_license_feature_status",
            "args": {"feature_name": "${notice.see_also}"},
        },
    ]
    result = await run_tool_pipeline(steps)
    assert result["step_count"] == 2
    assert result["executed_count"] == 2
    assert result["succeeded_count"] == 2
    assert result["results"][1]["args"]["feature_name"] == "get_in_design_analysis_alternatives"


@pytest.mark.asyncio
async def test_pipeline_missing_tool_key_is_an_error_and_stops():
    steps = [{"args": {}}, {"tool": "get_aurora_scope_notice", "args": {}}]
    result = await run_tool_pipeline(steps, stop_on_error=True)
    assert result["executed_count"] == 1
    assert "error" in result["results"][0]


@pytest.mark.asyncio
async def test_pipeline_continues_past_errors_when_stop_on_error_false():
    steps = [
        {"tool": "not_a_real_tool", "args": {}},
        {"tool": "get_aurora_scope_notice", "args": {}},
    ]
    result = await run_tool_pipeline(steps, stop_on_error=False)
    assert result["executed_count"] == 2
    assert "error" in result["results"][0]
    assert "error" not in result["results"][1]


@pytest.mark.asyncio
async def test_pipeline_rejects_self_nesting():
    steps = [{"tool": "run_tool_pipeline", "args": {"steps": []}}]
    result = await run_tool_pipeline(steps)
    assert "cannot call themselves" in result["results"][0]["error"]


@pytest.mark.asyncio
async def test_pipeline_unresolved_placeholder_reported_cleanly():
    steps = [{"tool": "get_license_feature_status", "args": {"feature_name": "${nope.field}"}}]
    result = await run_tool_pipeline(steps)
    assert result["succeeded_count"] == 0
    assert "unresolved placeholder" in result["results"][0]["error"]


@pytest.mark.asyncio
async def test_pipeline_rejects_too_many_steps():
    steps = [{"tool": "get_aurora_scope_notice", "args": {}}] * 51
    result = await run_tool_pipeline(steps)
    assert "error" in result
