"""Allegro Package Designer (APD) + Advanced Package Router (APR) — CONFIRMED LIVE, headless.

This module corrects a prior, wrong claim in this project: `allegro_placement_tools.py`
and `domains/cad/__init__.py` previously stated that "no batch-CLI or SKILL surface for
general trace autorouting was found anywhere on this installation (apr.exe /
placeroute.exe are GUI-only)." That was correct for `apr.exe`/`placeroute.exe` *specifically*
(bare `apr.exe` opens a GUI with no CLI args), but it was wrong as a claim about APD/APR
*as a feature*: Cadence's documented APD batch mechanism runs headlessly, and the Advanced
Package Router (APR) — the real dense flip-chip package auto-router — is drivable from
that same batch mechanism through `pkg_router` + FORM replay.

WHAT IS CONFIRMED LIVE, TWICE, ON THIS MACHINE (SPB 22.1, no-license-required)
---------------------------------------------------------------------------
All three tools below were exercised end-to-end against real sample designs on this box,
with the result independently re-read by a separate code path (`report.exe -v sum`) so a
"process exited 0" alone is never the success signal:

1. APD batch (`run_apd_batch_script`):
   apd.exe -product Allegro_Adv_Packaging_Plus -nograph -s <script.scr> -p <dir> <design.mcm>
   Loaded a real flip-chip .mcm (doc/algsigsi_integ/tutorial_example/fc_demo.mcm), executed a
   SKILL line (axlSaveDesign) from the .scr, SAVED the design (file hash + size changed,
   783332 -> 932052 bytes), wrote apd.jrl + dsuprev.log, and exited cleanly in ~4s with no
   GUI window. The journal (apd.jrl) is the authoritative record: "Design opened" ->
   "skill '(axlSaveDesign ?mode nocheck)'" -> '"input"' (the saved design name) -> "quit".
   Key gotcha: `apd.exe` is a 307KB launcher stub for allegro.exe; WITHOUT `-product`
   it dies in ~50ms at the (non-graphic) Product Choices stage with zero output and an
   UNMODIFIED design file — that silent early-exit is what made `-product` look optional.
   The legal product tiers are enumerated in share/pcb/batchhelp/apd.txt; the APR gate
   requires the APD+ tier (`Allegro_Adv_Packaging_Plus`).

2. Z-Router (`run_allegro_zrouter`, re-wired to this module's same -nograph launcher):
    allegro.exe -s <script.scr> -nograph <board.brd>
    Ran the documented `zrouter` dialog via FORM replay headlessly against a real sample
    .brd with a Connections Control File. The board gained REAL new vias (before/after
    `report.exe -v sum` via-count diff; "number pins with vias added: N" in zrouter.log),
    a genuine `zrouter.log` (lowercase — landed in the BOARD'S directory, not the job_dir)
    was written, and the saved board re-read as valid. The exact form field names (from
    share/pcb/text/forms/zrouter.form) and the THREE non-obvious requirements are the
    load-bearing detail:
      * `FORM zrouter <field> <value>` uses the form's INTERNAL field NAMES (lowercase):
        filename / xgrid / ygrid / xoffset / yoffset / minspace — NOT the display text
        ("X-grid spacing:") and NOT the older `grid` token.
      * The RUN button is the MENUBUTTON field `execute` and the CLOSE button is the
        MENUBUTTON field `cancel` (their display labels are "Run"/"Close"). In -nograph
        mode `FORM zrouter Run` fails with "Form field label not found"; `FORM zrouter
        execute` runs the router. A bare `setwindow pcb` after execute is NOT enough — the
        modeless dialog then blocks the next command ("Finish current command first"), so
        `FORM zrouter cancel` must be issued to close the dialog before the save.
      * **GRID/offset/minspace MUST be explicitly set before `execute` fires.** This is the
        biggest trap and a confirmed live root cause: if the REALFILLIN fields (xgrid,
        ygrid, xoffset, yoffset, minspace) are left at their empty/uninitialized form
        default when `FORM zrouter execute` is fired, the Z-Router's execute callback
        validates the form, finds the grid/spacing unset (the form even ships `MESSAGE
        nogrid "Grid must be greater than 0."`), and SILENTLY returns WITHOUT routing: it
        writes no `zrouter.log`, adds 0 vias, and emits no error to run.log or the
        journal. The journal logs `FORM zrouter execute`, `FORM zrouter cancel`, and the
        save, and the job still reports state=succeeded with rc=0 — a "successful" run
        that did nothing (0% connection completion, 0 vias). Reproduced live: a minimal
        `run_allegro_zrouter(board, control)` (no grid args) added 0 vias on the demo
        pre_fanout.brd BGA, while the identical call WITH xgrid/ygrid/minspace set added
        15. So `run_allegro_zrouter` ALWAYS emits all five REALFILLIN FORM lines (defaults
        10/10/0/0 and min_space 3.0, which route the 50 mil demo BGA to 15/15 interior
        pins) and then parses the real `zrouter.log` so a silent no-op is reported as an
        explicit `zrouter_result.silent_no_op` / `note` instead of a bare 'succeeded'.

3. APR (`run_allegro_apr`):
    apd.exe -product Allegro_Adv_Packaging_Plus -option "Advanced Package Router" -nograph \
        -s <script.scr> <design.mcm>
    Opened the real APR tutorial flip-chip design (doc/aprTut/examples/sample.zip ->
    APR_Training_FCsingledie.mcm), opened the APR dialog with the menu callback `pkg_router`
    (icp.men:1157), started routing with `FORM icp_pkg_router route`, and APR RAN A REAL,
    COMPLETE, HEADLESS AUTO-ROUTE: 178 passes over M1..M4 + BOTTOM, finishing at **91.4%
    completion, 460 connected / 43 unconnected, 1718 real vias, 00:02:37** (its own
    <design>_<stamp>_status.log). The saved design re-read as valid with all 1718 vias
    persisted. The journal shows "Launching the advanced package router. All actions will
    be blocked until routing is finished" — the process stays alive for the whole route,
    so this job legitimately takes minutes.

    Form field names come from share/pcb/text/forms/icp_pkg_router.form; the Run button is
    the MENUBUTTON field `route` and Cancel is `cancel` (`FORM icp_pkg_router cancel` is
    harmless after the route finishes — the dialog auto-closes, logged "Form not found").

    IMPORTANT — ENUM FIELD VALUES: The FORM command for icp_pkg_router POPUP (ENUMSET)
    fields requires the POPUP *display name* (the first string in each POP line of
    icp_pkg_router.form), NOT the internal token code. The token codes (COMPLETE,
    COMPLETION, RATIO, SPIRAL, ALL) are all rejected in -nograph mode with
    "Value for field is not legal"; the display names (100% Completion, Maximize for
    completion, Ratio, Spiral, All nets) are accepted (confirmed 2026-10-18). The token
    codes are short identifiers used in SKILL-level APIs; the FORM batch-replay command
    matches display names only. Multi-word display names work without quoting.

    NOTE on `apd.exe` launcher behaviour: `apd.exe` is a 307KB launcher stub that exits in
    ~20 ms after spawning the real `allegro.exe` child. Any job-status polling of the
    `apd.exe` process will report "succeeded" almost immediately while `allegro.exe` is
    still running the route. Callers that need to detect route completion should poll the
    APR `<design>_<stamp>_status.log` file (written by the router at the end of routing,
    before the save) for a non-zero "Total Pass" count, not the `apd.exe` job state.

FORM REPLAY MECHANICS (shared by zrouter and APR)
------------------------------------------------
The `-s <script.scr> -nograph <design>` launch replays the .scr top-to-bottom. To drive a
dialog without a GUI: issue the command that opens it (`zrouter` / `pkg_router`),
`setwindow form.<name>`, then one `FORM <form> <field> <value>` line per field (internal
field name, lowercase), then `FORM <form> <buttonField>` to fire a MENUBUTTON (the button's
internal NAME, not its caption), and for a modeless dialog `FORM <form> cancel` to close it
before any subsequent command. This is the same technique Cadence ships for netin
(share/pcb/examples/skill/ash/ashsched.il: `FORM niparams ...` then a button field,
inside `scriptmode +invisible`); the APR Run and Z-Router Run MENUBUTTONs were confirmed
to fire this way in -nograph mode, which is why both tools are `confirmed_live` and not
`built_untested`.

VERIFICATION (do not trust return code 0 alone)
-----------------------------------------------
Each tool returns the job record; `zrouter.log` (lowercase — the Z-Router's own log,
which Allegro writes into the DESIGN's directory / beside the board, NOT the job_dir and
NOT with uppercase `Zrouter.log`), the APR `<design>_<stamp>_status.log` files,
`apd.jrl`/`allegro.jrl`, and an independent `report.exe -w` re-read of the saved design
are the real success signals (see tool_status.TOOL_STATUS_NOTES for the live evidence
trail and exact counts). `run_allegro_zrouter` returns these machine-parsed as
`zrouter_result` (vias_added / errors / silence_no_op) by default.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sigrity_mcp.core import jobs as _jobs
from sigrity_mcp.core.config import settings
from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

# Z-Router's `execute` MENUBUTTON validates the form before it launches the I/O Pin
# Router. If the REALFILLIN fields (xgrid / ygrid / xoffset / yoffset / minspace) are
# left in their empty/uninitialized state when `execute` fires, the router validates
# them, finds them unset, and SILENTLY returns without routing: it does not write
# zrouter.log, does not add a single via, and emits no error anywhere. The journal logs
# `FORM zrouter execute` and moves straight to `cancel`, so the whole run looks
# "succeeded" with 0% completion. This is the silent-no-op that made a minimal
# `run_allegro_zrouter(board, control)` call add 0 vias while the identical call WITH
# grid/offset/minspace values set added a real 15. The form even ships a `MESSAGE
# nogrid "Grid must be greater than 0."` — a grid is mandatory. Defaults below are the
# values confirmed live to route the 50 mil-pitch demo BGA (pre_fanout.brd) to 15/15
# interior pins at minspace 3.0 (see this module's REPORT.md / bga_fanout evidence).
_ZROUTER_DEFAULT_XGRID = 10.0
_ZROUTER_DEFAULT_YGRID = 10.0
_ZROUTER_DEFAULT_XOFFSET = 0.0
_ZROUTER_DEFAULT_YOFFSET = 0.0
# minspace is the min via-to-pad-edge clearance (mil). 3.0 is the board's measured max
# working clearance for the 50 mil demo BGA; a tighter-pitch BGA needs it lower (the
# caller passes it explicitly for those). We never emit a minspace line for a None — no,
# we ALWAYS emit it (see above) so the real default here only matters if a caller
# explicitly passes 0.0. Kept a documented constant so the default is visible and tested.
_ZROUTER_DEFAULT_MINSPACE = 3.0


def _to_fwd(path: str) -> str:
    """Normalize a path to forward slashes for use inside a Cadence .scr command line."""
    return str(path).replace("\\", "/")


def _fmt_grid_value(value: float) -> str:
    """Render a grid/offset/minspace value for a FORM line with no trailing-0 ambiguity:
    an integer-valued float prints without a decimal point (the form reads both, but the
    confirmed-live scripts used `10.0`/`3.0`/`0.0` form, so we keep one decimal for
    non-integers and a clean `10.0` style)."""
    return f"{float(value):g}"


def _find_zrouter_log(board_file: str) -> Optional[Path]:
    """Locate the Z-Router's own `zrouter.log` after a run.

    Allegro's Z-Router writes `zrouter.log` (lowercase) into the DESIGN's directory
    (the directory of the board file it routed) — NOT the job's scratch job_dir that
    allegro.exe was launched from (confirmed live: every successful run's zrouter.log
    sat beside the routed board.brd, none ever appeared in the job_dir). On a
    case-insensitive filesystem a `Zrouter.log` probe matches; on a case-sensitive one
    it would not, so we probe both spellings and return the first real hit.
    """
    board_dir = Path(board_file).expanduser().resolve().parent
    for name in ("zrouter.log", "Zrouter.log", "ZROUTER.LOG"):
        candidate = board_dir / name
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    # Fall back to a non-empty case-insensitive scan of the board dir (covers any other
    # casing Allegro might choose) but ignore the .scr/journal we wrote ourselves.
    try:
        for entry in board_dir.iterdir():
            stem_match = entry.name.lower() == "zrouter.log"
            if stem_match and entry.is_file() and entry.stat().st_size > 0:
                return entry
    except OSError:
        pass
    return None


def _parse_zrouter_log(log_path: Optional[Path]) -> dict:
    """Parse zrouter.log into the machine-readable summary the tool returns.

    Returns a dict with:
      * `log_found`  — True if a real (non-empty) zrouter.log exists. When False the
        router did NOT actually execute (the silent-no-op signature); the caller turns
        that into an explicit, explained result instead of a bare 'succeeded' with 0.
      * `vias_added` — int, the "number pins with vias added" total (summed across every
        refdes the file routes), or None when the log is absent/unparseable.
      * `errors`     — Total number of error messages (int) or None.
      * `warnings`   — Total number of warning messages (int) or None.
      * `legal_connections` — "Number of legal I/O Pin Connections found in the file" or None.
      * `file_errors`       — "Number of errors found in the file" or None.
      * `per_pin_failures`  — list of the "Unable to connect any vias to pin ..." lines
        (the per-pin geometry/minspace failures from REPORT.md), capped.
      * `silent_no_op`      — True when log_found is False AND vias_added would be 0:
        the router never ran at all (no log written), the dangerous case this whole
        fix exists to surface.
    """
    result = {
        "log_found": False,
        "vias_added": None,
        "errors": None,
        "warnings": None,
        "legal_connections": None,
        "file_errors": None,
        "per_pin_failures": [],
        "silent_no_op": False,
    }
    if log_path is None:
        result["silent_no_op"] = True
        return result
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        result["silent_no_op"] = True
        return result
    result["log_found"] = bool(text.strip())
    if not result["log_found"]:
        result["silent_no_op"] = True
        return result
    pins_added = 0
    saw_any = False
    for line in text.splitlines():
        m = re.search(r"number pins with vias added[:\s]*(\d+)", line, re.IGNORECASE)
        if m:
            pins_added += int(m.group(1))
            saw_any = True
    if saw_any:
        result["vias_added"] = pins_added
    m = re.search(r"Total number of error messages[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        result["errors"] = int(m.group(1))
    m = re.search(r"Total number of warning messages[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        result["warnings"] = int(m.group(1))
    m = re.search(r"Number of legal I/O Pin Connections found in the file[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        result["legal_connections"] = int(m.group(1))
    m = re.search(r"Number of errors found in the file[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        result["file_errors"] = int(m.group(1))
    failures = [
        re.sub(r"\s+", " ", line.strip())
        for line in text.splitlines()
        if "unable to connect any vias to pin" in line.lower()
    ]
    result["per_pin_failures"] = failures[:50]
    return result


def _zrouter_result_note(rz: dict) -> str:
    """Human-readable summary line for the tool result's `note`, keyed off the parsed
    zrouter.log so the silent-0-via no-op can never masquerade as a clean success."""
    if not rz["log_found"]:
        return (
            "Z-Router DID NOT actually run: no zrouter.log was produced, so 0 vias were "
            "added and the board is unchanged. This is the silent-no-op signature — most "
            "commonly the REALFILLIN grid/offset/minspace form fields were empty when "
            "`FORM zrouter execute` fired. Re-run with explicit x_grid/y_grid/min_space "
            "(this tool now sets them by default) and confirm zrouter.log appears beside "
            "the board. Do NOT treat state=succeeded as proof of routing."
        )
    if rz.get("vias_added"):
        return (
            f"Z-Router ran and added vias to {rz['vias_added']} pin(s); "
            f"{rz.get('errors', 0)} error(s), {rz.get('warnings', 0)} warning(s) in zrouter.log."
            + (
                " Some pins could not be escaped — see per_pin_failures; lower min_space "
                "(via-to-pad-edge clearance) below the board's pitch/2 knee."
                if rz.get("errors")
                else ""
            )
        )
    if rz.get("errors"):
        return (
            f"Z-Router ran but added 0 vias with {rz['errors']} error(s): every matching "
            "pin failed to connect, typically because min_space is above the board's "
            "actual via-to-pad-edge clearance. See per_pin_failures. Lower min_space."
        )
    return (
        "Z-Router ran cleanly and matched pins, but 0 vias were added — on an "
        "already-routed/fabricated board that is a legitimate no-op (nothing left to "
        "route); on an unrouted BGA it means no pin qualified (check the refdes/net in "
        "the control file and the extend_layer subclass)."
    )


@mcp.tool
async def run_apd_batch_script(
    design_file: str,
    skill_line: Optional[str] = None,
    output_file: Optional[str] = None,
    product: str = "Allegro_Adv_Packaging_Plus",
) -> dict:
    """Run a SKILL command inside Allegro Package Designer (APD) against a .mcm/.sip package design
    in non-graphic batch mode (`apd -product <tier> -nograph -s <script.scr> <design.mcm>`), as a
    background job. This is the confirmed-live headless base for all APD/apd.exe automation —
    load a package design, execute SKILL, save, exit, no GUI. Call load_skill('sigrity-cad')
    for the full verified playbook. Use run_allegro_apr (this module) for the Advanced Package
    Router specifically."""
    clear_stale_design_lock(design_file)
    session = tcl_sessions.create("apd")

    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    if skill_line:
        tcl_sessions.add_line(session.session_id, f"skill {skill_line}")
    if output_file:
        clean_out = _to_fwd(output_file)
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?design {skill_str(clean_out)} ?mode {skill_str('nocheck')})")
    else:
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?mode {skill_str('nocheck')})")
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="apd",
        tcl_arg_flag="-s",
        build_args=["-product", product, "-nograph"],
        extra_args=[design_file],
        script_filename="apd_batch.scr",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def run_allegro_zrouter(
    board_file: str,
    control_file: str,
    output_file: Optional[str] = None,
    x_grid: Optional[float] = None,
    y_grid: Optional[float] = None,
    x_offset: Optional[float] = None,
    y_offset: Optional[float] = None,
    min_space: Optional[float] = None,
    wait_for_completion: bool = True,
    wait_timeout_seconds: Optional[float] = None,
) -> dict:
    """Run Allegro's Z-Router (via/pin-escape fanout routing) headlessly via
    `allegro -s <script.scr> -nograph <board.brd>` + FORM replay of the zrouter dialog.
    `control_file` is the Z-Router Connections Control File
    (<I/O refdes> <net> <extend_layer> <min#vias> [max#vias]; `extend_layer` is a BARE ETCH
    subclass name like BOTTOM/TOP, NOT ETCH/BOTTOM).

    CRITICAL: x_grid, y_grid, x_offset, y_offset and min_space are ALWAYS written to the
    form (defaulting to 10/10/0/0 and min_space 3.0), because leaving the REALFILLIN
    fields empty makes `FORM zrouter execute` SILENTLY no-op — the router never runs, no
    zrouter.log is written, 0 vias are added, and the job still reports 'succeeded'.
    Passing explicit values (or none — the defaults now fill them) is the difference
    between a real fanout and a silent 0. CONFIRMED LIVE headless (real new vias added +
    independently re-read). `wait_for_completion=True` (the default, correct for BGA
    fanout which finishes in seconds to a couple minutes) blocks until the job finishes
    and returns a `zrouter_result` parsed from the real `zrouter.log` beside the board:
    `vias_added`, `errors`, and a `silent_no_op` flag that is True iff the router never
    actually ran. Set `wait_for_completion=False` to just launch and poll the job_id via
    the platform job tools instead. Call load_skill('sigrity-cad') for the verified
    playbook."""
    # --- Pre-flight validation: fail fast and LOUDLY on inputs that would otherwise
    # launch a doomed/silent job, instead of letting Allegro open a design and do nothing.
    board = Path(board_file).expanduser()
    ctrl = Path(control_file).expanduser()
    if not board.is_file():
        return {"error": f"board_file not found: {board_file}", "state": "not_launched"}
    if board.suffix.lower() not in (".brd", ".mcm"):
        return {"error": f"board_file does not look like an Allegro design (.brd/.mcm): {board_file}", "state": "not_launched"}
    if not ctrl.is_file():
        return {"error": f"control_file not found: {control_file} (the Connections Control File must be a real, existing .txt/.cnv path)", "state": "not_launched"}

    # Resolve the REAL values that will be written to the form, applying the documented
    # defaults so `execute` is never fired against empty REALFILLIN fields (the silent
    # no-op). Explicit caller values always win.
    xg = _ZROUTER_DEFAULT_XGRID if x_grid is None else float(x_grid)
    yg = _ZROUTER_DEFAULT_YGRID if y_grid is None else float(y_grid)
    xo = _ZROUTER_DEFAULT_XOFFSET if x_offset is None else float(x_offset)
    yo = _ZROUTER_DEFAULT_YOFFSET if y_offset is None else float(y_offset)
    ms = _ZROUTER_DEFAULT_MINSPACE if min_space is None else float(min_space)
    # The form rejects a grid of 0 (shipped MESSAGE nogrid "Grid must be greater than 0")
    # and a negative spacing is nonsensical — reject before launching, not after a 5s no-op.
    if xg <= 0 or yg <= 0:
        return {"error": f"x_grid and y_grid must both be > 0 (got x_grid={xg}, y_grid={yg}); the Z-Router requires a non-zero via grid", "state": "not_launched"}
    if ms < 0:
        return {"error": f"min_space must be >= 0 (got {ms}); it is the min via-to-pad-edge clearance in mils", "state": "not_launched"}

    clear_stale_design_lock(board_file)
    session = tcl_sessions.create("allegro")

    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    tcl_sessions.add_line(session.session_id, "zrouter")
    tcl_sessions.add_line(session.session_id, "setwindow form.zrouter")
    tcl_sessions.add_line(session.session_id, f"FORM zrouter filename {_to_fwd(control_file)}")
    # ALWAYS set the grid/offset/minspace REALFILLIN fields before firing `execute`.
    # Omitting any of them is the root cause of the silent-0-via no-op (see the
    # _ZROUTER_DEFAULT_* constants' comment above and this module's docstring).
    tcl_sessions.add_line(session.session_id, f"FORM zrouter xgrid {_fmt_grid_value(xg)}")
    tcl_sessions.add_line(session.session_id, f"FORM zrouter ygrid {_fmt_grid_value(yg)}")
    tcl_sessions.add_line(session.session_id, f"FORM zrouter xoffset {_fmt_grid_value(xo)}")
    tcl_sessions.add_line(session.session_id, f"FORM zrouter yoffset {_fmt_grid_value(yo)}")
    tcl_sessions.add_line(session.session_id, f"FORM zrouter minspace {_fmt_grid_value(ms)}")
    # Fire the RUN button: the MENUBUTTON's internal field name is `execute` (display "Run").
    # `FORM zrouter Run` (the caption) fails in -nograph mode with "Form field label not found".
    tcl_sessions.add_line(session.session_id, "FORM zrouter execute")
    # Close the modeless dialog (MENUBUTTON `cancel`, display "Close") BEFORE the save, or the
    # next command is refused with "Finish current command first" and the save silently no-ops.
    tcl_sessions.add_line(session.session_id, "FORM zrouter cancel")
    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    if output_file:
        clean_out = _to_fwd(output_file)
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?design {skill_str(clean_out)} ?mode {skill_str('nocheck')})")
    else:
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?mode {skill_str('nocheck')})")
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="allegro",
        tcl_arg_flag="-s",
        build_args=["-nograph"],
        extra_args=[board_file],
        script_filename="zrouter_run.scr",
    )
    base = {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
    if not wait_for_completion:
        # Caller opts to launch-and-poll via the platform job tools. Tell them where the
        # real router log lands so a later poll doesn't mistake its absence for 0 vias.
        base["note"] = (
            "Launched without waiting. The Z-Router writes zrouter.log into the BOARD's "
            f"directory ({Path(board_file).parent}), not the job_dir. Poll "
            "wait_for_job/get_job_status, then read zrouter.log to confirm vias were added "
            "(its 'number pins with vias added' line is the real success signal, not rc=0)."
        )
        return base

    # Wait for completion (real time-bounded; BGA fanout is fast, not a multi-hour SIM).
    timeout = float(wait_timeout_seconds) if wait_timeout_seconds is not None else max(
        float(settings.allegro_session_stall_timeout_seconds), 60.0
    )
    try:
        finished = await _jobs.job_manager.wait(record.job_id, timeout=timeout)
    except Exception:
        finished = record
    base["state"] = finished.state
    base["returncode"] = finished.returncode
    # Parse the REAL router log (zrouter.log, in the board's dir) into an honest result.
    log_path = _find_zrouter_log(board_file)
    base["zrouter_log"] = str(log_path) if log_path is not None else None
    rz = _parse_zrouter_log(log_path)
    base["zrouter_result"] = rz
    base["note"] = _zrouter_result_note(rz)
    if finished.state != "succeeded":
        base["failure_note"] = getattr(finished, "failure_note", "") or ""
    return base


# FORM icp_pkg_router enum fields require the POPUP *display name* (first string in the
# POP line of icp_pkg_router.form), NOT the internal token code — token codes are rejected
# in -nograph mode with "Value for field is not legal". Mapping short API tokens to the
# display names confirmed to work with the FORM command.
_APR_GOAL_DISPLAY = {
    "COMPLETE": "100% Completion",
    "ESTIMATE": "Estimate Only",
    "FANOUT": "Fan-out Only",
    "PASSES": "Maximum Passes",
}
_APR_PRIORITY_DISPLAY = {
    "COMPLETION": "Maximize for completion",
    "FLOW": "Maximize for flow",
    "MULTI_LAYER": "Allow routing vias other then escapes",
}
_APR_DETOUR_DISPLAY = {
    "RATIO": "Ratio",
    "LENGTH": "Length",
}
_APR_VIA_DISPLAY = {
    "SPIRAL": "Spiral",
    "STAGGER": "Stagger",
    "STAIRCASE": "Staircase",
}
_APR_NET_DISPLAY = {
    "ALL": "All nets",
    "SIGNALS": "Signal nets",
    "SELECTED": "Selected nets",
    "NONSELECTED": "Non-selected nets",
}


@mcp.tool
async def run_allegro_apr(
    design_file: str,
    output_file: Optional[str] = None,
    routing_goal: str = "COMPLETE",
    routing_priority: str = "COMPLETION",
    detour_type: str = "RATIO",
    via_method: str = "SPIRAL",
    net_filter: str = "ALL",
    product: str = "Allegro_Adv_Packaging_Plus",
) -> dict:
    """Run the Advanced Package Router (APR) — the any-angle topological auto-router for
    dense flip-chip package substrates — headlessly, as a background job, via
    `apd -product <APD+ tier> -option "Advanced Package Router" -nograph -s <script.scr>
    <design.mcm>`. The .scr opens the APR dialog with the menu callback `pkg_router`, fires
    routing with `FORM icp_pkg_router route`, and saves. CONFIRMED LIVE headless: a real
    flip-chip tutorial design routed to 91.4% completion / 1718 real vias, all persisted and
    independently re-read. This job can take MINUTES (APR blocks the process for the whole
    route pass sequence) — do NOT wait on it as a quick call. Call load_skill('sigrity-cad')
    for the verified playbook. Enum args (token form):
    routing_goal={COMPLETE,ESTIMATE,FANOUT,PASSES}, routing_priority={COMPLETION,FLOW,
    MULTI_LAYER}, detour_type={RATIO,LENGTH}, via_method={SPIRAL,STAGGER,STAIRCASE},
    net_filter={ALL,SIGNALS,SELECTED,NONSELECTED}."""
    clear_stale_design_lock(design_file)
    session = tcl_sessions.create("apd")

    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    # `pkg_router` is the menu callback (icp.men) that opens the Advanced Package Router dialog.
    tcl_sessions.add_line(session.session_id, "pkg_router")
    tcl_sessions.add_line(session.session_id, "setwindow form.icp_pkg_router")
    # FORM icp_pkg_router enum fields require POPUP display names (confirmed 2026-10-18):
    # token codes (COMPLETE, COMPLETION, RATIO, SPIRAL, ALL) are all rejected with
    # "Value for field is not legal" in -nograph mode; display names (100% Completion,
    # Maximize for completion, Ratio, Spiral, All nets) are accepted. See the
    # _APR_*_DISPLAY mappings above for the authoritative token→display-name table.
    tcl_sessions.add_line(session.session_id, f"FORM icp_pkg_router routing_goal {_APR_GOAL_DISPLAY.get(routing_goal, routing_goal)}")
    tcl_sessions.add_line(session.session_id, f"FORM icp_pkg_router routing_priority {_APR_PRIORITY_DISPLAY.get(routing_priority, routing_priority)}")
    tcl_sessions.add_line(session.session_id, f"FORM icp_pkg_router detour_type {_APR_DETOUR_DISPLAY.get(detour_type, detour_type)}")
    tcl_sessions.add_line(session.session_id, f"FORM icp_pkg_router via_method {_APR_VIA_DISPLAY.get(via_method, via_method)}")
    tcl_sessions.add_line(session.session_id, f"FORM icp_pkg_router net_filter {_APR_NET_DISPLAY.get(net_filter, net_filter)}")
    # Fire the ROUTE button: MENUBUTTON internal field name `route` (display "Route"). This
    # blocks until routing finishes (journal: "All actions will be blocked until routing is
    # finished or cancelled").
    tcl_sessions.add_line(session.session_id, "FORM icp_pkg_router route")
    # Close the dialog after the route (harmless if APR already auto-closed it — logged
    # "Form not found"); required so the next command (the save) isn't refused.
    tcl_sessions.add_line(session.session_id, "FORM icp_pkg_router cancel")
    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    if output_file:
        clean_out = _to_fwd(output_file)
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?design {skill_str(clean_out)} ?mode {skill_str('nocheck')})")
    else:
        tcl_sessions.add_line(session.session_id, f"skill (axlSaveDesign ?mode {skill_str('nocheck')})")
    tcl_sessions.add_line(session.session_id, "quit")

    record = await run_session(
        session.session_id,
        tool="apd",
        tcl_arg_flag="-s",
        build_args=[
            "-product", product,
            "-option", "Advanced Package Router",
            "-nograph",
        ],
        extra_args=[design_file],
        script_filename="apr_run.scr",
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
