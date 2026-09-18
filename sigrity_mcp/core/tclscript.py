"""Minimal, safe Tcl script builder.

Sigrity tools are automated by writing a .tcl macro file and running the tool against it
in console/batch mode. We never string-format user input directly into Tcl source; every
value goes through `tcl_str`/`tcl_list`, which brace-quote it so embedded spaces,
backslashes, or `$`/`[` characters can't break out of the literal or inject commands.
"""

from __future__ import annotations

from pathlib import Path


def tcl_str(value: str) -> str:
    """Brace-quote a value for safe use as a single Tcl word/string literal."""
    text = str(value)
    if "}" in text or "{" in text:
        # Braces can't be escaped inside brace-quoting; fall back to backslash quoting.
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("[", "\\[")
        return f'"{escaped}"'
    return "{" + text + "}"


def tcl_list(values: list) -> str:
    return "[list " + " ".join(tcl_str(v) for v in values) + "]"


def tcl_path(path: str | Path) -> str:
    """Brace-quote a filesystem path, normalizing backslashes to forward slashes.

    Tcl treats `/` correctly on Windows and it avoids any backslash-escaping ambiguity.
    """
    return tcl_str(str(path).replace("\\", "/"))


class TclScript:
    """Accumulates lines of Tcl source, then writes them to a file."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def comment(self, text: str) -> "TclScript":
        for line in text.splitlines():
            self._lines.append(f"# {line}")
        return self

    def raw(self, line: str) -> "TclScript":
        self._lines.append(line)
        return self

    def call(self, command: str, *args: str) -> "TclScript":
        """Append `command arg1 arg2 ...` where args are already Tcl-quoted words."""
        self._lines.append(" ".join([command, *args]))
        return self

    def render(self) -> str:
        return "\n".join(self._lines) + "\n"

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")
        return path
