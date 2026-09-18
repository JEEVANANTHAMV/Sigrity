"""T2B — SPICE-to-IBIS behavioral model conversion.

Ships in the same `tools/bin` folder as the layout translators but is functionally
unrelated to them — it converts a SPICE transistor-level I/O buffer model into an IBIS
behavioral model, driven by a `.t2b` control file. Confirmed CLI-only, no Tcl API.

Confirmed batch syntax:
    t2b -b [-check] [-validation <validation_file.xml>] [-ML:<n>] [-resume] [-skip] [-wait[:<timeout>]] <filename.t2b>
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

    Runs `t2b -b [-check] [-validation <validation_file>] [-ML:<num_licenses>] [-resume]
    [-skip] [-wait:<wait_timeout>] <t2b_file>`.
    `check_ibis=True` adds `-check` to validate the generated IBIS file after conversion.
    `validation_file` points T2B at an XML file describing extra validation criteria.
    `num_licenses` sets `-ML:<n>`, the number of licenses T2B may check out for parallel
    model extraction. `resume`/`skip_to_validation` map to `-resume`/`-skip` for
    continuing or jumping ahead in a previously interrupted run. `wait_timeout` (seconds)
    maps to `-wait:<wait_timeout>`, telling T2B to wait up to that long for a free license
    instead of failing immediately if none is available.
    T2B writes its output log named after the input file with a `.log` extension (e.g.
    `mymodel.t2b` -> `mymodel.log`) into the job directory — look for it via
    list_job_files/read_job_output_file once the job finishes.
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
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
