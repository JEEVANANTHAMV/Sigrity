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
    # apd.exe is a thin launcher stub (307KB) for allegro.exe that starts Allegro Package
    # Designer (APD) in the APD product tier. CONFIRMED LIVE as a headless batch runner when
    # given `-product <APD tier> -nograph -s <script.scr> <design.mcm>` (see
    # apd_package_tools.py). Without `-product` it dies in ~50ms at the non-graphic Product
    # Choices stage with an unmodified design — always pass the product tier.
    "apd": "apd.exe",
    # allegro_batch.exe (the "central batch utility" multiplexer) is confirmed to have at
    # least one broken sub-program dispatch (dbdoctor: "Cannot find program 'dbdoctor'")
    # even though its own -help/<program> -help output is fine — so tools call each
    # underlying standalone exe directly instead of routing through it. Kept registered
    # here only for its own -help-style discovery value, not for running sub-programs.
    "allegro_batch": "allegro_batch.exe",
    "allegro_report": "report.exe",
    "allegro_dbdoctor": "dbdoctor.exe",
    # --- DRC / rule checking (confirmed live headless CLI, see allegro_drc_tools.py) ---
    "allegro_batch_drc": "batch_drc.exe",
    "allegro_checkplus": "checkplus.exe",
    # --- Placement & routing (confirmed live standalone CLI, see allegro_placement_tools.py) ---
    "allegro_placement": "placement.exe",
    "allegro_ncroute": "ncroute.exe",
    "allegro_zrouter": "zrouter.exe",
    # --- Manufacturing output (confirmed live CLI, see allegro_manufacturing_tools.py) ---
    "allegro_ipc2581_out": "ipc2581_out.exe",
    "allegro_ipc356_out": "ipc356_out.exe",
    "allegro_step_out": "step_out.exe",
    # artwork.exe is the real Gerber-film generator (confirmed live via its own -help
    # banner and a real run producing genuine RS274X .art files) -- the piece
    # run_allegro_gerber_plot was missing; see allegro_manufacturing_tools.py.
    "allegro_artwork": "artwork.exe",
    "allegro_gbplot": "gbplot.exe",
    # --- Library / model checking (confirmed live CLI, see allegro_library_tools.py) ---
    "ibischk3": "ibischk3.exe",
    "ibischk4": "ibischk4.exe",
    "ibischk5": "ibischk5.exe",
    "ibischk6": "ibischk6.exe",
    "allegro_diacheck": "diacheck.exe",
    "allegro_diacompare": "diacompare.exe",
    # --- Design data extraction (confirmed live CLI, see allegro_extraction_tools.py) ---
    "allegro_designextractor": "designextractor.exe",
    "allegro_extracta": "extracta.exe",
    # --- Interchange translators (GUI+CLI hybrids — WORK on this install via the GUI
    # product-chooser / "Translate" dialog, user-confirmed 2026-10-18). The supported
    # automation path is launch_translator_gui("<tool>") then driving the dialog. The
    # per-tool doc-verified switch contracts (doc\pdv\console_commands.html, all need
    # `-product pcb_librarian_expert`) live in interchange_tools.py as a best-effort
    # headless fallback; on THIS build the bare CLI stops at the pcb_librarian_expert
    # checkout — a property of the headless path, NOT a broken/missing tool. See the
    # tool_status notes. ---
    "con2xml": "con2xml.exe",
    "cap2xml": "cap2xml.exe",
    "dml2con": "dml2con.exe",
    "apd2con": "apd2con.exe",
    # --- SPECCTRA/SPIF autorouting bridge (confirmed live headless autorouting —
    # see spif_specctra_tools.py) ---
    "spif_batch": "spif_batch.exe",
    "specctra": "specctra.exe",
    # --- PSpice batch simulation (confirmed live CLI, see pspice_tools.py) ---
    "psp_cmd": "psp_cmd.exe",
    # --- Mechanical/DXF import-export & blank-board creation (confirmed live CLI, see
    # allegro_import_tools.py) ---
    "dxf2a": "dxf2a.exe",
    "a2dxf": "a2dxf.exe",
    # --- Mechanical ECAD/MCAD & manufacturing import-export (confirmed live CLI unless
    # noted, see allegro_manufacturing_tools.py) ---
    "ipc2581_in": "ipc2581_in.exe",
    "idf_out": "idf_out.exe",
    "idx_out": "idx_out.exe",
    "idf_in": "idf_in.exe",  # built_untested -- no sample .emn/.bdf/.out found on this machine
    "idx_in": "idx_in.exe",  # built_untested -- no sample .idx found on this machine
    "brd2dml": "brd2dml.exe",
    "pdf_out": "pdf_out.exe",
    # --- Design/project creation (confirmed live CLI, see allegro_project_tools.py) ---
    "copyproject": "copyproject.exe",
    "xcon2project": "xcon2project.exe",
    "generate_sim_variant": "generate_sim_variant.exe",
    # --- Library/symbol authoring (confirmed live CLI, see allegro_library_tools.py) ---
    "create_sym": "create_sym.exe",
    # --- Headless Capture DB read + native netlist import (confirmed live, see
    # capture_headless_tools.py / netlist_import_tools.py). `tclsh.exe` is the standalone
    # Tcl 8.6 shell Capture's own `orDb_Dll_Tcl64.dll` loads into -- no Capture.exe
    # process, no GUI, at all. `netrev`/`netin` import a netlist straight into an Allegro
    # .brd, the same native path Capture's own File > PCB > Netlist menu item drives. ---
    "tclsh": "tclsh.exe",
    "netrev": "netrev.exe",
    "netin": "netin.exe",
    # pstswp.exe generates a PCB netlist (.pst: pstchip/pstxprt/pstxnet.dat) directly
    # from a .dsn on disk -- confirmed live to work against a .dsn that was itself
    # authored headlessly (capture_headless_tools.author_capture_schematic_headless),
    # with NO Capture.exe GUI step anywhere, closing the last gap in the headless
    # schematic-to-board pipeline. See generate_capture_pcb_netlist.
    "pstswp": "pstswp.exe",
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
    # --- Standalone utility solvers (confirmed live self-documenting CLI, no doc-tree
    # coverage, see extraction/utility_solvers.py) ---
    "abcd": "abcd.exe",
    "bem2d3": "bem2d3.exe",
    # --- Thermal (Celsius) — confirmed live end-to-end against real
    # share/PostInstallationCheck sample projects, see domains/thermal/ ---
    "celsius3d": "Celsius3D.exe",
    "celsiuscfd": "CelsiusCFD.exe",
    "celsius2d": "Celsius2D.exe",
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


