import pytest

from sigrity_mcp.domains.cad.allegro_manufacturing_tools import (
    run_allegro_gerber_plot,
    run_ipc2581_export,
    run_ipc356_export,
    run_step_export,
)


@pytest.mark.asyncio
async def test_run_ipc2581_export_minimal(fake_exe):
    result = await run_ipc2581_export("board.brd")
    assert result["command"][1:] == ["board.brd"]


@pytest.mark.asyncio
async def test_run_ipc2581_export_with_attr_and_output(fake_exe):
    result = await run_ipc2581_export("board.brd", output_file="out.xml", attr_file="attrs.txt")
    assert result["command"][1:] == ["-g", "attrs.txt", "-o", "out.xml", "board.brd"]


@pytest.mark.asyncio
async def test_run_ipc356_export(fake_exe):
    result = await run_ipc356_export("board.brd", output_file="out.ipc")
    assert result["command"][1:] == ["board.brd", "out.ipc"]


@pytest.mark.asyncio
async def test_run_step_export(fake_exe):
    result = await run_step_export("board.brd", output_file="out.step")
    assert result["command"][1:] == ["-o", "out.step", "board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_gerber_plot(fake_exe):
    result = await run_allegro_gerber_plot("board.brd", output_file="out.art")
    assert result["command"][1:] == ["board.brd", "out.art"]
