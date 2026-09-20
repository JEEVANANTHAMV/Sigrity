from pathlib import Path

import pytest

from sigrity_mcp.domains.cad.allegro_project_tools import (
    allegro_copy_project,
    allegro_generate_sim_variant,
    allegro_package_xcon_project,
)


def _abs(name: str) -> str:
    return str(Path(name).resolve())


@pytest.mark.asyncio
async def test_allegro_copy_project(fake_exe):
    result = await allegro_copy_project(
        "template.cpm", "dest_path", "newproj.cpm", "newlib", "newdesign",
    )
    assert result["command"][1:] == [
        "-proj", _abs("template.cpm"),
        "-copytopath", _abs("dest_path"),
        "-newprojname", "newproj.cpm",
        "-newlib", "newlib",
        "-newdesign", "newdesign",
    ]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_allegro_package_xcon_project_required_only(fake_exe):
    result = await allegro_package_xcon_project("top.xcon", "top", "worklib", "ref.cpm")
    assert result["command"][1:] == [
        "-xcon", _abs("top.xcon"), "-root", "top", "-lib", "worklib", "-refproj", _abs("ref.cpm"),
    ]


@pytest.mark.asyncio
async def test_allegro_package_xcon_project_all_options(fake_exe):
    result = await allegro_package_xcon_project(
        "top.xcon", "top", "worklib", "ref.cpm", reference_cdslib_file="cds.lib", output_folder="out_dir"
    )
    assert result["command"][1:] == [
        "-xcon", _abs("top.xcon"), "-root", "top", "-lib", "worklib", "-refproj", _abs("ref.cpm"),
        "-refcdslib", _abs("cds.lib"), "-output", _abs("out_dir"),
    ]


@pytest.mark.asyncio
async def test_allegro_generate_sim_variant_minimal(fake_exe):
    result = await allegro_generate_sim_variant("master.brd")
    assert result["command"][1:] == [_abs("master.brd")]


@pytest.mark.asyncio
async def test_allegro_generate_sim_variant_percent(fake_exe):
    result = await allegro_generate_sim_variant(
        "master.brd", output_board_file="variant.brd", cline_oversize_percent=1.0, dielectric_oversize_percent=1.0
    )
    assert result["command"][1:] == ["-c", "1.0", "-d", "1.0", "-o", _abs("variant.brd"), _abs("master.brd")]


@pytest.mark.asyncio
async def test_allegro_generate_sim_variant_absolute(fake_exe):
    result = await allegro_generate_sim_variant(
        "master.brd", cline_oversize_absolute=0.1, dielectric_oversize_absolute=-0.05
    )
    assert result["command"][1:] == ["-C", "0.1", "-D", "-0.05", _abs("master.brd")]


@pytest.mark.asyncio
async def test_allegro_generate_sim_variant_rejects_both_cline_forms(fake_exe):
    with pytest.raises(ValueError):
        await allegro_generate_sim_variant("master.brd", cline_oversize_percent=1.0, cline_oversize_absolute=0.1)


@pytest.mark.asyncio
async def test_allegro_generate_sim_variant_rejects_both_dielectric_forms(fake_exe):
    with pytest.raises(ValueError):
        await allegro_generate_sim_variant(
            "master.brd", dielectric_oversize_percent=1.0, dielectric_oversize_absolute=0.1
        )
