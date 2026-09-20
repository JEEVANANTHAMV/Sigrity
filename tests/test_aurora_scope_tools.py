import pytest

from sigrity_mcp.domains.aurora.scope_tools import (
    get_aurora_scope_notice,
    get_in_design_analysis_alternatives,
    run_aurora_workflow,
)


@pytest.mark.asyncio
async def test_scope_notice_returns_options():
    result = await get_aurora_scope_notice()
    assert result["aurora_available"] is True
    assert len(result["automation_modes"]) >= 2
    assert "Crosstalk" in result["workflow_types"]


@pytest.mark.asyncio
async def test_alternatives_cover_core_pi_and_si_checks():
    result = await get_in_design_analysis_alternatives()
    checks = {a["aurora_check"] for a in result["alternatives"]}
    alternatives = " ".join(a["standalone_alternative"] for a in result["alternatives"])
    assert len(result["alternatives"]) >= 3
    assert any("IR-drop" in c or "resistance" in c for c in checks)
    assert "powerdc" in alternatives
    assert "powersi" in alternatives


@pytest.mark.asyncio
async def test_run_aurora_workflow(fake_exe):
    result = await run_aurora_workflow("board.brd", workflow_type="Crosstalk", output_file="checked.brd")
    assert result["command"][1] == "-s"
    assert result["command"][2].endswith("aurora_workflow.scr")
    assert result["command"][3] == "board.brd"
    assert result["workflow_type"] == "Crosstalk"
