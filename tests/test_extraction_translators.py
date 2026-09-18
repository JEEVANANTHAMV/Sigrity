import pytest

from sigrity_mcp.domains.extraction.translators import (
    translate_dsn_to_spd,
    translate_gds_to_spd,
    translate_ndd_to_spd,
    translate_oasis_to_spd,
    translate_pads_to_spd,
    translate_rif_to_spd,
    translate_to_spd_via_spdlinks,
)


@pytest.mark.asyncio
async def test_gds_to_spd_explicit_flags(fake_exe):
    result = await translate_gds_to_spd("design.gds", "design.spd", map_file="layer.map", tech_file="stackup.tech")
    assert result["command"][1:] == [
        "-b", "-gds", "design.gds", "-map", "layer.map", "-tech", "stackup.tech", "-spd", "design.spd",
    ]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_gds_to_spd_log_replay_mode_drops_map_tech(fake_exe):
    result = await translate_gds_to_spd(
        "design.gds", "design.spd", map_file="layer.map", tech_file="stackup.tech", log_file="prev.log"
    )
    assert result["command"][1:] == ["-b", "-log", "prev.log", "design.gds", "design.spd"]


@pytest.mark.asyncio
async def test_oasis_to_spd_optional_map_tech_omitted(fake_exe):
    result = await translate_oasis_to_spd("design.oasis", "design.spd")
    assert result["command"][1:] == ["-b", "-oasis", "design.oasis", "-spd", "design.spd"]


@pytest.mark.asyncio
async def test_oasis_to_spd_with_map_tech(fake_exe):
    result = await translate_oasis_to_spd("design.oasis", "design.spd", map_file="l.map", tech_file="t.tech")
    assert result["command"][1:] == [
        "-b", "-oasis", "design.oasis", "-map", "l.map", "-tech", "t.tech", "-spd", "design.spd",
    ]


@pytest.mark.asyncio
async def test_ndd_to_spd_positional(fake_exe):
    result = await translate_ndd_to_spd("design.ndd", "design.spd")
    assert result["command"][1:] == ["-b", "design.ndd", "design.spd"]


@pytest.mark.asyncio
async def test_ndd_to_spd_log_replay(fake_exe):
    result = await translate_ndd_to_spd("design.ndd", "design.spd", log_file="prev.log")
    assert result["command"][1:] == ["-b", "-log", "prev.log", "design.ndd", "design.spd"]


@pytest.mark.asyncio
async def test_pads_to_spd_positional(fake_exe):
    result = await translate_pads_to_spd("design.asc", "design.spd")
    assert result["command"][1:] == ["-b", "design.asc", "design.spd"]


@pytest.mark.asyncio
async def test_rif_to_spd_positional(fake_exe):
    result = await translate_rif_to_spd("design.rif", "design.spd")
    assert result["command"][1:] == ["-b", "design.rif", "design.spd"]


@pytest.mark.asyncio
async def test_dsn_to_spd_positional(fake_exe):
    result = await translate_dsn_to_spd("design.dsn", "design.spd")
    assert result["command"][1:] == ["-b", "design.dsn", "design.spd"]


@pytest.mark.asyncio
async def test_spdlinks_format_flag(fake_exe):
    result = await translate_to_spd_via_spdlinks("board.brd", "board.spd", format="brd")
    assert result["command"][1:] == ["-b", "-brd", "board.brd", "board.spd"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_spdlinks_log_replay(fake_exe):
    result = await translate_to_spd_via_spdlinks("board.brd", "board.spd", format="brd", log_file="prev.log")
    assert result["command"][1:] == ["-b", "-log", "prev.log", "board.brd", "board.spd"]
