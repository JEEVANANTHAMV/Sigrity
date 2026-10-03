import pytest

from sigrity_mcp.core.pipeline import PlaceholderError, freeze, resolve, unfreeze


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


# --- freeze/unfreeze: double-substitution trap -------------------------------------
#
# Regression coverage for a real documented gap: a saved step result can itself
# contain a literal "${...}" substring (e.g. a tool argument the caller passed
# through verbatim). Without escaping, a later step that reads that value WHOLE
# would get it back correctly (resolve's whole-placeholder branch never re-scans),
# but the pipeline layer stores results via freeze() specifically so that embedding
# one inline in a NEW template string can't be mistaken for a fresh placeholder.


def test_freeze_then_unfreeze_round_trips_literal_dollar_brace():
    original = {"note": "cost is ${total}", "nested": ["${x}", 2]}
    frozen = freeze(original)
    assert "${" not in frozen["note"]
    assert unfreeze(frozen) == original


def test_resolve_returns_frozen_value_verbatim_via_whole_placeholder():
    # Simulates exactly what pipeline_tools.py does: freeze() at store time, then
    # resolve() reading it back whole via a later step's placeholder.
    context = {"step1": freeze({"path": "C:/jobs/${job_id}/out.txt"})}
    result = resolve("${step1.path}", context)
    assert result == "C:/jobs/${job_id}/out.txt"


def test_resolve_does_not_double_substitute_a_frozen_value_embedded_inline():
    # The documented trap: step1's result contains a literal "${nope}" (something
    # that was never meant to be a placeholder). step2 embeds it inline in a new
    # template string. Without freezing, resolve's inline branch would try to look
    # up "nope" in the context and raise PlaceholderError for a value that was never
    # supposed to be resolved again.
    context = {"step1": freeze({"literal": "${nope}"})}
    result = resolve("prefix-${step1.literal}-suffix", context)
    assert result == "prefix-${nope}-suffix"
