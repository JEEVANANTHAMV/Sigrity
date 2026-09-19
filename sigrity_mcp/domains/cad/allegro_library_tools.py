"""Allegro/IBIS library & die-abstract model checking — standalone CLI, no SKILL session needed.

Confirmed live on this machine:
- `ibischk3.exe`/`ibischk4.exe`/`ibischk5.exe`/`ibischk6.exe` each print a version banner
  and try to open an argument as an IBIS filename (e.g. running one bare attempted to
  open a literal `-help.ibs`) — real invocation is `ibischkN <model.ibs>`, one binary per
  IBIS spec version (3.2, 4.x, 5.x, 6.x). No dedicated doc page was found, but the live
  behavior is unambiguous and there is no GUI.
- `diacheck.exe -help`: `diacheck <die_abstract_file> [output_file]
  [-nn][-nc][-nl][-ne][-nf][-nu][-ns][-nm][-np]` — validates a die-abstract file's
  syntax/semantics (3D-IC/interposer flows).
- `diacompare.exe -help`: `diacompare <golden_file> <eco_file> [output_file]
  [-nl][-ns][-np][-ni][-nd][-nr][-nb][-na][-nt][-nn][-nk][-id]` — compares two die-
  abstract files (an ECO diff).
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp

_IbisVersion = Literal["3", "4", "5", "6"]


@mcp.tool
async def run_ibis_check(model_file: str, ibis_version: _IbisVersion = "6") -> dict:
    """Validate an IBIS model file against a specific IBIS spec version, as a background job.

    Runs `ibischk<ibis_version>.exe <model_file>` — confirmed live: each of
    ibischk3/4/5/6 is a real, separate checker binary (one per IBIS spec generation),
    not a single tool with a version flag. Pick the checker matching the model's
    declared `[IBIS Ver]`; when unsure, `ibis_version="6"` (the newest checker) is
    usually the safest default since later checkers are generally backward-tolerant of
    older-spec models, but a genuinely old model may need its matching version to avoid
    spurious errors.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then read
    the checker's report via tail_job_log/read_job_output_file.
    """
    tool_name = f"ibischk{ibis_version}"
    record = await submit_job(tool=tool_name, build_args=[model_file])
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_die_abstract_check(
    die_abstract_file: str,
    output_file: Optional[str] = None,
    skip_net_names: bool = False,
    skip_connectivity: bool = False,
    skip_layer_info: bool = False,
) -> dict:
    """Validate a die-abstract file's syntax/semantics (3D-IC/interposer flows), as a background job.

    Runs `diacheck.exe <die_abstract_file> [output_file] [-nn] [-nc] [-nl]` — confirmed
    live via `diacheck.exe -help`'s usage banner. `skip_net_names`/`skip_connectivity`/
    `skip_layer_info` map to the `-nn`/`-nc`/`-nl` suppression flags respectively; several
    more (`-ne`/`-nf`/`-nu`/`-ns`/`-nm`/`-np`) exist in the full usage banner but are left
    at their defaults here — extend if you need finer control.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = [die_abstract_file]
    if output_file:
        args.append(output_file)
    if skip_net_names:
        args.append("-nn")
    if skip_connectivity:
        args.append("-nc")
    if skip_layer_info:
        args.append("-nl")
    record = await submit_job(tool="allegro_diacheck", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_die_abstract_compare(golden_file: str, eco_file: str, output_file: Optional[str] = None) -> dict:
    """Compare two die-abstract files (golden vs. ECO) and report differences, as a background job.

    Runs `diacompare.exe <golden_file> <eco_file> [output_file]` — confirmed live via
    `diacompare.exe -help`'s usage banner (a dozen `-n*`-style suppression flags exist for
    finer control over which difference categories are reported, all left at their
    defaults here).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = [golden_file, eco_file]
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_diacompare", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
