import os
import pytest

from sigrity_mcp.domains.cad.rigid_flex_stackup_tools import (
    generate_18layer_rigid_flex_stackup,
    get_high_speed_constraint_preset,
)


@pytest.mark.asyncio
async def test_generate_18layer_rigid_flex_stackup(tmp_path):
    scr_file = str(tmp_path / "stackup.scr")
    result = await generate_18layer_rigid_flex_stackup(output_script_path=scr_file)
    assert result["status"] == "success"
    assert result["layer_count"] == 18
    assert "L9_FLEX_SIG1" in result["flex_layers"]
    assert os.path.exists(scr_file)


@pytest.mark.asyncio
async def test_get_high_speed_constraint_preset():
    result = await get_high_speed_constraint_preset("DDR5")
    assert result["status"] == "success"
    assert result["constraints"]["diff_impedance_ohms"] == 80.0
    assert result["constraints"]["intra_pair_length_match_mils"] == 2.0

    pcie_res = await get_high_speed_constraint_preset("PCIE_GEN5")
    assert pcie_res["constraints"]["diff_impedance_ohms"] == 85.0
