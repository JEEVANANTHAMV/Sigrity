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

MECHANICAL ECAD/MCAD EXCHANGE (IDF/IDX) AND MORE MANUFACTURING EXPORT FORMATS — added
after a fresh sweep of every executable under `tools/bin` not yet registered turned up
several more genuinely real, self-documenting standalone CLIs:
- `ipc2581_in.exe [-x] [-g] [-o <output_board>] [-i <input_board>] <ipc2581_file>` —
  CONFIRMED LIVE, the import direction of the already-wrapped `ipc2581_out`: given a
  real IPC-2581 file, produces a genuine new `.brd` (confirmed valid by independently
  re-reading it with `report.exe`). See `run_ipc2581_import` below.
- `idf_out.exe`/`idx_out.exe` — CONFIRMED LIVE mechanical outline+placement export to
  IDF and IDX (ProSTEP EDMD) format respectively, both run bare against a real board
  with zero preconditions. `idf_in.exe`/`idx_in.exe` (the import direction — genuinely
  documented to create a brand-new `.brd` from IDF/IDX mechanical data the same way
  `dxf2a`/`ipc2581_in` do, per their own `-help` text) are wrapped too but
  `built_untested`: no real `.emn`/`.bdf`/`.idx` sample file was found on this machine
  to run them against.
- `brd2dml.exe` — CONFIRMED LIVE export of an Allegro board's connectivity to Cadence's
  own DML boardmodel format (real `(Library (BoardModel ...))` content confirmed).
- `pdf_out.exe` — CONFIRMED LIVE direct Allegro-to-PDF export (real `%PDF-1.7` output
  confirmed).

All seven new tools above resolve every file-path argument to absolute (relative to the
MCP server's own cwd, not the job's) before building argv — see `core/paths.py` for why:
a demonstrated real failure mode in this same executable family (dxf2a/a2dxf, see
`allegro_import_tools.py`) sends these tools into a runaway interactive re-prompt loop
on an unresolved relative path instead of failing cleanly.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.paths import resolve_path as _resolve
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


