from pathlib import Path

import pytest

from sigrity_mcp.domains.cad.allegro_manufacturing_tools import (
    run_allegro_generate_artwork,
    run_allegro_gerber_plot,
    run_dml_export,
    run_idf_export,
    run_idf_import,
    run_idx_export,
    run_idx_import,
    run_ipc2581_export,
    run_ipc2581_import,
    run_ipc356_export,
    run_pdf_export,
    run_step_export,
)


def _abs(name: str) -> str:
    # The newer tools below (added after dxf2a/a2dxf's runaway-re-prompt-loop discovery)
    # resolve every path argument relative to the server's cwd (fake_exe's fixture
    # chdir's into tmp_path) -- see allegro_manufacturing_tools.py's module docstring.
    return str(Path(name).resolve())


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
    result = await run_allegro_gerber_plot("top.art", penplot_file="out.plt")
    assert result["command"][1:] == ["top.art", "out.plt"]


@pytest.mark.asyncio
async def test_run_allegro_generate_artwork_all_films(fake_exe):
    result = await run_allegro_generate_artwork("board.brd")
    assert result["command"][1:] == ["board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_generate_artwork_specific_films(fake_exe):
    result = await run_allegro_generate_artwork("board.brd", film_names=["TOP", "BOTTOM"])
    assert result["command"][1:] == ["-f", "TOP", "-f", "BOTTOM", "board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_generate_artwork_list_only(fake_exe):
    result = await run_allegro_generate_artwork("board.brd", list_only=True)
    assert result["command"][1:] == ["-l", "board.brd"]


@pytest.mark.asyncio
async def test_run_ipc2581_import_minimal_new_design(fake_exe):
    result = await run_ipc2581_import("data.xml")
    assert result["command"][1:] == [_abs("data.xml")]


@pytest.mark.asyncio
async def test_run_ipc2581_import_full_options(fake_exe):
    result = await run_ipc2581_import(
        "data.xml", output_board_file="out.brd", input_board_file="in.brd",
        import_stackup=True, import_layer_features=True,
    )
    assert result["command"][1:] == [
        "-x", "-g", "-o", _abs("out.brd"), "-i", _abs("in.brd"), _abs("data.xml"),
    ]


@pytest.mark.asyncio
async def test_run_idf_export_minimal(fake_exe):
    result = await run_idf_export("board.brd")
    assert result["command"][1:] == [_abs("board.brd")]


@pytest.mark.asyncio
async def test_run_idf_export_with_options(fake_exe):
    result = await run_idf_export("board.brd", output_name="out", idf_format="PTC", idf_version="3.0")
    assert result["command"][1:] == ["-d", "PTC", "-o", _abs("out"), "-V", "3.0", _abs("board.brd")]


@pytest.mark.asyncio
async def test_run_idx_export_minimal(fake_exe):
    result = await run_idx_export("board.brd")
    assert result["command"][1:] == [_abs("board.brd")]


@pytest.mark.asyncio
async def test_run_idx_export_with_options(fake_exe):
    result = await run_idx_export("board.brd", output_name="out.idx", idx_version="4.0", export_traces_as_outlines=True)
    assert result["command"][1:] == ["-o", _abs("out.idx"), "-v", "4.0", "-u", _abs("board.brd")]


@pytest.mark.asyncio
async def test_run_idf_import_new_design(fake_exe):
    result = await run_idf_import("data.emn", idf_format="PTC")
    assert result["command"][1:] == ["-d", "PTC", _abs("data.emn")]


@pytest.mark.asyncio
async def test_run_idf_import_update_existing(fake_exe):
    result = await run_idf_import("data.bdf", input_board_file="in.brd", output_board_file="out.brd")
    assert result["command"][1:] == [_abs("data.bdf"), "-o", _abs("out.brd"), "-i", _abs("in.brd")]


@pytest.mark.asyncio
async def test_run_idx_import_new_design(fake_exe):
    result = await run_idx_import("data.idx")
    assert result["command"][1:] == [_abs("data.idx")]


@pytest.mark.asyncio
async def test_run_idx_import_update_existing(fake_exe):
    result = await run_idx_import("data.idx", input_board_file="in.brd", output_board_file="out.brd")
    assert result["command"][1:] == [_abs("data.idx"), "-i", _abs("in.brd"), "-o", _abs("out.brd")]


@pytest.mark.asyncio
async def test_run_dml_export_minimal(fake_exe):
    result = await run_dml_export("board.brd")
    assert result["command"][1:] == [_abs("board.brd")]


@pytest.mark.asyncio
async def test_run_dml_export_with_options(fake_exe):
    result = await run_dml_export(
        "board.brd", nets_file="nets.lst", comps_file="comps.lst", coupling_window="20mil", frequency="10GHZ"
    )
    assert result["command"][1:] == [
        f"nets={_abs('nets.lst')}", f"comps={_abs('comps.lst')}", "window=20mil", "freq=10GHZ", _abs("board.brd"),
    ]


@pytest.mark.asyncio
async def test_run_pdf_export_minimal(fake_exe):
    result = await run_pdf_export("board.brd")
    assert result["command"][1:] == [_abs("board.brd")]


@pytest.mark.asyncio
async def test_run_pdf_export_with_options(fake_exe):
    result = await run_pdf_export(
        "board.brd", output_name="out.pdf", black_and_white=True, pad_filled=True,
        separate_file_per_film=True, export_outlines=True,
    )
    assert result["command"][1:] == ["-o", _abs("out.pdf"), "-B", "-p", "-s", "-r", _abs("board.brd")]
