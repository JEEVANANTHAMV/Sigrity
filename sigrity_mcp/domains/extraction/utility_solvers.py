"""Standalone Sigrity utility solvers — CLI-only, no Tcl session, no doc-tree coverage
but fully self-documenting via their own `-help` output (confirmed live on this machine).

- `abcd.exe -help <token>` (confirmed live; a BARE `-help` with no following token
  instead prints only "command line contains too few arguments" to its own log, since
  `-help` is parsed as a flag expecting a value): a Touchstone S-parameter
  cascading/de-embedding utility — `abcd.exe -filepath "<dir>\" [-tsfile <s2p>]
  [-lefttsfile <s2p>] [-righttsfile <s2p>] -duttsfile <out.s2p>`. Per its own printed
  warnings: if `-tsfile` is omitted, it cascades `-lefttsfile` through `-righttsfile`;
  if either side file is omitted, it does one-sided de-embedding instead. Input port
  count must equal output port count on every file, all files need matching frequency
  points and reference impedance.

  CONFIRMED LIVE for 2-port cascade and de-embed, with two real operational
  requirements this tool enforces for every caller below:

  (1) `-filepath`'s value MUST end in a trailing path separator. Without one, abcd
      parses the command line and silently does nothing -- no output file, no error,
      rc 0, log shows only "Program started.". This looks identical to a license or
      input-file problem from the outside; it is neither. `run_touchstone_deembed`
      below normalizes this automatically so no caller needs to remember it.
  (2) abcd exits 0 even on the silent no-op above, so rc 0 is never proof the
      de-embedding actually ran -- always verify with list_job_files/
      read_job_output_file that `dut_touchstone_file` exists and is non-empty.

  4-port S-parameter files remain unverified either way: an earlier real segfault was
  seen on a specific 4-port magnitude/angle-format file, but the original input files
  were no longer present on a later attempt to re-test it (so that attempt exited 0
  with no output for lack of valid input, not because the segfault was fixed or
  absent). Treat 4-port work as untested-pending-real-inputs, not confirmed broken or
  confirmed working -- re-copy real 4-port files and re-test before relying on it.
- `bem2d3.exe -help` (confirmed live, though the tool's own banner still calls itself
  "BEM2D2" internally — a legacy name baked into its help text, not a typo in this
  module): a 2D static field solver, "complementary to existing BEM2D in order to
  support rigid-flex design" — extracts transmission-line impedance/propagation delay
  over x-hatched ground planes. `bem2d3.exe -in <geometry.in> -out <results.out>
  [-xhatchmode y -xhatchhp <hatch_space_m> -xhatchw <hatch_line_width_m>
  -xhatchangle <angle_deg>]`.
"""

from __future__ import annotations

import os
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
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    # abcd.exe resolves -tsfile/-lefttsfile/-righttsfile/-duttsfile against -filepath's
    # value ONLY when that value ends in a trailing path separator; without one it
    # silently does nothing (rc 0, no output, no error) -- a real, confirmed defect in
    # the tool itself, not a flag-name or quoting issue. Normalize here so every caller
    # gets a working invocation with no need to remember this.
    filepath_arg = file_path if file_path.endswith(("\\", "/")) else file_path + os.sep
    args = ["-filepath", filepath_arg]
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
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
