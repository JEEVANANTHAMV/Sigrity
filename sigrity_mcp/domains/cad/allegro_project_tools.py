"""Allegro/OrCAD schematic-project creation and design-variant generation — standalone CLI.

Found via a fresh sweep of every executable under `C:\\Cadence\\SPB_22.1\\tools\\bin` not
yet registered in this suite, specifically looking for a real answer to "create a new
schematic project from scratch" — `capture_tools.py`'s Tcl batch mode is documented
`known_blocked` (genuinely non-deterministic on this machine), and `syscap.exe`
("Allegro System Capture," a distinct, newer schematic tool) has a real, extensively
documented Tcl API (`doc/scap_tcl_comms/`, including a genuine `newProject` "create from
nothing" call) but NO confirmed headless/batch launch mode — both `-help` and `-tcl
<script>` were tried live and neither produced usable evidence either way (see
`domains/cad/__init__.py`'s module docstring for the full write-up).

The real, confirmed answer turned out to be a pair of standalone CLI executables that
are the non-interactive equivalents of the Tcl `copyProjectAs`/`createProject` commands
`doc/scap_tcl_comms/` documents (those Tcl procs require a live GUI session; these do
not):

- **`copyproject.exe`** — CONFIRMED LIVE, independently verified twice. Its own `-help`
  usage banner requires every argument (`-proj`, `-copytopath`, `-newprojname`,
  `-newlib`, `-newdesign`) with none shown as optional. Run against the real shipped
  sample project `share/pcb/translators/altium_proj_template/altium_proj_template.cpm`,
  it produced a complete, freshly-timestamped new project — a real CPM file (plain
  text, correct `design_name`/`design_library` fields) and a full
  `worklib/<newdesign>/{sch_1,packaged,physical,cfg_package}` tree with real schematic
  pages and a physical `.brd` placeholder, ending in "SUCCESS(COPYPROJ-67): Copy Project
  Success." — internally it drives `nconcepthdl` for you. IMPORTANT CONFIRMED QUIRK:
  the resulting project file is named EXACTLY the `new_project_name` value given, with
  NO `.cpm` extension appended automatically — pass one yourself
  (`new_project_name="myproj.cpm"`) if you want it.
- **`xcon2project.exe`** — CONFIRMED LIVE the same way, against the same real sample
  project's own `.xcon` connectivity file: produced a real new project `.cpm`/`cds.lib`,
  log showing real "Packaging design '<root>'" status. Its own usage banner shows
  `-refproj` in brackets but appends "(-refproj must be specified)" — treated as
  required here despite the bracket notation.

Both are genuinely headless/flag-driven — no GUI needed — making them a strictly better
automation path than System Capture's Tcl API for "create/duplicate a schematic
project," at least until a real `syscap.exe` batch invocation is confirmed.

**`generate_sim_variant.exe`** is a different kind of "create a new design," found the
same sweep: CONFIRMED LIVE to genuinely create a NEW derivative `.brd` from a master
board, over/undersizing trace (cline) widths and/or dielectric thicknesses for
signal-integrity what-if analysis — its own `-help` banner: "Utility to generate a
variant design from the provided master." A live run (`-c "1.0" -d "1.0"`, i.e. +1%
cline and dielectric sizing) against a real sample board produced a real, distinct
918KB new `.brd`, independently confirmed valid (not a stub/corrupt copy) by re-reading
it with `report.exe` (matching package/drill/connection counts). Per generate_sim_variant's
own documentation, on-line DRC is deliberately disabled in the resulting variant design
(oversized elements may legitimately violate spacing against their neighbors) — don't
expect (or force) a clean DRC pass against a variant board.

All three tools below resolve file/directory-path arguments to absolute (relative to
the MCP server's own cwd) before building argv — see `core/paths.py` — the same
defensive fix applied everywhere else in this Cadence CLI family after a demonstrated
runaway-re-prompt-loop failure mode. Bare name arguments (`new_project_name`,
`new_library_name`, `new_design_name`, `root_design_name`, `library_name`) are passed
through unresolved since they aren't paths — `copyproject`/`xcon2project` interpret them
relative to `copy_to_path`/`output_folder`, not the server's cwd.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.paths import resolve_path as _resolve
from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def allegro_copy_project(
    source_project_file: str,
    copy_to_path: str,
    new_project_name: str,
    new_library_name: str,
    new_design_name: str,
) -> dict:
    """Create a new schematic project by copying an existing one — CONFIRMED LIVE (see module docstring).

    Runs `copyproject.exe -proj <source_project_file> -copytopath <copy_to_path>
    -newprojname <new_project_name> -newlib <new_library_name> -newdesign
    <new_design_name>` as a background job. This is this suite's confirmed, fully
    headless way to create a genuinely new schematic project — copy a real starter/
    template `.cpm` project (e.g. one of the shipped `share/pcb/translators/*_template/`
    projects, or any existing internally-approved template) into a fresh project+design
    under a new name.

    IMPORTANT: the produced project file is named EXACTLY `new_project_name` with no
    `.cpm` extension appended automatically — include it yourself
    (e.g. `new_project_name="myproject.cpm"`) if you want a `.cpm`-suffixed file.
    `source_project_file` must be a real, already-existing `.cpm` (not a
    `@project@`-style unresolved template placeholder).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then browse
    the new project tree under `copy_to_path`/`worklib/<new_design_name>/` via
    list_job_files/read_job_output_file.
    """
    args = [
        "-proj", _resolve(source_project_file),
        "-copytopath", _resolve(copy_to_path),
        "-newprojname", new_project_name,
        "-newlib", new_library_name,
        "-newdesign", new_design_name,
    ]
    record = await submit_job(tool="copyproject", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def allegro_package_xcon_project(
    xcon_file: str,
    root_design_name: str,
    library_name: str,
    reference_project_file: str,
    reference_cdslib_file: Optional[str] = None,
    output_folder: Optional[str] = None,
) -> dict:
    """Package a `.xcon` connectivity file into a new schematic project — CONFIRMED LIVE (see module docstring).

    Runs `xcon2project.exe -xcon <xcon_file> -root <root_design_name> -lib
    <library_name> -refproj <reference_project_file> [-refcdslib <reference_cdslib_file>]
    [-output <output_folder>]` as a background job. `reference_project_file` is
    required — xcon2project's own usage banner shows it in brackets but explicitly
    appends "(-refproj must be specified)".
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    args = [
        "-xcon", _resolve(xcon_file),
        "-root", root_design_name,
        "-lib", library_name,
        "-refproj", _resolve(reference_project_file),
    ]
    if reference_cdslib_file:
        args += ["-refcdslib", _resolve(reference_cdslib_file)]
    if output_folder:
        args += ["-output", _resolve(output_folder)]
    record = await submit_job(tool="xcon2project", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def allegro_generate_sim_variant(
    master_board_file: str,
    output_board_file: Optional[str] = None,
    cline_oversize_percent: Optional[float] = None,
    cline_oversize_absolute: Optional[float] = None,
    dielectric_oversize_percent: Optional[float] = None,
    dielectric_oversize_absolute: Optional[float] = None,
) -> dict:
    """Create a new derivative Allegro design with over/undersized traces or dielectrics — CONFIRMED LIVE (see module docstring).

    Runs `generate_sim_variant.exe [-c <pct>|-C <abs>] [-d <pct>|-D <abs>]
    [-o <output_board_file>] <master_board_file>` as a background job. For each of
    clines/dielectrics, give EITHER the `_percent` OR the `_absolute` variant, not both
    (raises ValueError if both are given for the same axis) — percent maps to `-c`/`-d`
    (e.g. 1.0 = oversize by 1%), absolute maps to `-C`/`-D` (e.g. 0.1 = oversize by 0.1
    design units; negative undersizes). If `output_board_file` is omitted,
    generate_sim_variant names it `<master_board_file>_sim.brd` in the job's own working
    directory.

    Per the tool's own documentation, on-line DRC is deliberately disabled in the
    resulting variant design — oversized elements may legitimately violate spacing
    against their now-larger neighbors, so don't run/expect a clean DRC pass against the
    output.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    if cline_oversize_percent is not None and cline_oversize_absolute is not None:
        raise ValueError("give only one of cline_oversize_percent/cline_oversize_absolute, not both")
    if dielectric_oversize_percent is not None and dielectric_oversize_absolute is not None:
        raise ValueError("give only one of dielectric_oversize_percent/dielectric_oversize_absolute, not both")

    args: list[str] = []
    if cline_oversize_percent is not None:
        args += ["-c", str(cline_oversize_percent)]
    if cline_oversize_absolute is not None:
        args += ["-C", str(cline_oversize_absolute)]
    if dielectric_oversize_percent is not None:
        args += ["-d", str(dielectric_oversize_percent)]
    if dielectric_oversize_absolute is not None:
        args += ["-D", str(dielectric_oversize_absolute)]
    if output_board_file:
        args += ["-o", _resolve(output_board_file)]
    args.append(_resolve(master_board_file))
    record = await submit_job(tool="generate_sim_variant", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
