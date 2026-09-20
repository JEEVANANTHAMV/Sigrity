"""Allegro mechanical-data import/export and blank-board creation — CONFIRMED LIVE.

This suite previously had no way to create a brand-new Allegro `.brd` at all — every
existing CAD tool (`allegro_tools.py`, `allegro_geometry_tools.py`, ...) assumes a board
already exists on disk and is passed in as `allegro_run_session`'s own positional
argument. `axlOpenDesign`'s own doc page (share/pcb/examples/skill/DOC/FUNCS/
axlOpenDesign.txt) confirms why a pure-SKILL "create from nothing" path doesn't really
exist headlessly either: opening a design name that doesn't exist on disk pops the
interactive "Drawing Parameters" form, which has no scripted equivalent anywhere in the
~840-file SKILL function reference.

The real, confirmed-live answer is `dxf2a.exe` — a standalone Allegro CLI translator
whose own `-help` banner is explicit that its default mode (no `-g` flag) is "new
design, only": given a DXF mechanical outline plus a Layer Conversion File, it writes a
brand-new `.brd`/`.dra` from scratch, no existing design or GUI required. Confirmed live
on this machine using Cadence's own shipped tutorial sample
(doc/wb_tut/examples/Module_1/flag.dxf + flag_l.cnv): `dxf2a.exe -u MILS -a 2 flag_l.cnv
flag.dxf out.brd` produced a real 203456-byte `.brd`, and — independent verification,
bypassing SKILL/dxf2a entirely — re-opening that exact file with `report.exe` (already
`confirmed_live` elsewhere in this suite) produced a real summary showing 2 routing
layers and drawing extents matching the DXF outline's geometry, with `DRC State: UP TO
DATE`. IMPORTANT CONFIRMED QUIRKS from that same live run:
  - `dxf2a.exe` exits with returncode 1 even on this fully successful run (the job log's
    final line reads "dxf2a complete.") — the same "nonzero exit on real success" pattern
    already documented for `allegro_dbdoctor`/`artwork.exe`/`specctra` elsewhere in this
    suite. Do not treat this tool's job `state == "failed"` as proof of failure; read the
    job log for "dxf2a complete." first.
  - The sample `flag_l.cnv` mapped a DXF layer to the `CONDUCTOR` class, which a
    brand-new empty design's default class table doesn't yet recognize — this produced
    repeated `ERROR: Invalid class CONDUCTOR.` lines in the log, but did NOT stop dxf2a
    from completing and writing a valid board. A caller supplying their own
    `cnv_file` should expect the same: read the job log for `Invalid class` lines to see
    which DXF layers didn't land, rather than assuming a produced `.brd` means every
    layer mapped correctly.
  - Flag syntax is confirmed SPACE-separated (`-u MILS`, `-a 2`), NOT attached
    (`-uMILS`/`-a2` was live-tested and rejected outright with "ERROR: Invalid program
    arguments.").

`a2dxf.exe` (the reverse export direction — Allegro `.brd` mechanical data out to DXF)
is confirmed live the same way: run against this suite's own real routed sample board
(tools/capture/samples/PCB-Layout/Fault-Detector/allegro/
fault-detector_allegro_routed.brd), it produced a genuine, valid 6464-byte DXF (real
`SECTION`/`HEADER`/`$ACADVER`/`ENTITIES`/`EOF` structure, confirmed by reading the file
content directly), exit code 0, log ending "a2dxf complete."

For a caller who doesn't have a DXF outline at all and just wants an empty starting
board, `allegro_new_blank_board` is a plain filesystem copy (no Cadence process
involved) of a real shipped blank template,
`share/cdssetup/ult/2layer.brd` under `SIGRITY_CADENCE_SPB_HOME` — a genuine 2-layer
blank Allegro board Cadence itself ships as its own "Universal Land Pattern Template"
seed file (confirmed present on disk, ~322KB). This mirrors this suite's existing
`copy_file` (platform/file_tools.py) rather than inventing a new mechanism, and is the
same practical technique Cadence's own "Allegro Board File Project Creation Tutorial"
documents for starting new designs from a checked, approved template rather than from
an interactive New-Design wizard every time.

Investigated and confirmed NOT automatable this same pass, for honesty rather than
silent omission (matching this suite's treatment of `zrouter`/Aurora elsewhere):
`convert_gerber.exe` (Gerber -> Allegro import) and `EagleImport\\Eagle2Cp.exe` (Eagle ->
Concept-HDL bridge) are both real executables, but both are interactive stdin-prompt
loops with no `-help`/flag-driven non-interactive mode found (`convert_gerber.exe`
repeatedly re-prompts "Existing layout file name (*.brd):" forever; `Eagle2Cp.exe` halts
on "waiting for forcelabel parameter (yes or no)") — neither is wrapped here.

REAL FAILURE MODE FOUND WHILE BUILDING THIS MODULE, now fixed: `dxf2a.exe`/`a2dxf.exe`
run with the job's own scratch directory as their working directory (same as every other
`submit_job`-based tool). A caller-supplied *relative* `cnv_file`/`dxf_file` path that
doesn't resolve from THAT directory doesn't fail cleanly — dxf2a/a2dxf instead fall back
to their own interactive prompt ("Conversion File (*.cnv): ") and re-prompt in a tight
loop reading from a stdin that's never connected, generating output fast enough to hit
this suite's 200MB job-log watchdog (`core/config.py`'s `max_log_bytes`, itself added
after an earlier real incident with this exact "bad path -> unbounded output loop"
failure class in `report.exe`/`step_out.exe`/`ipc356_out.exe`) within seconds — live
reproduced twice while testing this module (two ~205-209MB `run.log` files). Both tools
below now resolve `cnv_file`/`dxf_file`/`board_file` to absolute paths (relative to the
MCP server's own working directory, not the job's) before building argv, specifically to
close off the most common cause of this. A genuinely wrong/nonexistent absolute path
will still trigger the same loop — if a job runs long past dxf2a/a2dxf's normal few-
second completion time, suspect this before assuming a hang.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal, Optional

from sigrity_mcp.core.config import settings
from sigrity_mcp.core.paths import resolve_path as _resolve
from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp

_UNITS = Literal["MILS", "INCHES", "CM", "MM", "MICRONS"]

# Relative to SIGRITY_CADENCE_SPB_HOME — confirmed present on disk, a real shipped blank
# 2-layer board (~322KB), not a placeholder/template with unresolved @project@ tokens.
BLANK_BOARD_TEMPLATE = Path("share") / "cdssetup" / "ult" / "2layer.brd"


@mcp.tool
async def allegro_import_dxf(
    cnv_file: str,
    dxf_file: str,
    board_file: str,
    update_existing: bool = False,
    output_units: Optional[_UNITS] = None,
    original_units: Optional[_UNITS] = None,
    accuracy: Optional[int] = None,
    use_default_text: bool = False,
) -> dict:
    """Import a DXF mechanical outline into Allegro — CREATES A BRAND-NEW .brd BY DEFAULT (CONFIRMED LIVE — see module docstring).

    Runs `dxf2a.exe [-u <output_units>] [-v <original_units>] [-a <accuracy>] [-g] [-t]
    <cnv_file> <dxf_file> <board_file>` as a background job.

    `update_existing=False` (the default) is dxf2a's real "new design, only" mode —
    `board_file` should NOT already exist; this is this suite's confirmed way to create
    a genuinely new Allegro `.brd` from scratch (see the live evidence in this module's
    docstring). Pass `update_existing=True` to instead merge the DXF data into an
    ALREADY-existing `board_file` (dxf2a's `-g`, "increment" mode) — e.g. to add a
    mechanical keepout/outline to a board someone else already started.

    `cnv_file` is a plain-text Layer Conversion File mapping DXF layer names to Allegro
    `CLASS!`/`SUBCLASS!` pairs — see dxf2a's own `-help` and the confirmed real sample
    at doc/wb_tut/examples/Module_1/flag_l.cnv for the exact grammar. `output_units`
    defaults to MILS for a new design if omitted; `original_units` defaults to whatever
    the DXF file itself specifies; `accuracy` is decimal places (0-4). `use_default_text`
    (dxf2a's `-t`) reuses existing/default Allegro text blocks instead of creating one
    per distinct DXF text height.

    Returns a job_id immediately; poll it with get_job_status/wait_for_job. IMPORTANT:
    dxf2a exits with returncode 1 even on a fully successful run (confirmed live) — read
    the job log for a trailing "dxf2a complete." line, and for any "ERROR: Invalid
    class" lines (a layer in `cnv_file` that the target design's class table doesn't
    recognize — the import still completes, just without that layer's geometry landing
    correctly), rather than trusting job state alone.
    """
    args: list[str] = []
    if output_units:
        args += ["-u", output_units]
    if original_units:
        args += ["-v", original_units]
    if accuracy is not None:
        args += ["-a", str(accuracy)]
    if update_existing:
        args.append("-g")
    if use_default_text:
        args.append("-t")
    args += [_resolve(cnv_file), _resolve(dxf_file), _resolve(board_file)]
    record = await submit_job(tool="dxf2a", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def allegro_export_dxf(
    cnv_file: str,
    dxf_file: str,
    board_file: str,
    output_units: Optional[_UNITS] = None,
    accuracy: Optional[int] = None,
    dxf_format: Optional[Literal["12", "14"]] = None,
    export_drill_info: bool = False,
) -> dict:
    """Export Allegro mechanical data to DXF (CONFIRMED LIVE — see module docstring).

    Runs `a2dxf.exe [-u <output_units>] [-a <accuracy>] [-f <dxf_format>] [-d]
    <cnv_file> <dxf_file> <board_file>` as a background job. Confirmed live against a
    real routed sample board, producing a genuine, valid DXF file.

    `cnv_file` is the same Layer Conversion File format `allegro_import_dxf` takes (maps
    Allegro `CLASS!`/`SUBCLASS!` pairs to DXF layer names for the export direction).
    `output_units`/`accuracy` default to the source board's own database units/accuracy
    if omitted. `dxf_format` selects the DXF revision to write ("12" or "14"; a2dxf's
    own default is "12"). `export_drill_info` (a2dxf's `-d`) additionally exports NC_DRILL
    data.

    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args: list[str] = []
    if output_units:
        args += ["-u", output_units]
    if accuracy is not None:
        args += ["-a", str(accuracy)]
    if dxf_format:
        args += ["-f", dxf_format]
    if export_drill_info:
        args.append("-d")
    args += [_resolve(cnv_file), _resolve(dxf_file), _resolve(board_file)]
    record = await submit_job(tool="a2dxf", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def allegro_new_blank_board(output_board_file: str, overwrite: bool = False, template_file: Optional[str] = None) -> dict:
    """Create a brand-new, empty Allegro board by copying a real blank template — no DXF outline needed.

    Plain filesystem copy (no Cadence process launched), for the case where
    `allegro_import_dxf` isn't applicable because no DXF mechanical outline exists yet.
    Defaults to Cadence's own shipped blank 2-layer board template
    (`share/cdssetup/ult/2layer.brd` under SIGRITY_CADENCE_SPB_HOME, confirmed present
    on disk) — pass `template_file` to start from a different real board instead (e.g.
    an internally-approved company template, following the same "start every new design
    from a checked template" practice Cadence's own documentation recommends over
    re-running an interactive New Design wizard each time).

    Fails with a clear error if `output_board_file` already exists and `overwrite=False`
    (the default). Once copied, open it with `allegro_run_session`/SKILL tools the same
    as any other `.brd` to rename it, set up a stackup, add an outline, etc. — this tool
    only stages the starting file; it does not open, rename, or otherwise script Allegro
    itself, so it works even in environments where Allegro's own batch reliability
    (documented elsewhere in this suite) is in question.
    """
    src = Path(template_file) if template_file else (settings.cadence_spb_home / BLANK_BOARD_TEMPLATE)
    dst = Path(output_board_file)
    if not src.is_file():
        raise FileNotFoundError(f"template board does not exist or is not a file: {src}")
    if dst.exists() and not overwrite:
        raise FileExistsError(f"output_board_file already exists (pass overwrite=True to replace it): {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"template_file": str(src), "output_board_file": str(dst), "size_bytes": dst.stat().st_size}
