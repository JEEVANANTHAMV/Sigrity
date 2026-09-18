# sigrity-mcp

A [FastMCP](https://github.com/jlowin/fastmcp) tool suite that drives a local **Cadence
Sigrity 2024.0** install through its Tcl batch-automation interface — Sigrity has no
first-party Python/REST API; every tool here either generates a `.tcl` macro and runs
it against the right Sigrity executable in batch/console mode, or (for the handful of
tools with no Tcl API at all) drives one directly via CLI switches.

Built against a real local install at `C:\Cadence\Sigrity2024.0` — every CLI/Tcl syntax
claim in this codebase was confirmed by reading the shipped documentation and real
sample scripts on disk, or by running the tool directly, not guessed.

## The five domains

| # | Domain | Package | Covers |
|---|---|---|---|
| 1 | Power Integrity (PI) | `sigrity_mcp/domains/pi/` | PowerDC, XcitePI, OptimizePI |
| 2 | Signal Integrity & Power-Aware | `sigrity_mcp/domains/si/` | PowerSI, SPDSIM, BroadbandSPICE |
| 3 | Interconnect Extraction & Modeling | `sigrity_mcp/domains/extraction/` | Layout translators (Gds2Spd, Oasis2Spd, Ndd2Spd, Pads2Spd, Rif2Spd, Dsn2Spd, SPDLinks), Clarity3D, XtractIM, T2B |
| 4 | In-Design Analysis (Sigrity Aurora) | `sigrity_mcp/domains/aurora/` | Honestly scoped — see below |
| 5 | Unified Framework (Sigrity X Platform) | `sigrity_mcp/domains/platform/` | FlexNet license status, install introspection, AMM model-library tools, and the job/session control shared by every other domain |

### A note on Domain 4 (Aurora)

Sigrity Aurora is Cadence's real-time in-design SI/PI checking flow — it runs *inside*
Allegro/OrCAD X PCB Editor, not as a standalone Sigrity Suite executable. This machine
has no Allegro/OrCAD install, and no public Aurora-specific scripting API was found
during research. Rather than fabricate automation this environment can't provide,
Domain 4 has two honest tools: one explaining the limitation and how it was confirmed,
and one mapping each kind of check Aurora performs to the closest standalone
equivalent already implemented in Domains 1–3 (e.g. PowerDC for IR-drop).

## Architecture

- **`sigrity_mcp/core/executables.py`** — registry of every Sigrity/FlexNet executable
  this suite touches, resolved against `SIGRITY_HOME`/`SIGRITY_LICENSE_MANAGER_HOME`.
- **`sigrity_mcp/core/tclscript.py`** — safe Tcl string/path quoting (`tcl_str`,
  `tcl_path`) — every tool uses these instead of raw string formatting to avoid Tcl
  command injection from untrusted input.
- **`sigrity_mcp/core/tclsession.py`** — the compose-then-run pattern used by every
  `sigrity::`/`xpi_*`-scripted tool: a `start_*_session` tool opens a session, several
  `*_add_*`/`*_set_*` tools each append one line to its in-memory Tcl script (no
  process launched), and a final `*_run_session` tool writes the script out and
  launches the real tool once. This matches how Sigrity's own Tcl automation is meant
  to be used — one process launch executing a whole scripted flow — rather than
  launching a fresh solver process per command.
- **`sigrity_mcp/core/jobs.py` / `process.py`** — every `run_*`/`*_run_session` tool
  launches its Sigrity process as a tracked background job and returns a `job_id`
  immediately (simulations can run for minutes to hours); `get_job_status`,
  `wait_for_job`, `tail_job_log`, `list_job_files`, `read_job_output_file`, `cancel_job`
  (in `domains/platform/job_tools.py`) are shared by every domain to track/retrieve
  results.
- **`sigrity_mcp/domains/platform/session_tools.py`** — `preview_tcl_session`,
  `close_tcl_session`, `list_tcl_sessions` are likewise shared by every session-based
  tool across all domains.

## Setup

```powershell
# uv manages the venv; installed here via `python -m pip install --user uv`
python -m uv sync              # installs runtime + dev dependencies from pyproject.toml
python -m uv run pytest -q     # run the test suite
python -m uv run python main.py   # start the MCP server (stdio transport)
```

Corporate proxy note: this environment requires `HTTP_PROXY`/`HTTPS_PROXY` pointed at
the corporate gateway for any internet access (PyPI, web research) — but Sigrity
itself and the local FlexNet license server are entirely local; no proxy is needed to
run the actual tools.

Configuration (see `.env.example`): `SIGRITY_HOME` (default
`C:\Cadence\Sigrity2024.0`), `SIGRITY_LICENSE_MANAGER_HOME` (default
`C:\Cadence\LicenseManager`), `SIGRITY_LICENSE_FILE` (default `5280@localhost`,
matching this machine's `CDS_LIC_FILE`), `SIGRITY_WORKDIR` (default `runs/`, where every
job's scratch directory is created).

## Known environment limitation: no active FlexNet license

This machine's FlexNet license server (`5280@localhost`) is not currently running and
no local `.lic` file was found — confirmed via `get_license_server_status` returning a
connection-refused error, and via directly testing a licensed tool (`AmLibGen.exe`),
which aborts immediately with a negative exit code and no output before printing
anything. This means **licensed Sigrity tool runs cannot be fully verified end-to-end
on this machine right now** — what's tested and confirmed working instead:

- Every tool's exact CLI/Tcl argument construction (unit tests, `tests/`)
- Every tool's MCP registration, schema, and description (`scripts/smoke_test.py`)
- The non-licensed platform tools live against the real install (install manifest
  parsing, executable inventory, FlexNet client queries, name-server check)
- Full MCP tool-calling protocol end-to-end with a real LLM
  (`scripts/test_llm_e2e.py`, against a local `qwen3-max` endpoint configured via the
  `TEST_LLM_BASE_URL` env var) — the model correctly discovers tools, chains multiple
  calls, and reports accurate results back, including the license-server-down state itself.

Once a license is active, every `run_*`/`*_run_session` tool is ready to execute for
real — nothing in the design assumes a license is present, and `job_tools`'s
`license_issue_suspected` flag plus `core.process`'s silent-failure heuristic exist
specifically to surface this class of failure clearly if it recurs.

## Testing

```powershell
python -m uv run pytest -q                          # unit tests (no Sigrity install required for most)
python -m uv run python scripts/smoke_test.py        # lists every registered MCP tool
python -m uv run python scripts/smoke_call.py         # calls a few real platform tools live
python -m uv run python scripts/test_llm_e2e.py "<prompt>"   # real LLM-driven MCP tool-calling test
```
