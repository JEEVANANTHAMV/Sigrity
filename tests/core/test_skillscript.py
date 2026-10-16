from sigrity_mcp.core.skillscript import skill_list, skill_path, skill_str


def test_skill_str_simple():
    assert skill_str("hello") == '"hello"'


def test_skill_str_with_spaces():
    assert skill_str("hello world") == '"hello world"'


def test_skill_str_escapes_backslash_and_quote():
    result = skill_str('he said "hi"')
    assert result == '"he said \\"hi\\""'


def test_skill_str_escapes_newline_and_carriage_return():
    result = skill_str("line1\nline2\r\n")
    assert "\n" not in result
    assert "\r" not in result
    assert "\\n" in result
    assert "\\r" in result


def test_skill_path_normalizes_backslashes():
    assert skill_path(r"C:\Cadence\design.brd") == '"C:/Cadence/design.brd"'


def test_skill_list_quotes_strings_but_not_numbers():
    assert skill_list(["a", "b c", 1, 2.5]) == 'list("a" "b c" 1 2.5)'


def test_skill_str_no_injection_via_embedded_newline():
    # An unescaped literal newline inside a SKILL string would let the remainder of a
    # malicious value execute as its own separate command-replay line — must never happen.
    hostile = 'safe"\n(exec "calc.exe")\n"'
    quoted = skill_str(hostile)
    assert "\n" not in quoted
    assert quoted.startswith('"') and quoted.endswith('"')


def test_skill_str_no_injection_via_unescaped_quote():
    hostile = '") (exec "calc.exe") ("'
    quoted = skill_str(hostile)
    # every embedded quote must be backslash-escaped, not a bare terminator
    inner = quoted[1:-1]
    assert '\\"' in inner
    # no unescaped " should remain in the inner content
    import re

    assert not re.search(r'(?<!\\)"', inner)
