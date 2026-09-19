import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session
from sigrity_mcp.domains.thermal.celsius2d_tools import run_celsius2d_workspace
from sigrity_mcp.domains.thermal.celsius3d_tools import celsius3d_run_session, start_celsius3d_session
from sigrity_mcp.domains.thermal.celsiuscfd_tools import (
    celsiuscfd_run_session,
    celsiuscfd_set_solver_cpu_percentage,
    start_celsiuscfd_session,
)


@pytest.mark.asyncio
async def test_celsius3d_session_composes_confirmed_sequence(fake_exe):
    session = await start_celsius3d_session("case.3dth")
    sid = session["session_id"]
    preview = await preview_tcl_session(sid)
    assert "sigrity::configure version -version {5}" in preview["script"]
    assert "sigrity::open file -file {case.3dth}" in preview["script"]

    result = await celsius3d_run_session(sid, "case.3dth")
    assert result["command"][1] == "-tcl"
    # session should be closed by run_session's close_after=True default
    assert sid not in [s.session_id for s in tcl_sessions.list_sessions()]


@pytest.mark.asyncio
async def test_celsius3d_run_session_appends_confirmed_trailer():
    session = await start_celsius3d_session("case.3dth")
    sid = session["session_id"]
    tcl_sessions.add_line(sid, "sigrity::begin simulation -fileName {case.3dth}")
    preview = await preview_tcl_session(sid)
    assert "sigrity::begin simulation -fileName {case.3dth}" in preview["script"]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_celsiuscfd_session_composes_confirmed_sequence(fake_exe):
    session = await start_celsiuscfd_session("pcb.3dth")
    sid = session["session_id"]
    await celsiuscfd_set_solver_cpu_percentage(sid, 50)
    preview_before_run = tcl_sessions.preview(sid)
    assert "sigrity::update CFDSolverOptions -SolverCPUPercentage {50}" in preview_before_run

    result = await celsiuscfd_run_session(sid, "pcb.3dth")
    assert result["job_id"]


@pytest.mark.asyncio
async def test_run_celsius2d_workspace_default_flags(fake_exe):
    result = await run_celsius2d_workspace("demo.pdcx")
    assert result["command"][1:] == ["-b", "-XIMSAVE", "-r", "demo.pdcx"]


@pytest.mark.asyncio
async def test_run_celsius2d_workspace_no_excel_save(fake_exe):
    result = await run_celsius2d_workspace("demo.pdcx", save_excel_result=False)
    assert result["command"][1:] == ["-b", "-r", "demo.pdcx"]
