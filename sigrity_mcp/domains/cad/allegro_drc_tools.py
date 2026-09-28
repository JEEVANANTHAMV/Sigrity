"""Allegro headless DRC / constraint-rule checking — standalone CLI, no SKILL session needed.

Confirmed live on this machine (not just documentation):
- `batch_drc.exe -help` prints no self-help text, but `doc/bcoms/bchap.html` documents
  the real syntax: `batch_drc [-nographic] <input_filename> [<output_filename>]` — a
  headless design-rule-check pass over a board, distinct from `allegro_run_drc`
  (`allegro_tools.py`'s in-session `axlDRCUpdate` SKILL call, which requires an already-
  open Allegro session) and from `run_allegro_report`'s `drc`/`drc_shorts` report codes
  (which read *existing* violation state rather than recomputing it).
- `checkplus.exe -help` prints a full usage banner confirmed live:
  `checkplus -help|-h|-version|{-proj <file> [-verbose [-verbose ...]]
  [-compiledfiledir <dir>] [-max_messages <n>] [-I <path>] [-r <env_file>]
  [-r <rule_file> [names]]}` — a standalone constraint/rule-file checker distinct from
  Allegro's interactive Constraint Manager (which has no scriptable CSV/XML import path
  found anywhere in the shipped SKILL function reference).

IMPORTANT, confirmed live: `-proj` does NOT take a raw `.brd` path or a bare directory
path — both were tried against this machine's real sample projects
(`tools/checkplus_exp/concept/examples/physical`, a real shipped example with its own
`cp.dat`) and both failed with `**Error! [5038] Project File '<value>' does not exist`
plus a `**Warning! [5015] Missing '<cwd>/checkplus/cp.dat'` that ignores the `-proj`
value entirely for that check — meaning checkplus resolves `-proj` through some CDS
project-registration convention (likely tied to a `.cpm`/project-manager entry, the same
family `designextractor.exe` expects `.cpm`/`.sdax` for), not a simple filesystem path.
This exact resolution convention was not isolated from the doc tree (`doc/checkplus/`
describes the check rules themselves, not this path convention in enough
implementation-level detail). Treat `run_allegro_checkplus` as `built_untested`: the CLI
launches correctly and is license-fetching (no dialog, no crash), but a correct
`project_file` value for it has not been confirmed on this machine.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_allegro_batch_drc(board_file: str, output_file: Optional[str] = None, nographic: bool = True) -> dict:
    """Run a headless DRC pass over an Allegro board and write a DRC report, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = []
    if nographic:
        args.append("-nographic")
    args.append(board_file)
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_batch_drc", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_checkplus(
    project_file: str,
    verbose: bool = False,
    max_messages: Optional[int] = None,
    include_path: Optional[str] = None,
    env_file: Optional[str] = None,
    rule_file: Optional[str] = None,
) -> dict:
    """Run Allegro's standalone constraint/rule checker (`checkplus.exe`) against a project file, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-proj", project_file]
    if verbose:
        args.append("-verbose")
    if max_messages is not None:
        args += ["-max_messages", str(max_messages)]
    if include_path:
        args += ["-I", include_path]
    if env_file:
        args += ["-r", env_file]
    if rule_file:
        args += ["-r", rule_file]
    record = await submit_job(tool="allegro_checkplus", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
