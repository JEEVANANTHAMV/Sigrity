"""Allegro batch placement & fanout/drill routing — standalone CLI, no SKILL session needed.

Confirmed live on this machine: `allegro_batch.exe placement -help` prints a full usage
banner headed "Allegro auto-place program" — `placement [options] <input_design>
[<output_design>]` with `-a` (iterate while improving), `-w` (weight edges), `-p` (print
the connection matrix). `placement.exe` also exists as its own standalone executable in
`tools/bin` (not only reachable through the `allegro_batch` multiplexer, which is
confirmed broken for at least one other sub-program dispatch — `dbdoctor`, see
`allegro_batch_tools.py`), so this tool calls it directly, matching the project's
established pattern.

IMPORTANT scope note: this is real automatic *placement* — component-to-board-position
assignment. It is NOT automatic trace *routing*. A thorough, doc-tree-wide search (SKILL
function reference, `allegro_batch -help`, live probes of `apr.exe`/`placeroute.exe`)
found no standalone or SKILL-scriptable batch interface for interactive autorouting
anywhere on this installation — `apr.exe`/`placeroute.exe` both launch a GUI window with
no CLI usage text. What IS confirmed batch-scriptable on the routing side is narrower:
`ncroute.exe` (NC drill-route file generation, not signal routing) and `zrouter.exe`
(via/pin-escape fanout routing driven by a Connections Control File, not general trace
routing).

`ncroute.exe`'s flags (`-q`/`-v`/`-o`/`-n`) and `zrouter.exe`'s control-file-driven
invocation were read from `doc/zcoms/zchap.html` and the `allegro_batch ncroute -help`/
`allegro_batch zrouter -help` output; `zrouter`'s exact flag syntax was not fully
recoverable (both variants returned "Help is not available" for flag detail), so
`run_allegro_zrouter` is best-effort and should be treated as `built_untested` until
exercised against a real control file.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_allegro_placement(
    board_file: str,
    output_file: Optional[str] = None,
    iterate_while_improving: bool = False,
    weight_edges: bool = False,
    print_connection_matrix: bool = False,
) -> dict:
    """Run Allegro's standalone auto-placement engine over a board, as a background job.

    Runs `placement.exe [-a] [-w] [-p] <board_file> [output_file]` — confirmed live via
    `allegro_batch placement -help`'s usage banner ("Allegro auto-place program").
    `iterate_while_improving` maps to `-a` (keep iterating while placement quality is
    still improving), `weight_edges` to `-w` (weight connections by net importance),
    `print_connection_matrix` to `-p` (diagnostic dump of the connection matrix, not a
    placement-quality setting). If `output_file` is omitted, the tool writes back to
    (or next to) the input board per its own default.
    This performs real component placement — it does NOT route traces; see
    run_allegro_ncroute/run_allegro_zrouter for the narrower routing capability actually
    confirmed on this installation (drill-route and via-fanout only, not general
    autorouting — no batch CLI was found for that).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then inspect
    the output board / job log via list_job_files/read_job_output_file.
    """
    args = []
    if iterate_while_improving:
        args.append("-a")
    if weight_edges:
        args.append("-w")
    if print_connection_matrix:
        args.append("-p")
    args.append(board_file)
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_placement", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_ncroute(
    board_file: str,
    output_file: Optional[str] = None,
    quiet: bool = False,
    verbose: bool = False,
) -> dict:
    """Generate NC (numerically-controlled) drill-route data for a board, as a background job.

    Runs `ncroute.exe [-q] [-v] [-o <output_file>] <board_file>` — confirmed live via
    `allegro_batch ncroute -help`'s usage banner. This produces drill/NC-route output for
    fabrication, not signal-trace autorouting (no batch CLI exists on this installation
    for that — see this module's docstring). `quiet`/`verbose` map to `-q`/`-v`
    respectively; pass at most one.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = []
    if quiet:
        args.append("-q")
    if verbose:
        args.append("-v")
    if output_file:
        args += ["-o", output_file]
    args.append(board_file)
    record = await submit_job(tool="allegro_ncroute", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_zrouter(board_file: str, control_file: str, output_file: Optional[str] = None) -> dict:
    """Run via/pin-escape fanout routing (`zrouter.exe`) driven by a Connections Control File, as a background job.

    BEST-EFFORT / built_untested: `doc/zcoms/zchap.html` documents `zrouter` as routing
    vias from MLC (multi-layer-ceramic) I/O pins according to a Connections Control File
    you author separately, and `allegro_batch zrouter -help` confirms it's a real
    batch-dispatched sub-program — but neither surfaced the exact flag syntax for
    supplying that control file (both returned "Help is not available" for flag detail).
    This tool currently passes `control_file` and `board_file` as bare positional
    arguments, which is a best-effort guess, not a confirmed invocation — treat this as
    unverified until exercised against a real board and control file, and check the
    job's log/output carefully rather than trusting a zero return code alone.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    args = [control_file, board_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_zrouter", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
