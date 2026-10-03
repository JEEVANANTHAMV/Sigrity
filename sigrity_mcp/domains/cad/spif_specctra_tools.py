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
only import route through the standalone CLI. It is a product-level crash in the
SPB_22.1 build of `spif_batch.exe` specifically; `run_specctra_import_session` is kept
to re-verify it (and as a reference for the standalone-CLI approach), but
`run_allegro_specctra_import` below is the recommended path — it drives Allegro's own
native `specctra_in` command via script replay instead of the crashing standalone binary,
sidestepping the bug entirely. The confirmed *export+route* half of this bridge remains
reliable either way — a routed `.ses`/`.rte` result plus `final.sts` connection stats is
directly useful on its own.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
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
async def run_allegro_specctra_import(
    board_file: str,
    session_file: str,
    output_file: Optional[str] = None,
) -> dict:
    """Import a routed SPECCTRA session (.ses) into an Allegro board via Allegro's own native `specctra_in` command (the recommended import path — see module docstring), as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    clear_stale_design_lock(board_file)
    session = tcl_sessions.create("allegro")
    clean_ses = str(session_file).replace("\\", "/")
    tcl_sessions.add_line(session.session_id, f'specctra_in "{clean_ses}"')
    # `specctra_in <file>` (one word -- see module docstring's ROOT CAUSE note) drives
    # the real "Import From Auto-Router" dialog (share/pcb/text/forms/spif_in.form:
    # fields SES_IN/TRANSLATE_TO/CLOSE) headlessly, auto-filling SES_IN and clicking
    # TRANSLATE_TO ("Run") in one step -- CONFIRMED live via the replay journal (no
    # separate FORM lines needed for that part). But the form stays open (modeless)
    # afterward, and Allegro's command dispatcher refuses any further top-level command
    # with "Finish current command first" (CONFIRMED live) until it is explicitly
    # closed -- so every caller must close it before anything else (a save, another
    # command, or `quit`) or that next command silently no-ops.
    tcl_sessions.add_line(session.session_id, "setwindow form.spif_in")
    tcl_sessions.add_line(session.session_id, "FORM spif_in CLOSE")
    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    if output_file:
        clean_out = str(output_file).replace("\\", "/")
        tcl_sessions.add_line(session.session_id, f'skill (axlSaveDesign ?design {skill_str(clean_out)} ?mode {skill_str("nocheck")})')
    else:
        tcl_sessions.add_line(session.session_id, f'skill (axlSaveDesign ?mode {skill_str("nocheck")})')
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        extra_args=[board_file],
        script_filename="import_specctra.scr",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_specctra_import_session(board_file: str, session_file: str) -> dict:
    """Import a routed SPECCTRA session via standalone spif_batch.exe (KNOWN BROKEN on this machine — prefer run_allegro_specctra_import), as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-i", board_file, session_file]
    record = await submit_job(tool="spif_batch", build_args=args)
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "warning": (
            "spif_batch.exe -i is CONFIRMED BROKEN on this installation (SPMHDB-238 "
            "crash, deterministic). Do NOT use this as the primary import path -- use "
            "run_allegro_specctra_import instead. Do NOT wait_for_job on this job: the "
            "launcher crashes and detaches, so the job record stays "
            "state='running'/returncode=None forever. If you must inspect the result, "
            "poll list_job_files for a spif_batch_P*.AllegroMiniDump.dmp artifact and "
            "read run.log for 'ERROR(SPMHDB-238)'."
        ),
    }
