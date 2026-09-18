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
    whatever type that lookup returns (dict, number, ...). A placeholder embedded inside
    a larger string (`"job-${job.job_id}-final"`) is stringified in place.
    """
    if isinstance(value, str):
        whole = _WHOLE.match(value)
        if whole:
            return _lookup(context, whole.group(1))
        if "${" in value:
            return _INLINE.sub(lambda m: str(_lookup(context, m.group(1))), value)
        return value
    if isinstance(value, dict):
        return {k: resolve(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, context) for v in value]
    return value
