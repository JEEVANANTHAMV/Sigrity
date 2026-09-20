from pathlib import Path

import pytest

from sigrity_mcp.domains.cad.allegro_import_tools import (
    allegro_export_dxf,
    allegro_import_dxf,
    allegro_new_blank_board,
)


def _abs(name: str) -> str:
    # allegro_import_dxf/allegro_export_dxf resolve every path argument relative to the
    # server's cwd (fake_exe's fixture chdir's into tmp_path) -- see module docstring for
    # why (dxf2a/a2dxf fall into a runaway interactive re-prompt loop on an unresolved
    # relative path, since the job itself runs from a different, per-job cwd).
    return str(Path(name).resolve())


@pytest.mark.asyncio
async def test_import_dxf_new_design_defaults(fake_exe):
    result = await allegro_import_dxf("layers.cnv", "outline.dxf", "new.brd")
    assert result["command"][1:] == [_abs("layers.cnv"), _abs("outline.dxf"), _abs("new.brd")]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_import_dxf_all_flags_are_space_separated(fake_exe):
    result = await allegro_import_dxf(
        "layers.cnv",
        "outline.dxf",
        "existing.brd",
        update_existing=True,
        output_units="MILS",
        original_units="MM",
        accuracy=2,
        use_default_text=True,
    )
    # Confirmed live: dxf2a rejects attached flag values ("-uMILS") outright; only the
    # space-separated form ("-u", "MILS") is accepted.
    assert result["command"][1:] == [
        "-u", "MILS", "-v", "MM", "-a", "2", "-g", "-t",
        _abs("layers.cnv"), _abs("outline.dxf"), _abs("existing.brd"),
    ]


@pytest.mark.asyncio
async def test_export_dxf_defaults(fake_exe):
    result = await allegro_export_dxf("layers.cnv", "out.dxf", "board.brd")
    assert result["command"][1:] == [_abs("layers.cnv"), _abs("out.dxf"), _abs("board.brd")]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_export_dxf_with_options(fake_exe):
    result = await allegro_export_dxf(
        "layers.cnv", "out.dxf", "board.brd", output_units="MM", accuracy=3, dxf_format="14", export_drill_info=True
    )
    assert result["command"][1:] == [
        "-u", "MM", "-a", "3", "-f", "14", "-d", _abs("layers.cnv"), _abs("out.dxf"), _abs("board.brd"),
    ]


@pytest.mark.asyncio
async def test_new_blank_board_copies_explicit_template(tmp_path):
    template = tmp_path / "blank_template.brd"
    template.write_bytes(b"fake board bytes")
    dst = tmp_path / "sub" / "new_design.brd"

    result = await allegro_new_blank_board(str(dst), template_file=str(template))

    assert dst.read_bytes() == b"fake board bytes"
    assert result["size_bytes"] == len(b"fake board bytes")
    assert result["template_file"] == str(template)


@pytest.mark.asyncio
async def test_new_blank_board_refuses_overwrite_by_default(tmp_path):
    template = tmp_path / "blank_template.brd"
    template.write_bytes(b"fake board bytes")
    dst = tmp_path / "new_design.brd"
    dst.write_bytes(b"already here")

    with pytest.raises(FileExistsError):
        await allegro_new_blank_board(str(dst), template_file=str(template))


@pytest.mark.asyncio
async def test_new_blank_board_overwrite_true_replaces(tmp_path):
    template = tmp_path / "blank_template.brd"
    template.write_bytes(b"fake board bytes")
    dst = tmp_path / "new_design.brd"
    dst.write_bytes(b"already here")

    await allegro_new_blank_board(str(dst), overwrite=True, template_file=str(template))

    assert dst.read_bytes() == b"fake board bytes"


@pytest.mark.asyncio
async def test_new_blank_board_missing_template_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        await allegro_new_blank_board(str(tmp_path / "new_design.brd"), template_file=str(tmp_path / "nope.brd"))
