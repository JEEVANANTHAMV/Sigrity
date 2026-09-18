import pytest

from sigrity_mcp.domains.si.broadbandspice_tools import run_broadbandspice_check, run_broadbandspice_extraction
from sigrity_mcp.domains.si.spdsim_tools import run_spdsim_simulation


@pytest.mark.asyncio
async def test_spdsim_builds_correct_argv(fake_exe):
    result = await run_spdsim_simulation("design.spd", save_interval_steps=50, logs="ept")
    assert result["command"][1:] == ["-b", "-n50", "-r:ept", "design.spd"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_spdsim_defaults_omit_optional_flags(fake_exe):
    result = await run_spdsim_simulation("design.spd")
    assert result["command"][1:] == ["-b", "design.spd"]


@pytest.mark.asyncio
async def test_broadbandspice_extraction_argv(fake_exe):
    result = await run_broadbandspice_extraction(
        "network.s4p", mode="Precision", netlist_format="SPICE", output_circuit_file="out.sp", ignore_threshold=0.01
    )
    assert result["command"][1:] == [
        "-b", "-Precision", "-SPICE", "-i200", "-uf125.0", "-cf:out.sp", "-ign0.01", "network.s4p",
    ]


@pytest.mark.asyncio
async def test_broadbandspice_check_argv(fake_exe):
    result = await run_broadbandspice_check("network.s4p")
    assert result["command"][1:] == ["-b", "-Checking", "network.s4p"]
