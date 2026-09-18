"""Domain 1 — Power Integrity (PI).

Covers PowerDC (DC IR-drop / electro-thermal co-simulation / thermal PI), XcitePI
(chip/package power integrity, decap & IO model extraction), and OptimizePI
(decap/VRM optimization, PDN target impedance). PowerTree has no standalone documented
batch invocation of its own — it's driven from *inside* PowerDC via the
`sigrity::do OneStepPowerTree` Tcl command, so it's exposed as one extra tool
(`powerdc_run_one_step_powertree`) inside `powerdc_tools.py` rather than as its own
package. `Optimality.exe` is a separate, unrelated Celsius thermal DoE tool despite the
similarly-spelled name and is intentionally not wrapped here.

All three tools that *are* wrapped here follow the same compose-then-run pattern as
Domain 2 (SI): a `start_*_session` tool opens a Tcl automation session (see
`sigrity_mcp.core.tclsession`), a series of `*_set_*`/`*_add_*`/`*_export_*` tools each
append one line to that session's in-memory script (no process launched), and a final
`*_run_session` tool writes the accumulated script out and launches the real tool as a
background job. Use the shared, generic `preview_tcl_session`/`close_tcl_session`/
`list_tcl_sessions` tools (`sigrity_mcp.domains.platform.session_tools`) to inspect or
discard a session, and the shared job-control tools (`get_job_status`, `wait_for_job`,
`tail_job_log`, `list_job_files`, `read_job_output_file`, `cancel_job`, `list_all_jobs`
in `sigrity_mcp.domains.platform.job_tools`) to track/retrieve a run's results.
"""

from sigrity_mcp.domains.pi import optimizepi_tools, powerdc_tools, xcitepi_tools  # noqa: F401
