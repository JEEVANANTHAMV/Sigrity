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
from sigrity_mcp.core.tool_status import get_tool_status
from sigrity_mcp.mcp_app import mcp


def _tools_with_status(names: dict[str, bool]) -> dict[str, dict]:
    return {name: {"available": present, **get_tool_status(name)} for name, present in names.items()}


@mcp.tool
async def list_sigrity_tools() -> dict:
    """List every Sigrity/FlexNet/Allegro-OrCAD executable this MCP suite knows how to drive: is it installed, and has it actually been proven to work.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    report = executables.available_tools()
    tools = _tools_with_status(report)
    return {
        "sigrity_home": str(settings.home),
        "license_manager_home": str(settings.license_manager_home),
        "cadence_spb_home": str(settings.cadence_spb_home),
        "available_count": sum(report.values()),
        "confirmed_live_count": sum(1 for t in tools.values() if t["status"] == "confirmed_live"),
        "total_count": len(report),
        "tools": tools,
    }


@mcp.tool
async def list_allegro_tools() -> dict:
    """List the Allegro/OrCAD (CAD creation) executables this suite knows about, whether each is installed, and its verification status.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    cad_names = set(executables.CAD_EXECUTABLES)
    report = {name: present for name, present in executables.available_tools().items() if name in cad_names}
    return {
        "cadence_spb_home": str(settings.cadence_spb_home),
        "available_count": sum(report.values()),
        "total_count": len(report),
        "tools": _tools_with_status(report),
    }


@mcp.tool
async def get_install_info() -> dict:
    """Read this machine's Sigrity install manifest (release version, install date, licensed product bundles).
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
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
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    result = await run_quick("mpsinfo", ["-c1"], timeout=15.0)
    result["name_server_running"] = result["returncode"] == 0
    return result


@mcp.tool
async def get_cds_environment_info(lookup_entry: str | None = None) -> dict:
    """Inspect Cadence's shared environment/config layer via cdsinfo.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-lookup", lookup_entry] if lookup_entry else ["-show"]
    return await run_quick("cdsinfo", args, timeout=15.0)
