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
   .brd (doc/cmadvcnstut/examples/start.brd) with a Connections Control File. The board
   gained 2 REAL new vias (a before/after `report.exe -v sum` via-count diff of 0 -> 2;
   "number pins with vias added: 2" in Zrouter.log), a genuine Zrouter.log was written,
   and the saved board re-read as valid (186 drilled holes, 0 DRC errors, 100% connection
   completeness). The exact form field names (from share/pcb/text/forms/zrouter.form) and
   the two non-obvious requirements are the load-bearing detail:
     * `FORM zrouter <field> <value>` uses the form's INTERNAL field NAMES (lowercase):
       filename / xgrid / ygrid / xoffset / yoffset / minspace — NOT the display text
       ("X-grid spacing:") and NOT the older `grid` token.
     * The RUN button is the MENUBUTTON field `execute` and the CLOSE button is the
       MENUBUTTON field `cancel` (their display labels are "Run"/"Close"). In -nograph
       mode `FORM zrouter Run` fails with "Form field label not found"; `FORM zrouter
       execute` runs the router. A bare `setwindow pcb` after execute is NOT enough — the
       modeless dialog then blocks the next command ("Finish current command first"), so
       `FORM zrouter cancel` must be issued to close the dialog before the save.

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
Each tool returns the job record; `Zrouter.log`, the APR `<design>_<stamp>_status.log`
files, `apd.jrl`/`allegro.jrl`, and an independent `report.exe -w` re-read of the saved
design are the real success signals (see tool_status.TOOL_STATUS_NOTES for the live
evidence trail and exact counts).
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.skillscript import skill_str
from sigrity_mcp.core.tclsession import clear_stale_design_lock, run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp


def _to_fwd(path: str) -> str:
    """Normalize a path to forward slashes for use inside a Cadence .scr command line."""
    return str(path).replace("\\", "/")


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
) -> dict:
    """Run Allegro's Z-Router (via/pin-escape fanout routing) headlessly via
    `allegro -s <script.scr> -nograph <board.brd>` + FORM replay of the zrouter dialog, as a
    background job. `control_file` is the Z-Router Connections Control File
    (<I/O refdes> <net> <extend_layer> <min#vias> [max#vias]; `extend_layer` is a BARE ETCH
    subclass name like BOTTOM/TOP, NOT ETCH/BOTTOM). Grid/offset/min-space args are optional.
    CONFIRMED LIVE headless (real new vias added + independently re-read). This supersedes the
    older interactive-GUI-session implementation — see this module's docstring. Call
    load_skill('sigrity-cad') for the verified playbook."""
    clear_stale_design_lock(board_file)
    session = tcl_sessions.create("allegro")

    tcl_sessions.add_line(session.session_id, "setwindow pcb")
    tcl_sessions.add_line(session.session_id, "zrouter")
    tcl_sessions.add_line(session.session_id, "setwindow form.zrouter")
    tcl_sessions.add_line(session.session_id, f"FORM zrouter filename {_to_fwd(control_file)}")
    if x_grid is not None:
        tcl_sessions.add_line(session.session_id, f"FORM zrouter xgrid {x_grid}")
    if y_grid is not None:
        tcl_sessions.add_line(session.session_id, f"FORM zrouter ygrid {y_grid}")
    if x_offset is not None:
        tcl_sessions.add_line(session.session_id, f"FORM zrouter xoffset {x_offset}")
    if y_offset is not None:
        tcl_sessions.add_line(session.session_id, f"FORM zrouter yoffset {y_offset}")
    if min_space is not None:
        tcl_sessions.add_line(session.session_id, f"FORM zrouter minspace {min_space}")
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
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


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
