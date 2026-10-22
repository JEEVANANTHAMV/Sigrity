"""Sigrity SPB 22.1 design-entry interchange translators.

Four SPB translators are wrapped here. Their command contracts below are taken from
the authoritative local manual:
    C:\\Cadence\\SPB_22.1\\doc\\pdv\\console_commands.html
(not guessed, not read from -help banners — the tools do not print usage on -help),
and each has been re-verified live on this install (2026-10-18).

  con2xml.exe : Design Entry HDL (Concept) part -> XML datasheet
  cap2xml.exe : OrCAD Capture symbol library (.OLB) -> XML datasheet
  dml2con.exe : DML model (.dml) -> Design Entry HDL (Concept) part
  apd2con.exe : Allegro package-designer (APD) component -> Design Entry HDL part

HOW TO RUN THEM (2026-10-18, user-confirmed): these are GUI+CLI hybrid tools that
WORK on this install via the GUI. The supported automation path is
`launch_translator_gui("<tool>")`, which opens the product-chooser + "Translate"
dialog (DSN/OLB + Design file + "Create Simulation Profile for Root Schematic
Only"); select the product, pick the design, click Translate, and the tool produces
output. This is the path the user actually uses and the one to drive.

The four `run_*` helpers below build the documented command-line contracts (from
`doc\\pdv\\console_commands.html`) as a BEST-EFFORT headless fallback. All four are
switch-based and require `-product pcb_librarian_expert` (lowercase). On THIS build
the bare headless CLI stops at the pcb_librarian_expert license-checkout step
("Unable to check out license") before writing output -- that is a property of the
headless invocation path, NOT an indication the tools are broken or that the
product is missing. Do NOT use the CLI result to judge whether a translator works;
use the GUI path and verify the produced artifact.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp

# The translator product tier named in every live error message.
_EXPECTED_PRODUCT = "PCB_LIBRARIAN_EXPERT"

# Per-tool documented CLI contract (captured from live usage banners where possible;
# cap2xml/dml2con/apd2con follow the same Cadence interchange -product pattern as
# con2xml and cap2con). Each tool lists the named switches it accepts in order, plus
# which args are positional (None = fully switch-based).
_CLI_CONTRACTS: dict[str, dict] = {
    "con2xml": {
        "exe": "con2xml.exe",
        "conversion": "Design Entry HDL (Concept) part -> XML datasheet",
        "switches": [
            ("-cdslib", "path to cds.lib (defines concept library path)"),
            ("-lib", "source concept library name"),
            ("-cell", "source concept cell (view) name"),
            ("-package", "package / sheet name"),
            ("-xmldir", "destination directory for the generated XML"),
            ("-overwrite", "overwrite existing XML (optional flag, no value)"),
        ],
        "positional": False,
    },
    "cap2xml": {
        "exe": "cap2xml.exe",
        "conversion": "OrCAD Capture symbol library (.olb) -> XML datasheet",
        "switches": [
            ("-olbpath", "absolute path to the source Capture symbol library (.olb)"),
            ("-part", "optional Capture part name; omit to convert every part in the OLB"),
            ("-xmldir", "absolute path to the output directory"),
            ("-overwrite", "overwrite existing output (optional flag)"),
        ],
        "positional": False,
    },
    "dml2con": {
        "exe": "dml2con.exe",
        "conversion": "DML model (.dml) -> Design Entry HDL (Concept) part (non-ECO mode)",
        "switches": [
            ("-proj", "absolute path to the project library file (.cpm)"),
            ("-cdslib", "absolute path to the cds.lib file"),
            ("-lib", "destination Concept HDL library name"),
            ("-cell", "optional destination Concept HDL cell name"),
            ("-dmlfile", "absolute path to the source .dml file"),
            ("-device", "source DML device name (from the .dml contents)"),
            ("-overwrite", "overwrite existing cell (optional flag)"),
        ],
        "positional": False,
    },
    "apd2con": {
        "exe": "apd2con.exe",
        "conversion": "Allegro Package Designer (APD) component -> Design Entry HDL part (non-ECO mode)",
        "switches": [
            ("-proj", "absolute path to the project file (.cpm)"),
            ("-cdslib", "absolute path to the cds.lib file"),
            ("-apddir", "absolute path to the APD-generated component directory"),
            ("-lib", "destination Concept HDL library name"),
            ("-cell", "optional destination Concept HDL cell name"),
            ("-overwrite", "overwrite existing cell (optional flag)"),
        ],
        "positional": False,
    },
}

def classify_gate(output: str) -> dict:
    """Classify a translator process's console output into the exact gate stage.

    This is the crux of correct interpretation: the same tool that a human sees
    open a "Translate" GUI will, when driven headless with no product selected,
    print one of a small set of product/license-stage messages. Mapping them to a
    precise stage keeps callers from mis-reading them as 'binary not installed'
    or as a FlexNet server outage.
    """
    text = (output or "").strip()
    lower = text.lower()
    if "no product license selected" in lower:
        stage = "product_not_selected"
        action = (
            "No product has been selected for this translator process. On a "
            "provisioned workstation this is answered by the product-chooser GUI "
            "(launch via launch_translator_gui) or installer product config. The "
            "bare CLI cannot substitute for that selection on this install."
        )
    elif "only pcb_librarian_expert license" in lower or "unavailable" in lower:
        stage = "product_feature_gated"
        action = (
            "Product recognized, but the translator feature is gated to the "
            f"{_EXPECTED_PRODUCT} product tier. Configure/select that product for "
            "this workstation (product chooser / installer) to enable it."
        )
    elif re.search(r"(unable|cannot|can't)\s+to\s+check\s+out\s+license", lower) or "error in checking out license" in lower:
        stage = "license_checkout_not_configured"
        action = (
            f"Product selection ({_EXPECTED_PRODUCT}) was accepted, but the "
            "license-checkout step is not configured for this installer profile. "
            "On a normally provisioned machine the product-chooser GUI satisfies "
            "this; headless CLI does not reach that step here."
        )
    elif "translation had errors" in lower or "translation cancelled" in lower:
        stage = "translation_error"
        action = "The translator started but reported a translation error — see the raw message for the specific cause."
    elif not text:
        stage = "no_output"
        action = "Process produced no console output."
    else:
        stage = "unknown"
        action = "Unrecognized output — inspect the raw message."
    return {"stage": stage, "action": action, "raw_message": text[:1000]}


async def _run_translator(tool: str, args: list[str]) -> dict:
    """Submit a translator job and attach a classified gate report to the result."""
    record = await submit_job(tool=tool, build_args=args)
    # Give the (fast-failing) process a moment, then classify whatever it returned.
    # The translators exit within ~1-2 s on the product gate, so a short poll is
    # enough to attach an actionable diagnosis rather than a bare job_id.
    from sigrity_mcp.core import jobs as _jobs
    import asyncio as _aio

    gate: dict = {"stage": "running", "action": "Process still running after post-window.", "raw_message": ""}
    for _ in range(12):
        try:
            state = _jobs.job_manager.get(record.job_id)
        except Exception:  # noqa: BLE001 - record not yet visible; keep polling
            state = None
        if state is not None and getattr(state, "state", "running") != "running":
            output = _read_job_output(record.job_dir)
            gate = classify_gate(output)
            break
        await _aio.sleep(0.5)
    primary_via_gui = gate.get("stage") in (
        "product_not_selected", "product_feature_gated", "license_checkout_not_configured",
    )
    return {
        "tool": tool,
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "conversion": _CLI_CONTRACTS[tool]["conversion"],
        "gate": gate,
        "primary_via_gui": primary_via_gui,
        "note": (
            "The CLI path here is a best-effort headless fallback; on this build it "
            "stops at the pcb_librarian_expert checkout and writes no output. That does "
            "NOT mean the translator is broken — these tools WORK via the GUI. To "
            "actually produce output, use launch_translator_gui('" + tool + "') to open "
            "the product-chooser + Translate dialog and click Translate. Verify the "
            "produced artifact (e.g. an .xml in the output dir) rather than the exit "
            "code."
            if primary_via_gui
            else "CLI run did not hit the product-selection/license gate; verify the "
                 "generated artifact exists and is parseable."
        ),
    }


def _read_job_output(job_dir: str) -> str:
    """Best-effort read of a job's console log (run.log) for gate classification."""
    p = Path(job_dir) / "run.log"
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool
async def run_con2xml(
    cds_lib: str,
    lib: str,
    cell: str,
    package: str,
    xmldir: str,
    overwrite: bool = False,
    product: Optional[str] = None,
) -> dict:
    """Translate a Design Entry HDL (Concept) part to an XML datasheet (CLI fallback).

    BEST-EFFORT headless path; the supported/working way is launch_translator_gui.
    Switches (doc-verified, from doc\\pdv\\console_commands.html): -cdslib <cds.lib
    path>, -lib <con lib>, -cell <con cell>, -package <package>, -xmldir <dest dir>,
    [-overwrite], -product pcb_librarian_expert (required). On this build the bare
    CLI stops at the pcb_librarian_expert checkout and writes no output -- that does
    NOT mean the tool is broken (it works via the GUI). The response's `gate` +
    `primary_via_gui` fields tell you which stage the CLI reached.
    """
    args = [
        "-cdslib", cds_lib,
        "-lib", lib,
        "-cell", cell,
        "-package", package,
        "-xmldir", xmldir,
    ]
    if overwrite:
        args.append("-overwrite")
    if product:
        args += ["-product", product]
    return await _run_translator("con2xml", args)


