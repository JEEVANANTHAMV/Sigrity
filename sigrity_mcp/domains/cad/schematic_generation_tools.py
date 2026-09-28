"""Requirement-to-schematic generation — one call from a structured circuit spec to a real, saved OrCAD Capture schematic.

FORJINN's top-priority workflow (discovery form §5.1, item 1) is turning a hardware
requirement (HRS/PRD + datasheets/app notes/errata) into a draft schematic. The
document-intelligence side of that — reading the HRS/PRD/datasheets and deciding what
components, nets, and power tree the design needs — is explicitly out of scope here
(the client already has a document-intelligence system for that outside this MCP
suite). What belongs in *this* codebase is the other half: given that already-decided
circuit intent as a structured spec, actually author it in the real CAD tool.

Before this module, that meant a caller composing 6-9 individual `capture_*` tool calls
by hand (start_capture_session -> capture_place_part x N -> capture_place_wire x N ->
... -> capture_save -> capture_run_session), each needing the same session_id threaded
through correctly. `generate_schematic_from_spec` collapses that into one call: pass a
part list, wire list, and pin list, get back one job_id for the whole authored-and-saved
schematic.

HONEST LIMITATION, read before relying on this end-to-end: this composes
`capture_tools.py`'s existing primitives, and that module's own docstring documents
OrCAD Capture's batch invocation as `known_blocked` — genuinely non-deterministic on
this machine even after the stale-lock root-cause fix (one clean 3.2s run, then the next
attempt hanging the full timeout with an empty log, repeatedly, per
`core/tool_status.py`'s `capture` note). Composing more capture_* calls into one script
does not fix that underlying reliability issue — it only removes the *sequencing*
burden from the caller. Treat a `succeeded` result from this tool the same way
`capture_run_session` itself warns to: check the job's actual log content (via
`tail_job_log`/`list_job_files`), not just the returncode, before trusting that the
parts/wires described below actually landed in the saved design. Per-part property
assignment (e.g. setting a specific REFDES on a specific placed part) is deliberately
NOT attempted here: Capture's own `SetProperty` Tcl command operates on "the currently
selected object(s)", and there is no confirmed way to select a specific just-placed part
by name from a batch script — attempting to fake that would silently set the wrong
part's property. Use `capture_annotate` (auto-reference-designation, already queued
below) instead of hand-assigned REFDES for this pass.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sigrity_mcp.domains.cad.capture_tools import (
    auto_dismiss_recovery_dialog_if_stuck,
    capture_annotate,
    capture_create_netlist,
    capture_place_part,
    capture_place_pin,
    capture_place_wire,
    capture_run_session,
    capture_save,
    capture_select_page,
    start_capture_session,
)
from sigrity_mcp.mcp_app import mcp

# Matches `(File "<path>"` entries in an .opj project file's project model (S-expr).
_PROJECT_FILE_ENTRY = re.compile(r'\(File\s+"([^"]+)"')
# A file entry that is the actual schematic design, not a sub-document like a library.
_DESIGN_TYPES = {"Schematic Design", "OrCAD Capture Schematic Design"}


def _find_project_schematic_design(project_file: str) -> Optional[tuple[str, str]]:
    """Return (design, design_stem) for the project's root schematic design, if found.

    Reads the .opj's project model (an S-expr) and finds the design entry whose Type is
    a schematic design. Returns the design's project-model path (e.g. `./fault-
    detector.dsn`, kept exactly as written — relative forms resolve against the
    project directory the same way Capture's own recorded-replay samples do) and its
    stem with any extension (used to build the root schematic folder name, which
    OrCAD derives from the design name — e.g. `Fault-Detector` for
    `.\fault-detector.dsn`, per this project's own shipped sample: design
    `fault-detector.dsn` / folder `Detector-Dsn`). None when no such entry exists.
    """
    try:
        text = Path(project_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for m in _PROJECT_FILE_ENTRY.finditer(text):
        entry = m.group(1)
        # Look at the 400 chars after the entry for a (Type "...") belonging to this file.
        window = text[m.end() : m.end() + 400]
        t = re.search(r'\(Type\s+"([^"]+)"', window, re.IGNORECASE)
        if t and t.group(1).strip() in _DESIGN_TYPES:
            stem = entry
            for ext in (".dsn", ".Dsn", ".DSN", ".olb", ".opj"):
                if stem.lower().endswith(ext.lower()):
                    stem = stem[: -len(ext)]
                    break
            # Strip a leading relative path (./ or folder\).
            stem = re.sub(r"^[\./\\]+", "", stem)
            return entry, stem
    return None


@mcp.tool
async def generate_schematic_from_spec(
    project_file: str,
    parts: list[dict],
    wires: Optional[list[dict]] = None,
    pins: Optional[list[dict]] = None,
    design: Optional[str] = None,
    schematic_folder: Optional[str] = None,
    page: Optional[str] = None,
    annotate: bool = True,
    create_netlist: bool = True,
) -> dict:
    """Author a complete schematic from a structured circuit spec in one call, then save and run it.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    given = [design, schematic_folder, page]
    if any(given) and not all(given):
        return {
            "error": "design, schematic_folder, and page must all be given together (or all omitted to auto-derive from the project file)."
        }
    if all(given):
        design_resolved, folder_resolved, page_resolved = design, schematic_folder, page
    else:
        resolved = _find_project_schematic_design(project_file)
        if resolved is None:
            # Best-effort fallback when the .opj can't be read or has no schematic
            # design entry: use the project's own stem as both the design path and the
            # root schematic folder name, PAGE_1 as the first page. The run proceeds,
            # and the returned `page` field names exactly what was targeted, so a wrong
            # address is visible in the result rather than silent.
            stem = Path(project_file).stem or "design"
            design_resolved = f"./{stem}.dsn"
            folder_resolved = stem
        else:
            design_resolved, folder_resolved = resolved
        page_resolved = "PAGE_1"

    session = await start_capture_session(project_file)
    session_id = session["session_id"]
    await capture_select_page(
        session_id=session_id,
        design=design_resolved,
        schematic_folder=folder_resolved,
        page=page_resolved,
    )

    for part in parts:
        await capture_place_part(
            session_id=session_id,
            x=part["x"],
            y=part["y"],
            library_file=part["library_file"],
            part_name=part["part_name"],
            package=part.get("package", ""),
        )

    for wire in wires or []:
        await capture_place_wire(session_id=session_id, x1=wire["x1"], y1=wire["y1"], x2=wire["x2"], y2=wire["y2"])

    for pin in pins or []:
        await capture_place_pin(
            session_id=session_id,
            x=pin["x"],
            y=pin["y"],
            pin_name=pin["pin_name"],
            pin_type=pin.get("pin_type", "Passive"),
        )

    if annotate:
        await capture_annotate(session_id)
    if create_netlist:
        await capture_create_netlist(session_id)
    await capture_save(session_id)

    run_result = await capture_run_session(session_id)
    stuck_note = await auto_dismiss_recovery_dialog_if_stuck(run_result["job_id"])
    if stuck_note is not None:
        run_result = {**run_result, "stuck_check_note": stuck_note}
    return {
        **run_result,
        "parts_placed": len(parts),
        "wires_placed": len(wires or []),
        "pins_placed": len(pins or []),
        "page": f"{design_resolved} -> {folder_resolved}/{page_resolved}",
    }
