import pytest

from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_design_extractor


@pytest.mark.asyncio
async def test_run_allegro_design_extractor_default_pretty(fake_exe):
    result = await run_allegro_design_extractor("proj.cpm")
    assert result["command"][1:] == ["-p", "proj.cpm", "-f"]


@pytest.mark.asyncio
async def test_run_allegro_design_extractor_all_options(fake_exe):
    result = await run_allegro_design_extractor(
        "proj.sdax",
        output_file="out.json",
        pretty_format=False,
        elastic_url="http://localhost:9200",
        connectivity_server_as_source=True,
    )
    assert result["command"][1:] == [
        "-p", "proj.sdax", "-o", "out.json", "-u", "http://localhost:9200", "-c",
    ]


@pytest.mark.asyncio
async def test_run_allegro_extracta_bom(fake_exe, tmp_path):
    from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_extracta

    board = str(tmp_path / "test.brd")
    out = str(tmp_path / "test_bom.txt")
    result = await run_allegro_extracta(board, view_type="bom", output_file=out)
    assert result["output_file"] == out
    assert result["command"][1] == board
    assert result["command"][2] == result["command_file"]
    assert result["command"][3] == out


# Regression test for a real, live-confirmed bug (2026-10-02 campaign review): the
# built-in EXTRACTION_TEMPLATES used to contain invented view-name/field-name keywords
# ("NETS", "COMPONENTS", "PINS", "TESTPOINTS", "DRC", "COMP_LOCATION_X", ...) that real
# extracta.exe rejects with `ERROR(SPMHDX-10): Illegal view name.` for every single
# view_type -- this reproduced 100% of the time (10 consecutive failed job submissions
# in one campaign conversation alone). The fix copies the real view/field keywords from
# Cadence's own shipped `share/pcb/text/views/*.txt` command files. Assert each
# generated command file opens with a real, Cadence-documented view keyword, not one of
# the old invented ones, so this can't silently regress.
REAL_VIEW_KEYWORDS = {
    "bom": "COMPONENT",
    "nets": "LOGICAL_PIN",
    "components": "COMPONENT",
    "pins": "COMPONENT_PIN",
    "testpoints": "COMPOSITE_PAD",
    "drc": "DRC_ERROR",
}

INVENTED_VIEW_KEYWORDS = {"NETS", "COMPONENTS", "PINS", "TESTPOINTS", "DRC"}


@pytest.mark.asyncio
@pytest.mark.parametrize("view_type", sorted(REAL_VIEW_KEYWORDS))
async def test_run_allegro_extracta_uses_real_view_keywords(fake_exe, tmp_path, view_type):
    from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_extracta

    board = str(tmp_path / "test.brd")
    result = await run_allegro_extracta(board, view_type=view_type)
    cmd_file_content = open(result["command_file"], encoding="utf-8").read()
    first_line = cmd_file_content.strip().splitlines()[0].strip()

    assert first_line == REAL_VIEW_KEYWORDS[view_type]
    assert first_line not in INVENTED_VIEW_KEYWORDS


