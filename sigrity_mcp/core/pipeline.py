"""Placeholder substitution for pipeline step arguments.

A pipeline step's args can reference an earlier step's saved result with
`${name.path.to.value}`, where `name` is whatever `save_as` that earlier step used.
Kept separate from pipeline_tools.py so the substitution logic is unit-testable without
needing a running FastMCP Client.
"""

from __future__ import annotations

import re
from typing import Any

_WHOLE = re.compile(r"^\$\{([\w.]+)\}$")
_INLINE = re.compile(r"\$\{([\w.]+)\}")

# A result a step saved via `save_as` can itself contain a literal `${...}` substring
# (e.g. a tool argument the caller passed through verbatim, or a path containing a
# template-looking token) -- without escaping, a LATER step reading that value whole
# is fine (resolve() returns it as-is), but if a step embeds it INLINE in a new
# template string, resolve()'s inline branch would re-scan and attempt to substitute
# that embedded `${...}` against a context it was never meant to reference. freeze()
# neutralizes `${` in every string a result contains at store time; unfreeze() restores
# it verbatim at the one point a whole-placeholder lookup returns it to the caller.
_FREEZE_TOKEN = "\x00PIPELINE_DOLLAR_BRACE\x00"


def freeze(value: Any) -> Any:
    """Escape `${` in every string within `value` so later substitution passes cannot
    mistake saved-result content for a live placeholder. See module docstring note."""
    if isinstance(value, str):
        return value.replace("${", _FREEZE_TOKEN)
    if isinstance(value, dict):
        return {k: freeze(v) for k, v in value.items()}
    if isinstance(value, list):
        return [freeze(v) for v in value]
    return value


def unfreeze(value: Any) -> Any:
    """Inverse of `freeze` -- restores literal `${` sequences in a value read back out
    of the pipeline context, so the caller/tool sees the original content verbatim."""
    if isinstance(value, str):
        return value.replace(_FREEZE_TOKEN, "${")
    if isinstance(value, dict):
        return {k: unfreeze(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unfreeze(v) for v in value]
    return value


class PlaceholderError(KeyError):
    """Raised when a `${...}` reference can't be resolved against the pipeline context."""


def _lookup(context: dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    value: Any = context
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            raise PlaceholderError(path)
        value = value[part]
    return value


def resolve(value: Any, context: dict[str, Any]) -> Any:
    """Recursively substitute `${...}` placeholders in strings/dicts/lists.

    A value that is *entirely* one placeholder (`"${session.session_id}"`) resolves to
    whatever type that lookup returns (dict, number, ...) -- unfrozen, so any `${`
    content the looked-up value itself contains (see `freeze`) comes back verbatim
    rather than being mistaken for a new placeholder. A placeholder embedded inside a
    larger string (`"job-${job.job_id}-final"`) is stringified in place.
    """
    if isinstance(value, str):
        whole = _WHOLE.match(value)
        if whole:
            return unfreeze(_lookup(context, whole.group(1)))
        if "${" in value:
            return _INLINE.sub(lambda m: str(unfreeze(_lookup(context, m.group(1)))), value)
        return value
    if isinstance(value, dict):
        return {k: resolve(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, context) for v in value]
    return value
