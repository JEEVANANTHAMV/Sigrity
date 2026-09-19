import pytest

from sigrity_mcp.domains.cad.allegro_drc_tools import run_allegro_batch_drc, run_allegro_checkplus


@pytest.mark.asyncio
async def test_run_allegro_batch_drc_default_nographic(fake_exe):
    result = await run_allegro_batch_drc("board.brd")
    assert result["command"][1:] == ["-nographic", "board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_batch_drc_with_output_and_graphic(fake_exe):
    result = await run_allegro_batch_drc("board.brd", output_file="drc.txt", nographic=False)
    assert result["command"][1:] == ["board.brd", "drc.txt"]


@pytest.mark.asyncio
async def test_run_allegro_checkplus_minimal(fake_exe):
    result = await run_allegro_checkplus("proj")
    assert result["command"][1:] == ["-proj", "proj"]


@pytest.mark.asyncio
async def test_run_allegro_checkplus_all_options(fake_exe):
    result = await run_allegro_checkplus(
        "proj",
        verbose=True,
        max_messages=50,
        include_path="C:/inc",
        env_file="env.txt",
        rule_file="rules.txt",
    )
    assert result["command"][1:] == [
        "-proj", "proj", "-verbose", "-max_messages", "50",
        "-I", "C:/inc", "-r", "env.txt", "-r", "rules.txt",
    ]
