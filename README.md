# sigrity-mcp

A [FastMCP](https://github.com/jlowin/fastmcp) tool suite that drives a local **Cadence
Sigrity 2024.0** install through its Tcl batch-automation interface — Sigrity has no
first-party Python/REST API; every tool here either generates a `.tcl` macro and runs
it against the right Sigrity executable in batch/console mode, or (for the handful of
tools with no Tcl API at all) drives one directly via CLI switches.

Built against a real local install at `C:\Cadence\Sigrity2024.0` — every CLI/Tcl syntax
claim in this codebase was confirmed by reading the shipped documentation and real
sample scripts on disk, or by running the tool directly, not guessed. This machine has
no internet access, so every claim in this README and in the code is grounded in local
Cadence documentation, real shipped sample projects (mainly
`share/PostInstallationCheck/*` — Cadence's own installer self-test scripts, which turn
out to be the single best source of *confirmed* CLI/Tcl invocation syntax on this
machine), and live runs against them — never web research.

This suite also automates a second, sibling Cadence product line on the same machine —
**Allegro/OrCAD SPB 22.1** (`C:\Cadence\SPB_22.1`) — for CAD creation (PCB layout,
schematic capture, DRC, placement, manufacturing output, library/model checking) via
SKILL, Tcl, and standalone CLI tools respectively, closing the loop from blank design
through simulated signoff.

**139 MCP tools across 7 domains**, one Python package.

## The domains

| # | Domain | Package | Covers |
|---|---|---|---|
| 1 | Power Integrity (PI) | `sigrity_mcp/domains/pi/` | PowerDC, XcitePI, OptimizePI |
| 2 | Signal Integrity & Power-Aware | `sigrity_mcp/domains/si/` | PowerSI, SPDSIM, BroadbandSPICE |
| 3 | Interconnect Extraction & Modeling | `sigrity_mcp/domains/extraction/` | Layout translators (Gds2Spd, Oasis2Spd, Ndd2Spd, Pads2Spd, Rif2Spd, Dsn2Spd, SPDLinks), Clarity3D, XtractIM, T2B, plus two standalone utility solvers (Touchstone de-embedding, 2D x-hatch field solver) |
| 4 | In-Design Analysis (Sigrity Aurora) | `sigrity_mcp/domains/aurora/` | Honestly scoped — see below |
| 5 | Unified Framework (Sigrity X Platform) | `sigrity_mcp/domains/platform/` | FlexNet license status, install introspection, AMM model-library tools, the pipeline orchestrator, and the job/session control shared by every other domain |
| 6 | CAD Creation (Allegro/OrCAD) | `sigrity_mcp/domains/cad/` | Allegro PCB layout (SKILL), OrCAD Capture schematic (Tcl), plus real batch DRC, auto-placement, drill-route/via-fanout routing, manufacturing export (IPC-2581/IPC-356/STEP/Gerber), IBIS/die-abstract checking, design-data extraction, and license-gated schematic/netlist interchange |
| 7 | Thermal (Celsius) | `sigrity_mcp/domains/thermal/` | Celsius3D (electrothermal/stress), CelsiusCFD, Celsius2D — a previously completely-unwrapped Sigrity product line, added and confirmed live this pass |

### A note on Domain 4 (Aurora)

Sigrity Aurora is Cadence's real-time in-design SI/PI checking flow. Allegro/OrCAD
*is* installed on this machine (see Domain 6) — but Aurora itself is confirmed, from
Allegro's own docs and its complete 840-file SKILL function reference, to be a
GUI-only mode inside `allegro.exe` with **zero** CLI or SKILL automation surface for
any of its six checks (impedance, coupling, crosstalk, return path, reflection, IR
drop) — every workflow is dialog/wizard-driven only. Rather than fabricate automation
this feature genuinely doesn't expose, Domain 4 has two honest tools: one explaining
the limitation (with the confirming evidence), and one mapping each Aurora check to
the closest standalone equivalent already implemented in Domains 1–3/6/7 (e.g. PowerDC
for IR-drop, PowerSI for crosstalk/coupling via RLGC export, Celsius3D for a real
thermal-stress solve instead of Aurora's live in-editor thermal-adjacent checks).

### Domain 6 (CAD Creation) — what's confirmed, what isn't

This pass audited all 350+ executables shipped in `C:\Cadence\SPB_22.1\tools\bin` (only
5 were registered before) against the doc tree and each exe's own `-help` output, then
live-tested every plausible candidate against a real routed sample board
(`tools/capture/samples/PCB-Layout/Fault-Detector/allegro/fault-detector_allegro_routed.brd`).

**Confirmed live, standalone CLI, no session needed** (each calls its own exe directly,
same reasoning as the original `allegro_report`/`allegro_dbdoctor`: the
`allegro_batch.exe` multiplexer is confirmed broken for at least one sub-program
dispatch, so nothing routes through it):

- **`allegro_drc_tools.py`** — `run_allegro_batch_drc` (`batch_drc.exe -nographic`,
  confirmed: "Batch DRC checking done."). `run_allegro_checkplus` (`checkplus.exe`) is
  a real, license-fetching standalone constraint/rule checker, but its `-proj` argument
  resolves through some CDS project-registration convention rather than a plain
  filesystem path (confirmed via real `**Error! [5038]`/`**Warning! [5015]` diagnostics
  against a real shipped example project) — not yet confirmed end-to-end.
- **`allegro_placement_tools.py`** — `run_allegro_placement` wraps the **real Allegro
  auto-*placement*  engine** (`placement.exe`, confirmed via `allegro_batch placement
  -help`'s "Allegro auto-place program" banner; also exists standalone). Confirmed
  live: it ran the genuine algorithm (real weight/rotation-parameter log) against the
  sample board, failing only on that board's own missing "Package Keepin" — a
  board-authoring precondition, not a wrapper bug. `run_allegro_ncroute` (NC
  drill-route generation, confirmed: "Program completed. Done.") and
  `run_allegro_zrouter` (via/pin-escape fanout routing, driven by a Connections
  Control File — real batch-dispatched sub-program confirmed via `allegro_batch
  zrouter -help`, but exact flag syntax for the control file wasn't recoverable, so
  it's best-effort). **Important scope note**: no batch CLI or SKILL surface for
  general trace *autorouting* was found anywhere on this installation —
  `apr.exe`/`placeroute.exe` are GUI-only with no usage text. Auto-*placement* is real
  and automated; full autorouting is not.
- **`allegro_manufacturing_tools.py`** — IPC-2581 (`ipc2581_out.exe`, confirmed:
  "a2ipc2581 complete."), IPC-356 (`ipc356_out.exe`, confirmed: "Successfully generated
  file"), STEP/3D export (`step_out.exe`, confirmed: "step_out complete."), and
  best-effort Gerber plot (`gbplot.exe` — real batch-dispatched tool per
  `allegro_batch`'s menu, but normally driven by an Artwork Control Form saved with the
  board rather than CLI flags, so untested end-to-end).
- **`allegro_library_tools.py`** — IBIS model checking (`ibischk3`/`4`/`5`/`6.exe`,
  one binary per IBIS spec generation; `ibischk6` confirmed live against a real
  shipped `.ibs` sample — it correctly found real syntax errors/warnings in that
  model, which is the checker doing its job, not a tool failure). Die-abstract
  validation/comparison (`diacheck.exe`/`diacompare.exe`, 3D-IC/interposer flows) —
  real confirmed CLI syntax via `-help`, but no sample die-abstract file was found on
  this machine to run end-to-end.
- **`allegro_extraction_tools.py`** — `run_allegro_design_extractor`
  (`designextractor.exe`) dumps Allegro's own connectivity/data model to JSON. Confirmed
  it genuinely requires a populated `.cpm`/`.sdax` project (passing a raw `.brd`, as
  every other CAD tool here takes directly, is rejected outright) — no populated
  instance of either format exists on this machine (only unfilled `@project@.cpm`
  templates), so this is real but untested end-to-end.
- **`interchange_tools.py`** — `con2xml`/`cap2xml`/`dml2con`/`apd2con`: real,
  standalone translators (Concept-HDL⇄XML, Capture⇄XML, DML⇄Concept-HDL, Package
  Designer⇄Concept-HDL), confirmed genuinely license-gated on this machine — every one
  fails immediately with `"No Product License selected... Translation cancelled"`
  before printing even a usage banner. **This is the clearest "needs a license grant,
  not a code fix" item in this whole suite** — see Known gaps below.

**Confirmed GUI-only or with zero discoverable batch surface — deliberately NOT
wrapped**, to avoid fabricating a capability that doesn't exist: `apr.exe`/
`placeroute.exe` (interactive autorouting), `pspice.exe`/`pspiceaa.exe` (circuit
simulation), `padstack_editor.exe`, `symboleditor.exe`/`symbolcreator.exe` (library
authoring), `dfa_dlg.exe`, `pdnsim.exe`, `apd.exe` (the GUI half of the license-blocked
Package Designer bridge), `orcad.exe`/`orcadx.exe` (redundant GUI entry points into
Capture). Allegro's Constraint Manager has no SKILL API for scripted CSV/XML
constraint import either (grepped the complete 840-file SKILL function reference —
nothing beyond a reporting-only example script).

**Pre-existing tools, status unchanged or improved this pass**:

- **`allegro_batch_tools.py`** (`run_allegro_report`, `run_allegro_dbdoctor`) —
  confirmed live end-to-end against a real board: real component/DRC counts, real
  integrity-check results.
- **`allegro_tools.py`** (SKILL-scripted PCB layout) — session/query mechanics
  confirmed live. **Database mutation is now also confirmed live**: after the user
  resolved a machine-wide licensing issue, `allegro_create_net` (`axlDBCreateNet`) was
  re-tested against a real board and completed cleanly in ~5.6 seconds (previously this
  hung past two minutes in the same session shape — the earlier block really was
  license/queue-related). Only `allegro_create_net` was independently re-confirmed this
  way; the sibling `axlDBCreate*`/`axlSaveDesign`/`axlDRCUpdate` calls share the same
  mechanics but weren't each individually re-run.
- **`capture_tools.py`** (Tcl-scripted schematic capture) — **re-tested after the
  licensing fix, against a real shipped sample project**
  (`Fault-Detector.opj`) with a minimal Open+Save+Close+Exit macro: the process
  launched with the correct argv but was still running with an empty log after 60
  seconds and had to be force-killed. This rules out licensing as the cause
  definitively — the batch-invocation unreliability documented before is a separate,
  still-unresolved issue.
- **The real, confirmed CAD-to-analysis bridge is PowerSI, not a dedicated
  translator**: `start_powersi_session` accepts a real Allegro `.brd` directly —
  PowerSI's built-in "BRDExtractor" translates it automatically on open. Call
  `powersi_save_document` right after (required — PowerSI refuses to simulate a
  design that hasn't been saved to native `.spd` form first), then proceed normally.
  Confirmed live producing a real 237KB `.spd` file and reaching `begin simulation`.

### Domain 7 (Thermal / Celsius) — new this pass, confirmed live

Before this pass, Cadence's whole Celsius electrothermal/thermal-stress product line
(`CelsiusStudio.exe`, `Celsius3D.exe`, `CelsiusCFD.exe`, `Celsius2D.exe`, ...) was
completely unwrapped. A bare `Celsius3D.exe -help` is a dead end (it just prints "You
are using the legacy command line syntax. Run 'Celsius3D -h' to know the details about
the new one" and exits). The real answer was found in Cadence's own installer
self-test script, `share/PostInstallationCheck/bin/postInstallCheck.pl`, which drives
Celsius3D/CelsiusCFD the exact same way it drives the already-confirmed PowerSI/PowerDC
— `<exe> -tcl <script>.tcl` against a real `sigrity::`-namespaced Tcl macro — and drives
Celsius2D via `<exe> -b -XIMSAVE -r <workspace>.pdcx`, the same convention PowerDC's own
CLI uses.

All three were then run live against Cadence's own shipped sample projects and produced
real results:

- **Celsius3D**: `Celsius3D.exe -tcl case.tcl` → exit 0, "Stress engine started and
  completed successfully!", real numeric displacement/strain/stress values written to
  `case_Result_Summary.dat`/`.json`.
- **CelsiusCFD**: `CelsiusCFD.exe -tcl pcb_pkg_sav.tcl` → exit 0, "CelsiusECSolver is
  completed", a real `.cfd` network file generated.
- **Celsius2D**: `Celsius2D.exe -b -XIMSAVE -r demo_sim.pdcx` → exit 0, "Simulation
  succeed", full thermal+stress engine logs with real memory/timing/mesh statistics.

`celsius3d_tools.py`/`celsiuscfd_tools.py` follow this suite's standard
compose-then-run session pattern; `celsius2d_tools.py` is a single CLI-only tool since
the confirmed invocation runs directly against an already-built `.pdcx` workspace.
**Scope note**: no additional Celsius-specific Tcl *authoring* vocabulary (materials,
boundary conditions, power maps) was found documented beyond this confirmed open/run/
close sequence — these tools automate *running* an already-built project, not
constructing one from bare geometry (build that via `CelsiusStudio.exe`'s GUI, or
PowerDC's own thermal features in Domain 1). `CelsiusStudio.exe` itself, and internal
workers `CelsiusEngine.exe`/`celsius_client.exe`, are deliberately not wrapped (GUI-only
or internal-dispatch, confirmed by probing).

### Domain 3 (Extraction) — two new standalone utility solvers

A sweep of every Sigrity `tools/bin` executable not already wrapped turned up two
genuine, self-documenting standalone CLI tools with zero doc-tree coverage but a
complete real `-help` usage banner: **`abcd.exe`** (Touchstone S-parameter
cascading/de-embedding — `run_touchstone_deembed`) and **`bem2d3.exe`** (a 2D static
field solver for transmission-line impedance/delay over x-hatched ground, for
rigid-flex designs — `run_xhatch_field_solver`). Both confirmed via their own `-help`
output; neither was run against a real data file (none was on hand) so both are
`built_untested`. Everything else swept this way (E100/S400–S610, AFSfor3DEM, CIE,
PdcMesh/PdcSolver, VFandEnforcement, RootNodeSpice, MatMgr, LayoutWorkbench, PStarter)
turned out to be internal solver-dispatch workers or GUI-only, consistent with the
existing documented exclusion of `AFSmodule.exe`/`HexMesh.exe`/etc. — none are wrapped.

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
  because 139 individual tools is a lot of surface area for a caller to sequence
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

Note: `pyproject.toml` now declares a `[build-system]`/`hatchling` config so `uv sync`
installs this project itself into the venv (editable). Without it, plain
`python scripts/whatever.py` invocations fail with `ModuleNotFoundError: No module
named 'sigrity_mcp'` because a bare script's own directory, not the repo root, is what
Python puts on `sys.path` — this was silently broken for every `scripts/*.py` smoke
script until this pass (pytest worked anyway, since `tests/__init__.py` makes pytest's
own rootdir-insertion put the repo root on `sys.path`).

This environment has no internet access — Sigrity itself and the local FlexNet license
server are entirely local, so nothing here needs it. (An earlier revision of this
section documented a corporate-proxy workaround for `WebSearch`-based research; that
capability isn't available/used in this environment at all now — every claim in this
README is grounded in local docs, real shipped sample projects, and live test runs.)

Configuration (see `.env.example`): `SIGRITY_HOME` (default
`C:\Cadence\Sigrity2024.0`), `SIGRITY_LICENSE_MANAGER_HOME` (default
`C:\Cadence\LicenseManager`), `SIGRITY_LICENSE_FILE` (default `5280@localhost`,
matching this machine's `CDS_LIC_FILE`), `SIGRITY_WORKDIR` (default `runs/`, where every
job's scratch directory is created).

## Live validation and what it caught

`lmutil lmstat` reports this machine's FlexNet server (`5280@localhost`) as
unreachable — but treat license status as per-tool/per-feature, not a single on/off
switch (see `get_license_server_status`/`diagnose_license_feature`): this pass alone
found PowerSI/PowerDC/XcitePI/OptimizePI/XtractIM/Dsn2Spd/Celsius3D/CelsiusCFD/Celsius2D/
Allegro's session+mutation mechanics/every new batch-CLI CAD tool all fetching real
licenses and running successfully, while a genuinely separate handful of tools are
blocked on distinct, specific causes below — a blanket "no license" read of `lmstat`
would have wrongly written off all of them.

Running real tools against real designs (mostly Cadence's own
`share/PostInstallationCheck/*` self-test projects, plus other shipped samples) caught
several genuine, previously-undocumented facts, this pass and before:

1. **Tcl flag/value spacing** (prior pass). Cadence's own docs render Tcl flags as
   `-start{value}` (no space) — the real Tcl parser requires `-start {value}` as two
   separate words. Fixed everywhere it was found in `si/powersi_tools.py` and
   `pi/powerdc_tools.py`.
2. **Frequency value format** (prior pass). PowerSI's `-start`/`-end` frequency flags
   need plain numeric Hz values (`"1e6"`), not unit-suffixed strings (`"1MHz"`).
3. **PowerDC's `-tcl` batch switch** (prior pass) — never documented in PowerDC's own
   user guide, confirmed working anyway.
4. **This pass: the licensing fix genuinely resolved two previously-blocked
   capabilities and definitively ruled out licensing for a third.** Allegro's
   `axlDBCreateNet` database-mutation call, which previously hung past two minutes,
   now completes in ~5.6 seconds. `allegro_create_net`'s status moved from unverified
   to confirmed_live. Conversely, OrCAD Capture's batch-script invocation was
   re-tested the same way and *still* hangs with an empty log — proving that
   specific unreliability was never a licensing problem to begin with; it remains
   an open, separate issue.
5. **`AmLibGen.exe`'s "silent failure" root cause is now identified, and it isn't
   licensing either**: it writes a log (`AMLibGen.log`) showing it receives the
   correct command line, begins processing, then fails with `[ERROR] Init excel
   failed` — consistent with a broken/missing Microsoft Excel COM dependency on this
   machine for reading legacy `.xls` files. Needs Excel installed/repaired, not a
   license grant.
6. **T2B genuinely requires an external SPICE engine (HSpice) this machine doesn't
   have.** `T2B.exe -b <model>.t2b` launches correctly, parses the model, and
   dispatches real per-pin SPICE characterization jobs — every one aborts because no
   working HSpice install exists here. Not a Cadence license issue; T2B itself never
   failed a license fetch.
7. **`checkplus.exe` and `designextractor.exe` both take a project-registration
   reference, not a raw board file** — confirmed via real, readable error diagnostics
   (`**Error! [5038]`/`**Warning! [5015]` for checkplus; an outright usage-banner
   re-print for designextractor's `.brd` input). Real, license-fetching, headless
   tools; just not yet confirmed against a correctly-shaped project reference.
8. **`SigritySuiteCon.exe` is a Google Test (`gtest`) binary**, not a Chromium-embedded
   GUI shell as an earlier pass of this research speculated — corrected in
   `platform/__init__.py`. Still correctly unwrapped either way.

**What this does and doesn't prove:** the tools listed `confirmed_live` in
`core/tool_status.py` were each individually exercised against a real license and a
real design/sample on this machine, end-to-end. Everything marked `built_untested` is
built from the same research rigor and passes its unit tests (argv/Tcl-line
construction, job lifecycle) but has not been individually run against a real license
and design — treat exact flag spellings as best transcription until exercised.
Everything marked `known_blocked` has a specific, documented, non-code-fixable reason
(see the notes in `core/tool_status.py` and Known gaps below).

## Known gaps

Grouped by what would actually fix them — some need a license grant, some need a
missing third-party dependency installed, and some have no automation surface at all on
this Cadence release, confirmed by exhausting the doc tree and every plausible CLI
probe (not just "we didn't get to it yet").

**Needs a Cadence license grant** (the tool itself is real, confirmed CLI, and fails
specifically with a license-selection message before doing any work):
- `con2xml`/`cap2xml`/`dml2con`/`apd2con` (Domain 6, `interchange_tools.py`) —
  schematic/netlist ⇄ XML/DML translators. Fails with `"No Product License selected...
  Translation cancelled"`.

**Needs a third-party dependency this machine doesn't have** (not a Sigrity/Allegro
license issue at all — these tools' own Sigrity license fetch succeeds or isn't even
reached):
- `T2B.exe` full IBIS-from-SPICE conversion needs a working **HSpice** (or
  Cadence-integrated equivalent) install — T2B itself runs fine and dispatches real
  jobs to it.
- `AmLibGen.exe` (AMM library generation from a spreadsheet) needs a working
  **Microsoft Excel** COM automation path on this machine to read legacy `.xls` files —
  fails with `[ERROR] Init excel failed`, not a license error.

**No automation surface found anywhere (GUI-only or undiscoverable), confirmed by
exhausting the local doc tree + live `-help` probes — not fabricated, not attempted**:
- General trace *autorouting* in Allegro (`apr.exe`/`placeroute.exe`) — only
  auto-*placement* (`placement.exe`) and narrower drill-route/via-fanout routing
  (`ncroute.exe`/`zrouter.exe`) have a confirmed batch CLI.
- PSpice circuit simulation (`pspice.exe`/`pspiceaa.exe`).
- Allegro library authoring GUIs: `padstack_editor.exe`, `symboleditor.exe`/
  `symbolcreator.exe`, `dfa_dlg.exe` (DFA).
- Allegro Constraint Manager scripted CSV/XML import (no `axl*Constraint*` SKILL API
  found).
- Sigrity Aurora (Domain 4) — see above, exhaustively documented as GUI-only.
- `CelsiusStudio.exe`'s own setup/authoring GUI — Celsius3D/CelsiusCFD/Celsius2D's
  batch mode (Domain 7) can *run* an already-built project, not construct one from
  bare geometry via CLI/Tcl.

**Unconfirmed shape, real and license-fetching, just needs the right input to test
end-to-end** (not blocked on license or a missing dependency — needs either a sample
file this machine doesn't have, or a correctly-shaped project reference this pass
didn't isolate):
- `checkplus.exe` (Domain 6) — needs the right CDS project-registration reference, not
  a raw path.
- `designextractor.exe` (Domain 6) — needs a populated `.cpm`/`.sdax` project (none
  exists on this machine; only unfilled templates).
- `diacheck.exe`/`diacompare.exe` (Domain 6) — no die-abstract sample file was found to
  test against.
- `abcd.exe`/`bem2d3.exe` (Domain 3) — no Touchstone/geometry sample file was found to
  test against.
- `SPDSIM.exe` — a real shipped sample failed with `"Failed to open the file"` despite
  matching the original byte-for-byte; root cause (legacy text-format `.spd`, a
  working-directory quirk, or something else) not isolated.

## Multi-model end-to-end evaluation

`scripts/eval_e2e.py` runs a fixed set of realistic, complex tasks against multiple
OpenAI-compatible endpoints (this project's runs used two vLLM nodes,
`172.16.34.5:8000` and `172.16.34.11:8000`, both serving `qwen3-max`), tracking
per-task turns/tool-calls/errors/wall-clock time instead of just printing a transcript,
and writing a JSON report (`eval_results_summary.json` holds one saved run).

First run (prior pass): 4 of 6 task+endpoint combinations failed to reach a final
answer within 14 turns, with one silent tool-call error. Both root causes were in the
eval harness/task prompts, not the tools: the harness's own 90s per-call timeout was
firing on a legitimate multi-step `run_tool_pipeline` call, and two task prompts asked
the model to "copy the file first" into a scratch location — but this suite has no
file-copy tool, so that instruction was unfulfillable. After raising the timeout,
making timeout errors self-identifying, fixing the prompts, and tightening the system
prompt: **6/6 succeeded**, with turn/call counts and wall-clock time dropping
substantially across every task that had needed tuning.

**This pass**: extended `TASKS` with three new scenarios exercising the new CAD/thermal
coverage — `cad_drc_and_placement` (batch DRC + real auto-placement on the sample
board, including reporting the board's genuine "No Package Keepin" error rather than
claiming false success), `cad_manufacturing_export_and_ibis_check` (IPC-2581 + STEP
export, plus an IBIS model check with real error/warning content), and
`thermal_celsius3d_signoff` (a full Celsius3D electrothermal/stress run against a
pre-staged real sample project, citing the engine's own log). Learning from the prior
pass's "no file-copy tool" pitfall, every new task prompt points directly at an
already-staged real file under `runs/` rather than asking the model to copy one first.
Run with `python -m uv run python scripts/eval_e2e.py` against both endpoints — **12/12
task+endpoint combinations reached a final answer** (`eval_results_summary.json` holds
this run):

| Task | node-5 | node-11 |
|---|---|---|
| brd_to_powersi_signoff | OK, 227s, 16 turns, 0 errors | OK, 92s, 9 turns, 0 errors |
| allegro_report_and_check | OK, 89s, 7 turns, 0 errors | OK, 26s, 5 turns, 0 errors |
| aurora_scope_and_alternative | OK, 81s, 2 turns, 0 errors | OK, 25s, 3 turns, 0 errors |
| cad_drc_and_placement | OK, 82s, 6 turns, 0 errors | OK, 21s, 4 turns, 0 errors |
| cad_manufacturing_export_and_ibis_check | OK, 117s, 5 turns, 0 errors | OK, 63s, 8 turns, 0 errors |
| thermal_celsius3d_signoff | OK, 662s, 11 turns, 3 errors | OK, 784s, 12 turns, 3 errors |

The 172.16.34.11 endpoint was again consistently faster than 172.16.34.5 for equivalent
work, matching the prior run.

**The two `thermal_celsius3d_signoff` runs caught a genuine, real, reproducible bug in
Celsius3D itself, not a harness/prompt problem** — both models independently ran the
task, hit a job that never progressed past its startup banner, retried up to the task's
built-in limits, and then correctly reported failure ("the run hung for ~10 minutes
producing no progress at all — I couldn't confirm the stress engine completed, because
it never did") instead of fabricating success from a non-error return. Investigating
why turned up the real cause: **re-running Celsius3D against a project directory that
already contains a prior run's result folder hangs indefinitely** — independently
reproduced with a direct `timeout 20 Celsius3D.exe -tcl case.tcl` (exit 124, no
output). Both eval runs happened to reuse the same staged sample project from this
pass's first successful Celsius3D test, so this was a real bug the eval caught, not an
eval artifact — now documented in `celsius3d_tools.py`'s docstring and
`core/tool_status.py` with the workaround (always use a fresh project copy per run).

Both models correctly used the confirmed CAD-to-analysis bridge and multi-step
pipelines throughout, and — notably — were consistently honest rather than fabricating:
in the prior pass, both models independently flagged that "job exited 0" isn't the
same as "verified extraction results"; in this pass, `cad_drc_and_placement` correctly
reported the real board-specific "No Package Keepin" placement failure at both
endpoints instead of claiming success, and both models exhausted every reasonable
retry/diagnostic tool (`wait_for_job`, `tail_job_log`, `get_license_server_status`,
`cancel_job`) before giving up honestly on the Celsius3D hang.

## Testing

```powershell
python -m uv run pytest -q                          # unit tests (no Sigrity install required for most)
python -m uv run python scripts/smoke_test.py        # lists every registered MCP tool
python -m uv run python scripts/smoke_call.py         # calls a few real platform tools live
python -m uv run python scripts/smoke_amm.py          # runs AmLibGen against a real sample spreadsheet (currently fails on a missing Excel COM dependency — see Known gaps)
python -m uv run python scripts/smoke_powersi_real.py # real PowerSI session against a shipped sample .spd
python -m uv run python scripts/smoke_powerdc_real.py # real PowerDC session against a shipped sample .spd
python -m uv run python scripts/smoke_allegro_batch_real.py  # real Allegro report/dbdoctor against a shipped sample .brd
python -m uv run python scripts/smoke_brd_bridge.py    # real .brd -> PowerSI -> .spd bridge, end to end
python -m uv run python scripts/smoke_new_cad_tools.py # real batch_drc/placement/ncroute/manufacturing-export/checkplus/ibischk run against a real sample board
python -m uv run python scripts/smoke_capture_retest.py          # re-verifies Capture's batch invocation is still unreliable (not license-related)
python -m uv run python scripts/smoke_allegro_mutation_retest.py # re-verifies allegro_create_net now completes live
python -m uv run python scripts/test_llm_e2e.py "<prompt>"   # real LLM-driven MCP tool-calling test, single task
python -m uv run python scripts/eval_e2e.py             # multi-task, multi-endpoint evaluation with metrics
```
