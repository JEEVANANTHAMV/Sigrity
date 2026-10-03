import pytest

from sigrity_mcp.domains.si.broadbandspice_tools import (
    run_broadbandspice_check,
    run_broadbandspice_extraction,
)

# Regression coverage for a real documented gap: BroadbandSPICE writes its real
# output next to the input network_file's own directory, never into a separate
# report location the wrapper's return value previously mentioned at all -- a
# caller checking only job_dir/list_job_files would find nothing and wrongly
# conclude the run failed.


@pytest.mark.asyncio
async def test_run_extraction_surfaces_artifact_dir(fake_exe, tmp_path):
    network_file = tmp_path / "subdir" / "network.s2p"
    result = await run_broadbandspice_extraction(str(network_file))
    assert result["artifact_dir"] == str(network_file.parent)
    assert "BBSResult_" in result["note"]


@pytest.mark.asyncio
async def test_run_extraction_builds_correct_argv(fake_exe):
    result = await run_broadbandspice_extraction(
        "network.s2p", mode="Precision", netlist_format="SPICE", max_iterations=50, upper_frequency_ghz=40.0
    )
    assert result["command"][1:] == ["-b", "-Precision", "-SPICE", "-i50", "-uf40.0", "network.s2p"]


@pytest.mark.asyncio
async def test_run_check_surfaces_artifact_dir_and_report_name(fake_exe, tmp_path):
    network_file = tmp_path / "net.s4p"
    result = await run_broadbandspice_check(str(network_file))
    assert result["artifact_dir"] == str(network_file.parent)
    assert "Checking Report" in result["note"]
    assert result["command"][1:] == ["-b", "-Checking", str(network_file)]