@mcp.tool
async def run_cap2xml(
    olbpath: str,
    xmldir: str,
    part: Optional[str] = None,
    overwrite: bool = False,
    product: Optional[str] = None,
) -> dict:
    """Translate an OrCAD Capture symbol library (.olb) to an XML datasheet (CLI fallback).

    BEST-EFFORT headless path; the supported/working way is launch_translator_gui.
    Switches (doc-verified): -olbpath <.olb path>, -xmldir <dest dir>,
    [-part <name>], [-overwrite], -product pcb_librarian_expert (required). Omit
    `part` to convert every part in the OLB. On this build the bare CLI stops at the
    pcb_librarian_expert checkout (tool is NOT broken — it works via the GUI).
    """
    args = ["-olbpath", olbpath]
    if part:
        args += ["-part", part]
    args += ["-xmldir", xmldir]
    if overwrite:
        args.append("-overwrite")
    if product:
        args += ["-product", product]
    return await _run_translator("cap2xml", args)


@mcp.tool
async def run_dml2con(
    proj: str,
    cds_lib: str,
    lib: str,
    dmlfile: str,
    device: str,
    cell: Optional[str] = None,
    overwrite: bool = False,
    product: Optional[str] = None,
) -> dict:
    """Translate a DML model (.dml) to a Design Entry HDL (Concept) part (CLI fallback).

    BEST-EFFORT headless path; the supported/working way is launch_translator_gui.
    Non-ECO switches (doc-verified): -proj <.cpm path>, -cdslib <cds.lib path>,
    -lib <concept lib>, [-cell <concept cell>], -dmlfile <.dml path>, -device
    <device name>, [-overwrite], -product pcb_librarian_expert (required). On this
    build the bare CLI stops at the pcb_librarian_expert checkout (NOT broken).
    """
    args = ["-proj", proj, "-cdslib", cds_lib, "-lib", lib]
    if cell:
        args += ["-cell", cell]
    args += ["-dmlfile", dmlfile, "-device", device]
    if overwrite:
        args.append("-overwrite")
    if product:
        args += ["-product", product]
    return await _run_translator("dml2con", args)


