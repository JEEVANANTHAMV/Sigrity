"""Lightweight parsers for common Sigrity output artifacts.

These deliberately stay shallow (metadata + a content preview) rather than doing full
numeric parsing — the MCP tools that expose them are meant to let an LLM caller *find
and skim* results, not replace a real post-processing toolchain.
"""

from __future__ import annotations

from pathlib import Path


def touchstone_summary(path: str | Path) -> dict:
    """Parse the header of a Touchstone file (.s1p/.s2p/.s4p/...) without loading the matrix."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    option_line = None
    port_count = None
    if path.suffix.lower().startswith(".s") and path.suffix.lower().endswith("p"):
        digits = "".join(c for c in path.suffix[2:-1] if c.isdigit())
        port_count = int(digits) if digits else None
    n_data_lines = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        if stripped.startswith("#"):
            option_line = stripped
            continue
        n_data_lines += 1
    return {
        "path": str(path),
        "port_count": port_count,
        "option_line": option_line,
        "data_line_count": n_data_lines,
        "size_bytes": path.stat().st_size,
    }


def text_preview(path: str | Path, max_lines: int = 80) -> dict:
    """Return the first/last few lines of a text report/log file plus its size."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    head = lines[: max_lines // 2]
    tail = lines[-max_lines // 2 :] if len(lines) > max_lines // 2 else []
    return {
        "path": str(path),
        "total_lines": len(lines),
        "head": head,
        "tail": tail if tail and tail != head else [],
        "size_bytes": path.stat().st_size,
    }


def classify_output(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix.startswith(".s") and suffix.endswith("p") and suffix[2:-1].isdigit():
        return "touchstone"
    if suffix in {".log", ".txt", ".rpt"}:
        return "text_report"
    if suffix in {".csv"}:
        return "csv"
    if suffix in {".sp", ".cir", ".spi"}:
        return "spice_netlist"
    if suffix in {".spd"}:
        return "sigrity_design"
    return suffix.lstrip(".") or "unknown"
