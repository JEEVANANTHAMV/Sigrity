# sigrity-mcp

A [FastMCP](https://github.com/jlowin/fastmcp) tool suite that drives a local **Cadence
Sigrity 2024.0** install through its Tcl batch-automation interface — Sigrity has no
first-party Python/REST API; every tool here either generates a `.tcl` macro and runs
it against the right Sigrity executable in batch/console mode, or (for the handful of
tools with no Tcl API at all) drives one directly via CLI switches.

Built against a real local install at `C:\Cadence\Sigrity2024.0` — every CLI/Tcl syntax
claim in this codebase was confirmed by reading the shipped documentation and real
sample scripts on disk, or by running the tool directly, not guessed.

This suite also automates a second, sibling Cadence product line on the same machine —
**Allegro/OrCAD SPB 22.1** (`C:\Cadence\SPB_22.1`) — for CAD creation (PCB layout,
schematic capture) via SKILL and Tcl respectively, closing the loop from blank design
through simulated signoff.

## The domains

| # | Domain | Package | Covers |
|---|---|---|---|
| 1 | Power Integrity (PI) | `sigrity_mcp/domains/pi/` | PowerDC, XcitePI, OptimizePI |
| 2 | Signal Integrity & Power-Aware | `sigrity_mcp/domains/si/` | PowerSI, SPDSIM, BroadbandSPICE |
| 3 | Interconnect Extraction & Modeling | `sigrity_mcp/domains/extraction/` | Layout translators (Gds2Spd, Oasis2Spd, Ndd2Spd, Pads2Spd, Rif2Spd, Dsn2Spd, SPDLinks), Clarity3D, XtractIM, T2B |
| 4 | In-Design Analysis (Sigrity Aurora) | `sigrity_mcp/domains/aurora/` | Honestly scoped — see below |
| 5 | Unified Framework (Sigrity X Platform) | `sigrity_mcp/domains/platform/` | FlexNet license status, install introspection, AMM model-library tools, the pipeline orchestrator, and the job/session control shared by every other domain |
| 6 | CAD Creation (Allegro/OrCAD) | `sigrity_mcp/domains/cad/` | Allegro PCB layout (SKILL), OrCAD Capture schematic (Tcl), Allegro report/integrity batch tools |

### A note on Domain 4 (Aurora)

Sigrity Aurora is Cadence's real-time in-design SI/PI checking flow. Allegro/OrCAD
*is* installed on this machine (see Domain 6) — but Aurora itself is confirmed, from
Allegro's own docs and its complete 840-file SKILL function reference, to be a
GUI-only mode inside `allegro.exe` with **zero** CLI or SKILL automation surface for
any of its six checks (impedance, coupling, crosstalk, return path, reflection, IR
drop) — every workflow is dialog/wizard-driven only. Rather than fabricate automation
this feature genuinely doesn't expose, Domain 4 has two honest tools: one explaining
the limitation (with the confirming evidence), and one mapping each Aurora check to
the closest standalone equivalent already implemented in Domains 1–3/6 (e.g. PowerDC
for IR-drop, PowerSI for crosstalk/coupling via RLGC export).

### Domain 6 (CAD Creation) — what's confirmed, what isn't

- **`allegro_batch_tools.py`** (`run_allegro_report`, `run_allegro_dbdoctor`) —
  confirmed live end-to-end against a real board: real component/DRC counts, real
  integrity-check results. Calls the standalone `report.exe`/`dbdoctor.exe` directly
  rather than through the `allegro_batch.exe` multiplexer Cadence's own docs describe
  as the entry point, because that multiplexer is confirmed broken at dispatching to
  at least one sub-program (`dbdoctor`) even though its own `-help` text is fine.
- **`allegro_tools.py`** (SKILL-scripted PCB layout, `allegro.exe -s script.scr
  board.brd`) — the session/query mechanics are confirmed live (a real board loads, a
  real SKILL query executes and returns, the process exits cleanly via a trailing
  `quit` line). Database *mutation* calls (`allegro_create_net` and friends) are
  implemented from Cadence's documented `axl*` API but did **not** complete within two
  minutes in live testing — cause unconfirmed (possibly a hidden dialog, possibly a
  genuinely slow first-mutation cost). Treat those specific tools as unverified.
- **`capture_tools.py`** (Tcl-scripted schematic capture) — a bare `Capture.exe`
  launch opens cleanly, but the batch-script invocation itself
  (`-product=<name> script.tcl`) was **not** reliably reproduced across repeated
  attempts — inconsistent behavior, and once a dialog Cadence's own docs describe as a
  crash-recovery prompt, not a license chooser. Built from documentation and real
  sample scripts, but unverified end-to-end.
- **The real, confirmed CAD-to-analysis bridge is PowerSI, not a dedicated
  translator**: `start_powersi_session` accepts a real Allegro `.brd` directly —
  PowerSI's built-in "BRDExtractor" translates it automatically on open. Call
  `powersi_save_document` right after (required — PowerSI refuses to simulate a
  design that hasn't been saved to native `.spd` form first), then proceed normally.
  Confirmed live producing a real 237KB `.spd` file and reaching `begin simulation`.

## Architecture

- **`sigrity_mcp/core/executables.py`** — three registries (Sigrity Suite, FlexNet
  license client, Allegro/OrCAD), resolved against `SIGRITY_HOME`/
  `SIGRITY_LICENSE_MANAGER_HOME`/`SIGRITY_CADENCE_SPB_HOME` respectively.
- **`sigrity_mcp/core/tclscript.py`** / **`skillscript.py`** — safe string/path
  quoting for each scripting language this suite generates (`tcl_str`/`tcl_path` for
  Tcl, `skill_str`/`skill_path`/`skill_list` for SKILL) — every tool uses these
  instead of raw string formatting to avoid command injection from untrusted input.
- **`sigrity_mcp/core/tclsession.py`** (`ScriptSession`/`ScriptSessionManager`,
  aliased as `TclSession`/`TclSessionManager` for backward compatibility) — the
  compose-then-run pattern used by every scripted tool regardless of language
  (`sigrity::`/`xpi_*` Tcl, Capture's Tcl, Allegro's SKILL): a `start_*_session` tool
  opens a session, several `*_add_*`/`*_set_*` tools each append one line to its
  in-memory script (no process launched), and a final `*_run_session` tool writes the
  script out and launches the real tool once. This matches how each of these
  automation surfaces is meant to be used — one process launch executing a whole
  scripted flow — rather than launching a fresh process per command.
- **`sigrity_mcp/core/jobs.py` / `process.py`** — every `run_*`/`*_run_session` tool
  launches its process as a tracked background job and returns a `job_id` immediately
  (simulations/GUI sessions can run for minutes); `get_job_status`, `wait_for_job`,
  `tail_job_log`, `list_job_files`, `read_job_output_file`, `cancel_job` (in
  `domains/platform/job_tools.py`) are shared by every domain to track/retrieve
  results. `cancel_job` is confirmed to actually terminate a real hung GUI process
  (found and fixed a real race condition here via live testing against Allegro — see
  git history).
- **`sigrity_mcp/domains/platform/session_tools.py`** — `preview_tcl_session`,
  `close_tcl_session`, `list_tcl_sessions` are likewise shared by every session-based
  tool across all domains.
- **`sigrity_mcp/domains/platform/pipeline_tools.py`** (`run_tool_pipeline`) — runs a
  declarative list of `{tool, args, save_as}` steps as one MCP call, with
  `${step_name.field}` placeholders auto-resolved from earlier steps' results. Exists
  because 100+ individual tools is a lot of surface area for a caller to sequence
  correctly by hand — confirmed live driving a full 6-step PowerSI flow in one call,
  and it's what the multi-model evaluation below relies on most.
- **`sigrity_mcp/core/tool_status.py`** — a hand-curated `confirmed_live` /
  `built_untested` / `known_blocked` status per tool (deliberately *not* a live
  `lmutil`-based query, which is already proven unreliable — see below), surfaced
  through `list_sigrity_tools`/`list_allegro_tools`.

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

## Multi-model end-to-end evaluation

`scripts/eval_e2e.py` runs a fixed set of realistic, complex tasks against multiple
OpenAI-compatible endpoints (this project's runs used two vLLM nodes both serving
`qwen3-max`), tracking per-task turns/tool-calls/errors/wall-clock time instead of
just printing a transcript, and writing a JSON report (`eval_results_summary.json`
holds one saved run).

First run: 4 of 6 task+endpoint combinations failed to reach a final answer within 14
turns, with one silent tool-call error. Both root causes were in the eval harness/task
prompts, not the tools: the harness's own 90s per-call timeout was firing on a
legitimate multi-step `run_tool_pipeline` call (and stringifying to an empty message,
since `asyncio.TimeoutError` has no `str()`), and two task prompts asked the model to
"copy the file first" into a scratch location — but this suite has no file-copy tool,
so that instruction was unfulfillable. After raising the timeout, making timeout
errors self-identifying, fixing the prompts, and tightening the system prompt
(explicit rules against unnecessary discovery-tool calls, a standing recommendation to
use `run_tool_pipeline` for 3+ step flows, and to pass generous `wait_for_job`
timeouts): **6/6 succeeded**, with turn/call counts and wall-clock time dropping
substantially across every task that had needed tuning (one task went from 14
turns/19 calls/383s/1 error to 4 turns/4 calls/67s/0 errors).

Both models correctly used the confirmed CAD-to-analysis bridge and multi-step
pipelines, and — notably — both were honest rather than fabricating: for the
PowerSI-extraction task, both models independently flagged that "job exited 0" isn't
the same as "verified extraction results" once they noticed the job's log was empty
and no export step had been requested — a real gap in the task prompt itself, caught
by the model, not a tool defect. The 172.16.34.11 endpoint was consistently faster
than 172.16.34.5 for equivalent work across every matched task.

## Testing

```powershell
python -m uv run pytest -q                          # unit tests (no Sigrity install required for most)
python -m uv run python scripts/smoke_test.py        # lists every registered MCP tool
python -m uv run python scripts/smoke_call.py         # calls a few real platform tools live
python -m uv run python scripts/smoke_amm.py          # runs AmLibGen against a real sample spreadsheet
python -m uv run python scripts/smoke_powersi_real.py # real PowerSI session against a shipped sample .spd
python -m uv run python scripts/smoke_powerdc_real.py # real PowerDC session against a shipped sample .spd
python -m uv run python scripts/smoke_allegro_batch_real.py  # real Allegro report/dbdoctor against a shipped sample .brd
python -m uv run python scripts/smoke_brd_bridge.py    # real .brd -> PowerSI -> .spd bridge, end to end
python -m uv run python scripts/test_llm_e2e.py "<prompt>"   # real LLM-driven MCP tool-calling test, single task
python -m uv run python scripts/eval_e2e.py             # multi-task, multi-endpoint evaluation with metrics
```
