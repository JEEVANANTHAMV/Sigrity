"""Generic filesystem utility tools — copy/move/delete a file.

Added after the multi-model end-to-end evaluation (`scripts/eval_e2e.py`) repeatedly hit
the same wall: several realistic task prompts needed to stage a read-only source file
(a shipped Cadence sample, an existing design) into a scratch working directory before
running a tool against it, and this suite had no way to do that — see the README's
"What this caught" notes on task prompts that asked the model to "copy the file first."
These three tools are plain, synchronous `shutil`-based filesystem operations (not
background jobs — copying/moving/deleting a file is fast and doesn't need job tracking
the way a multi-minute Sigrity simulation does).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def copy_file(source_file: str, destination_file: str, overwrite: bool = False) -> dict:
    """Copy a file (e.g. a read-only Cadence sample) to a new location before running a tool against it.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    src = Path(source_file)
    dst = Path(destination_file)
    if not src.is_file():
        raise FileNotFoundError(f"source_file does not exist or is not a file: {src}")
    if dst.exists() and not overwrite:
        raise FileExistsError(f"destination_file already exists (pass overwrite=True to replace it): {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"source_file": str(src), "destination_file": str(dst), "size_bytes": dst.stat().st_size}


@mcp.tool
async def move_file(source_file: str, destination_file: str, overwrite: bool = False) -> dict:
    """Move (rename) a file to a new location.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    src = Path(source_file)
    dst = Path(destination_file)
    if not src.is_file():
        raise FileNotFoundError(f"source_file does not exist or is not a file: {src}")
    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"destination_file already exists (pass overwrite=True to replace it): {dst}")
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"source_file": str(src), "destination_file": str(dst)}


@mcp.tool
async def delete_file(file_path: str) -> dict:
    """Delete a single file. DESTRUCTIVE — there is no undo.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    path = Path(file_path)
    if path.is_dir():
        raise IsADirectoryError(f"delete_file only deletes a single file, not a directory: {path}")
    if not path.exists():
        raise FileNotFoundError(f"file_path does not exist: {path}")
    path.unlink()
    return {"deleted": str(path)}


@mcp.tool
async def check_design_lock(design_path: str) -> dict:
    """Check whether a `<design_path>.lck` file exists next to an Allegro/Capture design.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    lock_path = Path(f"{design_path}.lck")
    return {"design_path": design_path, "lock_exists": lock_path.is_file(), "lock_path": str(lock_path)}
