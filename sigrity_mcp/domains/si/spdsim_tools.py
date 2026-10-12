"""SPDSIM — legacy SPEED2000 transmission-line field solver.

Confirmed (doc/spd2k_ug, doc/speedem_ug, zero Tcl hits in either): SPDSIM has no Tcl
API at all — it's driven entirely by CLI switches against a `.spd` project file
authored in SPDGEN (SPDGEN itself is GUI-only; no batch/Tcl automation is documented
for it, so it isn't wrapped here).

RE-TESTED 2026-10-11 and CONFIRMED WORKING standalone — the earlier "blocked" status was
a misdiagnosis, now corrected (see `core.tool_status`'s `spdsim` note for the full
evidence). A clean `SPDSIM.exe -b <file.spd>` with the CWD set to the folder containing
the .spd (the trial sample `share\\PostInstallationCheck\\spdsim\\ESD_testcase0.spd`) ran
the full transient to rtlog 99%, 0 errors/0 warnings, and wrote real artifacts (a ~1MB
C.CUR, a ~4.2MB V.CUR, a dc.out). The "Skip license fetch" line is a benign no-license
probe on this install (no license exists to fetch), NOT fatal — and "Failed to open the
file" was the CWD-relative path not resolving. Two takeaways from the re-test: (1) the
older hypothesis (drive it via `sigrity::do exec ...` inside a live PowerSI session) is
UNNEEDED and is also not valid in 24.0 — standalone `-b` works; (2) judge success by the
ARTIFACTS (C.CUR/V.CUR/dc.out/rtlog) and the CWD, never by that single log line. This
tool is routed through the GUI-tool runner (GUI_TOOL_EXE_NAMES) purely because SPDSIM can
open a GUI in some flows — a quiet successful console run must not be mistaken for
"needs_user_intervention".
"""

from __future__ import annotations

from typing import Optional

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_spdsim_simulation(
    spd_file: str,
    save_interval_steps: Optional[int] = None,
    minimized_window: bool = False,
    logs: Optional[str] = None,
) -> dict:
    """Run a SPDSIM transmission-line field simulation against a `.spd` project (built beforehand in SPDGEN) as a background job.
See `.forjinn/skills/sigrity-si/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    args = ["-b"]
    if minimized_window:
        args.append("-s")
    if save_interval_steps is not None:
        args.append(f"-n{save_interval_steps}")
    if logs is not None:
        args.append(f"-r:{logs}" if logs else "-r")
    args.append(spd_file)

    record = await submit_job(tool="spdsim", build_args=args)
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
