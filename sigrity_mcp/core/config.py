"""Runtime configuration for the Sigrity MCP suite.

All settings can be overridden via environment variables or a `.env` file in the
project root (see `.env.example`). Nothing here is required for the server to start;
missing paths only surface as errors when a tool actually tries to use them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class SigritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIGRITY_", env_file=".env", extra="ignore")

    home: Path = Path(r"C:\Cadence\Sigrity2024.0")
    """Root install directory of the Sigrity Suite (contains tools/bin, doc, share)."""

    bin_subdir: str = r"tools\bin"
    """Subdirectory of `home` that contains the tool executables."""

    workdir: Path = Path("runs")
    """Directory (relative to CWD unless absolute) where per-job scratch folders are created."""

    default_timeout_seconds: int = 1800
    """Default wall-clock timeout for a synchronous/blocking tool run."""

    license_queue_seconds: int = 0
    """Passed to tools that support a license wait/queue flag; 0 = fail fast if no license."""

    max_log_tail_lines: int = 400
    """Cap on how many lines a "tail log" style tool will return in one call."""

    @property
    def bin_dir(self) -> Path:
        return self.home / self.bin_subdir

    def resolve_workdir(self) -> Path:
        wd = self.workdir if self.workdir.is_absolute() else Path.cwd() / self.workdir
        wd.mkdir(parents=True, exist_ok=True)
        return wd


settings = SigritySettings()
