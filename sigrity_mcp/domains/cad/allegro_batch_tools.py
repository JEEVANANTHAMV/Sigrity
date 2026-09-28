"""Allegro standalone batch/report executables — CLI-only, no SKILL session needed.

Cadence's own docs describe these as sub-programs of a "central batch utility"
multiplexer, `allegro_batch.exe <program> <args>`. That multiplexer's own `-help` and
`<program> -help` output is genuine and correct, but actually dispatching a sub-program
through it is unreliable: routing `dbdoctor` through it failed outright
("ERROR: Cannot find program \"dbdoctor\"", exit 2) on this machine, while calling the
identical standalone `dbdoctor.exe` directly succeeded. So these tools call each
standalone exe directly (`report.exe`, `dbdoctor.exe`) instead of going through the
multiplexer — confirmed working end-to-end against a real sample board file, not just
from documentation.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp

# Full code list as printed by `report.exe -help` (confirmed live on this machine):
# asf, bom, cbm, cmp, cpn, dpf, dpg, drc, drc_shorts, ecp, eld, ell, eln, elp, elw, fcn,
# fpn, jcp, mod, net, netloop, pad, psu, psw, pcp, npr, slp, slt, spf, sum, spn, uaf,
# ucn, upc, vfb, waived_drc, vialist_net, vialist_netlayer, x-section.
_REPORT_CODES = (
    "asf", "bom", "cbm", "cmp", "cpn", "dpf", "dpg", "drc", "drc_shorts", "ecp",
    "eld", "ell", "eln", "elp", "elw", "fcn", "fpn", "jcp", "mod", "net", "netloop",
    "pad", "psu", "psw", "pcp", "npr", "slp", "slt", "spf", "sum", "spn", "uaf",
    "ucn", "upc", "vfb", "waived_drc", "vialist_net", "vialist_netlayer", "x-section",
)


@mcp.tool
async def run_allegro_report(
    board_file: str,
    report_code: str,
    output_file: Optional[str] = None,
    html: bool = False,
) -> dict:
    """Generate a legacy Allegro design report (BOM, DRC, net list, summary, cross-section, ...) as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-v", report_code]
    if html:
        args.append("-H")
    args.append(board_file)
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_report", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_dbdoctor(
    board_file: str,
    check_only: bool = True,
    run_drc: bool = False,
    check_shapes: bool = False,
    no_backup: bool = False,
    output_file: Optional[str] = None,
    purge_vialist: bool = False,
    purge_padstacks: bool = False,
    regenerate_xnets: bool = False,
) -> dict:
    """Check (and optionally repair) an Allegro board database's integrity, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = []
    if check_only:
        args.append("-check_only")
    elif run_drc:
        args.append("-drc")
    elif check_shapes:
        args.append("-shapes")
    if no_backup:
        args.append("-no_backup")
    if output_file:
        args += ["-outfile", output_file]
    if purge_vialist:
        args.append("-purge_vialist")
    if purge_padstacks:
        args.append("-purge_padstacks")
    if regenerate_xnets:
        args.append("-regenerate_xnets")
    args.append(board_file)

    record = await submit_job(tool="allegro_dbdoctor", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
