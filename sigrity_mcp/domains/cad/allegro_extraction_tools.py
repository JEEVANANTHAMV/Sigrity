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

    Runs `designextractor.exe -p <project_file> [-o <output_file>] [-f]
    [-u <elastic_url>] [-c]` — confirmed live via `designextractor.exe -help`'s full
    usage banner. `pretty_format=True` (default) maps to `-f` (pretty-printed JSON,
    easier to inspect/read back with read_job_output_file than minified output).
    `elastic_url` optionally streams the result directly to an Elasticsearch endpoint
    instead of (or in addition to) writing `output_file` — leave unset for a plain file
    dump. `connectivity_server_as_source` (`-c`) sources data from Allegro's live
    connectivity server rather than the static project file, for use against an
    already-open design session.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then read
    the JSON via read_job_output_file once it succeeds.
    """
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


EXTRACTION_TEMPLATES: dict[str, str] = {
    "bom": (
        "COMPONENTS\n"
        "REFDES\n"
        "DEVICE\n"
        "VALUE\n"
        "TOLERANCE\n"
        "CLASS\n"
        "PACKAGE\n"
        "END\n"
    ),
    "nets": (
        "NETS\n"
        "NET_NAME\n"
        "PIN_NUMBER\n"
        "REFDES\n"
        "PIN_NAME\n"
        "END\n"
    ),
    "components": (
        "COMPONENTS\n"
        "REFDES\n"
        "COMP_DEVICE_TYPE\n"
        "COMP_PACKAGE\n"
        "COMP_LOCATION_X\n"
        "COMP_LOCATION_Y\n"
        "COMP_ROTATION\n"
        "COMP_MIRRORED\n"
        "END\n"
    ),
    "pins": (
        "PINS\n"
        "PIN_NAME\n"
        "PIN_NUMBER\n"
        "REFDES\n"
        "NET_NAME\n"
        "PIN_X\n"
        "PIN_Y\n"
        "PIN_ROTATION\n"
        "END\n"
    ),
    "testpoints": (
        "TESTPOINTS\n"
        "TESTPOINT_NAME\n"
        "TESTPOINT_GRID\n"
        "TESTPOINT_LOCATION_X\n"
        "TESTPOINT_LOCATION_Y\n"
        "NET_NAME\n"
        "END\n"
    ),
    "drc": (
        "DRC\n"
        "DRC_ERROR_NAME\n"
        "DRC_LOCATION_X\n"
        "DRC_LOCATION_Y\n"
        "DRC_LAYER\n"
        "DRC_VIOLATION_DETAILS\n"
        "END\n"
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

