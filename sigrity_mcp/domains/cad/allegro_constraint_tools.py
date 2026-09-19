"""Allegro Constraint Manager automation — SKILL-scripted, session-based.

CORRECTION to this project's own earlier research: an initial pass concluded "no
axl*Constraint* SKILL API found" after grepping for that literal substring. That grep
was too narrow — the real naming convention is `axlCNS*`/`axlCns*` (Constraint
Namespace), not `axl*Constraint*`. A full listing of
`share/pcb/examples/skill/DOC/FUNCS/axlCNS*.txt` on this machine shows roughly 60 real,
individually documented functions covering spacing rules, physical rules (min line
width, allowed vias, etc.), electrical constraint sets (ecsets — drive/load, impedance,
propagation delay), design-value get/set, and cset/domain management. This module wraps
the highest-value subset for a PCB-generation flow; extend it with more `axlCNS*`
functions from that same doc directory as needed — the full list is confirmed real, not
speculative.

Every tool here appends one `skill (axlCNS...)` line to an already-open `allegro_tools`
session (`start_allegro_session`) — compose alongside `allegro_create_net`/
`allegro_create_component`/etc. in the same session, then finish with
`allegro_run_session`. These calls are `built_untested`: confirmed real via their own
doc pages (exact signatures below), but not yet independently exercised live against a
real board on this machine — treat flag/value spellings as a faithful transcription,
not guaranteed correct, the same caution this project applies to every other
newly-added, doc-sourced tool.
"""

from __future__ import annotations

from typing import Optional, Union

from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.mcp_app import mcp


def _skill_line(expr: str) -> str:
    return f"skill {expr}"


def _cset_arg(cset: Optional[str]) -> str:
    if cset is None:
        return "nil"
    if cset == "":
        return '""'
    return skill_str(cset)


def _layer_arg(layer: Optional[str]) -> str:
    return "nil" if layer is None else skill_str(layer)


def _value_arg(value: Union[str, float, int, bool]) -> str:
    if isinstance(value, bool):
        return "t" if value else "nil"
    if isinstance(value, (int, float)):
        return str(value)
    return skill_str(value)


@mcp.tool
async def allegro_set_spacing_constraint(
    session_id: str,
    constraint: str,
    value: Union[str, float, int, bool],
    cset: Optional[str] = None,
    layer: Optional[str] = None,
) -> dict:
    """Set a Constraint Manager spacing rule (e.g. line-to-line, line-to-shape clearance), within the current Allegro SKILL session.

    Appends `skill (axlCNSSetSpacing {cset} {layer} '{constraint} {value})`, per the
    confirmed real `axlCNSSetSpacing` function
    (`share/pcb/examples/skill/DOC/FUNCS/axlCNSSetSpacing.txt`). `cset` is the
    constraint-set name — pass `None` (default) to apply to all csets, `""` for the
    DEFAULT cset, or a specific cset name. `layer` similarly defaults to all ETCH
    layers when omitted. `constraint` is a Constraint Manager spacing symbol (e.g.
    `"line_line"`, `"line_shape"`) — the full permissible list is only obtainable live
    from a real session via `axlCNSGetPhysical(nil nil nil)` per the doc; common values
    are documented in Allegro's own Constraint Manager reference. `value` accepts a
    number, a unit string, or a boolean depending on the constraint's data type.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    expr = f"(axlCNSSetSpacing {_cset_arg(cset)} {_layer_arg(layer)} '{constraint} {_value_arg(value)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "constraint": constraint, "value": value, "cset": cset, "layer": layer}


@mcp.tool
async def allegro_set_physical_constraint(
    session_id: str,
    constraint: str,
    value: Union[str, float, int, bool],
    cset: Optional[str] = None,
    layer: Optional[str] = None,
) -> dict:
    """Set a Constraint Manager physical rule (e.g. minimum line width, allowed via types), within the current Allegro SKILL session.

    Appends `skill (axlCNSSetPhysical {cset} {layer} '{constraint} {value})`, per the
    confirmed real `axlCNSSetPhysical` function. Same `cset`/`layer` semantics as
    allegro_set_spacing_constraint. Common `constraint` symbols per the doc's own
    examples include `"width_min"` (minimum trace width) and `"allow_etch"`/
    `"allow_ts"` (booleans/symbols controlling what's allowed on a layer) — the full
    permissible list is only obtainable live via `axlCNSGetPhysical(nil nil nil)`.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    expr = f"(axlCNSSetPhysical {_cset_arg(cset)} {_layer_arg(layer)} '{constraint} {_value_arg(value)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "constraint": constraint, "value": value, "cset": cset, "layer": layer}


@mcp.tool
async def allegro_create_ecset(session_id: str, name: str, copy_from: Optional[str] = None) -> dict:
    """Create a new electrical constraint set (ecset) — e.g. for impedance/length-matching rules on a net group.

    Appends `skill (axlCNSEcsetCreate {name} [{copy_from}])`, per the confirmed real
    `axlCNSEcsetCreate` function. `name` is upper-cased and must pass Allegro's legal
    character set; fails if an ecset with that name already exists. If `copy_from` is
    given, the new ecset starts as a copy of that existing one instead of empty.
    Populate the new ecset's actual rule values with axlCNSEcsetValueSet-family calls
    (not yet wrapped here — extend this module following the same pattern if needed).
    This only queues the step — call allegro_run_session to actually execute it.
    """
    expr = f"(axlCNSEcsetCreate {skill_str(name)}" + (f" {skill_str(copy_from)})" if copy_from else ")")
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "name": name, "copy_from": copy_from}


@mcp.tool
async def allegro_get_net_constraint(session_id: str, net_name: str, constraint_name: str) -> dict:
    """Queue a read-only query of an electrical constraint value flattened onto a net (e.g. impedance, propagation delay), within the current Allegro SKILL session.

    Appends `skill (axlCnsNetFlattened {net_name} {constraint_name})`, per the confirmed
    real `axlCnsNetFlattened` function — this is Allegro's own "traditional net view"
    rollup of pinpair-level electrical constraints (the same view shown in Allegro's
    "Properties attached to net" panel), useful for verifying a constraint actually
    landed on a net after setting it up, or before running Sigrity extraction.
    `constraint_name` is the constraint's property name (e.g. `"IMPEDANCE_RULE"`,
    `"PROPAGATION_DELAY"`) per the doc's own examples.
    Like every other `skill` query line in this suite, the result is only visible in the
    session's own output stream once run — this suite has no mechanism to pipe a SKILL
    return value back into the MCP response automatically; inspect the job's log via
    tail_job_log/read_job_output_file after allegro_run_session, following the same
    established pattern as allegro_tools.py's `axlCurrentDesign` query example.
    This only queues the step — call allegro_run_session to actually execute it.
    """
    expr = f"(axlCnsNetFlattened {skill_str(net_name)} {skill_str(constraint_name)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "net_name": net_name, "constraint_name": constraint_name}
