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

    Creates any missing parent directories of `destination_file`. Fails with a clear
    error if `destination_file` already exists and `overwrite=False` (the default) —
    pass `overwrite=True` to replace it. Uses `shutil.copy2`, which preserves file
    metadata (timestamps) but not any alternate-data-stream/ACL-specific Windows
    attributes.
    """
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

    Creates any missing parent directories of `destination_file`. Fails with a clear
    error if `destination_file` already exists and `overwrite=False` (the default).
    """
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

    Refuses (raises) if `file_path` is a directory, to avoid an accidental recursive
    delete via this tool — this suite intentionally has no directory-delete tool.
    """
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

    Diagnostic for a real, confirmed-live failure mode: if a prior Allegro/Capture batch
    job against this exact path was killed rather than exiting cleanly, it leaves an
    orphaned lock file behind, and the NEXT launch against that path then blocks forever
    on a modal "design is open/locked, override?" GUI dialog with zero console output —
    indistinguishable from a generic hang or a license-fetch delay until a human clicks
    through it. `allegro_run_session`/`start_capture_session` already clear this
    automatically before launching, so this should be rare going forward — use this to
    check a suspiciously stuck job (one still `running` well past its usual load time
    with a run.log that hasn't grown beyond the startup banner) BEFORE assuming it's a
    license or performance issue. If `lock_exists` is true, cancel_job the stuck job
    first, then call this suite's own *_run_session tool again (it will clear the lock
    itself) rather than deleting the lock out from under a job that might still
    legitimately be running.
    """
    lock_path = Path(f"{design_path}.lck")
    return {"design_path": design_path, "lock_exists": lock_path.is_file(), "lock_path": str(lock_path)}
