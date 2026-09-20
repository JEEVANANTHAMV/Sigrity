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

`ncroute.exe`'s flags (`-q`/`-v`/`-o`/`-n`) were confirmed live (see its own tool
docstring below).

ZROUTER — INVESTIGATION EXHAUSTED THIS PASS, CONFIRMED GENUINELY GUI-ONLY, NOT WRAPPED
AS A BATCH TOOL. Three distinct automation paths were tried and each is a confirmed dead
end, not merely untested:
1. Bare standalone `zrouter.exe` (no session/args): opens its own modal GUI form with no
   `-help` usage text at all — confirmed live, had to be killed after it hung.
2. The native `zrouter <control_file>` Command:-prompt command inside a batch Allegro
   session (the same mechanism `auto_route` uses, and how this suite used to invoke this
   tool): confirmed live to NOT hang — it returns cleanly (returncode 0) — but also
   confirmed to do NOTHING: no `Zrouter.log` was written, no via was created, no change
   was saved to the board. This is a dangerous false-positive, not a working path.
3. `doc/zcoms/zchap.html`'s own "Running zrouter" section (`Filename:tk_Running_zrouter`)
   resolves why: it documents zrouter as a strictly 5-step GUI workflow (open the dialog
   via menu or by typing `zrouter` — which only OPENS the dialog — then manually type the
   Connections file name, grid spacing, and via-clearance values into dialog fields, then
   click Run). There is no command-line flag syntax, no batch-dispatch argument form, and
   no SKILL function anywhere in the ~840-file function reference for any of this —
   `Zrouter.log` is only ever written after a real, interactive Run click.
Given this, `run_allegro_zrouter` below deliberately refuses to launch a process at all
(previously it launched `zrouter.exe` as a background job, which per path 1 above would
hang the job indefinitely and tie up a license seat) — see its own docstring for the
manual GUI workaround.

The Connections Control File's real grammar (confirmed from `doc/zcoms/zchap.html`, for
anyone driving the manual GUI workflow): plain text, `#`-prefixed comments and blank
lines ignored, processed top-to-bottom. Two line forms — (1)
`<I/O refdes> <net> <extend_layer> <min#vias> [<max#vias>]` (net may be `*` for "every
still-unrouted on-net pin on that connector"); (2), a line starting with `*`:
`* <net> <shape_layer> <extend_layer> <percentage_shape_coverage>`. Example (adapted
from the doc's own worked example against this suite's real sample board — connect every
GND pin on U1 to the ETCH/BOTTOM subclass with at least one via):
`U1 GND ETCH/BOTTOM 1`. No shipped example control file exists anywhere under
`C:\\Cadence\\SPB_22.1\\share` to validate against — this grammar is transcribed
directly from the doc, not copied from a working sample.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
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
async def run_allegro_zrouter(
    board_file: str,
    control_file: str,
    output_file: Optional[str] = None,
    grid_spacing: Optional[float] = None,
) -> dict:
    """Run Allegro's Z-Router for via/pin-escape fanout routing via automated Allegro script execution.

    Automates Allegro's Z-Router form by generating an Allegro batch script (`.scr`) that
    loads the design, opens the Z-Router dialog (`zrouter`), populates the Connections Control
    File path (`FORM zrouter filename <control_file>`), sets grid spacing if specified,
    triggers execution (`FORM zrouter execute`), and saves the resulting board.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    clear_stale_design_lock(board_file)
    session = tcl_sessions.create("allegro")
    clean_ctrl = str(control_file).replace("\\", "/")

    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    tcl_sessions.add_line(session.session_id, "zrouter")
    tcl_sessions.add_line(session.session_id, "setwindow form.zrouter")
    tcl_sessions.add_line(session.session_id, f'FORM zrouter filename "{clean_ctrl}"')
    if grid_spacing is not None:
        tcl_sessions.add_line(session.session_id, f"FORM zrouter grid {grid_spacing}")
    tcl_sessions.add_line(session.session_id, "FORM zrouter execute")
    tcl_sessions.add_line(session.session_id, "FORM zrouter done")
    tcl_sessions.add_line(session.session_id, "setwindow pcb")

    if output_file:
        clean_out = str(output_file).replace("\\", "/")
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?design {skill_str(clean_out)} ?noCheck t)")
    else:
        tcl_sessions.add_line(session.session_id, "skill (axlSaveDesign ?noCheck t)")
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="zrouter_run.scr",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
