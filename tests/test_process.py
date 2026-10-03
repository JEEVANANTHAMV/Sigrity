"""Tests for core.process.submit_job's argv-construction options added for OrCAD Capture
(positional script arg, no flag) and Allegro (SKILL command-replay, non-.tcl filename).
"""

from pathlib import Path

import pytest

from sigrity_mcp.core import jobs as jobs_module
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


@pytest.mark.asyncio
async def test_dismiss_dialogs_flag_reaches_job_manager_submit(fake_exe, monkeypatch):
    """submit_job's dismiss_dialogs param must actually reach JobManager.submit (not get
    silently dropped) -- this is the one thing standing between a modal Allegro startup
    dialog and an indefinite hang (see win32gui_helper.DismissWatcher's docstring for the
    confirmed-live failure mode)."""
    seen = {}
    real_submit = jobs_module.JobManager.submit

    async def _spy_submit(self, *args, **kwargs):
        seen["dismiss_dialogs"] = kwargs.get("dismiss_dialogs", False)
        return await real_submit(self, *args, **kwargs)

    monkeypatch.setattr(jobs_module.JobManager, "submit", _spy_submit)

    script = TclScript().raw("skill (something)")
    await submit_job(tool="fake_tool", tcl_script=script, tcl_arg_flag="-s",
                      script_filename="macro.scr", dismiss_dialogs=True)
    assert seen["dismiss_dialogs"] is True

    seen.clear()
    await submit_job(tool="fake_tool", tcl_script=script, tcl_arg_flag="-s",
                      script_filename="macro.scr")
    assert seen["dismiss_dialogs"] is False
