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

# logical name -> exe filename under SIGRITY_CADENCE_SPB_HOME/tools/bin — Allegro/OrCAD
# (Silicon Package Board), a separate sibling product line from the Sigrity Suite, used
# for CAD creation (schematic capture, PCB layout) rather than post-layout analysis.
CAD_EXECUTABLES: dict[str, str] = {
    "capture": "Capture.exe",
    "allegro": "allegro.exe",
    # allegro_batch.exe (the "central batch utility" multiplexer) is confirmed to have at
    # least one broken sub-program dispatch (dbdoctor: "Cannot find program 'dbdoctor'")
    # even though its own -help/<program> -help output is fine — so tools call each
    # underlying standalone exe directly instead of routing through it. Kept registered
    # here only for its own -help-style discovery value, not for running sub-programs.
    "allegro_batch": "allegro_batch.exe",
    "allegro_report": "report.exe",
    "allegro_dbdoctor": "dbdoctor.exe",
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
    "dsn2spd": "Dsn2Spd.exe",
    "dsn2spd_console": "Dsn2SpdCon.exe",
    "t2b": "T2B.exe",
    "xtractim_techgen": "XPITechGen.exe",
    "fdtddesigner": "FDTDDesigner.exe",
    "fdtdsolver": "FDTDSolver.exe",
    "fdtdgenerator": "FDTDGenerator.exe",
    "fdtdcombine": "FDTDCombine.exe",
    "fdtdpcfmaker": "FDTDPCFMaker.exe",
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


def _registries() -> list[tuple[dict[str, str], Path, str]]:
    """Each registry paired with the base dir its filenames resolve against and a
    human-readable hint for the error message when a file is missing. Order matters only
    in that the first dict containing `name` wins; names are unique across all three today."""
    return [
        (EXECUTABLES, settings.bin_dir, f"Check SIGRITY_HOME (currently {settings.home})"),
        (
            LICENSE_EXECUTABLES,
            settings.license_manager_home,
            f"Check SIGRITY_LICENSE_MANAGER_HOME (currently {settings.license_manager_home})",
        ),
        (
            CAD_EXECUTABLES,
            settings.cad_bin_dir,
            f"Check SIGRITY_CADENCE_SPB_HOME (currently {settings.cadence_spb_home})",
        ),
    ]


@lru_cache(maxsize=None)
def resolve(name: str) -> Path:
    """Resolve a logical tool name to its absolute executable path.

    Checks the Sigrity Suite, FlexNet license-manager, and Allegro/OrCAD registries in
    turn. Raises ExecutableNotFoundError if the name is unknown in all three, or if the
    exe is not present on disk (e.g. a differently-licensed/installed edition).
    """
    for registry, base_dir, hint in _registries():
        if name in registry:
            path = base_dir / registry[name]
            if not path.is_file():
                raise ExecutableNotFoundError(
                    f"'{name}' should be at {path} but the file does not exist. {hint} and "
                    "confirm this component was installed."
                )
            return path

    known = sorted(set(EXECUTABLES) | set(LICENSE_EXECUTABLES) | set(CAD_EXECUTABLES))
    raise ExecutableNotFoundError(f"Unknown Sigrity tool '{name}'. Known tools: {known}")


def available_tools() -> dict[str, bool]:
    """Report, for every registered logical tool name, whether the exe is actually present."""
    report: dict[str, bool] = {}
    for registry, base_dir, _hint in _registries():
        report.update({name: (base_dir / exe).is_file() for name, exe in registry.items()})
    return report
