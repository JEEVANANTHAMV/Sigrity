from sigrity_mcp.core.tool_status import get_tool_status


def test_confirmed_live_tool_has_no_forced_note():
    result = get_tool_status("powersi")
    assert result["status"] == "confirmed_live"
    assert "description" in result


def test_known_blocked_tool_has_explanatory_note():
    result = get_tool_status("capture")
    assert result["status"] == "known_blocked"
    assert result["note"] and "dialog" in result["note"]


def test_allegro_confirmed_live_with_nuance_note():
    result = get_tool_status("allegro")
    assert result["status"] == "confirmed_live"
    assert result["note"] and "axlDBCreateNet" in result["note"]


def test_unlisted_tool_defaults_to_built_untested():
    result = get_tool_status("powerdc_totally_made_up_variant")
    assert result["status"] == "built_untested"
    assert result["note"] is None
