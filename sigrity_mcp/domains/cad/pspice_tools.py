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

    Runs `psp_cmd.exe <circuit_file>` — confirmed live (see module docstring): the tool
    launches headlessly, reads the circuit, and reports specific, real diagnostics
    rather than hanging or crashing. `circuit_file` should be self-contained (no
    `.include` references to files that don't exist on this machine) — if it references
    external model/subcircuit files, make sure those are reachable from wherever this
    job actually runs (the job's own scratch directory, not the circuit file's original
    location), or pre-resolve/inline them before calling this tool.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job, then read
    the `.out` file (same base name as the input, `.out` extension) via
    list_job_files/read_job_output_file for full simulation results/diagnostics beyond
    this job's own stdout capture.
    """
    record = await submit_job(tool="psp_cmd", build_args=[circuit_file])
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
