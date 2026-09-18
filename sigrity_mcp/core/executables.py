"""Registry of Sigrity tool executables, keyed by a short logical name.

Every executable referenced anywhere in this package must be listed here. This gives us
one place to audit "what does this suite actually touch" and lets `resolve()` raise a
clear, actionable error instead of a bare Windows "file not found".
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sigrity_mcp.core.config import settings
from sigrity_mcp.core.errors import ExecutableNotFoundError

# logical name -> exe filename, resolved against C:\Cadence\LicenseManager (FlexNet client
# tools ship separately from the Sigrity Suite install itself).
LICENSE_EXECUTABLES: dict[str, str] = {
    "lmutil": "lmutil.exe",
}

# logical name -> exe filename under SIGRITY_HOME/tools/bin
EXECUTABLES: dict[str, str] = {
    # --- Power Integrity ---
    "powerdc": "PowerDC.exe",
    "powertree": "PowerTree.exe",
    "xcitepi": "XcitePI.exe",
    "xcitepi_console": "XcitePICon.exe",
    "optimality": "Optimality.exe",
    "optimizepi": "OptimizePI.exe",
    "decapgenerator": "DecapGenerator.exe",
    "amm": "Amm.exe",
    "amlibgen": "AmLibGen.exe",
    # --- Signal Integrity & Power-Aware ---
    "powersi": "PowerSI.exe",
    "spdsim": "SPDSIM.exe",
    "spdsim_console": "SPDsimCon.exe",
    "broadbandspice": "BroadbandSPICE.exe",
    "spdlinks": "SPDLinks.exe",
    "spdlinks_console": "SPDLinksCon.exe",
    "siweb": "SiWeb.exe",
    "siwebquery": "SiWebQuery.exe",
    # --- Interconnect Extraction & Modeling ---
    "clarity3d_workbench": "Clarity3DWorkbench.exe",
    "clarity3d_layout": "Clarity3DLayout.exe",
    "clarity3d_setup": "Clarity3DSetup.exe",
    "clarity3d_agent": "Clarity3DAgent.exe",
    "clarity3d_hpc_launcher": "Clarity3DHPCLauncher.exe",
    "xtractim": "XtractIM.exe",
    "workbench3d": "3DWorkbench.exe",
    "hexmesh": "HexMesh.exe",
    "meshrefiner": "MeshRefiner.exe",
    "sigmamesh": "SigmaMesh.exe",
    "gds2spd": "Gds2Spd.exe",
    "gds2spd_console": "Gds2SpdCon.exe",
    "ndd2spd": "Ndd2Spd.exe",
    "ndd2spd_console": "Ndd2SpdCon.exe",
    "oasis2spd": "Oasis2Spd.exe",
    "oasis2spd_console": "Oasis2SpdCon.exe",
    "pads2spd": "Pads2Spd.exe",
    "pads2spd_console": "Pads2SpdCon.exe",
    "rif2spd": "Rif2Spd.exe",
    "rif2spd_console": "Rif2SpdCon.exe",
    "t2b": "T2B.exe",
    "xtractim_techgen": "XPITechGen.exe",
    # --- Unified Sigrity X platform / suite management ---
    "sigritysuite": "SigritySuite.exe",
    "sigritysuite_console": "SigritySuiteCon.exe",
    "sigritysuite_manager": "SigritySuiteManager.exe",
    "sigsuitereg": "SigSuiteReg.exe",
    "clsadmintool": "clsAdminTool.exe",
    "cdsinfo": "cdsinfo.exe",
    "mpsinfo": "mpsinfo.exe",
    "vercheck": "vercheck.exe",
    "consmgr": "consmgr.exe",
}


@lru_cache(maxsize=None)
def resolve(name: str) -> Path:
    """Resolve a logical tool name to its absolute executable path.

    Checks the Sigrity Suite registry first, then the FlexNet license-manager registry.
    Raises ExecutableNotFoundError if the name is unknown in both, or if the exe is not
    present on disk (e.g. a differently-licensed/installed Sigrity edition).
    """
    if name in EXECUTABLES:
        path = settings.bin_dir / EXECUTABLES[name]
        hint = f"Check SIGRITY_HOME (currently {settings.home})"
    elif name in LICENSE_EXECUTABLES:
        path = settings.license_manager_home / LICENSE_EXECUTABLES[name]
        hint = f"Check SIGRITY_LICENSE_MANAGER_HOME (currently {settings.license_manager_home})"
    else:
        known = sorted(set(EXECUTABLES) | set(LICENSE_EXECUTABLES))
        raise ExecutableNotFoundError(f"Unknown Sigrity tool '{name}'. Known tools: {known}")

    if not path.is_file():
        raise ExecutableNotFoundError(
            f"'{name}' should be at {path} but the file does not exist. {hint} and confirm "
            "this component was installed."
        )
    return path


def available_tools() -> dict[str, bool]:
    """Report, for every registered logical tool name, whether the exe is actually present."""
    report = {name: (settings.bin_dir / exe).is_file() for name, exe in EXECUTABLES.items()}
    report.update(
        {name: (settings.license_manager_home / exe).is_file() for name, exe in LICENSE_EXECUTABLES.items()}
    )
    return report
