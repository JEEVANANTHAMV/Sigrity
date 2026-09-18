"""Tests for core.process.submit_job's argv-construction options added for OrCAD Capture
(positional script arg, no flag) and Allegro (SKILL command-replay, non-.tcl filename).
"""

from pathlib import Path

import pytest

from sigrity_mcp.core.process import submit_job
from sigrity_mcp.core.tclscript import TclScript


@pytest.mark.asyncio
async def test_default_tcl_arg_flag_and_filename_unchanged(fake_exe):
    script = TclScript().raw("puts hello")
    record = await submit_job(tool="fake_tool", tcl_script=script)
    assert record.command[1:3] == ["-TCL", str(Path(record.job_dir) / "macro.tcl")]
    assert (Path(record.job_dir) / "macro.tcl").is_file()


@pytest.mark.asyncio
async def test_tcl_arg_flag_none_appends_script_positionally(fake_exe):
    script = TclScript().raw("puts hello")
    record = await submit_job(
        tool="fake_tool",
        build_args=["-product=OrCAD Capture"],
        tcl_script=script,
        tcl_arg_flag=None,
    )
    script_path = str(Path(record.job_dir) / "macro.tcl")
    assert record.command[1:] == ["-product=OrCAD Capture", script_path]


@pytest.mark.asyncio
async def test_custom_script_filename_used_on_disk(fake_exe):
    script = TclScript().raw("skill load(\"x.il\")")
    record = await submit_job(
        tool="fake_tool",
        build_args=["-s"],
        tcl_script=script,
        tcl_arg_flag=None,
        script_filename="macro.scr",
    )
    written = Path(record.job_dir) / "macro.scr"
    assert written.is_file()
    assert not (Path(record.job_dir) / "macro.tcl").exists()
    assert record.command[1:] == ["-s", str(written)]