#: Logical names of the tools that, on this PREMIUM / no-license-required install,
#: launch a GUI (open a workbench/work window) and block on interactive startup
#: dialogs ("Product Choices", welcome, "what would you like to do?" ...) even
#: when driven from the command line. Their console log is empty by nature, so the
#: console-oriented job watcher in `core.jobs` misreads a GUI tool's normal startup
#: as "no output for N seconds -> stall" and the negative-rc/empty-log heuristic as a
#: "license issue". `core.gui_tool_runner.is_gui_tool` / `submit_job` route these
#: through the screenshot+dismiss path instead. Keep in sync with
#: `GUI_TOOL_EXE_NAMES` in core.gui_tool_runner (that set is the source of truth for
#: exe-stem matching; this set is keyed by logical name for tool-facing messages).
GUI_TOOL_NAMES: frozenset[str] = frozenset({
    "powerdc",
    "powersi",
    "xtractim",
    "clarity3d_workbench",
    "optimizepi",
    "xcitepi",
    "xcitepi_console",
    "broadbandspice",
    "spdsim",
    "spdsim_console",
    "powertree",
    "optimality",
    "celsius3d",
})


#: Modal dialogs that block a GUI-tool launch by demanding the user SELECT something
#: (a default product/tree/proxy target, or a "waiting on a resource" confirmation)
#: rather than just acknowledging one. A plain confirm-word click (OK/Next) does NOT
#: drive these forward: the process keeps spinning 100% CPU with an empty log, which the
#: console job-watcher misreads as a stall and the old heuristic flagged as a "license
#: issue". On this build these are the single root cause behind most "known blocked"
#: labels. `core.gui_tool_runner.preseed_selection` resolves them BEFORE launching, and
#: `_selection_actions` answers them in-line if one still appears during a run.
#:
#: Keys are case-insensitive substrings matched against the dialog TITLE (and, for the
#: "waiting on resource" probe, the window class). Values are the in-line answer: a small
#: list of (description, keyword) pairs — the first (description) the runner tries is the
#: auto-answer (default/local/continue); a match means "click the child whose text is
#: this keyword", falling back to the default confirm-word ladder.
SELECTOR_DIALOG_PATTERNS: dict[str, dict[str, object]] = {
    # "Product Choices" / product-tier chooser: pick the installed default product.
    "product": {
        "answer_keywords": ("default", "ok", "continue", "accept"),
        "note": "one-time: Allegro/Capture default product chooser. Auto-answers 'default' "
        "and persists; subsequent launches skip it.",
    },
    # "Select a tree" / model-tree / BOM-tree picker: pick the local default tree.
    "tree": {
        "answer_keywords": ("default", "local", "browse", "ok"),
        "note": "tree/model-tree picker. Auto-answers the local default tree so the "
        "process proceeds without a network/proxy tree.",
    },
    # "Select a proxy" / proxy-host chooser: point at localhost (no external proxy).
    "proxy": {
        "answer_keywords": ("localhost", "default", "no proxy", "ok"),
        "note": "proxy-host picker. Auto-answers localhost/no-proxy so the tool does not "
        "wait on an external proxy that is not configured.",
    },
    # "Waiting" / "Checking" / "Connecting" / "Contacting" resource probes: confirm
    # local and continue (the classic 'internet waiting' freeze).
    "waiting": {
        "answer_keywords": ("continue", "yes", "ok", "default", "local"),
        "note": "'waiting on a resource' / 'checking ...' / 'contacting ...' probe. "
        "Confirms local continuation so the tool does not hang on a network resource.",
    },
    # "Choose License Suites" (PowerSI/PowerDC and other Sigrity analysis tools, even on
    # a no-seat-limit/PREMIUM install): a multi-checkbox feature-selection modal -- NOT a
    # single confirm button -- so the plain confirm-word ladder in the base DismissWatcher
    # can never advance it: the process idles/exits with an empty log and silently writes
    # no simulation output at all (e.g. `sigrity::begin simulation` logs "the layout is
    # empty. First load an SPD layout file" because the tool never got as far as opening
    # the design without a chosen feature suite). CONFIRMED LIVE 2026-10-21 as the actual
    # root cause behind the long-standing "PowerSI batch mode produces no S-params"
    # failure -- every `-b -tcl` run silently exited in ~3s rc=0, no window, no dialog ever
    # caught by the screen watcher, no side `.log`, for every macro tried (5/5 reproducible,
    # see sigrity_mcp/domains/si/powersi_tools.py's module docstring for the full evidence
    # trail and per-probe job dirs). Answer: select the relevant feature suite for the tool
    # being launched (PowerSI 2D for the S-parameter/RLGC extraction paths this suite
    # targets; "Choose all" is the dialog's own fallback "select every available suite"
    # button and is the safe universal answer on this no-license-restriction install,
    # matching the 'choose the default/continue answer' convention used for every other
    # selector dialog above) plus tick "Save the chosen suites and do not prompt again"
    # so subsequent launches skip the prompt entirely.
    "license": {
        # Multi-step (see core.gui_tool_runner._auto_answer_selector's "answer_steps"
        # contract): click "Choose all" (selects every available suite -- this install is
        # PREMIUM/no-license-restriction, so choosing all licensed suites is the correct,
        # universal answer, not an over-broad one) AND THEN separately click the dialog's
        # own final-dismiss "Close" button. A single-click keyword ladder alone (the old
        # default behavior) could only ever click the FIRST matched word and stop,
        # leaving the dialog open after just selecting suites -- `answer_steps` exists
        # precisely to drive both clicks in sequence.
        "answer_steps": ("choose all", "close"),
        "answer_keywords": ("choose all", "powersi 2d", "close"),
        "note": "one-time (persists if 'Save the chosen suites and do not prompt again' is "
        "also ticked): Sigrity analysis-tool feature-license-suite chooser. Auto-answers "
        "'Choose all' then 'Close' (two distinct controls, driven in order via "
        "answer_steps) so the tool has a valid feature checkout to actually run a "
        "simulation with, instead of silently exiting with no output.",
    },
}
"""Registry of 'make-a-selection' modals that block GUI-tool launches, plus how the
runner auto-answers each (default/local/localhost/continue). See module docstring and
`core.gui_tool_runner.preseed_selection` for the two-phase strategy (pre-seed before
launch, answer in-line if one still appears). This is the fix for the 'select a tree /
proxy / internet waiting' modal that is the root cause of most 'known blocked' labels."""


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
    exe is not present on disk (e.g. a differently-installed/edited edition).
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
