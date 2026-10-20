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
async def test_run_allegro_zrouter_uses_nograph_batch_launcher(fake_exe):
    result = await run_allegro_zrouter(
        "board.brd",
        "control.txt",
        output_file="out.brd",
        x_grid=10.0,
        y_grid=10.0,
        min_space=5.0,
    )
    # The command must be `allegro -nograph -s <script> <board>` — the confirmed-live
    # headless batch mechanism (not the old interactive-GUI session). build_args (-nograph)
    # come before the script flag, so the argv is [exe, -nograph, -s, script, board].
    assert result["command"][-1] == "board.brd"
    assert result["command"][-2].endswith("zrouter_run.scr")
    assert result["command"][-3] == "-s"
    assert "-nograph" in result["command"]
