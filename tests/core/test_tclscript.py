from sigrity_mcp.core.tclscript import TclScript, tcl_list, tcl_path, tcl_str


def test_tcl_str_simple():
    assert tcl_str("hello") == "{hello}"


def test_tcl_str_with_spaces():
    assert tcl_str("hello world") == "{hello world}"


def test_tcl_str_with_braces_falls_back_to_quotes():
    # Unbalanced/embedded braces can't be brace-quoted safely, so we fall back to "..."
    # quoting, where a literal { or } is legal Tcl and needs no escaping.
    result = tcl_str("has {brace}")
    assert result == '"has {brace}"'


def test_tcl_str_escapes_dollar_and_bracket():
    result = tcl_str('a{b}$c[d]')
    assert result.startswith('"')
    assert "\\$" in result
    assert "\\[" in result


def test_tcl_path_normalizes_backslashes():
    assert tcl_path(r"C:\Cadence\design.spd") == "{C:/Cadence/design.spd}"


def test_tcl_list():
    assert tcl_list(["a", "b c"]) == "[list {a} {b c}]"


def test_tclscript_render_and_write(tmp_path):
    script = TclScript()
    script.comment("test script").call("puts", tcl_str("hello"))
    text = script.render()
    assert "# test script" in text
    assert "puts {hello}" in text

    out = script.write(tmp_path / "sub" / "macro.tcl")
    assert out.exists()
    assert out.read_text(encoding="utf-8") == text


def test_tcl_str_no_injection_via_command_substitution():
    hostile = "]; exec calc.exe; #"
    quoted = tcl_str(hostile)
    # Must be brace- or quote-wrapped as a single literal, never bare.
    assert quoted[0] in "{\""
    assert quoted != hostile
