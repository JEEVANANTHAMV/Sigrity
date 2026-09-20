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

from typing import Optional

from sigrity_mcp.domains.cad.capture_tools import (
    capture_annotate,
    capture_create_netlist,
    capture_place_part,
    capture_place_pin,
    capture_place_wire,
    capture_run_session,
    capture_save,
    start_capture_session,
)
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def generate_schematic_from_spec(
    project_file: str,
    parts: list[dict],
    wires: Optional[list[dict]] = None,
    pins: Optional[list[dict]] = None,
    annotate: bool = True,
    create_netlist: bool = True,
) -> dict:
    """Author a complete schematic from a structured circuit spec in one call, then save and run it.

    `project_file`: the OrCAD Capture project (.opj) to open (see start_capture_session).

    `parts`: required, one dict per component to place —
        {"x": float, "y": float, "library_file": str, "part_name": str, "package": str (optional)}
    each mapped 1:1 to capture_place_part.

    `wires` (optional): one dict per wire segment —
        {"x1": float, "y1": float, "x2": float, "y2": float}
    each mapped 1:1 to capture_place_wire. This is how the spec's net connectivity is
    actually expressed on the page — the caller (or the upstream system that produced
    this spec) is responsible for supplying real, connecting page coordinates; this
    tool does not do any auto-routing/auto-layout of the schematic page itself.

    `pins` (optional): one dict per page pin/mechanical pin —
        {"x": float, "y": float, "pin_name": str, "pin_type": str (default "Passive")}
    each mapped 1:1 to capture_place_pin.

    `annotate=True` (default) queues reference-designator annotation after placement —
    the confirmed way to get real REFDES values without this tool having to (unsafely)
    guess which placed object a SetProperty call would currently apply to.
    `create_netlist=True` (default) queues netlist creation for PCB layout handoff.

    Composes, in order: start_capture_session -> capture_place_part (xN) ->
    capture_place_wire (xN) -> capture_place_pin (xN) -> [capture_annotate] ->
    [capture_create_netlist] -> capture_save -> capture_run_session. Returns
    `{job_id, state, job_dir, command, parts_placed, wires_placed, pins_placed}` — poll
    the job_id with wait_for_job/tail_job_log exactly as capture_run_session itself
    documents, and read this module's docstring's HONEST LIMITATION note before trusting
    a `succeeded` state alone.
    """
    session = await start_capture_session(project_file)
    session_id = session["session_id"]

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
    return {
        **run_result,
        "parts_placed": len(parts),
        "wires_placed": len(wires or []),
        "pins_placed": len(pins or []),
    }
