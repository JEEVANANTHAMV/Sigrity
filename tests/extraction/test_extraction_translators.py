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
async def test_spdlinks_format_flag_dbr(fake_exe):
    # 2026-10-26: the `format` Literal was narrowed to the formats SPDLinks.exe 2024.0
    # ACTUALLY accepts (from its own "Valid choices" error list). Cadvance `.dbr` is the
    # primary, live-verified format. The old test used `format="brd"` -- a format this
    # build rejects ("Unknown File Type") -- which is exactly the regression this guards
    # against: the wrapper must not advertise a format the binary will refuse.
    result = await translate_to_spd_via_spdlinks("design.dbr", "design.spd", format="dbr")
    assert result["command"][1:] == ["-b", "-dbr", "design.dbr", "design.spd"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_spdlinks_format_flag_zip(fake_exe):
    # ODB++ archive (.zip/.tgz) -> .spd, another live-verified format.
    result = await translate_to_spd_via_spdlinks("design.tgz", "design.spd", format="zip")
    assert result["command"][1:] == ["-b", "-zip", "design.tgz", "design.spd"]


@pytest.mark.asyncio
async def test_spdlinks_format_flag_zuken_ftf(fake_exe):
    # Zuken CR-5000/8000 set (ftf/pcf/dsgf/mrf/sdf/sff) -- all live-verified as accepted flags.
    result = await translate_to_spd_via_spdlinks("design.ftf", "design.spd", format="ftf")
    assert result["command"][1:] == ["-b", "-ftf", "design.ftf", "design.spd"]


@pytest.mark.asyncio
async def test_spdlinks_log_replay(fake_exe):
    result = await translate_to_spd_via_spdlinks("design.dbr", "design.spd", format="dbr", log_file="prev.log")
    assert result["command"][1:] == ["-b", "-log", "prev.log", "design.dbr", "design.spd"]


def test_spdlinks_rejects_formats_this_build_does_not_support():
    # Regression coverage for the 2026-10-26 narrowing: the OLD Literal advertised
    # brd/dbg/mcm/sip/txt, all of which SPDLinks.exe 2024.0 rejects with
    # "Unknown File Type". They must no longer be in the wrapper's format set either.
    # (Call-time Literal validation is not enforced by the underlying runtime in this
    # FastMCP version, so we assert against the parameter annotation directly rather
    # than expecting a call-time raise.)
    from typing import get_args, get_type_hints
    hints = get_type_hints(translate_to_spd_via_spdlinks)
    allowed = set(get_args(hints["format"]))
    for rejected in ("brd", "dbg", "mcm", "sip", "txt"):
        assert rejected not in allowed, f"'{rejected}' must not be an accepted SPDLinks format on 2024.0"
    # The live-verified 2024.0 format set is present.
    for accepted in ("dbr", "mbs", "zip", "ftf", "pcf", "dsgf", "mrf", "sdf", "sff"):
        assert accepted in allowed, f"'{accepted}' must be an accepted SPDLinks format on 2024.0"
