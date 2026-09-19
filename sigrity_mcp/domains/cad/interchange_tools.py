"""Allegro/OrCAD schematic & netlist interchange translators — CONFIRMED LICENSE-BLOCKED on this machine.

`con2xml.exe`, `cap2xml.exe`, and `dml2con.exe` are real, standalone CLI translators
(Concept-HDL netlist -> XML, OrCAD Capture design -> XML, and DML -> Concept-HDL
respectively) — confirmed real (not GUI-only, not vaporware) because running any of them
with `-help` fails with `"No Product License selected... Translation cancelled"` rather
than opening a window or hanging: the license gate fires before argument parsing even
gets far enough to print a usage banner, so this machine's FlexNet setup does not
currently have whichever license feature these three check for. `apd2con.exe` (Allegro
Package Designer -> Concept-HDL bridge) hit the identical message.

Because the license check happens before any usage text is printed, the exact flag
syntax for all four could not be independently confirmed from this machine the way every
other new tool in this domain was (live `-help` output). The argv shapes below are a
best-effort transcription of the conventional Cadence interchange-tool pattern (a bare
input-file positional argument, optional output-file positional) — until the license
feature is granted and these are re-run live, treat every tool in this module as
`known_blocked` (see `core.tool_status`), not `confirmed_live` or even `built_untested`
in the normal sense: the blocker is licensing, not an implementation gap.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_con2xml(input_file: str, output_file: Optional[str] = None) -> dict:
    """Translate a Concept-HDL netlist to XML (KNOWN LICENSE-BLOCKED on this machine — see module docstring).

    Runs `con2xml.exe <input_file> [output_file]`. Confirmed real (License-gated,
    "No Product License selected... Translation cancelled") rather than missing/GUI-only.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job — expect a
    license-failure message in the job log until this feature is licensed.
    """
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="con2xml", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_cap2xml(input_file: str, output_file: Optional[str] = None) -> dict:
    """Translate an OrCAD Capture design to XML (KNOWN LICENSE-BLOCKED on this machine — see module docstring).

    Runs `cap2xml.exe <input_file> [output_file]`. Confirmed real (license-gated) rather
    than missing/GUI-only.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job — expect a
    license-failure message in the job log until this feature is licensed.
    """
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="cap2xml", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_dml2con(input_file: str, output_file: Optional[str] = None) -> dict:
    """Translate a DML library/design file to Concept-HDL format (KNOWN LICENSE-BLOCKED on this machine — see module docstring).

    Runs `dml2con.exe <input_file> [output_file]`. Confirmed real (license-gated) rather
    than missing/GUI-only.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job — expect a
    license-failure message in the job log until this feature is licensed.
    """
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="dml2con", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_apd2con(input_file: str, output_file: Optional[str] = None) -> dict:
    """Bridge an Allegro Package Designer (APD) design to Concept-HDL (KNOWN LICENSE-BLOCKED on this machine — see module docstring).

    Runs `apd2con.exe <input_file> [output_file]`. Confirmed real (license-gated,
    identical "No Product License selected" failure as the other three tools in this
    module) rather than missing/GUI-only — `apd.exe` itself (the GUI half of Package
    Designer) is separately unwrapped as GUI-only with no CLI usage text found.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job — expect a
    license-failure message in the job log until this feature is licensed.
    """
    args = [input_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="apd2con", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
