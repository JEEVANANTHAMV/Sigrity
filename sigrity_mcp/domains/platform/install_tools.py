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

    Each entry has `available` (the exe is present on disk — a false here means either
    this edition doesn't include it or SIGRITY_HOME/SIGRITY_CADENCE_SPB_HOME is
    misconfigured, check get_install_info's `product_path` first) and a verification
    `status`: 'confirmed_live' (actually run successfully against a real license and
    design), 'built_untested' (implemented and unit-tested but never run live — treat
    exact command/flag spellings as best-effort), or 'known_blocked' (attempted live and
    found genuinely stuck — see its `note` for specifics). This status is a hand-curated
    fact, not a live license query — `lmutil lmstat` has been proven unreliable as a
    predictor of real tool usability on this machine (PowerSI/PowerDC both work despite
    it reporting the license server unreachable), so don't rely on lmstat-based tools to
    answer "can I actually run this" — this field is the honest answer to that question.
    """
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

    Same shape and status semantics as list_sigrity_tools, scoped to the separate
    Allegro/OrCAD SPB install (schematic capture, PCB layout) rather than the Sigrity
    Suite. Status as of this writing:
    - `allegro`: 'confirmed_live' — the initial product-chooser dialog blocker is
      resolved; a real board loads and a real SKILL query executes and returns
      correctly via `allegro.exe -s script.scr board.brd`. Database *mutation* calls
      (create net/component/etc.) are a different story — see allegro_tools.py's module
      docstring for what's still unverified there.
    - `capture`: 'known_blocked' — a bare launch now opens cleanly, but the batch-script
      invocation itself remains unreliable across repeated attempts.
    - `allegro_report`/`allegro_dbdoctor`: 'confirmed_live' — genuinely headless,
      each already ran a real operation against a real board sample end-to-end.
    - `allegro_batch` (the "central batch utility" multiplexer): 'known_blocked' at
      actually dispatching sub-programs (confirmed: routing `dbdoctor` through it
      failed outright even though calling `dbdoctor.exe` directly works) — this suite
      calls each standalone exe directly instead.
    Check each entry's `note` for the exact symptom/confirmation observed.
    """
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
