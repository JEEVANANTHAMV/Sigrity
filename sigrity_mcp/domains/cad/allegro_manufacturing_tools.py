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

import asyncio
import time
from pathlib import Path
from typing import Literal, Optional

from sigrity_mcp.core.paths import resolve_path as _resolve
from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


async def _wait_for_terminal_state(job_id: str, poll_timeout_seconds: float) -> str:
    """Bounded poll for a job to reach any terminal state, returning whatever state is
    current when the window expires (never raises, never blocks past the timeout)."""
    from sigrity_mcp.core.jobs import job_manager

    deadline = time.monotonic() + poll_timeout_seconds
    while time.monotonic() < deadline:
        current = job_manager.get(job_id)
        if current.state != "running":
            return current.state
        await asyncio.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    return job_manager.get(job_id).state


@mcp.tool
async def run_ipc2581_export(board_file: str, output_file: Optional[str] = None, attr_file: Optional[str] = None) -> dict:
    """Export an Allegro board to IPC-2581 (unified fab/assembly/test data), as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [board_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_ipc356_out", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_step_export(board_file: str, output_file: Optional[str] = None) -> dict:
    """Export an Allegro board to STEP (3D mechanical/ECAD-MCAD interchange), as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if list_only:
        args = ["-l", board_file]
    else:
        args = []
        for film in film_names or []:
            args += ["-f", film]
        args.append(board_file)
    record = await submit_job(tool="allegro_artwork", build_args=args)
    result = {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}

    if list_only:
        return result

    final_state = await _wait_for_terminal_state(record.job_id, poll_timeout_seconds=60.0)
    result["state"] = final_state
    if final_state != "running":
        job_dir = Path(record.job_dir)
        art_files = sorted(str(p.name) for p in job_dir.glob("*.art"))
        result["art_files"] = art_files
        if not art_files:
            result["note"] = (
                "artwork.exe produced no .art files -- the board likely has no film "
                "records defined yet. Run allegro_create_film + allegro_save_design + "
                "allegro_run_session on this board first, then re-run."
            )
        elif final_state == "failed":
            result["note"] = (
                "artwork.exe exits with a nonzero return code ('ARTWORK had warnings') "
                f"even on a fully successful run -- real .art files were produced "
                f"({art_files}), so do not treat state='failed' alone as proof this "
                "run failed. Check photoplot.log in job_dir for the actual warnings."
            )
    return result


@mcp.tool
async def run_allegro_gerber_plot(artwork_file: str, penplot_file: Optional[str] = None) -> dict:
    """Convert an already-generated Gerber artwork file to legacy pen-plotter format, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
