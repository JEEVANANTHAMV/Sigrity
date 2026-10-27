import os
from pathlib import Path

import pytest

from sigrity_mcp.domains.extraction.utility_solvers import (
    run_touchstone_deembed,
    run_xhatch_field_solver,
    run_xpitechgen,
)


@pytest.mark.asyncio
async def test_run_touchstone_deembed_cascade_mode(fake_exe):
    result = await run_touchstone_deembed(
        "C:/data",
        dut_touchstone_file="dut.s2p",
        left_touchstone_file="left.s2p",
        right_touchstone_file="right.s2p",
    )
    assert result["command"][1:] == [
        "-filepath", "C:/data" + os.sep, "-lefttsfile", "left.s2p", "-righttsfile", "right.s2p",
        "-duttsfile", "dut.s2p",
    ]


@pytest.mark.asyncio
async def test_run_touchstone_deembed_with_tsfile(fake_exe):
    result = await run_touchstone_deembed("C:/data", dut_touchstone_file="dut.s2p", touchstone_file="alls.s2p")
    assert result["command"][1:] == ["-filepath", "C:/data" + os.sep, "-tsfile", "alls.s2p", "-duttsfile", "dut.s2p"]


@pytest.mark.asyncio
async def test_run_touchstone_deembed_appends_trailing_separator_when_missing(fake_exe):
    # Regression coverage for a real, confirmed-live abcd.exe defect: -filepath's value
    # resolves the tsfile/lefttsfile/righttsfile/duttsfile arguments ONLY when it ends
    # in a trailing path separator -- without one, abcd silently does nothing (rc 0, no
    # output, no error). Every prior caller passed a bare directory path with no
    # trailing separator, which reproduced the no-op 100% of the time.
    result = await run_touchstone_deembed("C:/data", dut_touchstone_file="dut.s2p", touchstone_file="alls.s2p")
    assert result["command"][1] == "-filepath"
    assert result["command"][2].endswith(os.sep)


@pytest.mark.asyncio
async def test_run_touchstone_deembed_does_not_double_up_an_existing_trailing_separator(fake_exe):
    result = await run_touchstone_deembed("C:/data/", dut_touchstone_file="dut.s2p", touchstone_file="alls.s2p")
    assert result["command"][2] == "C:/data/"


@pytest.mark.asyncio
async def test_run_xhatch_field_solver_solid_ground(fake_exe):
    result = await run_xhatch_field_solver("geo.in", "results.out")
    assert result["command"][1:] == ["-in", "geo.in", "-out", "results.out"]


@pytest.mark.asyncio
async def test_run_xhatch_field_solver_xhatch_mode(fake_exe):
    result = await run_xhatch_field_solver(
        "geo.in",
        "results.out",
        xhatch_mode=True,
        hatch_space_meters=0.0005,
        hatch_line_width_meters=0.0002,
        hatch_angle_degrees=45,
    )
    assert result["command"][1:] == [
        "-in", "geo.in", "-out", "results.out", "-xhatchmode", "y",
        "-xhatchhp", "0.0005", "-xhatchw", "0.0002", "-xhatchangle", "45",
    ]


@pytest.mark.asyncio
async def test_run_xpitechgen_internal_key(fake_exe):
    # 2026-10-26: run_xpitechgen wraps XPITechGen.exe (XcitePI tech-file encryption,
    # CONFIRMED LIVE). Both -i/-o are absolute-ified relative to the server's cwd because
    # the job runs with a fresh per-job scratch dir as cwd -- a relative path would send
    # the tools/bin CLI into the interactive re-prompt loop documented in core/paths.py.
    in_abs = str(Path("in.tech").resolve())
    out_abs = str(Path("out.tech").resolve())
    result = await run_xpitechgen("in.tech", "out.tech")
    assert result["command"][1:] == ["-i", in_abs, "-o", out_abs]
    assert "note" in result  # the tool tells the caller to verify the output artifact
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_run_xpitechgen_with_custom_key(fake_exe):
    in_abs = str(Path("in.tech").resolve())
    out_abs = str(Path("out.tech").resolve())
    result = await run_xpitechgen("in.tech", "out.tech", key="my-key-123")
    assert result["command"][1:] == ["-i", in_abs, "-o", out_abs, "-key", "my-key-123"]


def test_run_xpitechgen_registered_against_xpitechgen_exe():
    # The logical tool name maps to XPITechGen.exe, NOT xtractim (XtractIM.exe) -- the
    # two are distinct executables (one encrypts XcitePI tech files, the other is the
    # 2.5D/3D extraction solver). Assert against the registry itself, bypassing the
    # fake_exe monkeypatch (which replaces executables.resolve for the in-test job
    # launch and would shadow the real registry lookup).
    from sigrity_mcp.core.executables import EXECUTABLES
    assert EXECUTABLES["xtractim_techgen"] == "XPITechGen.exe"
