"""Lightweight parsers for common Sigrity output artifacts.

These deliberately stay shallow (metadata + a content preview) rather than doing full
numeric parsing — the MCP tools that expose them are meant to let an LLM caller *find
and skim* results, not replace a real post-processing toolchain.
"""

from __future__ import annotations

from pathlib import Path


_TOUCHSTONE_HARD_CAP_BYTES = 500 * 1024 * 1024


def touchstone_summary(path: str | Path) -> dict:
    """Parse the header of a Touchstone file (.s1p/.s2p/.s4p/...) without loading the matrix."""
    path = Path(path)
    size = path.stat().st_size
    if size > _TOUCHSTONE_HARD_CAP_BYTES:
        # Defense in depth against the same runaway-output class of bug documented in
        # core.config's `max_log_bytes` — a genuine Touchstone export has never
        # approached this size in any real run on this machine; something is wrong.
        return {"path": str(path), "size_bytes": size, "note": "file too large to parse safely — inspect manually"}
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


_PREVIEW_HEAD_BYTES = 512 * 1024
_PREVIEW_TAIL_BYTES = 512 * 1024


def text_preview(path: str | Path, max_lines: int = 80) -> dict:
    """Return the first/last few lines of a text report/log file plus its size.

    Reads only bounded head/tail byte windows, never the whole file — a real incident
    on this machine (see core.config's `max_log_bytes` docstring) saw a job's output
    file grow to ~150GB; `path.read_text()` on that would exhaust memory regardless of
    how small `max_lines` was, since the whole file has to be loaded before it can be
    split into lines and trimmed.
    """
    path = Path(path)
    size = path.stat().st_size
    half = max(1, max_lines // 2)

    with open(path, "rb") as f:
        head_bytes = f.read(_PREVIEW_HEAD_BYTES)
        whole_file = size <= _PREVIEW_HEAD_BYTES
        if not whole_file:
            f.seek(max(0, size - _PREVIEW_TAIL_BYTES))
            tail_bytes = f.read()

    head_all_lines = head_bytes.decode("utf-8", errors="replace").splitlines()
    head_lines = head_all_lines[:half]
    # Whole small file: derive both head and tail from the one read. Large file: the
    # tail comes from the separate end-of-file window read above instead.
    tail_lines = head_all_lines[-half:] if whole_file else tail_bytes.decode("utf-8", errors="replace").splitlines()[-half:]
    # total_lines is only exact for files small enough to have been read whole above;
    # otherwise it's unknown rather than a misleadingly-precise-looking guess.
    total_lines = len(head_all_lines) if whole_file else None
    return {
        "path": str(path),
        "total_lines": total_lines,
        "total_lines_note": None if total_lines is not None else "file too large to count exactly; head/tail only",
        "head": head_lines,
        "tail": tail_lines if tail_lines and tail_lines != head_lines else [],
        "size_bytes": size,
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
