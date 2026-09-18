"""Minimal, safe SKILL string/path quoting — the SKILL-language counterpart to
`core.tclscript`, for automating Allegro PCB Editor (a different language and engine
from Sigrity's/Capture's Tcl; see `core.tclsession`'s module docstring).

SKILL string literals are C-like: double-quoted, with `\\` and `"` backslash-escaped and
no literal newline allowed inside one (`\n` must be the two-character escape sequence,
not an actual line break — an unescaped newline would end the "line" our SKILL command-
replay `.scr` file treats as one step, letting the remainder of a malicious value execute
as its own, unintended command). We never string-format user input directly into SKILL
source; every value goes through `skill_str`/`skill_path`.
"""

from __future__ import annotations

from pathlib import Path


def skill_str(value: str) -> str:
    """Double-quote a value for safe use as a single SKILL string literal."""
    text = str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def skill_path(path: str | Path) -> str:
    """Double-quote a filesystem path, normalizing backslashes to forward slashes.

    SKILL accepts `/` in paths on Windows and it avoids doubling up backslash escapes on
    top of Windows' own backslash path separators.
    """
    return skill_str(str(path).replace("\\", "/"))


def skill_list(values: list) -> str:
    """Render a SKILL list literal, e.g. `list("a" "b" 1)` — strings quoted, numbers bare."""
    rendered = [skill_str(v) if isinstance(v, str) else str(v) for v in values]
    return "list(" + " ".join(rendered) + ")"
