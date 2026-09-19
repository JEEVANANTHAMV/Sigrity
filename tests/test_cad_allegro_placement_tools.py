import pytest

from sigrity_mcp.core.errors import SigrityError
from sigrity_mcp.domains.cad.allegro_placement_tools import (
    run_allegro_ncroute,
    run_allegro_placement,
    run_allegro_zrouter,
)


@pytest.mark.asyncio
async def test_run_allegro_placement_no_flags(fake_exe):
    result = await run_allegro_placement("board.brd")
    assert result["command"][1:] == ["board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_placement_all_flags(fake_exe):
    result = await run_allegro_placement(
        "board.brd",
        output_file="placed.brd",
        iterate_while_improving=True,
        weight_edges=True,
        print_connection_matrix=True,
    )
    assert result["command"][1:] == ["-a", "-w", "-p", "board.brd", "placed.brd"]


@pytest.mark.asyncio
async def test_run_allegro_ncroute_minimal(fake_exe):
    result = await run_allegro_ncroute("board.brd")
    assert result["command"][1:] == ["board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_ncroute_with_flags(fake_exe):
    result = await run_allegro_ncroute("board.brd", output_file="drill.rte", verbose=True)
    assert result["command"][1:] == ["-v", "-o", "drill.rte", "board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_zrouter_refuses_to_run(fake_exe):
    # Confirmed live this pass: zrouter has no working batch/scriptable path (hangs
    # standalone, silently no-ops via the in-session console command) -- the tool must
    # refuse rather than launch a process that hangs or falsely reports success.
    with pytest.raises(SigrityError):
        await run_allegro_zrouter("board.brd", "control.txt", output_file="out.brd")
