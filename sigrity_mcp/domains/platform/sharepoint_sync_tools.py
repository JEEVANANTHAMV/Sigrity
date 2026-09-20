"""SharePoint & Enterprise Network Storage Sync Tools.

Aligned with FORJINN Discovery Form Section 3.3:
- Sync design files (.dsn, .brd, .olb, .cpm) and reference documents from SharePoint / OneDrive
  or Enterprise Network Drives into local working directories.
- Support Microsoft Graph REST API or local sync folder mirrors.
- Keep all credentials and tokens inside customer environment without leaking design data.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Optional

import httpx

from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def sync_sharepoint_design_repository(
    site_id_or_url: str,
    remote_folder_path: str,
    local_destination_dir: str,
    graph_access_token: Optional[str] = None,
    file_extensions: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Sync design files and component libraries from a SharePoint document library to local workspace.

    `site_id_or_url`: SharePoint Site ID or URL (e.g. "ltsct.sharepoint.com/sites/HardwareDesign").
    `remote_folder_path`: Folder path inside the Document Library (e.g. "/Shared Documents/Designs/FRDM-IMX91").
    `local_destination_dir`: Local directory where design files should be downloaded.
    `graph_access_token`: OAuth2 Bearer token from Entra ID / Microsoft Graph. If omitted, checks
                          `SHAREPOINT_ACCESS_TOKEN` env var or local sync mirror.
    `file_extensions`: Filter extensions (e.g. [".dsn", ".brd", ".cpm", ".olb", ".pdf", ".xlsx"]).
    """
    token = graph_access_token or os.getenv("SHAREPOINT_ACCESS_TOKEN")
    os.makedirs(local_destination_dir, exist_ok=True)
    allowed_exts = [e.lower() for e in file_extensions] if file_extensions else None

    # If local network/sync mirror exists at the path, sync directly
    if os.path.exists(remote_folder_path):
        copied_files = []
        for root, _, files in os.walk(remote_folder_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if allowed_exts and ext not in allowed_exts:
                    continue
                src = os.path.join(root, f)
                rel = os.path.relpath(src, remote_folder_path)
                dst = os.path.join(local_destination_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied_files.append(dst)
        return {
            "status": "success",
            "sync_mode": "local_filesystem_mirror",
            "files_synced": len(copied_files),
            "destination_dir": os.path.abspath(local_destination_dir),
            "file_list": copied_files,
        }

    # If using Microsoft Graph API
    if not token:
        return {
            "status": "not_configured",
            "detail": "SHAREPOINT_ACCESS_TOKEN not configured and remote path is not a mounted local directory.",
            "destination_dir": os.path.abspath(local_destination_dir),
        }

    # Query Microsoft Graph
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    graph_url = f"https://graph.microsoft.com/v1.0/sites/{site_id_or_url}/drive/root:{remote_folder_path}:/children"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(graph_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("value", [])
                downloaded = []
                for item in items:
                    name = item.get("name", "")
                    ext = os.path.splitext(name)[1].lower()
                    if allowed_exts and ext not in allowed_exts:
                        continue
                    download_url = item.get("@microsoft.graph.downloadUrl")
                    if download_url:
                        file_resp = await client.get(download_url)
                        if file_resp.status_code == 200:
                            dst_path = os.path.join(local_destination_dir, name)
                            with open(dst_path, "wb") as f:
                                f.write(file_resp.content)
                            downloaded.append(dst_path)
                return {
                    "status": "success",
                    "sync_mode": "microsoft_graph_api",
                    "files_synced": len(downloaded),
                    "destination_dir": os.path.abspath(local_destination_dir),
                    "file_list": downloaded,
                }
            else:
                return {
                    "status": "error",
                    "http_status": resp.status_code,
                    "detail": resp.text,
                }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
        }
