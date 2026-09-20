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

CORRECTION to this suite's own earlier "library authoring is GUI-only" conclusion
(README/`domains/cad/__init__.py` previously named `padstack_editor.exe`/
`symboleditor.exe`/`symbolcreator.exe` as the confirmed-GUI-only set — that finding
still stands for those three specifically, but a fresh sweep of `tools/bin` found a
distinct exe they don't cover): **`create_sym.exe`** — CONFIRMED LIVE, its own `-help`
banner: "This is the command line version of File->Create Symbol." Compiles a `.dra`
source into a real package/mechanical/format/pad-shape/thermal-flash symbol file.
Live-tested against a real shipped footprint source
(doc/lc_tut/tutorial_examples/Master_Library/Symbols/asp-134488-01.dra):
`create_sym -p mysym.dra mysym.psm` produced a real 2.9MB `.psm`, independently
re-verified with `dbdoctor.exe -check_only` ("0 warnings, 0 errors detected").
`allegro_create_symbol` resolves its file-path arguments to absolute before building
argv (see `core/paths.py`) — the same defensive fix applied everywhere else in this
same Cadence CLI family after a demonstrated runaway-re-prompt-loop failure mode.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.paths import resolve_path as _resolve
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


_SYMBOL_TYPES = Literal["mechanical", "package", "format", "pad_shape", "thermal_flash"]

_SYMBOL_TYPE_FLAGS: dict[str, str] = {
    "mechanical": "-m",
    "package": "-p",
    "format": "-f",
    "pad_shape": "-s",
    "thermal_flash": "-t",
}


@mcp.tool
async def allegro_create_symbol(
    dra_file: str, output_symbol_file: Optional[str] = None, symbol_type: Optional[_SYMBOL_TYPES] = None
) -> dict:
    """Compile a `.dra` source into an Allegro symbol — CONFIRMED LIVE (see module docstring).

    Runs `create_sym.exe [-m|-p|-f|-s|-t] <dra_file> [<output_symbol_file>]` as a
    background job — the command-line equivalent of Allegro's File > Create Symbol.
    `symbol_type` selects which kind to compile: "mechanical" (.bsm), "package" (.psm),
    "format" (.osm), "pad_shape" (.ssm), "thermal_flash" (.fsm). If omitted, create_sym
    uses whatever default type is set inside the `.dra` file itself. If
    `output_symbol_file` is omitted, create_sym derives a name from `dra_file` and the
    selected type.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job. Independently
    verify a produced symbol with `run_allegro_dbdoctor -check_only` if you need extra
    confidence beyond a clean exit (confirmed live this way during this tool's own
    testing).
    """
    args: list[str] = []
    if symbol_type:
        args.append(_SYMBOL_TYPE_FLAGS[symbol_type])
    args.append(_resolve(dra_file))
    if output_symbol_file:
        args.append(_resolve(output_symbol_file))
    record = await submit_job(tool="create_sym", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
