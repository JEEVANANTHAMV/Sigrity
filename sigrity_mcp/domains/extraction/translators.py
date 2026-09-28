"""Layout-format translators — pure CLI conversion utilities, no Tcl at all.

Confirmed (Translators_UG doc tree: zero Tcl hits across all six tools' chapters) — each
of Gds2Spd/Oasis2Spd/Ndd2Spd/Pads2Spd/Rif2Spd/Dsn2Spd, plus the broader-format SPDLinks,
is driven purely by CLI switches in batch mode (`-b`). None of them expose a `sigrity::`
Tcl automation surface; a translation run is submitted as a plain background job the
same way SPDSIM/BroadbandSPICE are in Domain 2.

These six (plus SPDLinks) are dedicated standalone-exe translators, but they are NOT the
only import path into `.spd` — Sigrity ships a built-in "SPDIF Translator" inside every
Layout Workbench tool (PowerSI, PowerDC, ...), not a separate exe, documented in
doc/Translators_UG/Introduction_to_Sigrity_Translators.html, that additionally covers
Altium (`.pcbdoc`), IPC-2581 (`.xml`), DXF (`.dxf`), ODB++ archives, and Allegro
`.brd`/`.mcm`/etc. Reached via `sigrity::open document` inside a PowerSI/PowerDC session
(`start_powersi_session` + `powersi_save_document` in `sigrity_mcp/domains/si/
powersi_tools.py` — see that module's docstring for full live-test evidence: confirmed
against real DXF and Altium samples, producing valid multi-KB/multi-MB `.spd` files).
Reach for a dedicated `translate_*_to_spd` tool below only for a format this built-in
translator doesn't cover (GDSII, OASIS, NDD, PADS, RIF, Cadvance, Zuken CR5000/CR8000).

Documented gotcha that applies to every tool below: passing `-log <log_file>` replays a
previously recorded run's stored settings, and those stored values **silently override**
any explicit format/map/tech arguments given alongside it on the same command line. So
each tool here treats `log_file` as switching to an entirely different mode: when given,
the explicit-flags form (map/tech file, format-specific switches) is dropped and the
command becomes `-b -log <log_file> [input_file] [output_file]` instead — `input_file`/
`output_file` are still appended (some tools require them positionally regardless), but
per the docs they should be treated as override *attempts* the log's own stored settings
will likely win over, not a reliable way to redirect a replayed run's I/O.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


async def _submit(tool: str, args: list[str]) -> dict:
    record = await submit_job(tool=tool, build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}


@mcp.tool
async def translate_gds_to_spd(
    gds_file: str,
    spd_file: str,
    map_file: Optional[str] = None,
    tech_file: Optional[str] = None,
    log_file: Optional[str] = None,
) -> dict:
    """Convert a GDSII layout (.gds) to Sigrity's `.spd` format using Gds2Spd, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, gds_file, spd_file]
    else:
        args = ["-b", "-gds", gds_file]
        if map_file:
            args += ["-map", map_file]
        if tech_file:
            args += ["-tech", tech_file]
        args += ["-spd", spd_file]
    return await _submit("gds2spd", args)


@mcp.tool
async def translate_oasis_to_spd(
    oasis_file: str,
    spd_file: str,
    map_file: Optional[str] = None,
    tech_file: Optional[str] = None,
    log_file: Optional[str] = None,
) -> dict:
    """Convert an OASIS layout (.oasis) to Sigrity's `.spd` format using Oasis2Spd, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, oasis_file, spd_file]
    else:
        args = ["-b", "-oasis", oasis_file]
        if map_file:
            args += ["-map", map_file]
        if tech_file:
            args += ["-tech", tech_file]
        args += ["-spd", spd_file]
    return await _submit("oasis2spd", args)


@mcp.tool
async def translate_ndd_to_spd(ndd_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a Cadence Allegro/NDD design (.ndd) to Sigrity's `.spd` format using Ndd2Spd, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, ndd_file, spd_file]
    else:
        args = ["-b", ndd_file, spd_file]
    return await _submit("ndd2spd", args)


@mcp.tool
async def translate_pads_to_spd(asc_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a PADS ASCII design (.asc) to Sigrity's `.spd` format using Pads2Spd, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, asc_file, spd_file]
    else:
        args = ["-b", asc_file, spd_file]
    return await _submit("pads2spd", args)


@mcp.tool
async def translate_rif_to_spd(rif_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a RIF layout (.rif) to Sigrity's `.spd` format using Rif2Spd, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, rif_file, spd_file]
    else:
        args = ["-b", rif_file, spd_file]
    return await _submit("rif2spd", args)


@mcp.tool
async def translate_dsn_to_spd(dsn_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a Cadence Allegro design (.dsn) to Sigrity's `.spd` format using Dsn2Spd, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, dsn_file, spd_file]
    else:
        args = ["-b", dsn_file, spd_file]
    return await _submit("dsn2spd", args)


@mcp.tool
async def translate_to_spd_via_spdlinks(
    input_file: str,
    spd_file: str,
    format: Literal["dbr", "dbg", "mcm", "sip", "brd", "txt", "pcf", "ftf", "zip"],
    log_file: Optional[str] = None,
) -> dict:
    """Convert a broader range of third-party layout/netlist formats to `.spd` using SPDLinks, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if log_file:
        args = ["-b", "-log", log_file, input_file, spd_file]
    else:
        args = ["-b", f"-{format}", input_file, spd_file]
    return await _submit("spdlinks", args)
