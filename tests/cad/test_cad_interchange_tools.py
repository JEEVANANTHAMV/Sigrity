import pytest

from sigrity_mcp.domains.cad.interchange_tools import run_apd2con, run_cap2xml, run_con2xml, run_dml2con


@pytest.mark.asyncio
async def test_run_con2xml_minimal(fake_exe):
    result = await run_con2xml("in.hdl")
    assert result["command"][1:] == ["in.hdl"]


@pytest.mark.asyncio
async def test_run_con2xml_with_output(fake_exe):
    result = await run_con2xml("in.hdl", output_file="out.xml")
    assert result["command"][1:] == ["in.hdl", "out.xml"]


@pytest.mark.asyncio
async def test_run_cap2xml(fake_exe):
    result = await run_cap2xml("design.dsn", output_file="out.xml")
    assert result["command"][1:] == ["design.dsn", "out.xml"]


@pytest.mark.asyncio
async def test_run_dml2con(fake_exe):
    result = await run_dml2con("lib.dml", output_file="lib.hdl")
    assert result["command"][1:] == ["lib.dml", "lib.hdl"]


@pytest.mark.asyncio
async def test_run_apd2con(fake_exe):
    result = await run_apd2con("pkg.apd", output_file="pkg.hdl")
    assert result["command"][1:] == ["pkg.apd", "pkg.hdl"]