@mcp.tool
async def run_ipc2581_import(
    ipc2581_file: str,
    output_board_file: Optional[str] = None,
    input_board_file: Optional[str] = None,
    import_stackup: bool = False,
    import_layer_features: bool = False,
) -> dict:
    """Import IPC-2581 data into Allegro — CONFIRMED LIVE (see module docstring).

    Runs `ipc2581_in.exe [-x] [-g] [-o <output_board_file>] [-i <input_board_file>]
    <ipc2581_file>` as a background job. With `input_board_file` omitted (the default),
    this creates a BRAND-NEW `.brd` — confirmed live producing a real, valid board
    (independently re-verified with report.exe). Pass `input_board_file` to instead
    update an existing board (overwriting it unless `output_board_file` is also given).
    `import_stackup`/`import_layer_features` map to `-x`/`-g` (both off by default,
    matching ipc2581_in's own defaults); a live test with both enabled surfaced a real,
    readable "Layer stackup import failed." warning on one sample without stopping the
    rest of the import — read the job log rather than assuming a clean run means every
    layer/stackup detail landed.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if import_stackup:
        args.append("-x")
    if import_layer_features:
        args.append("-g")
    if output_board_file:
        args += ["-o", _resolve(output_board_file)]
    if input_board_file:
        args += ["-i", _resolve(input_board_file)]
    args.append(_resolve(ipc2581_file))
    record = await submit_job(tool="ipc2581_in", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_idf_export(
    board_file: str,
    output_name: Optional[str] = None,
    idf_format: Optional[Literal["IDF", "PTC", "SDRC"]] = None,
    idf_version: Optional[Literal["2.0", "3.0"]] = None,
) -> dict:
    """Export Allegro mechanical outline/placement data to IDF format — CONFIRMED LIVE (see module docstring).

    Runs `idf_out.exe [-d <idf_format>] [-o <output_name>] [-V <idf_version>]
    <board_file>` as a background job. Confirmed live in its bare (all-defaults) form,
    producing real `<design_name>.bdf`/`.ldf` output. `idf_format` selects the third-
    party mechanical-system naming convention (IDF/PTC/SDRC — default IDF);
    `idf_version` is the IDF spec revision (default 2.0).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if idf_format:
        args += ["-d", idf_format]
    if output_name:
        args += ["-o", _resolve(output_name)]
    if idf_version:
        args += ["-V", idf_version]
    args.append(_resolve(board_file))
    record = await submit_job(tool="idf_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_idx_export(
    board_file: str,
    output_name: Optional[str] = None,
    idx_version: Optional[Literal["1.2", "2.0", "3.0", "4.0"]] = None,
    export_traces_as_outlines: bool = False,
) -> dict:
    """Export Allegro mechanical/placement data to IDX (ProSTEP EDMD) format — CONFIRMED LIVE (see module docstring).

    Runs `idx_out.exe [-o <output_name>] [-v <idx_version>] [-u] <board_file>` as a
    background job. Confirmed live in its bare (all-defaults) form, producing a real
    ProSTEP EDMD XML `.idx` file. `export_traces_as_outlines` maps to `-u` (default:
    traces exported as lines). Several more flags exist for incremental/baseline-diff
    IDX generation (`-i`/`-f`/`-p`/`-c`) — not exposed here, extend if needed.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if output_name:
        args += ["-o", _resolve(output_name)]
    if idx_version:
        args += ["-v", idx_version]
    if export_traces_as_outlines:
        args.append("-u")
    args.append(_resolve(board_file))
    record = await submit_job(tool="idx_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_idf_import(
    idf_file: str,
    output_board_file: Optional[str] = None,
    input_board_file: Optional[str] = None,
    idf_format: Optional[Literal["IDF", "PTC", "SDRC"]] = None,
) -> dict:
    """Import IDF mechanical outline/placement data into Allegro (BUILT, UNTESTED — see module docstring).

    Runs `idf_in.exe [-d <idf_format>] <idf_file> [-o <output_board_file>]
    [-i <input_board_file>]` as a background job. Confirmed real via idf_in's own
    `-help` usage banner (not yet live-tested — no real `.emn`/`.bdf`/`.out` sample file
    was found on this machine). With `input_board_file` omitted (the default), idf_in's
    own docs say this creates a brand-new `.brd` (`<drawing_name>.brd`) — the same class
    of "create from scratch" capability confirmed live for `dxf2a`/`ipc2581_in`, just not
    independently exercised for this specific tool yet.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if idf_format:
        args += ["-d", idf_format]
    args.append(_resolve(idf_file))
    if output_board_file:
        args += ["-o", _resolve(output_board_file)]
    if input_board_file:
        args += ["-i", _resolve(input_board_file)]
    record = await submit_job(tool="idf_in", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_idx_import(idx_file: str, output_board_file: Optional[str] = None, input_board_file: Optional[str] = None) -> dict:
    """Import IDX (ProSTEP EDMD) mechanical data into Allegro (BUILT, UNTESTED — see module docstring).

    Runs `idx_in.exe <idx_file> [-i <input_board_file>] [-o <output_board_file>]` as a
    background job. Confirmed real via idx_in's own `-help` usage banner and worked
    example, not yet live-tested (no real `.idx` sample file was found on this machine).
    With `input_board_file` omitted, creates a brand-new `.brd` from the IDX data.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = [_resolve(idx_file)]
    if input_board_file:
        args += ["-i", _resolve(input_board_file)]
    if output_board_file:
        args += ["-o", _resolve(output_board_file)]
    record = await submit_job(tool="idx_in", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_dml_export(
    board_file: str,
    nets_file: Optional[str] = None,
    comps_file: Optional[str] = None,
    coupling_window: Optional[str] = None,
    frequency: Optional[str] = None,
) -> dict:
    """Export an Allegro board's connectivity to Cadence's DML boardmodel format — CONFIRMED LIVE (see module docstring).

    Runs `brd2dml.exe [nets=<nets_file>] [comps=<comps_file>] [window=<coupling_window>]
    [freq=<frequency>] <board_file>` as a background job — note brd2dml's own unusual
    `key=value` argument style (confirmed via its own `-help` banner), not `-flag value`
    like every other tool in this module. Confirmed live in its bare (all-defaults) form
    against a real board, producing a real `.dml` file with genuine boardmodel content.
    If both `nets_file`/`comps_file` are omitted, every valid net in the design is
    extracted. `coupling_window`/`frequency` take unit-suffixed strings per brd2dml's own
    examples (e.g. "20mil", "10GHZ").
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if nets_file:
        args.append(f"nets={_resolve(nets_file)}")
    if comps_file:
        args.append(f"comps={_resolve(comps_file)}")
    if coupling_window:
        args.append(f"window={coupling_window}")
    if frequency:
        args.append(f"freq={frequency}")
    args.append(_resolve(board_file))
    record = await submit_job(tool="brd2dml", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_pdf_export(
    board_file: str,
    output_name: Optional[str] = None,
    black_and_white: bool = False,
    pad_filled: bool = False,
    separate_file_per_film: bool = False,
    export_outlines: bool = False,
) -> dict:
    """Export Allegro data directly to PDF — CONFIRMED LIVE (see module docstring).

    Runs `pdf_out.exe [-o <output_name>] [-B] [-p] [-s] [-r] <board_file>` as a
    background job. Confirmed live in its bare (all-defaults) form against a real
    board, producing a genuine PDF (verified `%PDF-1.7` file header). `black_and_white`
    (`-B`) uses black/white instead of the design's own colors; `pad_filled` (`-p`)
    fills pads; `separate_file_per_film` (`-s`) writes one PDF per artwork film instead
    of one combined PDF; `export_outlines` (`-r`) exports board/symbol outlines (and
    refdes, if pins are also exported). Several more flags exist (user/permission
    passwords, per-film selection, paper-size config file) — not exposed here.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if output_name:
        args += ["-o", _resolve(output_name)]
    if black_and_white:
        args.append("-B")
    if pad_filled:
        args.append("-p")
    if separate_file_per_film:
        args.append("-s")
    if export_outlines:
        args.append("-r")
    args.append(_resolve(board_file))
    record = await submit_job(tool="pdf_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
