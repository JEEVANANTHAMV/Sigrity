"""Layout-format translators — pure CLI conversion utilities, no Tcl at all.

Confirmed (Translators_UG doc tree: zero Tcl hits across all six tools' chapters) — each
of Gds2Spd/Oasis2Spd/Ndd2Spd/Pads2Spd/Rif2Spd/Dsn2Spd, plus the broader-format SPDLinks,
is driven purely by CLI switches in batch mode (`-b`). None of them expose a `sigrity::`
Tcl automation surface; a translation run is submitted as a plain background job the
same way SPDSIM/BroadbandSPICE are in Domain 2.

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

    Confirmed batch syntax: `gds2spd -b -gds <gds_file> -map <map_file> -tech <tech_file>
    -spd <spd_file>`. `map_file` (layer mapping) and `tech_file` (process stackup) are
    normally required for a meaningful translation, but are left optional here in case a
    prior interactive session already has defaults configured.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `gds2spd -b -log <log_file> <gds_file> <spd_file>` and `map_file`/`tech_file` are
    ignored — per Gds2Spd's docs, a replayed log's stored map/tech settings silently
    override anything passed explicitly alongside it, so don't rely on combining them.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
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

    Confirmed batch syntax: `oasis2spd -b -oasis <oasis_file> [-map <map_file>]
    [-tech <tech_file>] -spd <spd_file>` — unlike Gds2Spd, `map_file`/`tech_file` are
    genuinely optional for Oasis2Spd, not just left out of a required pair.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `oasis2spd -b -log <log_file> <oasis_file> <spd_file>` and `map_file`/`tech_file` are
    ignored — the replayed log's stored settings silently override explicit arguments
    passed alongside it, per Oasis2Spd's docs.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
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

    Confirmed batch syntax: `ndd2spd -b <DesignName.ndd> <DesignName.spd>` — positional
    input/output, no format-specific flags.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `ndd2spd -b -log <log_file> <ndd_file> <spd_file>` — per Ndd2Spd's docs, the replayed
    log's stored settings silently override the explicit input/output paths given
    alongside it, so treat those as override attempts only, not guaranteed.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
    if log_file:
        args = ["-b", "-log", log_file, ndd_file, spd_file]
    else:
        args = ["-b", ndd_file, spd_file]
    return await _submit("ndd2spd", args)


@mcp.tool
async def translate_pads_to_spd(asc_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a PADS ASCII design (.asc) to Sigrity's `.spd` format using Pads2Spd, as a background job.

    Confirmed batch syntax: `Pads2Spd -b <DesignName.asc> <DesignName.spd>` — positional
    input/output, no format-specific flags.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `Pads2Spd -b -log <log_file> <asc_file> <spd_file>` — per Pads2Spd's docs, the
    replayed log's stored settings silently override the explicit input/output paths
    given alongside it, so treat those as override attempts only, not guaranteed.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
    if log_file:
        args = ["-b", "-log", log_file, asc_file, spd_file]
    else:
        args = ["-b", asc_file, spd_file]
    return await _submit("pads2spd", args)


@mcp.tool
async def translate_rif_to_spd(rif_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a RIF layout (.rif) to Sigrity's `.spd` format using Rif2Spd, as a background job.

    Confirmed batch syntax: `Rif2Spd -b <DesignName.rif> <DesignName.spd>` — positional
    input/output, no format-specific flags.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `Rif2Spd -b -log <log_file> <rif_file> <spd_file>` — per Rif2Spd's docs, the replayed
    log's stored settings silently override the explicit input/output paths given
    alongside it, so treat those as override attempts only, not guaranteed.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
    if log_file:
        args = ["-b", "-log", log_file, rif_file, spd_file]
    else:
        args = ["-b", rif_file, spd_file]
    return await _submit("rif2spd", args)


@mcp.tool
async def translate_dsn_to_spd(dsn_file: str, spd_file: str, log_file: Optional[str] = None) -> dict:
    """Convert a Cadence Allegro design (.dsn) to Sigrity's `.spd` format using Dsn2Spd, as a background job.

    Confirmed batch syntax: `Dsn2Spd -b <DesignName.dsn> <DesignName.spd>` — positional
    input/output, no format-specific flags.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `Dsn2Spd -b -log <log_file> <dsn_file> <spd_file>` — per Dsn2Spd's docs, the replayed
    log's stored settings silently override the explicit input/output paths given
    alongside it, so treat those as override attempts only, not guaranteed.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
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

    SPDLinks covers formats the other five dedicated translators don't: Cadvance layout
    (`dbr`/`dbg`), Cadvance netlist (`mcm`/`sip`/`brd`/`txt`), Zuken CR5000/CR8000
    (`pcf`/`ftf`), and ODB++ archives (`zip`, also typically `.tgz`/`.gz`/`.tar`/`.7z` in
    practice even though `format` here only takes the literal `-zip` switch name).

    Confirmed batch syntax: `SPDLinks.exe -b -<format> <input_file> <spd_file>`.

    If `log_file` is given, this switches to log-replay mode instead: the command becomes
    `SPDLinks.exe -b -log <log_file> <input_file> <spd_file>` and `format` is ignored —
    per SPDLinks' docs, the replayed log's stored settings silently override explicit
    arguments passed alongside it.
    Returns a job_id; poll it with get_job_status/wait_for_job.
    """
    if log_file:
        args = ["-b", "-log", log_file, input_file, spd_file]
    else:
        args = ["-b", f"-{format}", input_file, spd_file]
    return await _submit("spdlinks", args)
