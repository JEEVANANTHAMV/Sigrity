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

    max_log_bytes: int = 200 * 1024 * 1024
    """Runaway-process safety net: if a job's log file grows past this size, JobManager
    force-kills it and marks the job "failed" with an explanatory note, instead of
    letting it run forever. Added after a real incident on this machine: `report.exe`/
    `step_out.exe`/`ipc356_out.exe`, given a nonexistent board-file path, entered an
    unbounded output loop instead of failing fast — one such job's log reached ~150GB
    before being caught and killed by hand. 200MB is already far beyond any legitimate
    Sigrity/Allegro log this suite has seen in real testing."""

    log_watchdog_poll_seconds: float = 2.0
    """How often JobManager polls a running job's log size against `max_log_bytes`."""

    skills_dir: Path = Path(".forjinn/skills")
    """Where the domain skill playbooks (`<name>/SKILL.md`) live. Relative to CWD unless
    absolute. Claude Code reads these off disk directly; `list_skills`/`load_skill`
    (see `domains/platform/skill_tools.py`) serve the same files over the MCP protocol
    itself for clients with no filesystem access to this machine (e.g. a deepagents/
    LangChain agent connected over http/sse from elsewhere)."""

    mcp_transport: str = "stdio"
    """`stdio` (default, for a same-machine launcher like Claude Code's mcp.json),
    `http` (Streamable HTTP, the current MCP standard for remote clients), or `sse`
    (legacy Server-Sent Events, for older clients that don't yet speak Streamable HTTP).
    Overridable per-launch with `main.py --transport ...`."""

    mcp_host: str = "127.0.0.1"
    """Bind address for `http`/`sse` transport. Use `0.0.0.0` to accept connections
    from other machines on the network (see README's remote-client section for the
    security tradeoffs of doing that before opening this up)."""

    mcp_port: int = 8765
    """Bind port for `http`/`sse` transport."""

    mcp_path: str = "/mcp"
    """URL path the MCP endpoint is served on for `http`/`sse` transport, e.g.
    `http://<host>:<port>/mcp`."""

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

    def resolve_skills_dir(self) -> Path:
        """Unlike `resolve_workdir`, never creates the directory — skills are
        version-controlled content, not job scratch space; a missing dir is a
        deployment error `skill_tools` surfaces explicitly rather than papering over."""
        return self.skills_dir if self.skills_dir.is_absolute() else Path.cwd() / self.skills_dir


settings = SigritySettings()
