import pytest

from sigrity_mcp.core.pipeline import PlaceholderError, resolve


def test_whole_string_placeholder_returns_native_type():
    context = {"session": {"session_id": "powersi-abc123", "spd_file": "board.spd"}}
    assert resolve("${session.session_id}", context) == "powersi-abc123"


def test_whole_string_placeholder_can_return_non_string():
    context = {"job": {"returncode": 0, "state": "succeeded"}}
    assert resolve("${job.returncode}", context) == 0


def test_inline_placeholder_stringifies():
    context = {"job": {"job_id": "powersi-abc123"}}
    assert resolve("prefix-${job.job_id}-suffix", context) == "prefix-powersi-abc123-suffix"


def test_dict_and_list_are_recursively_resolved():
    context = {"a": {"x": 1}}
    value = {"one": "${a.x}", "two": ["${a.x}", "literal"]}
    assert resolve(value, context) == {"one": 1, "two": [1, "literal"]}


def test_plain_values_pass_through_unchanged():
    context = {}
    assert resolve("no placeholders here", context) == "no placeholders here"
    assert resolve(42, context) == 42
    assert resolve(None, context) is None


def test_unknown_reference_raises_placeholder_error():
    with pytest.raises(PlaceholderError):
        resolve("${missing.key}", {})


def test_unknown_nested_reference_raises():
    with pytest.raises(PlaceholderError):
        resolve("${session.does_not_exist}", {"session": {"session_id": "x"}})
