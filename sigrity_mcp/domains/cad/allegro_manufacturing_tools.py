"""Allegro manufacturing-output generators — standalone CLI, no SKILL session needed.

Confirmed live on this machine via each executable's own `-help` usage banner:
- `ipc2581_out.exe [-ufdblRnpstcgkvexyzPDOIMS] [-g <attrFile>] [-o <outFile>] <brd>` —
  IPC-2581 (unified fabrication/assembly/test data) export.
- `ipc356_out.exe [-t/-i/-r/-f/-A/-c/-b/-e] <in.brd> [<out.ipc>]` — IPC-356 bare-board
  netlist/test-point export.
- `step_out.exe [-upsmnadcbz] [-o <output_file>] <brd>` — STEP (3D mechanical) export.

GERBER — FIXED this pass, confirmed live end-to-end. The real pipeline has two steps,
not one: (1) define film records on the board (there was no wrapper for this at all —
now `allegro_create_film` in `allegro_geometry_tools.py`, SKILL `axlFilmCreate`) then
save the design; (2) run `artwork.exe <board> [-f <film>]...`, confirmed via its own
full `-help` usage banner AND a real live run — a board with `ETCH/TOP`/`ETCH/BOTTOM`
films defined produced genuine `TOP.art`/`BOTTOM.art` files in real RS274X Gerber format
(`G04 File Format: Gerber RS274X`), plus a `photoplot.log`. Non-fatal warnings seen on
that run ("Can't open parameter file ... using default values", "Photoplot outline
rectangle not found; using drawing extents") are `artwork.exe` falling back to sane
defaults when no `art_param.txt`/explicit outline exists — not errors. `run_allegro_generate_artwork`
below wraps this step.

`gbplot.exe` is a SEPARATE, later, optional step — NOT required for standard Gerber
output (that's `artwork.exe`'s own job, confirmed above). `doc/gcoms/gchap.html`
documents its real syntax as `gbplot artwork_file_name [penplot_file_name] [-version]` —
it converts an already-generated `.art` file (from `run_allegro_generate_artwork`) to
legacy `.plt`/`.ctl` pen-plotter format, for shops that still drive physical photoplotter
hardware rather than consuming Gerber/RS274X directly. `run_allegro_gerber_plot` below
was originally wired to pass a `.brd` directly (confirmed wrong: fails immediately with
`"gbplot: Error opening parameter file."`) — corrected to take the `.art` file
`run_allegro_generate_artwork` produces. Still `built_untested` for this specific
conversion step (not independently re-run against a real `.art` file this pass) — see
`core.tool_status`.
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
async def run_allegro_generate_artwork(
    board_file: str,
    film_names: Optional[list[str]] = None,
    list_only: bool = False,
) -> dict:
    """Generate real Gerber (RS274X) artwork films from an Allegro board, as a background job.

    CONFIRMED LIVE — this is the fix for Gerber export (see module docstring): the
    board must already have film records defined (via `allegro_create_film` +
    `allegro_save_design` in an Allegro SKILL session first) or this produces nothing.
    Runs `artwork.exe <board_file>` (all films) or `artwork.exe -f <film> [-f <film>...]
    <board_file>` (specific films only) per the tool's own confirmed `-help` banner.
    `list_only=True` instead runs `artwork.exe -l <board_file>`, which lists the film
    names currently defined on the board without generating anything — use this first to
    check what's already there. Output: one `<FILM_NAME>.art` file per film (real
    RS274X Gerber, confirmed live) plus `photoplot.log` in the job's working directory
    — retrieve them via list_job_files/read_job_output_file. Non-fatal warnings in the
    log about a missing `art_param.txt` or outline rectangle are expected (the tool
    falls back to sane defaults) — treat a nonzero-but-"had warnings" exit distinctly
    from a real parameter/license error by reading `photoplot.log`.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    if list_only:
        args = ["-l", board_file]
    else:
        args = []
        for film in film_names or []:
            args += ["-f", film]
        args.append(board_file)
    record = await submit_job(tool="allegro_artwork", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_gerber_plot(artwork_file: str, penplot_file: Optional[str] = None) -> dict:
    """Convert an already-generated Gerber artwork file to legacy pen-plotter format, as a background job.

    CORRECTED this pass (see module docstring) — `gbplot.exe` takes a `.art` file
    (produced by run_allegro_generate_artwork), not a `.brd` directly; the original
    version of this tool passed a board file and failed immediately with
    `"gbplot: Error opening parameter file."`. Runs `gbplot.exe <artwork_file>
    [penplot_file]` per `doc/gcoms/gchap.html`'s real documented syntax. Only needed for
    shops driving physical photoplotter/pen-plotter hardware — most Gerber/RS274X
    consumers (fab houses, CAM tools) want run_allegro_generate_artwork's `.art` output
    directly and don't need this step at all.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    args = [artwork_file]
    if penplot_file:
        args.append(penplot_file)
    record = await submit_job(tool="allegro_gbplot", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
