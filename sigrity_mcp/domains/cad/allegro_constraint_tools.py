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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    expr = f"(axlCNSSetPhysical {_cset_arg(cset)} {_layer_arg(layer)} '{constraint} {_value_arg(value)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "constraint": constraint, "value": value, "cset": cset, "layer": layer}


@mcp.tool
async def allegro_create_ecset(session_id: str, name: str, copy_from: Optional[str] = None) -> dict:
    """Create a new electrical constraint set (ecset) — e.g. for impedance/length-matching rules on a net group.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    expr = f"(axlCNSEcsetCreate {skill_str(name)}" + (f" {skill_str(copy_from)})" if copy_from else ")")
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "name": name, "copy_from": copy_from}


@mcp.tool
async def allegro_get_net_constraint(session_id: str, net_name: str, constraint_name: str) -> dict:
    """Queue a read-only query of an electrical constraint value flattened onto a net (e.g. impedance, propagation delay), within the current Allegro SKILL session.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    expr = f"(axlCnsNetFlattened {skill_str(net_name)} {skill_str(constraint_name)})"
    tcl_sessions.add_line(session_id, _skill_line(expr))
    return {"session_id": session_id, "net_name": net_name, "constraint_name": constraint_name}
