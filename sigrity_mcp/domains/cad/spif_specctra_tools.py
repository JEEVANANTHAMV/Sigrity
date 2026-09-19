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

**CONFIRMED BROKEN on this machine**: `spif_batch.exe -i board.brd routed.ses` (importing
the routed session back into the Allegro board) crashes — `ERROR(SPMHDB-238): The
design is corrupted...` plus a real crash-dump file, reproduced identically whether run
against the original export directory or a fresh copy, with a matching or mismatched
filename. This is NOT the same "design is corrupted...copied using ASCII mode" scenario
the error text describes (everything stayed on one Windows machine, no cross-platform
copy occurred) — root cause not isolated. So `run_specctra_import_session` is
`known_blocked`/best-effort here: use it, but expect it may currently fail on this
installation, and treat the confirmed *export+route* half of this bridge as the
reliable, high-value part — a routed `.ses`/`.rte` result is still directly useful
(inspect routing completion/conflict stats from `final.sts`, or as an intermediate
artifact for the import step once its root cause is fixed).
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_spif_export_to_specctra(board_file: str, dsn_file: Optional[str] = None) -> dict:
    """Export an Allegro board to a SPECCTRA `.dsn` design file, as a background job.

    Runs `spif_batch.exe -o <board_file> [dsn_file]` — confirmed live: a real ~85KB
    `.dsn` file was produced from a real sample board, with only a benign warning about
    a missing crosstalk table (unrelated to core translation). This `.dsn` is the input
    `run_specctra_autoroute` needs. If `dsn_file` is omitted, `spif_batch` picks its own
    default name next to the input board.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
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

    Runs `specctra.exe <dsn_file> [-nog] -do <do_file> -quit` — confirmed live TWICE:
    against Cadence's own shipped tutorial design (100% connected, 0 conflicts) and
    against this suite's own real sample board (75 nets, 163 connections, 100%
    connected, 0 conflicts, real `.ses` session file written). `graphics=False`
    (default) maps to `-nog` (headless, no GUI window) — the confirmed mode for
    unattended automation; set `True` only if you specifically need the interactive
    router GUI (not useful from an MCP tool call). `-quit` (always appended) exits the
    router after the do-file's last command, per the confirmed real startup-options
    reference (`doc/spug/appendixA.html`).

    `do_file` must be a real SPECCTRA "Do file" — a plain-text script of router
    commands. The confirmed-working minimal shape (from Cadence's own shipped
    `share/specctra/tutorial/basic.do`, and this suite's own successful live test) is:
    ```
    bestsave on <dir>\\best.wir
    status_file <dir>\\route.sts
    smart_route
    write session <dir>\\routed.ses
    report status <dir>\\final.sts
    ```
    `smart_route` is the actual autoroute command; `write session <file>.ses` (confirmed
    real syntax per `doc/spug/chap2.html`) saves the result for
    run_specctra_import_session. You can also add `rule pcb (width <n>)`/`rule pcb
    (clearance <n> (type wire_wire))` lines before `smart_route` to set simple global
    design rules (confirmed real from the same tutorial script), or `-docmd
    "<command>"`-equivalent inline commands via additional do-file lines.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job — routing a
    real board can take anywhere from seconds to minutes depending on complexity; the
    two real runs tested here both completed in well under a minute. Read
    `final.sts`/`route.sts` via list_job_files/read_job_output_file for the real
    connection-completion/conflict statistics rather than trusting a nonzero return code
    alone (specctra.exe returns a nonzero exit code even on a fully successful route —
    confirmed exit code 4 on both successful test runs).
    """
    args = [dsn_file]
    if not graphics:
        args.append("-nog")
    args += ["-do", do_file, "-quit"]
    record = await submit_job(tool="specctra", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_specctra_import_session(board_file: str, session_file: str) -> dict:
    """Import a routed SPECCTRA session back into an Allegro board (KNOWN BROKEN on this machine — see module docstring), as a background job.

    Runs `spif_batch.exe -i <board_file> <session_file>`. CONFIRMED LIVE ATTEMPT, NOT
    CONFIRMED WORKING: this crashed with `ERROR(SPMHDB-238): The design is
    corrupted...` (plus a real crash-dump file) every time it was tried on this
    machine, regardless of directory or filename. The export+autoroute half of this
    bridge (run_spif_export_to_specctra, run_specctra_autoroute) is confirmed solid;
    this specific import direction needs further root-cause investigation before
    relying on it — check the job's log carefully and do not assume success from a
    nonzero-vs-zero return code alone, since this tool may simply not work yet on this
    installation.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job/tail_job_log.
    """
    args = ["-i", board_file, session_file]
    record = await submit_job(tool="spif_batch", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
