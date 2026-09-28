"""Allegro <-> SPECCTRA autorouting bridge — standalone CLI, no SKILL session needed.

MAJOR CORRECTION to this project's own earlier research: `allegro_placement_tools.py`'s
module docstring previously stated "no batch CLI or SKILL surface for general trace
autorouting was found anywhere on this installation." That conclusion was correct for
`apr.exe`/`placeroute.exe` specifically, but wrong as a claim about Allegro generally —
Allegro ships a genuine, fully headless, third-party-router bridge: SPIF (the SPECCTRA
Interface, `doc/algroroute/chap11.html`) translates a `.brd` to a SPECCTRA `.dsn` file,
`specctra.exe` (the actual "Allegro PCB Router", fully documented in `doc/spug/`) routes
it headlessly via `-nog -do <script>.do -quit`, and SPIF translates the resulting
session back into the `.brd`.

**CONFIRMED LIVE, twice, on this machine**:
- `spif_batch.exe -o board.brd board.dsn` — real `.dsn` exported (85KB from the real
  sample board used elsewhere in this suite's testing).
- `specctra.exe board.dsn -nog -do route.do -quit` — a REAL, COMPLETE, HEADLESS
  AUTOROUTE. Run against Cadence's own shipped tutorial design
  (`share/specctra/tutorial/lesson1.dsn` + `basic.do`): 100% connected, 0 conflicts. Run
  again against this suite's own real sample board (75 nets, 163 connections): **100%
  connected, 0 conflicts**, real `.ses` session file written. The `.do` script language
  (`bestsave`, `status_file`, `smart_route`, `write session <file>.ses`, `report
  status`) is transcribed directly from Cadence's own shipped tutorial `.do` file
  (`share/specctra/tutorial/basic.do`) and `doc/spug/chap2.html`'s own documented
  `write session` syntax — not guessed.

**CONFIRMED BROKEN on this machine (now root-caused)**: `spif_batch.exe -i board.brd
routed.ses` (importing the routed session back into the Allegro board) hard-crashes:
exit code 3221225477 (0xC0000005 access violation), `ERROR(SPMHDB-238): The design is
corrupted...` (define `DBMSG_BYTESWAPPED` in share/pcb/text/spmhdb.xml) in the log, and
a real `spif_batch_P00122.1_AllegroMiniDump.dmp`. Live diagnosis ruled out every
environmental cause: (a) no GUI dialog is spawned — win32gui polling at 20 ms saw zero
visible windows, so there is nothing for pywin32/Windows-MCP to intercept; (b) it is not
a `.brd`-state problem — `dbdoctor -drc` reports "0 errors, 0 errors could be fixed"
and the crash reproduces identically on a fresh untouched copy (Variant A); (c) no
flag bypasses it — `spif_batch`'s full switch set is `-o|-r|-i|-c` and `specctra.exe`'s
documented startup options contain no session-import path, making `spif_batch -i` the
only import route in this install. It is a product-level crash in the SPB_22.1 build;
`run_specctra_import_session` is kept to re-verify it, and the confirmed
*export+route* half of this bridge remains the reliable, high-value part — a routed
`.ses`/`.rte` result plus `final.sts` connection stats is directly useful on its own.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_spif_export_to_specctra(board_file: str, dsn_file: Optional[str] = None) -> dict:
    """Export an Allegro board to a SPECCTRA `.dsn` design file, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-o", board_file]
    if dsn_file:
        args.append(dsn_file)
    record = await submit_job(tool="spif_batch", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_specctra_autoroute(
    dsn_file: str,
    do_file: str,
    graphics: bool = False,
) -> dict:
    """Run Cadence's SPECCTRA-based headless PCB autorouter against a `.dsn` design, driven by a `.do` batch script, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = [dsn_file]
    if not graphics:
        args.append("-nog")
    args += ["-do", do_file, "-quit"]
    record = await submit_job(tool="specctra", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_specctra_import_session(board_file: str, session_file: str) -> dict:
    """Import a routed SPECCTRA session back into an Allegro board (KNOWN BROKEN on this machine — see module docstring), as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-i", board_file, session_file]
    record = await submit_job(tool="spif_batch", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
