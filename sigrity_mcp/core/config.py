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

    license_manager_home: Path = Path(r"C:\Cadence\LicenseManager")
    """Install directory of the Cadence FlexNet License Manager (contains lmutil.exe)."""

    cadence_spb_home: Path = Path(r"C:\Cadence\SPB_22.1")
    """Root install directory of Allegro/OrCAD (Silicon Package Board) — a separate,
    sibling Cadence product line from the Sigrity Suite, used for CAD creation (schematic
    capture, PCB layout). Same tools/bin layout convention as Sigrity's `home`."""

    license_file: str = "5280@localhost"
    """Default FlexNet license server spec, as understood by `lmutil lmstat -c`. Matches
    this machine's CDS_LIC_FILE env var by default; override if your license server differs."""

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

    @property
    def cad_bin_dir(self) -> Path:
        return self.cadence_spb_home / self.bin_subdir

    def resolve_workdir(self) -> Path:
        wd = self.workdir if self.workdir.is_absolute() else Path.cwd() / self.workdir
        wd.mkdir(parents=True, exist_ok=True)
        return wd


settings = SigritySettings()
