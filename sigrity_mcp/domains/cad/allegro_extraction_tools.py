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

