import pytest

from sigrity_mcp.domains.cad.pspice_tools import run_pspice_simulation


@pytest.mark.asyncio
async def test_run_pspice_simulation(fake_exe):
    result = await run_pspice_simulation("circuit.cir")
    assert result["command"][1:] == ["circuit.cir"]
