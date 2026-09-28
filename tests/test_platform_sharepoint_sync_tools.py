import os
import pytest

from sigrity_mcp.domains.platform.sharepoint_sync_tools import (
    sync_sharepoint_design_repository,
)


@pytest.mark.asyncio
async def test_sync_sharepoint_local_mirror(tmp_path):
    remote_dir = tmp_path / "remote_sharepoint"
    remote_dir.mkdir()
    (remote_dir / "design.brd").write_text("dummy brd content", encoding="utf-8")
    (remote_dir / "schematic.dsn").write_text("dummy dsn content", encoding="utf-8")
    (remote_dir / "notes.txt").write_text("ignored text", encoding="utf-8")

    local_dst = tmp_path / "local_workspace"

    res = await sync_sharepoint_design_repository(
        site_id_or_url="ltsct.sharepoint.com/sites/Hardware",
        remote_folder_path=str(remote_dir),
        local_destination_dir=str(local_dst),
        file_extensions=[".brd", ".dsn"],
    )

    assert res["status"] == "success"
    assert res["sync_mode"] == "local_filesystem_mirror"
    assert res["files_synced"] == 2
    assert os.path.exists(local_dst / "design.brd")
    assert os.path.exists(local_dst / "schematic.dsn")
    assert not os.path.exists(local_dst / "notes.txt")


@pytest.mark.asyncio
async def test_sync_sharepoint_unconfigured_token(tmp_path):
    local_dst = tmp_path / "local_dst"
    res = await sync_sharepoint_design_repository(
        site_id_or_url="ltsct.sharepoint.com/sites/Hardware",
        remote_folder_path="/non_existent_folder_xyz",
        local_destination_dir=str(local_dst),
    )
    assert res["status"] == "not_configured"
