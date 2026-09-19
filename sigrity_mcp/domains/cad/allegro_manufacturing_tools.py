"""Allegro manufacturing-output generators — standalone CLI, no SKILL session needed.

Confirmed live on this machine via each executable's own `-help` usage banner:
- `ipc2581_out.exe [-ufdblRnpstcgkvexyzPDOIMS] [-g <attrFile>] [-o <outFile>] <brd>` —
  IPC-2581 (unified fabrication/assembly/test data) export.
- `ipc356_out.exe [-t/-i/-r/-f/-A/-c/-b/-e] <in.brd> [<out.ipc>]` — IPC-356 bare-board
  netlist/test-point export.
- `step_out.exe [-upsmnadcbz] [-o <output_file>] <brd>` — STEP (3D mechanical) export.
`gbplot.exe` (Gerber plot) is different: its own `-help` and `allegro_batch gbplot -help`
both returned "Help is not available", and `doc/gcoms/gchap.html` documents `gbplot` as
an in-app command that is normally driven by an Artwork Control Form / film-control
setup saved with the board, not by CLI flags — so `run_allegro_gerber_plot` is
best-effort (bare positional board/output args) and should be treated as
`built_untested` until exercised against a real board with real Artwork/film-control
settings already configured.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_ipc2581_export(board_file: str, output_file: Optional[str] = None, attr_file: Optional[str] = None) -> dict:
    """Export an Allegro board to IPC-2581 (unified fab/assembly/test data), as a background job.

    Runs `ipc2581_out.exe [-g <attr_file>] [-o <output_file>] <board_file>` — confirmed
    live via `ipc2581_out.exe -help`'s full usage banner. `attr_file` optionally supplies
    a Cadence attribute-mapping file (the `-g` flag); most of the other documented single-
    letter flags (units, layer selection, etc.) are left at their defaults here — pass
    them via a future extension if you need non-default IPC-2581 output options.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then retrieve
    the generated file via list_job_files/read_job_output_file.
    """
    args = []
    if attr_file:
        args += ["-g", attr_file]
    if output_file:
        args += ["-o", output_file]
    args.append(board_file)
    record = await submit_job(tool="allegro_ipc2581_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_ipc356_export(board_file: str, output_file: Optional[str] = None) -> dict:
    """Export an Allegro board to IPC-356 (bare-board electrical test netlist), as a background job.

    Runs `ipc356_out.exe <board_file> [output_file]` — confirmed live via
    `ipc356_out.exe -help`'s usage banner (`-t/-i/-r/-f/-A/-c/-b/-e` flags exist for
    finer control but are left at their defaults here). If `output_file` is omitted, the
    tool picks its own default name next to the input board.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = [board_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_ipc356_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_step_export(board_file: str, output_file: Optional[str] = None) -> dict:
    """Export an Allegro board to STEP (3D mechanical/ECAD-MCAD interchange), as a background job.

    Runs `step_out.exe [-o <output_file>] <board_file>` — confirmed live via
    `step_out.exe -help`'s usage banner (additional `-upsmnadcbz` unit/detail flags exist
    but are left at their defaults here). This is the confirmed CAD-side complement to
    Sigrity's own Dsn2Spd/layout translators — use this when the destination is a
    mechanical/MCAD tool rather than a Sigrity analysis session.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = []
    if output_file:
        args += ["-o", output_file]
    args.append(board_file)
    record = await submit_job(tool="allegro_step_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_gerber_plot(board_file: str, output_file: Optional[str] = None) -> dict:
    """Generate Gerber photoplot output from an Allegro board (BEST-EFFORT — see module docstring), as a background job.

    Runs `gbplot.exe <board_file> [output_file]`. UNVERIFIED: no flag syntax was
    recoverable from either `gbplot.exe -help` or the shipped doc tree — `gbplot` is
    normally driven by an Artwork Control Form saved with the board rather than CLI
    flags, so this call may need the board to already have film/Gerber settings
    configured in Allegro before it will produce useful output. Treat this as
    `built_untested` and check the job's log/output carefully rather than trusting a
    zero return code alone.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    args = [board_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_gbplot", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
