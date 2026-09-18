import pytest

from sigrity_mcp.domains.cad.allegro_batch_tools import run_allegro_dbdoctor, run_allegro_report


@pytest.mark.asyncio
async def test_run_allegro_report_argv(fake_exe):
    result = await run_allegro_report("board.brd", "sum", output_file="sum.txt")
    assert result["command"][1:] == ["-v", "sum", "board.brd", "sum.txt"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_run_allegro_report_html_flag_and_no_output_file(fake_exe):
    result = await run_allegro_report("board.brd", "bom", html=True)
    assert result["command"][1:] == ["-v", "bom", "-H", "board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_dbdoctor_default_is_check_only(fake_exe):
    result = await run_allegro_dbdoctor("board.brd")
    assert result["command"][1:] == ["-check_only", "board.brd"]


@pytest.mark.asyncio
async def test_run_allegro_dbdoctor_drc_mode_and_purge_flags(fake_exe):
    result = await run_allegro_dbdoctor(
        "board.brd",
        check_only=False,
        run_drc=True,
        no_backup=True,
        purge_vialist=True,
        purge_padstacks=True,
        regenerate_xnets=True,
        output_file="out.brd",
    )
    assert result["command"][1:] == [
        "-drc", "-no_backup", "-outfile", "out.brd",
        "-purge_vialist", "-purge_padstacks", "-regenerate_xnets", "board.brd",
    ]
