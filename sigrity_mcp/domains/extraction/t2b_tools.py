"""T2B — SPICE-to-IBIS behavioral model conversion.

Ships in the same `tools/bin` folder as the layout translators but is functionally
unrelated to them — it converts a SPICE transistor-level I/O buffer model into an IBIS
behavioral model, driven by a `.t2b` control file. Confirmed CLI-only, no Tcl API.

Confirmed batch syntax:
    t2b -b [-check] [-validation <validation_file.xml>] [-ML:<n>] [-resume] [-skip] [-wait[:<timeout>]] <filename.t2b>

IMPORTANT, confirmed live on this machine (Sigrity 2024.0): T2B has no SPICE engine of
its own — it shells out to an EXTERNAL SPICE simulator and fails (silently, or with a
license/timeout stall in our run) unless one is installed and findable.

  * The engine is chosen per `[Spice type]` in the `.t2b` control file: `HSPICE` (the
    samples under share/SpeedXP/Samples/T2B/Example1/*.t2b) or `Spectre` (the
    Example_Spectre/Example_Spectre1 samples). Cadence's own HSPICE (the v6952-era
    "HSPICE" referenced throughout doc/t2b_hspice, i.e. v69a_dq.sp / HSPICE -C
    client-server mode per doc/t2b_qref's "Running HSPICE in Client-Server Mode") is a
    SEPARATE product that is NOT installed on this machine:
      - No `hspice.exe` anywhere under C:\Cadence (Sigrity Suite or SPB).
      - `reg query "HKCR\\HSpice.Application"` and `reg query "HKCR\\HSpice.HSpice"` both
        fail — HSpice exposes NO COM interface on this box, so there is no COM
        alternative to reach it either. A full `reg query HKCR /f HSpice /d` returns 0
        matches.
      - No `_t2b_config.ini` (the file T2B reads to point at a HSPICE command line, incl.
        the `[command_extension] +grid` option) is present in the install.
  * Cadence ships its *own* SPICE engines with SPB_22.1 — chsim.exe, SimSrvr.exe,
    tlsim.exe, cktsim.exe, modelsim.exe — but these are CLI/GUI simulators, none
    register a COM object T2B can call, so they are not drop-in HSpice
    substitutes for T2B. T2B's HSPICE code path specifically invokes the Cadence HSPICE
    `hspice` command (or `hspice -C` server), not a generic engine.
  * Practical consequence on this machine: `run_t2b_conversion` on an HSPICE-type `.t2b`
    (the bundled Example1/buffer.t2b) will not produce an IBIS model because there is no
    HSPICE to run. A Spectrum-type `.t2b` (Example_Spectre/*) is the variant that could
    work here IF Spectre is installed and licensed — verify with `run_quick(tool=...,
    ["-help"])`-style probing, but even Spectre is not clearly installed. The module
    should be extended (or callers should be told) that HSPICE-backed T2B is
    effectively unsupported in this environment.
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_t2b_conversion(
    t2b_file: str,
    check_ibis: bool = False,
    validation_file: Optional[str] = None,
    num_licenses: Optional[int] = None,
    resume: bool = False,
    skip_to_validation: bool = False,
    wait_timeout: Optional[float] = None,
) -> dict:
    """Convert a SPICE I/O buffer model to an IBIS behavioral model using T2B, as a background job.
See `.forjinn/skills/sigrity-extraction/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-b"]
    if check_ibis:
        args.append("-check")
    if validation_file:
        args += ["-validation", validation_file]
    if num_licenses is not None:
        args.append(f"-ML:{num_licenses}")
    if resume:
        args.append("-resume")
    if skip_to_validation:
        args.append("-skip")
    if wait_timeout is not None:
        args.append(f"-wait:{wait_timeout}")
    args.append(t2b_file)

    record = await submit_job(tool="t2b", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
