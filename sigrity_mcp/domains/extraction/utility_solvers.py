"""Standalone Sigrity utility solvers — CLI-only, no Tcl session, no doc-tree coverage
but fully self-documenting via their own `-help` output (confirmed live on this machine).

- `abcd.exe -help` (confirmed live): a Touchstone S-parameter cascading/de-embedding
  utility — `abcd.exe -filepath "<dir>" [-tsfile <s2p>] [-lefttsfile <s2p>]
  [-righttsfile <s2p>] -duttsfile <out.s2p>`. Per its own printed warnings: if `-tsfile`
  is omitted, it cascades `-lefttsfile` through `-righttsfile`; if either side file is
  omitted, it does one-sided de-embedding instead. Input port count must equal output
  port count on every file, all files need matching frequency points and reference
  impedance.
- `bem2d3.exe -help` (confirmed live, though the tool's own banner still calls itself
  "BEM2D2" internally — a legacy name baked into its help text, not a typo in this
  module): a 2D static field solver, "complementary to existing BEM2D in order to
  support rigid-flex design" — extracts transmission-line impedance/propagation delay
  over x-hatched ground planes. `bem2d3.exe -in <geometry.in> -out <results.out>
  [-xhatchmode y -xhatchhp <hatch_space_m> -xhatchw <hatch_line_width_m>
  -xhatchangle <angle_deg>]`.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_touchstone_deembed(
    file_path: str,
    dut_touchstone_file: str,
    touchstone_file: Optional[str] = None,
    left_touchstone_file: Optional[str] = None,
    right_touchstone_file: Optional[str] = None,
) -> dict:
    """Cascade or de-embed Touchstone S-parameter files with Sigrity's standalone `abcd.exe`, as a background job.

    Runs `abcd.exe -filepath <file_path> [-tsfile <touchstone_file>]
    [-lefttsfile <left_touchstone_file>] [-righttsfile <right_touchstone_file>]
    -duttsfile <dut_touchstone_file>` — confirmed live via `abcd.exe -help`'s full usage
    banner. `file_path` is the directory all the other filenames are resolved relative to
    (per the tool's own printed constraint, this path must not contain spaces).
    Behavior per the tool's own documented rules: if `touchstone_file` is omitted, it
    cascades `left_touchstone_file` through `right_touchstone_file`; if either side file
    is omitted, it performs one-sided de-embedding instead. All input files must have
    equal input/output port counts, matching frequency points, and the same reference
    impedance.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then read
    `dut_touchstone_file` via read_job_output_file once it succeeds.
    """
    args = ["-filepath", file_path]
    if touchstone_file:
        args += ["-tsfile", touchstone_file]
    if left_touchstone_file:
        args += ["-lefttsfile", left_touchstone_file]
    if right_touchstone_file:
        args += ["-righttsfile", right_touchstone_file]
    args += ["-duttsfile", dut_touchstone_file]
    record = await submit_job(tool="abcd", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_xhatch_field_solver(
    input_file: str,
    output_file: str,
    xhatch_mode: bool = False,
    hatch_space_meters: Optional[float] = None,
    hatch_line_width_meters: Optional[float] = None,
    hatch_angle_degrees: Optional[float] = None,
) -> dict:
    """Run Sigrity's standalone 2D static field solver (`bem2d3.exe`) for transmission-line impedance/delay over x-hatched ground, as a background job.

    Runs `bem2d3.exe -in <input_file> -out <output_file> [-xhatchmode y -xhatchhp
    <hatch_space_meters> -xhatchw <hatch_line_width_meters>
    -xhatchangle <hatch_angle_degrees>]` — confirmed live via `bem2d3.exe -help`'s full
    usage banner (the tool's own banner still calls itself "BEM2D2" internally — a
    legacy name in its help text, not an error in this docstring). This solver
    complements Sigrity's existing BEM2D to support rigid-flex designs with a
    cross-hatched (rather than solid) reference-ground plane. `input_file` is a
    geometry file (IML syntax can also specify the cross-hatch parameters directly
    inside it, as an alternative to the CLI flags below). `xhatch_mode=True` enables
    x-hatch extraction (`-xhatchmode y`) and requires `hatch_space_meters`/
    `hatch_line_width_meters`/`hatch_angle_degrees` to be meaningful; leave it False to
    solve the geometry as given (solid ground, or hatch parameters embedded in the
    input file itself).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then read
    the RLGC/impedance/delay results via read_job_output_file once it succeeds.
    """
    args = ["-in", input_file, "-out", output_file]
    if xhatch_mode:
        args.append("-xhatchmode")
        args.append("y")
        if hatch_space_meters is not None:
            args += ["-xhatchhp", str(hatch_space_meters)]
        if hatch_line_width_meters is not None:
            args += ["-xhatchw", str(hatch_line_width_meters)]
        if hatch_angle_degrees is not None:
            args += ["-xhatchangle", str(hatch_angle_degrees)]
    record = await submit_job(tool="bem2d3", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
