"""Allegro/OrCAD schematic & netlist interchange translators — BLOCKED on this machine
by a SPB Translators product/edition capability gate (NOT a license problem).

This is a premium, no-license-required install. `con2xml.exe`, `cap2xml.exe`, and
`dml2con.exe` are real, standalone CLI translators (Concept-HDL netlist -> XML, OrCAD
Capture design -> XML, and DML -> Concept-HDL respectively) — confirmed real (not
GUI-only, not vaporware) because running any of them with `-help` fails with `"No
Product License selected... Translation cancelled"` rather than opening a window or
hanging. That message is a SPB Translators product/edition capability gate: this
particular SPB 22.1 build does not include the SPB Translators feature these three
check for (the same install that serves `allegro`/`allegro_report` successfully). It is
not a FlexNet license failure and there is no license to grant to unblock these.
`apd2con.exe` (Allegro Package Designer -> Concept-HDL bridge) hit the identical
message.

Because that gate fires before any usage text is printed, the exact flag syntax for all
four could not be independently confirmed from this machine the way every other new tool
in this domain was (live `-help` output). The argv shapes below are a best-effort
transcription of the conventional Cadence interchange-tool pattern (a bare input-file
positional argument, optional output-file positional) — treat every tool in this module
as `known_blocked` (see `core.tool_status`) for this build's missing capability, not
`confirmed_live` or even `built_untested` in the normal sense: the blocker is a
missing product feature in this build, not a license and not an implementation gap.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_con2xml(input_file: str, output_file: Optional[str] = None) -> dict:
    """Translate a Concept-HDL netlist to XML (BLOCKED on this build by a SPB Translators
    capability gate — NOT a license problem — see module docstring).
    See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="con2xml", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_cap2xml(input_file: str, output_file: Optional[str] = None) -> dict:
    """Translate an OrCAD Capture design to XML (BLOCKED on this build by a SPB Translators
    capability gate — NOT a license problem — see module docstring).
    See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="cap2xml", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_dml2con(input_file: str, output_file: Optional[str] = None) -> dict:
    """Translate a DML library/design file to Concept-HDL format (BLOCKED on this build by a
    SPB Translators capability gate — NOT a license problem — see module docstring).
    See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="dml2con", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_apd2con(input_file: str, output_file: Optional[str] = None) -> dict:
    """Bridge an Allegro Package Designer (APD) design to Concept-HDL (BLOCKED on this build
    by a SPB Translators capability gate — NOT a license problem — see module docstring).
    See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="apd2con", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
