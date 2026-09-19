import pytest

from sigrity_mcp.domains.platform.file_tools import check_design_lock, copy_file, delete_file, move_file


@pytest.mark.asyncio
async def test_copy_file_creates_parents_and_copies_content(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "sub" / "dst.txt"

    result = await copy_file(str(src), str(dst))

    assert dst.read_text() == "hello"
    assert src.exists()  # copy, not move
    assert result["size_bytes"] == 5


@pytest.mark.asyncio
async def test_copy_file_refuses_overwrite_by_default(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "dst.txt"
    dst.write_text("existing")

    with pytest.raises(FileExistsError):
        await copy_file(str(src), str(dst))


@pytest.mark.asyncio
async def test_copy_file_overwrite_true_replaces(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "dst.txt"
    dst.write_text("existing")

    await copy_file(str(src), str(dst), overwrite=True)

    assert dst.read_text() == "hello"


@pytest.mark.asyncio
async def test_copy_file_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        await copy_file(str(tmp_path / "nope.txt"), str(tmp_path / "dst.txt"))


@pytest.mark.asyncio
async def test_move_file_relocates_and_removes_source(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    dst = tmp_path / "sub" / "dst.txt"

    await move_file(str(src), str(dst))

    assert dst.read_text() == "hello"
    assert not src.exists()


@pytest.mark.asyncio
async def test_delete_file_removes_it(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("bye")

    result = await delete_file(str(target))

    assert not target.exists()
    assert result["deleted"] == str(target)


@pytest.mark.asyncio
async def test_delete_file_refuses_directory(tmp_path):
    with pytest.raises(IsADirectoryError):
        await delete_file(str(tmp_path))


@pytest.mark.asyncio
async def test_check_design_lock_reports_no_lock(tmp_path):
    board = tmp_path / "board.brd"
    board.write_text("fake")

    result = await check_design_lock(str(board))

    assert result["lock_exists"] is False
    assert result["lock_path"] == str(board) + ".lck"


@pytest.mark.asyncio
async def test_check_design_lock_detects_existing_lock(tmp_path):
    board = tmp_path / "board.brd"
    board.write_text("fake")
    (tmp_path / "board.brd.lck").write_text("locked by pid 1234")

    result = await check_design_lock(str(board))

    assert result["lock_exists"] is True
