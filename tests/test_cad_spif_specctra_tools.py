import pytest

from sigrity_mcp.domains.cad.spif_specctra_tools import (
    run_specctra_autoroute,
    run_specctra_import_session,
    run_spif_export_to_specctra,
)


@pytest.mark.asyncio
async def test_run_spif_export_to_specctra_minimal(fake_exe):
    result = await run_spif_export_to_specctra("board.brd")
    assert result["command"][1:] == ["-o", "board.brd"]


@pytest.mark.asyncio
async def test_run_spif_export_to_specctra_with_output(fake_exe):
    result = await run_spif_export_to_specctra("board.brd", dsn_file="board.dsn")
    assert result["command"][1:] == ["-o", "board.brd", "board.dsn"]


@pytest.mark.asyncio
async def test_run_specctra_autoroute_headless_default(fake_exe):
    result = await run_specctra_autoroute("board.dsn", "route.do")
    assert result["command"][1:] == ["board.dsn", "-nog", "-do", "route.do", "-quit"]


@pytest.mark.asyncio
async def test_run_specctra_autoroute_graphics_mode(fake_exe):
    result = await run_specctra_autoroute("board.dsn", "route.do", graphics=True)
    assert result["command"][1:] == ["board.dsn", "-do", "route.do", "-quit"]


@pytest.mark.asyncio
async def test_run_specctra_import_session(fake_exe):
    result = await run_specctra_import_session("board.brd", "routed.ses")
    assert result["command"][1:] == ["-i", "board.brd", "routed.ses"]