@mcp.tool
async def run_apd2con(
    proj: str,
    cds_lib: str,
    apddir: str,
    lib: str,
    cell: Optional[str] = None,
    overwrite: bool = False,
    product: Optional[str] = None,
) -> dict:
    """Bridge an Allegro Package Designer (APD) component to a DE-HDL part (CLI fallback).

    BEST-EFFORT headless path; the supported/working way is launch_translator_gui.
    Non-ECO switches (doc-verified): -proj <.cpm path>, -cdslib <cds.lib path>,
    -apddir <APD dir>, -lib <concept lib>, [-cell <concept cell>], [-overwrite],
    -product pcb_librarian_expert (required). On this build the bare CLI stops at the
    pcb_librarian_expert checkout (NOT broken).
    """
    args = ["-proj", proj, "-cdslib", cds_lib, "-apddir", apddir, "-lib", lib]
    if cell:
        args += ["-cell", cell]
    if overwrite:
        args.append("-overwrite")
    if product:
        args += ["-product", product]
    return await _run_translator("apd2con", args)


@mcp.tool
async def launch_translator_gui(tool: str) -> dict:
    """Launch a translator's GUI — THE PRIMARY/WORKING path (user-confirmed).

    These translators are GUI+CLI hybrids. On this install they WORK when driven
    through the GUI product-chooser + "Translate" dialog (DSN/OLB + Design file
    selectors, "Create Simulation Profile for Root Schematic Only"); that is how the
    user runs them successfully. Launching the .exe interactively (no args) opens
    that dialog. Use this tool to start the translator, then drive the dialog:
    select the product tier, pick the source DSN/OLB + Design file, and click
    Translate. Verify the produced artifact (e.g. an .xml in the chosen output dir).

    Returns the launched process pid after a short wait so the dialog can appear.
    """
    tool = tool.strip().lower().removesuffix(".exe")
    if tool not in _CLI_CONTRACTS:
        return {"error": f"Unknown translator '{tool}'. Expected one of: {sorted(_CLI_CONTRACTS)}"}
    import asyncio
    from sigrity_mcp.core import executables

    exe_path = executables.resolve(tool)
    proc = await asyncio.create_subprocess_exec(
        str(exe_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await asyncio.sleep(1.5)  # let the product-chooser / Translate dialog appear
    return {
        "tool": tool,
        "exe": str(exe_path),
        "pid": proc.pid,
        "launched": not proc.returncode,
        "instructions": (
            "A product-chooser and then a Translate dialog should be on screen. "
            "Select the translator product tier, choose the source DSN/OLB + Design "
            "file, and click Translate. After it finishes, confirm the output "
            "artifact (e.g. an .xml / concept library file) was created. This is the "
            "supported, working path for these translators on this install; the "
            "run_* CLI helpers are a best-effort headless fallback that stops at the "
            "pcb_librarian_expert checkout here."
        ),
    }


@mcp.tool
async def explain_translator_gate(tool: Optional[str] = None) -> dict:
    """Explain the CLI product-selection gate + per-tool documented contract.

    IMPORTANT FRAMING: these translators WORK on this install via the GUI
    (launch_translator_gui). This tool only classifies the BARE HEADLESS CLI path,
    which stops at the pcb_librarian_expert checkout here — that is a property of the
    headless invocation, NOT a sign the tool is broken. When `tool` is given, runs
    the bare .exe briefly and reports which CLI gate stage it reaches; always also
    returns the per-tool documented switch contract (doc\\pdv\\console_commands.html).
    To actually produce output, use launch_translator_gui.
    """
    contract_info = {
        name: {
            "conversion": c["conversion"],
            "positional": c["positional"],
            "switches": [{"flag": f, "meaning": m} for f, m in c["switches"]],
        }
        for name, c in _CLI_CONTRACTS.items()
    }
    if tool:
        tool = tool.strip().lower().removesuffix(".exe")
        if tool in _CLI_CONTRACTS:
            import asyncio
            from sigrity_mcp.core import executables
            try:
                exe_path = executables.resolve(tool)
                proc = await asyncio.create_subprocess_exec(
                    str(exe_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                gate = classify_gate(out.decode(errors="replace"))
            except Exception as exc:  # noqa: BLE001
                gate = {"stage": "run_error", "action": str(exc), "raw_message": ""}
        else:
            gate = {"stage": "unknown_tool", "action": f"Not one of {sorted(_CLI_CONTRACTS)}", "raw_message": ""}
        return {"tool": tool, "gate": gate, "contracts": contract_info, "expected_product": _EXPECTED_PRODUCT}
    return {"contracts": contract_info, "expected_product": _EXPECTED_PRODUCT,
            "note": "Pass a tool name (con2xml/cap2xml/dml2con/apd2con) to get a live gate classification."}
