"""PSpice batch circuit simulation — standalone CLI, no session needed.

CORRECTION to this project's own earlier research: `pspice.exe`/`pspiceaa.exe` were
probed directly and both hung with no output (consistent with a GUI launch), leading to
a "GUI-only" classification. `psp_cmd.exe` — a separate, dedicated batch-simulation
executable also shipped in the same `tools/bin` — was not probed in that pass.

CONFIRMED LIVE on this machine: a bare `psp_cmd.exe` prints `"Missing circuit file
argument"` and exits immediately (no GUI, no hang) — real headless CLI. Running
`psp_cmd.exe <circuit>.cir` against a real shipped OrCAD PSpice example
(`share/orcad/examples/PSpice/TI/DRV8837/.../trans.cir`) genuinely loaded and attempted
the simulation, printing a specific, readable diagnostic
(`ERROR(ORPSIM-15347): Cannot open input file ...`) when a `.include`d model file
referenced an absolute path from the original authoring machine that doesn't exist
here — a real, sample-portability issue, not a tool or license failure. A self-contained
`.cir` file (no missing `.include`s) should simulate cleanly with this same invocation.
"""

from __future__ import annotations

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def run_pspice_simulation(circuit_file: str) -> dict:
    """Run a batch PSpice circuit simulation against a `.cir` netlist, as a background job.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    record = await submit_job(tool="psp_cmd", build_args=[circuit_file])
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
