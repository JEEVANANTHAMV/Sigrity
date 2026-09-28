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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args: list[str] = []
    if symbol_type:
        args.append(_SYMBOL_TYPE_FLAGS[symbol_type])
    args.append(_resolve(dra_file))
    if output_symbol_file:
        args.append(_resolve(output_symbol_file))
    record = await submit_job(tool="create_sym", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
