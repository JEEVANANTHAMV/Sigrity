"""Install/environment introspection tools for the local Sigrity Suite.

These are read-only and fast: no Sigrity process is launched. Use them before running
anything else to confirm which tools are actually present on this machine and what was
licensed/installed, instead of discovering it from a job failure later.
"""

from __future__ import annotations

import configparser

from sigrity_mcp.core import executables
from sigrity_mcp.core.config import settings
from sigrity_mcp.core.process import run_quick
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def list_sigrity_tools() -> dict:
    """List every Sigrity/FlexNet executable this MCP suite knows how to drive, and whether it's actually installed here.

    Cross-checks the suite's internal tool registry against disk. A tool being 'available:
    false' means either this Sigrity edition doesn't include it, or SIGRITY_HOME is
    misconfigured — check get_install_info's `product_path` first.
    """
    report = executables.available_tools()
    return {
        "sigrity_home": str(settings.home),
        "license_manager_home": str(settings.license_manager_home),
        "available_count": sum(report.values()),
        "total_count": len(report),
        "tools": report,
    }


@mcp.tool
async def get_install_info() -> dict:
    """Read this machine's Sigrity install manifest (release version, install date, licensed product bundles).

    Parses the components .dat file Cadence's installer writes at SIGRITY_HOME (a plain
    INI file) — no process launch, so this always works even if the license server or
    a GUI tool would fail.
    """
    dat_files = sorted(settings.home.glob("compnts_sig*.dat"))
    if not dat_files:
        return {"error": f"No compnts_sig*.dat manifest found under {settings.home}"}

    parser = configparser.ConfigParser()
    parser.read(dat_files[0], encoding="utf-8")
    general = dict(parser["GENERAL"]) if parser.has_section("GENERAL") else {}
    products = list(dict(parser["PRODUCTS"]).values()) if parser.has_section("PRODUCTS") else []
    return {
        "manifest_file": str(dat_files[0]),
        "install_name": general.get("installname"),
        "release_version": general.get("release version"),
        "install_date": general.get("date"),
        "product_path": general.get("productpath"),
        "architecture": general.get("architecture"),
        "licensed_product_bundles": products,
    }


@mcp.tool
async def check_name_server() -> dict:
    """Check whether the Cadence common name server (cdsNameServer) is running for this session.

    Equivalent to `mpsinfo -c1`, which exits 0 if the name server is up and 1 if not.
    Several Sigrity tools rely on this being up for cross-process communication (e.g.
    console/batch variants talking to a running suite process); a job that hangs rather
    than failing outright can indicate this is down.
    """
    result = await run_quick("mpsinfo", ["-c1"], timeout=15.0)
    result["name_server_running"] = result["returncode"] == 0
    return result


@mcp.tool
async def get_cds_environment_info(lookup_entry: str | None = None) -> dict:
    """Inspect Cadence's shared environment/config layer via cdsinfo.

    Without `lookup_entry`, runs `cdsinfo -show` (dumps the current cds env config).
    With `lookup_entry`, runs `cdsinfo -lookup <entry>` to resolve one specific entry
    name (useful for checking library/tool path resolution when a run_* tool can't find
    an input file you expect it to).
    """
    args = ["-lookup", lookup_entry] if lookup_entry else ["-show"]
    return await run_quick("cdsinfo", args, timeout=15.0)
