import pytest

from sigrity_mcp.domains.aurora.scope_tools import get_aurora_scope_notice, get_in_design_analysis_alternatives


@pytest.mark.asyncio
async def test_scope_notice_is_honest_about_unavailability():
    result = await get_aurora_scope_notice()
    assert result["aurora_available"] is False
    assert "Allegro" in result["reason"]
    assert len(result["confirmed_by"]) >= 1


@pytest.mark.asyncio
async def test_alternatives_cover_core_pi_and_si_checks():
    result = await get_in_design_analysis_alternatives()
    checks = {a["aurora_check"] for a in result["alternatives"]}
    alternatives = " ".join(a["standalone_alternative"] for a in result["alternatives"])
    assert len(result["alternatives"]) >= 3
    assert any("IR-drop" in c or "resistance" in c for c in checks)
    assert "powerdc" in alternatives
    assert "powersi" in alternatives
