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

## Live validation and what it caught

`lmutil lmstat` reports this machine's FlexNet server (`5280@localhost`) as
unreachable, and one AMM tool (`AmLibGen.exe`) aborted immediately with no output when
tested directly — so a blanket "no license available" was the initial assumption.
That turned out to be wrong for at least PowerSI and PowerDC: running a real session
against real sample designs shipped with Sigrity (`share/SpeedXP/Samples/...`) showed
both tools successfully fetching a license, loading the design, and running. Whatever
`AmLibGen.exe`'s problem is, it isn't a suite-wide license outage — treat license
status as per-tool/per-feature, not a single on/off switch, and check
`get_license_server_status`/`diagnose_license_feature` for the specific feature you
need rather than assuming from one tool's failure.

Running real tools against real designs caught two genuine bugs that documentation
alone didn't surface, both now fixed:

1. **Tcl flag/value spacing.** Cadence's own docs render Tcl flags as `-start{value}`
   (no space), which reads naturally as one token — but the real Tcl parser requires
   `-start {value}` as two separate words; the concatenated form is rejected as one
   unrecognized parameter. This affected several flags in `si/powersi_tools.py` and
   `pi/powerdc_tools.py` and is now fixed everywhere it was found (`git log` for the
   fix commit has the full list).
2. **Frequency value format.** PowerSI's `-start`/`-end` frequency flags reject
   unit-suffixed strings like `"1MHz"`/`"1GHz"` — they need plain numeric Hz values
   (`"1e6"`, `"1e9"`). Fixed in `powersi_set_frequency_sweep`'s docstring and applied
   the same caution to `optimizepi_set_frequency_range` (same underlying Tcl engine,
   not yet independently tested).

This also resolved a standing question: PowerDC's `-tcl` batch switch — never
documented in PowerDC's own user guide, only inferred from the shared launcher
family — is now confirmed working, not just best-effort.

**What this does and doesn't prove:** PowerSI and PowerDC were exercised against real
sample designs end-to-end (session compose → run → job succeeds, real Sigrity log
shows real Tcl commands executing). The other domains (XcitePI, OptimizePI, Clarity3D,
XtractIM, the translators, T2B, AMM) are built from the same research rigor and pass
their unit tests (argv/Tcl-line construction, job lifecycle), but have not each been
individually run against a real license and a real design — given the bugs found in
the two that *were* tested, treat any untested tool's exact flag spellings as "best
transcription from documentation," not guaranteed correct, until exercised the same
way. `job_tools`'s `license_issue_suspected` flag and `core.process`'s silent-failure
heuristic exist to help surface it quickly if a specific flag turns out wrong.

Full MCP tool-calling protocol was also validated end-to-end with a real LLM
(`scripts/test_llm_e2e.py`, against a local OpenAI-compatible endpoint configured via
the `TEST_LLM_BASE_URL` env var) — the model correctly discovers tools, composes a
multi-step PowerSI session (open → mode → frequency sweep → ports → export → run →
check status) unassisted, and reports accurate results back.

## Testing

```powershell
python -m uv run pytest -q                          # unit tests (no Sigrity install required for most)
python -m uv run python scripts/smoke_test.py        # lists every registered MCP tool
python -m uv run python scripts/smoke_call.py         # calls a few real platform tools live
python -m uv run python scripts/smoke_amm.py          # runs AmLibGen against a real sample spreadsheet
python -m uv run python scripts/smoke_powersi_real.py # real PowerSI session against a shipped sample .spd
python -m uv run python scripts/smoke_powerdc_real.py # real PowerDC session against a shipped sample .spd
python -m uv run python scripts/test_llm_e2e.py "<prompt>"   # real LLM-driven MCP tool-calling test
```
