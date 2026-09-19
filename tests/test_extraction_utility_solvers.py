import pytest

from sigrity_mcp.domains.extraction.utility_solvers import run_touchstone_deembed, run_xhatch_field_solver


@pytest.mark.asyncio
async def test_run_touchstone_deembed_cascade_mode(fake_exe):
    result = await run_touchstone_deembed(
        "C:/data",
        dut_touchstone_file="dut.s2p",
        left_touchstone_file="left.s2p",
        right_touchstone_file="right.s2p",
    )
    assert result["command"][1:] == [
        "-filepath", "C:/data", "-lefttsfile", "left.s2p", "-righttsfile", "right.s2p",
        "-duttsfile", "dut.s2p",
    ]


@pytest.mark.asyncio
async def test_run_touchstone_deembed_with_tsfile(fake_exe):
    result = await run_touchstone_deembed("C:/data", dut_touchstone_file="dut.s2p", touchstone_file="alls.s2p")
    assert result["command"][1:] == ["-filepath", "C:/data", "-tsfile", "alls.s2p", "-duttsfile", "dut.s2p"]


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
