"""Standalone Sigrity utility solvers — CLI-only, no Tcl session, no doc-tree coverage
but fully self-documenting via their own `-help` output (confirmed live on this machine).

- `abcd.exe -help` (confirmed live): a Touchstone S-parameter cascading/de-embedding
  utility — `abcd.exe -filepath "<dir>" [-tsfile <s2p>] [-lefttsfile <s2p>]
  [-righttsfile <s2p>] -duttsfile <out.s2p>`. Per its own printed warnings: if `-tsfile`
  is omitted, it cascades `-lefttsfile` through `-righttsfile`; if either side file is
  omitted, it does one-sided de-embedding instead. Input port count must equal output
  port count on every file, all files need matching frequency points and reference
  impedance.

  IMPORTANT — two independent, confirmed-live defects in `abcd.exe` on this machine
  (Sigrity 2024.0), reproduced against the real sample files under
  `share/SpeedXP/Samples/Broadband SPICE/` (channel.s4p, app1_drv.S4P,
  CoupledLines_SplitPlane.s4p — all real 4-port files):

  (1) SEGFAULT on some real 4-port S-parameter files. `abcd.exe` returns a Windows
      access-violation for `channel.s4p` (a magnitude/angle "MA"/dB-format Touchstone,
      4220 frequency points) every time it's used as any input file — 12/12 runs → rc
      3221225477 (0xC0000005  STATUS_ACCESS_VIOLATION) or 3221226505 (0xC0000029
      STATUS_DATATYPE_MISALIGNMENT), stdout/stderr empty, no output file. The two other
      sample files, in "RI" (real-imaginary) format — `app1_drv.S4P` and
      `CoupledLines_SplitPlane.s4p` — do NOT crash (rc 0, 12/12). The crash is
      file/data-dependent, not frequency-grid or port-count dependent: synthetic
      identity 4-port files (both MA and RI headers, even on channel.s4p's exact
      frequency grid) do NOT crash, while channel.s4p still crashes even truncated to
      its first frequency block. channel.s4p's large-angle "physical" S-data appears
      to be the trigger, but the exact offending field could not be isolated
      (single-element mutations crashed in some runs and not others — non-deterministic
      per-element, but deterministic for the whole file). Practical rule: treat abcd as
      incompatible with 4-port MA/dB-format S-parameters and pre-convert them to RI
      (or feed only RI-format files).

  (2) SILENT NO-OP (no output file written) for EVERY non-crashing combination tested —
      2-port, 4-port-RI, and 10-port (the port count in abcd's own -help example). abcd
      returns rc 0 on all of them, prints nothing, and NEVER writes the -duttsfile:
      0/12 attempts produced an output file across all of 2-port MA, 2-port RI, 4-port
      RI, 10-port RI, and identical-data MA-vs-RI cross-pairs — even cascading
      identically-sized, identical-data 4-port RI files writes nothing. As shipped on
      this machine, `run_touchstone_deembed` returns a "succeeded" job that may have
      produced no usable output. Callers MUST verify with list_job_files/
      read_job_output_file that `dut_touchstone_file` exists and is non-empty after a
      "succeeded" job: rc 0 alone is NOT proof the de-embedding actually ran.
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
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
