"""Allegro design-data extraction — standalone CLI, no SKILL session needed.

Confirmed live on this machine (help banner and argument-parsing only — see caveat
below): `designextractor.exe -help` prints a full Boost-style usage banner
(`-p/--proj <file>`, `-o/--out <file>`, `-u/--elastic-url <url>`, `-f/--format-pretty`,
`-c/--connectivityserver-as-source`) — a standalone tool that dumps a design's
connectivity/parasitic data to JSON, optionally pushing it straight to an Elasticsearch
endpoint via `-u`. Distinct from Sigrity's own extraction tools (Clarity3D/XtractIM,
Domain 3) — this reads Allegro's own design database/connectivity representation rather
than doing EM/parasitic solving.

IMPORTANT, confirmed live: `-p/--proj` genuinely requires a `.cpm`/`.sdax` project file
— running it against a raw `.brd` (as this suite's other CAD tools take directly) failed
immediately with argument-parsing rejection, re-printing the usage banner. No populated
`.cpm`/`.sdax` project instance was found on this machine to test end-to-end (the ones
shipped under `share/cdssetup/pcbdw/workspaces/` are unfilled `@project@.cpm` templates,
not real projects) — treat `run_allegro_design_extractor` as `built_untested` until run
against a real `.cpm`/`.sdax` file. Do not pass a `.brd` file to this tool.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_allegro_design_extractor(
    project_file: str,
    output_file: Optional[str] = None,
    pretty_format: bool = True,
    elastic_url: Optional[str] = None,
    connectivity_server_as_source: bool = False,
) -> dict:
    """Extract an Allegro design's connectivity/data model to JSON, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-p", project_file]
    if output_file:
        args += ["-o", output_file]
    if pretty_format:
        args.append("-f")
    if elastic_url:
        args += ["-u", elastic_url]
    if connectivity_server_as_source:
        args.append("-c")
    record = await submit_job(tool="allegro_designextractor", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


# CONFIRMED LIVE 2026-10-02: the view-name/field-name keywords below are copied from
# Cadence's own shipped extract command files (`share/pcb/text/views/*.txt` -- e.g.
# bom_rep.txt, net_rep.txt, cmp_rep.txt, cpin_bv.txt, tstpoint.txt, drc_rep.txt), NOT
# invented. This replaces an earlier version of this dict that used made-up view names
# ("NETS", "COMPONENTS", "PINS", "TESTPOINTS", "DRC") and made-up field names
# ("DEVICE", "VALUE", "TOLERANCE", "COMP_LOCATION_X/Y", "COMP_ROTATION", "COMP_MIRRORED",
# "TESTPOINT_NAME", "DRC_ERROR_NAME", ...) that extracta.exe genuinely rejects outright
# with `ERROR(SPMHDX-10): Illegal view name.` (confirmed live via the real per-job
# extract.log -- NOT run.log, which only ever says "see extract.log for errors" --
# extract.log is written to the submitted job's own job_dir/cwd, not next to
# board_file/output_file, which is why this failure went undiagnosed across many calls
# during the campaign: nothing ever read the real extract.log). Live-reproduced with the
# OLD templates (10 consecutive run_allegro_extracta + wait_for_job calls, every one
# failing with returncode 2, across two separate campaign conversations) and fixed by
# switching to these real view/field names, confirmed working end-to-end against a real
# sample board (zero errors in extract.log, real non-empty output file, returncode 0).
EXTRACTION_TEMPLATES: dict[str, str] = {
    "bom": (
        "COMPONENT\n"
        "COMP_BOM_IGNORE = ''\n"
        "SYM_NAME\n"
        "COMP_DEVICE_TYPE\n"
        "COMP_VALUE\n"
        "COMP_TOL\n"
        "COMP_CLASS\n"
        "REFDES_SORT\n"
        "REFDES\n"
    ),
    "nets": (
        "LOGICAL_PIN\n"
        "NET_NAME_SORT\n"
        "NET_NAME\n"
        "REFDES_SORT\n"
        "REFDES\n"
        "PIN_NUMBER_SORT\n"
        "PIN_NUMBER\n"
        "FUNC_DES_SORT\n"
        "FUNC_DES\n"
        "PIN_NAME\n"
    ),
    "components": (
        "COMPONENT\n"
        "REFDES_SORT\n"
        "REFDES\n"
        "COMP_DEVICE_TYPE\n"
        "COMP_VALUE\n"
        "COMP_TOL\n"
        "COMP_PACKAGE\n"
        "SYM_X\n"
        "SYM_Y\n"
        "SYM_ROTATE\n"
        "SYM_MIRROR\n"
    ),
    "pins": (
        "COMPONENT_PIN\n"
        "REFDES_SORT\n"
        "PIN_NUMBER_SORT\n"
        "REFDES\n"
        "PIN_NUMBER\n"
        "PIN_X\n"
        "PIN_Y\n"
        "PAD_STACK_NAME\n"
        "NET_NAME\n"
        "END\n"
    ),
    "testpoints": (
        "COMPOSITE_PAD\n"
        "TEST_POINT != ''\n"
        "CLASS\n"
        "NET_NAME\n"
        "NET_PROBE_NUMBER\n"
        "REFDES\n"
        "PIN_NUMBER\n"
        "PIN_X\n"
        "PIN_Y\n"
        "VIA_X\n"
        "VIA_Y\n"
        "TEST_POINT\n"
        "END\n"
    ),
    "drc": (
        "DRC_ERROR\n"
    ),
}


@mcp.tool
async def run_allegro_extracta(
    board_file: str,
    view_type: str = "bom",
    custom_command_content: Optional[str] = None,
    custom_command_file: Optional[str] = None,
    output_file: Optional[str] = None,
) -> dict:
    """Extract design database information from an Allegro .brd file using native extracta.exe.

    Runs `extracta.exe <board_file> <command_file> <output_file>`.
    extracta is Cadence Allegro's standard headless command-line extraction engine for dumping
    BOMs, components, nets, pins, test points, DRC errors, and geometry without requiring
    an interactive GUI or SKILL session.

    `view_type`: One of 'bom', 'nets', 'components', 'pins', 'testpoints', 'drc', or 'custom'.
    `custom_command_content`: Control file lines to execute when view_type is 'custom'.
    `custom_command_file`: Path to an existing .txt/.view command file.
    `output_file`: Destination file path. If omitted, defaults to <board>_<view_type>.txt.
    """
    import os
    from sigrity_mcp.core.config import settings

    if not output_file:
        base, _ = os.path.splitext(board_file)
        output_file = f"{base}_{view_type}.txt"

    cmd_file_path = custom_command_file
    if not cmd_file_path:
        if view_type in EXTRACTION_TEMPLATES:
            content = EXTRACTION_TEMPLATES[view_type]
        elif custom_command_content:
            content = custom_command_content
        else:
            raise ValueError(f"Unknown view_type '{view_type}' and no custom_command_content or custom_command_file provided.")

        # Create command file in output directory or cwd
        out_dir = os.path.dirname(output_file) or str(settings.runs_dir)
        os.makedirs(out_dir, exist_ok=True)
        cmd_file_path = os.path.join(out_dir, f"extract_{view_type}.txt")
        with open(cmd_file_path, "w", encoding="utf-8") as f:
            f.write(content)

    args = [board_file, cmd_file_path, output_file]
    record = await submit_job(tool="allegro_extracta", build_args=args)
    return {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "output_file": output_file,
        "command_file": cmd_file_path,
    }


@mcp.tool
async def allegro_get_board_extent_points(
    board_file: str,
    margin: float = 500.0,
    timeout_seconds: float = 60.0,
) -> dict:
    """Derive a safe default copper-pour/shape boundary from the board's real placed
    component/pin extents, for callers of `allegro_create_copper_shape` who don't want
    to hand-supply an explicit polygon.

    `allegro_create_copper_shape`'s `points` parameter is deliberately required with no
    built-in default (see that tool's own docstring) because a real board's physical
    outline is typically drawn as plain LINE/ARC segments, not a shape database object —
    `axlDBGetShapes("BOARD GEOMETRY/OUTLINE")` returns `nil` on boards that don't define
    one, and this was independently confirmed on two structurally different real boards
    through three separate mechanisms (axlDB live query, extracta text dump, IDF export):
    none of them has a readable closed-polygon outline.

    The `run_allegro_extracta`/`run_allegro_report` "Drawing Extents" figure (also
    always available) is NOT a safe substitute: it is the board's inherited drawing
    SHEET/canvas size, not board-specific geometry — confirmed by two structurally
    different real boards reporting byte-identical "Drawing Extents" while their real
    populated areas differed completely. Using it as a pour boundary risks covering a
    huge empty area far outside the actual board.

    This tool instead runs a real `run_allegro_extracta(view_type="pins")` job against
    `board_file`, parses the real `PIN_X`/`PIN_Y` columns, takes their min/max, and
    expands by `margin` (board units, typically mils) on every side — a rectangle that
    is (a) genuinely board-specific geometry, (b) always available via an existing
    non-UI tool, and (c) provably contains the real board content. It is a
    "populated-region" bounding box, not the literal physical board edge: on a board
    whose parts are sparsely placed in one corner of a larger sheet, this box covers
    the populated region, not the full sheet. For a `dynamic=True` (BOUNDARY-class)
    pour this is safe either way — the flood fill only covers copper connected to its
    net, so a boundary larger than the true edge cannot create copper in empty space.
    Callers wanting an exact custom shape or a true whole-board pour on a board that
    DOES define a real outline should still pass their own explicit `points`.

    Returns `points` as a closed 4-corner rectangle
    `[[XL-margin, YL-margin], [XU+margin, YL-margin], [XU+margin, YU+margin],
    [XL-margin, YU+margin]]`, ready to pass straight into `allegro_create_copper_shape`.
    """
    extraction = await run_allegro_extracta(board_file=board_file, view_type="pins")
    job_id = extraction["job_id"]

    from sigrity_mcp.core.jobs import job_manager

    record = await job_manager.wait(job_id, timeout=timeout_seconds)
    if record.state != "succeeded":
        return {
            "error": f"pins extraction job {job_id} did not succeed (state={record.state})",
            "job_id": job_id,
        }

    output_path = extraction["output_file"]
    try:
        with open(output_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as exc:
        return {"error": f"could not read extracta output '{output_path}': {exc}", "job_id": job_id}

    xs: list[float] = []
    ys: list[float] = []
    for line in lines:
        if not line.startswith("S!"):
            continue
        fields = line.split("!")
        # pins view column order: S!REFDES_SORT!PIN_NUMBER_SORT!REFDES!PIN_NUMBER!PIN_X!PIN_Y!...
        if len(fields) < 7:
            continue
        try:
            xs.append(float(fields[5]))
            ys.append(float(fields[6]))
        except ValueError:
            continue

    if not xs or not ys:
        return {
            "error": "no S! pin rows with numeric PIN_X/PIN_Y found in extracta output "
            f"'{output_path}' — board may have zero placed pins",
            "job_id": job_id,
            "output_file": output_path,
        }

    xl, xu = min(xs) - margin, max(xs) + margin
    yl, yu = min(ys) - margin, max(ys) + margin
    points = [[xl, yl], [xu, yl], [xu, yu], [xl, yu]]
    return {
        "points": points,
        "real_pin_extent": {"xl": min(xs), "yl": min(ys), "xu": max(xs), "yu": max(ys)},
        "margin": margin,
        "pin_count": len(xs),
        "job_id": job_id,
        "output_file": output_path,
    }

