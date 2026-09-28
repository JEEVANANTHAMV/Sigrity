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


