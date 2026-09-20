"""Manufacturing package analysis — structural completeness/well-formedness checks over
Allegro's real Gerber/IPC-2581/IPC-356 export outputs.

FORJINN's discovery form asks for Gerber/manufacturing-package "analysis" and DFM/DFA
readiness assessment. This suite already has real, confirmed-live *generators* for
Gerber (`allegro_create_film` + `run_allegro_generate_artwork`), IPC-2581
(`run_ipc2581_export`), and IPC-356 (`run_ipc356_export`) — see
`allegro_manufacturing_tools.py`. What was missing was anything that looks back at what
those generators actually produced and checks it's real, complete, and internally
consistent before handing it to a fab house — that's this module.

Deliberately scoped to what can be honestly verified from file content alone, not a
fabricated electrical/manufacturability analysis this suite has no tool to actually
perform (`dfa_dlg.exe` is confirmed GUI-only with zero batch surface — see
`domains/cad/__init__.py`'s docstring): this checks that each expected file exists,
is non-empty, and matches its format's own real structural signature, plus a light
refdes-count cross-check against a BOM report where available. That is a genuine,
useful first DFM gate (a fab house's own intake process starts the same way — "is this
package even complete and well-formed") even though it is not a design-rule/clearance
check.

Every structural signature checked below was read from a real file this suite itself
produced on this machine, not guessed:
- Gerber `.art` (RS274X): starts with a `G04 ================== begin FILE
  IDENTIFICATION RECORD ==================*` banner, and always contains a
  `G04 File Format:  Gerber RS274X*` line and a `G04 Layer:  <name>*` line (confirmed
  from a real `TOP.art`/`BOTTOM.art` pair produced by `run_allegro_generate_artwork`).
- IPC-2581: a real XML document whose root element is `<IPC-2581 revision="..."
  xmlns="http://webstds.ipc.org/2581" ...>` (confirmed from a real `board_ipc2581.xml`
  produced by `run_ipc2581_export`).
- IPC-356: a real fixed-width/space-delimited text format whose header block starts
  with `P  JOB`/`P  FORM`/... parameter records and a `C  IPC-D-356 Output File from
  Allegro` comment line (confirmed from a real `out.ipc356` produced by
  `run_ipc356_export`).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from sigrity_mcp.domains.cad.schematic_checklist_tools import parse_bom_report
from sigrity_mcp.mcp_app import mcp

_GERBER_FORMAT_RE = re.compile(r"File Format:\s*(Gerber\s+[^\s*]+)", re.IGNORECASE)
_GERBER_LAYER_RE = re.compile(r"^\s*G04\s+Layer:\s*([^\s*]+)", re.IGNORECASE | re.MULTILINE)
_IPC2581_ROOT_LOCALNAME = "IPC-2581"
_IPC356_MARKER = "IPC-D-356 Output File from Allegro"
_REFDES_RE = re.compile(r'refDesRef="([^"]+)"|RefDes="([^"]+)"', re.IGNORECASE)


def _check_gerber_file(path_str: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        return {"file": path_str, "exists": False, "well_formed": False, "issue": "file does not exist"}
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return {"file": path_str, "exists": True, "well_formed": False, "issue": "file is empty"}
    format_match = _GERBER_FORMAT_RE.search(text)
    layer_match = _GERBER_LAYER_RE.search(text)
    well_formed = format_match is not None and "RS274X" in format_match.group(1).upper()
    result = {
        "file": path_str,
        "exists": True,
        "size_bytes": path.stat().st_size,
        "well_formed": well_formed,
        "format": format_match.group(1) if format_match else None,
        "layer": layer_match.group(1) if layer_match else None,
    }
    if not well_formed:
        result["issue"] = "missing the expected 'File Format: Gerber RS274X' header line — not a real RS274X artwork file"
    return result


def _check_ipc2581_file(path_str: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        return {"file": path_str, "exists": False, "well_formed": False, "issue": "file does not exist"}
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return {"file": path_str, "exists": True, "well_formed": False, "issue": "file is empty"}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return {"file": path_str, "exists": True, "well_formed": False, "issue": f"not well-formed XML: {exc}"}
    local_name = root.tag.rsplit("}", 1)[-1]
    well_formed = local_name == _IPC2581_ROOT_LOCALNAME
    refdes_matches = _REFDES_RE.findall(text)
    refdes_count = sum(1 for pair in refdes_matches if pair[0] or pair[1])
    result = {
        "file": path_str,
        "exists": True,
        "size_bytes": path.stat().st_size,
        "well_formed": well_formed,
        "root_tag": root.tag,
        "refdes_count_in_file": refdes_count,
    }
    if not well_formed:
        result["issue"] = f"root element is '{root.tag}', not the expected IPC-2581 root"
    elif refdes_count == 0:
        result["note"] = (
            "Well-formed IPC-2581 XML but no per-component RefDes records were found in it — this can be "
            "genuinely normal for a minimal/default export (component-level detail depends on the export "
            "flags used with run_ipc2581_export), not necessarily an error."
        )
    return result


def _check_ipc356_file(path_str: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        return {"file": path_str, "exists": False, "well_formed": False, "issue": "file does not exist"}
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return {"file": path_str, "exists": True, "well_formed": False, "issue": "file is empty"}
    well_formed = _IPC356_MARKER in text and text.lstrip().startswith("P")
    result = {"file": path_str, "exists": True, "size_bytes": path.stat().st_size, "well_formed": well_formed}
    if not well_formed:
        result["issue"] = f"missing the expected '{_IPC356_MARKER}' header marker or 'P ...' parameter records"
    return result


@mcp.tool
async def analyze_manufacturing_package(
    gerber_files: Optional[list[str]] = None,
    ipc2581_file: Optional[str] = None,
    ipc356_file: Optional[str] = None,
    bom_report_file: Optional[str] = None,
) -> dict:
    """Check a generated manufacturing package (Gerber/.art, IPC-2581, IPC-356, BOM) for completeness and real-format well-formedness.

    All arguments are optional file paths to whatever this suite's own
    `run_allegro_generate_artwork` / `run_ipc2581_export` / `run_ipc356_export` /
    `run_allegro_report(..., "bom")` calls produced — pass whichever ones you actually
    generated; nothing is required, but an empty call returns an empty (useless)
    report, so pass at least one.

    Each file is checked for: existing, being non-empty, and matching that format's own
    real structural signature (see this module's docstring for exactly what's checked
    per format — a Gerber RS274X header line, an IPC-2581 root element, an IPC-356
    header marker). If `bom_report_file` is also given, its REFDES count is reported
    alongside any RefDes records found in `ipc2581_file`, as a light completeness
    cross-check (not a guaranteed match — see the IPC-2581 check's own `note` field for
    when a minimal export genuinely has none).

    This is a structural/completeness gate, NOT an electrical or clearance DFM check —
    no batch/SKILL automation surface exists on this installation for that (Allegro's
    `dfa_dlg.exe` is confirmed GUI-only). Use `run_allegro_batch_drc`/
    `run_allegro_checkplus` for the electrical-rule side of manufacturability.

    Returns `{gerber: [...], ipc2581: {...} | None, ipc356: {...} | None,
    bom_refdes_count: int | None, overall: {all_well_formed: bool, issues: [...]}}`.
    """
    gerber_results = [_check_gerber_file(f) for f in (gerber_files or [])]
    ipc2581_result = _check_ipc2581_file(ipc2581_file) if ipc2581_file else None
    ipc356_result = _check_ipc356_file(ipc356_file) if ipc356_file else None

    bom_refdes_count: Optional[int] = None
    if bom_report_file:
        bom_path = Path(bom_report_file)
        if bom_path.is_file():
            rows = parse_bom_report(bom_path.read_text(encoding="utf-8", errors="replace"))
            bom_refdes_count = len(rows)
        else:
            bom_refdes_count = None

    issues: list[str] = []
    for g in gerber_results:
        if not g.get("well_formed"):
            issues.append(f"Gerber file '{g['file']}': {g.get('issue', 'not well-formed')}")
    if ipc2581_result and not ipc2581_result.get("well_formed"):
        issues.append(f"IPC-2581 file '{ipc2581_result['file']}': {ipc2581_result.get('issue', 'not well-formed')}")
    if ipc356_result and not ipc356_result.get("well_formed"):
        issues.append(f"IPC-356 file '{ipc356_result['file']}': {ipc356_result.get('issue', 'not well-formed')}")

    return {
        "gerber": gerber_results,
        "ipc2581": ipc2581_result,
        "ipc356": ipc356_result,
        "bom_refdes_count": bom_refdes_count,
        "overall": {"all_well_formed": len(issues) == 0, "issues": issues},
    }
