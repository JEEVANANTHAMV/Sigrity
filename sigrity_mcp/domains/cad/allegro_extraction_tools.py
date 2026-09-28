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
