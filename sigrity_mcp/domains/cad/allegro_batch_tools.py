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

    Runs `report.exe -v <report_code> [-H] <board_file> [output_file]`. `report_code`
    is Cadence's short code for the report type — common ones: 'sum' (summary drawing
    statistics: layer/component/DRC/drill/connection counts), 'bom' (bill of
    materials), 'drc' (design rules check), 'net' (net list), 'cmp' (component),
    'x-section' (layer stackup cross-section). Confirmed live against a real `.brd`
    sample on this machine (not just documentation) — the full code list, as printed by
    `report.exe -help`, is: asf, bom, cbm, cmp, cpn, dpf, dpg, drc, drc_shorts, ecp,
    eld, ell, eln, elp, elw, fcn, fpn, jcp, mod, net, netloop, pad, psu, psw, pcp, npr,
    slp, slt, spf, sum, spn, uaf, ucn, upc, vfb, waived_drc, vialist_net,
    vialist_netlayer, x-section. `html=True` requests HTML output where that report
    type supports it (not all do — report.exe's own error tells you if the one you
    picked doesn't). If `output_file` is omitted, report.exe picks its own default
    name next to the input board.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then read
    the report via read_job_output_file once it succeeds.
    """
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

    Runs `dbdoctor.exe [-check_only|-drc|-shapes] [-no_backup] [-outfile <output_file>]
    [-purge_vialist] [-purge_padstacks] [-regenerate_xnets] <board_file>`. Confirmed
    live against a real `.brd` sample on this machine: a check-only pass ran a real
    orphan-record check end-to-end and reported its result.
    `check_only=True` (default) only checks, never modifies, the database — the safest
    mode. Set it False and `run_drc=True` to also check-and-repair plus update all DRCs,
    or `check_shapes=True` for additional shape checks (repairs, not just checks).
    Without `no_backup` or `output_file`, dbdoctor copies the input to `<board_file>.orig`
    before making any change.
    IMPORTANT: dbdoctor exits non-zero (1) even for a clean check-only pass that finds
    only warnings, not just on hard failure — read the job's log/output rather than
    treating any non-zero returncode as a failure by itself.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
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
