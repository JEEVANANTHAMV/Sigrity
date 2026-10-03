"""Runtime configuration for the Sigrity MCP suite.

All settings can be overridden via environment variables or a `.env` file in the
project root (see `.env.example`). Nothing here is required for the server to start;
missing paths only surface as errors when a tool actually tries to use them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (contains .forjinn/, main.py, pyproject.toml), independent of the
# launching process's CWD — a caller (e.g. forji-desk's mcp-client.ts) may spawn this
# server without setting `cwd`, in which case Path.cwd() would resolve to the caller's
# own working directory instead of this repo.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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

    job_stall_timeout_seconds: int = 7200
    """Safety-net wall-clock watchdog for a job whose log has gone completely silent:
    if a running job's log file has not grown by a single byte for this many seconds,
    JobManager force-kills it and marks it "failed" (with `stall_timeout_killed=True` on
    the job record) instead of leaving it to hang forever with only a human -- or an
    agent polling `get_job_status` in a loop -- ever noticing. This is the missing piece
    this suite's `max_log_bytes` runaway-log killer already guards against the opposite
    shape of the same problem (too much output instead of too little).

    Confirmed-real failure modes this catches that nothing else in this suite does:
    (1) an interactive Allegro/Capture GUI launch raising a modal dialog
    `core.win32gui_helper.DismissWatcher` doesn't recognize or fails to dismiss (defense
    in depth -- DismissWatcher is the primary fix and should catch the known dialog
    shape well before this fires); (2) a silent FlexNet license-fetch wait with zero
    console output (see `core.tool_status`'s license-unreliability notes); (3) Celsius3D's
    own confirmed post-completion idle-stall (see `tool_status.TOOL_STATUS_NOTES["celsius3d"]`)
    -- the process finishes real work, writes a full result set, then simply never exits
    on its own (frozen CPU, idle main window, no dialog of any kind) -- a real 2.5+ hour
    live incident, previously only recoverable by a human finding and killing it by hand.

    Deliberately generous (2 hours, well past the max_log_tail_lines/max_log_bytes
    scale of "minutes") and measured from "last byte written", not "job start": a real
    sweep of this suite's own past job logs under `runs/` shows PowerSI and OptimizePI in
    particular have produced a genuine, fully successful `run.log` of exactly 0 bytes --
    i.e. these tools can legitimately write NOTHING to console for their entire run,
    success or failure, so "log size has not changed" is a necessarily weak signal for
    them specifically; a short timeout would risk killing a real, still-working job with
    no way to tell the difference from the outside. This must never fire on a job that is
    genuinely still working, only one that has gone truly, completely silent for the full
    timeout window -- if the live campaign's real heavier PI/SI/thermal/extraction runs
    turn out to legitimately exceed 2 hours of total silence, raise this via
    `SIGRITY_JOB_STALL_TIMEOUT_SECONDS` rather than treat 2 hours as a hard ceiling. Set
    to 0 to disable entirely."""

    allegro_session_stall_timeout_seconds: int = 300
    """Same safety-net as `job_stall_timeout_seconds`, but specifically for Allegro/Capture
    interactive SESSION jobs (`core.tclsession.run_session` for `tool in ("allegro",
    "capture")`), which run far shorter than the long batch simulations the 2-hour global
    default is tuned for (confirmed live: ~5-20s for simple session calls, ~1-3 minutes for
    the most complex documented stackup/routing session). A real, repeatedly-confirmed
    failure mode (ripping up and re-routing a multi-branch/multi-pin net) hangs these
    sessions indefinitely with the log gone completely silent; the 2-hour default would
    leave that running for hours before anything noticed. Override via
    `SIGRITY_ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS` if a future session class is confirmed
    to legitimately need a longer silent stretch than 300s."""

    stall_watchdog_poll_seconds: float = 5.0
    """How often JobManager samples a running job's log size for `job_stall_timeout_seconds`'s
    "has this gone completely silent" check. Coarser than `log_watchdog_poll_seconds`
    (which guards a much faster-moving runaway-growth signal) since "did the size change
    at all since last sample" needs far less frequent sampling than "did it exceed a hard
    byte cap"."""

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
        deployment error `skill_tools` surfaces explicitly rather than papering over.

        Resolved against this repo's own root, not the launching process's CWD — skills
        ship with this repo, so they must be found regardless of what directory spawned
        the server (a real bug: a client launching this server with no explicit `cwd`
        resolved this to its own working directory and found nothing)."""
        return self.skills_dir if self.skills_dir.is_absolute() else _PROJECT_ROOT / self.skills_dir


settings = SigritySettings()
