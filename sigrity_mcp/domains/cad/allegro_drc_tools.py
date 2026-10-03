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

import asyncio
import time
from pathlib import Path
from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp

_BATCH_DRC_COMPLETION_MARKER = "DRC update completed"


@mcp.tool
async def run_allegro_batch_drc(
    board_file: str,
    output_file: Optional[str] = None,
    nographic: bool = True,
    poll_timeout_seconds: float = 60.0,
) -> dict:
    """Run a headless DRC pass over an Allegro board and write a DRC report, as a background job.

    Confirmed live (real on-disk job records, not just documentation): `batch_drc.exe`'s
    launcher process intermittently detaches before the DRC work itself finishes writing
    its own `batch_drc.log` completion marker -- the job's own state/returncode then
    never reaches a terminal value (confirmed: real job dirs with a complete
    `batch_drc.log` ending "DRC update completed" and a complete `dbdoctor.log`, yet
    `state:"running"`/`returncode:null` forever). This is intermittent, not universal
    (the large majority of runs resolve normally via the launcher's own exit).

    To avoid returning a misleading `state:"running"` for a job that may already be
    done, this call blocks for up to `poll_timeout_seconds` (default 60s, well past the
    tool's real observed ~1-15s runtime) re-checking both the job's own state and
    `batch_drc.log`'s completion marker. If the job reaches a real terminal state first,
    the corrected state is returned with no other change. If the log's completion
    marker appears while the job record is still stuck at "running" (the detached-
    launcher case), a `note` field says so explicitly and points at `batch_drc.log`/
    `dbdoctor.log` for the real results, instead of leaving the caller to trust a
    state that will never change. If neither happens within the window, today's
    original behavior is preserved exactly (the record as-is, no note) -- not a
    regression for genuinely slow/stuck runs.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = []
    if nographic:
        args.append("-nographic")
    args.append(board_file)
    if output_file:
        args.append(output_file)
    record = await submit_job(tool="allegro_batch_drc", build_args=args)
    result = {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}

    from sigrity_mcp.core.jobs import job_manager

    log_path = Path(record.job_dir) / "batch_drc.log"
    deadline = time.monotonic() + poll_timeout_seconds
    while time.monotonic() < deadline:
        current = job_manager.get(record.job_id)
        if current.state != "running":
            result["state"] = current.state
            result["returncode"] = current.returncode
            return result
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            tail = ""
        if _BATCH_DRC_COMPLETION_MARKER in tail:
            result["note"] = (
                "batch_drc.exe's launcher process detached before its job record "
                "reached a terminal state -- a known, intermittent launcher quirk, not "
                "a sign the DRC pass failed. Real completion was detected instead via "
                f"batch_drc.log's '{_BATCH_DRC_COMPLETION_MARKER}' marker: the DRC pass "
                "is done. Read batch_drc.log/dbdoctor.log in job_dir for the real "
                "results; do not keep waiting on this job's state to change."
            )
            return result
        await asyncio.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
    return result


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
