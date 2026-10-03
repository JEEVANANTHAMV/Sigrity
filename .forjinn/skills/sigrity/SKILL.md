---
name: sigrity
description: Drive the local Cadence Sigrity 2024.0 + Allegro/OrCAD SPB 22.1 install through its 181-tool MCP suite. Use for any Sigrity/Allegro/Cadence EDA task — board analysis, SI/PI/thermal simulation, extraction, DRC, placement, routing, manufacturing export, project creation, or job/license introspection. Always start here to learn which tool to call, the minimal call sequence, and which sample file to use.
---

# Sigrity MCP — Foundation

You drive Cadence EDA through MCP tools on machine C: where `SIGRITY_HOME=C:\Cadence\Sigrity2024.0`,
SPB = `C:\Cadence\SPB_22.1`. There is no internet and no Cadence Python API — every tool either
generates a Tcl/SKILL macro and runs one batch process, or calls a standalone CLI directly.

## How automation actually works (the two mental models)

**Model A — "run" tools (no session).** Call `run_<x>(file=...)` → returns `{"job_id","state","job_dir","command"}`
immediately. The real work continues as a background job. Then you MUST poll.

**Model B — session tools (compose, then run).** A `start_<x>_session(...)` returns a `session_id`.
You call any number of `<x>_set_*` / `<x>_add_*` / `<x>_create_*` tools (each takes `session_id`
first and only QUEUES one script line — nothing executes). Then ONE `*_run_session(session_id, ...)`
writes the whole macro and launches the process, returning `job_id`. The session auto-closes;
reuse of a closed id → `{"error": "No open script session ..."}`.

## The three inviolable rules (90% of errors come from breaking these — all verified live)

1. **A `run_*`/`*_run_session` tool does NOT block.** It returns `state:"running"` with a `job_id`
   immediately. You must follow with `wait_for_job(job_id, timeout_seconds=...)` and/or `get_job_status`
   until `state` is `succeeded`/`failed`. If `wait_for_job` times out still `"running"`, call it again.
   `wait_for_job` is session-local to the server process that launched the job — if it errors
   "not tracking", fall back to `get_job_status` polling (or re-issue the whole flow inside one
   `run_tool_pipeline`, where the wait always resolves).
   **A DIFFERENT, more common failure looks similar but needs a different fix**: any tool call —
   `wait_for_job`, `run_tool_pipeline`, `start_allegro_session`, etc. — can come back as an outright
   tool ERROR reading `Error calling <tool>: MCP request timed out after 30000ms: tools/call` (confirmed
   recurring: observed 15 times across 9 independent runs). This is the MCP CLIENT's own
   flat 30-second cap on one request/response round trip — it fires even when you passed a much larger
   `timeout_seconds`, and it tells you NOTHING about whether the underlying job succeeded, failed, or is
   still running. Do not resubmit the same job (you may now have two running against the same files) —
   the `job_id` from the original submission still works; recover with `get_job_status(job_id)` (or
   `list_all_jobs(state="running")` if you've lost track of the id) to read the real state, then go back
   to polling/waiting normally.
2. **`state` is a liar in BOTH directions.** `succeeded`+rc0 ≠ the work happened (PowerSI batch run
   missing its final trigger exits 0 in ~3s with zero output; abcd silently no-ops) AND
   `running` ≠ stuck (batch_drc/ibischk launchers exit while `job.json` still says running;
   Celsius3D idles forever AFTER a successful solve). The log file is the only source of truth:
   `tail_job_log(job_id)` for the real completion/error line, and confirm a real non-empty artifact.
3. **`list_job_files` is NOT where the results are for most tools.** Job dir holds only
   `job.json`/`macro.tcl`/`run.log` (often 0-byte `run.log`). PowerSI writes its `*_S.sNp` + netlist
   + timestamped log **in the design's own directory**; XtractIM writes RLC CSVs **next to the `.ximx`**;
   Celsius writes result folders **next to the input project**; PowerDC reports next to the `.pdcx`.
   So: after a job ends, list the *input file's* directory (e.g. `runs/` if you staged there with
   `copy_file`) for a new non-empty artifact newer than the job start — that is the real success check.

## Every job, regardless of domain, uses these 7 job tools

| Tool | Purpose |
|---|---|
| `get_job_status(job_id)` | current state (pending/running/succeeded/failed/cancelled/timeout) + `returncode`, `job_dir`, `license_issue_suspected` |
| `wait_for_job(job_id, timeout_seconds=60)` | block until done or timeout; re-call to keep waiting |
| `tail_job_log(job_id, max_lines=200)` | last N log lines — the ONLY place you see solver progress / the real error text |
| `list_job_files(job_id)` | list output files in `job_dir` (macro.tcl, run.log, job.json, + result artifacts) |
| `read_job_output_file(job_id, relative_path, max_lines=80)` | read one artifact (auto-detects touchstone/text/csv/binary) |
| `cancel_job(job_id)` | kill a stuck/running job |
| `list_all_jobs(state="any")` | list jobs this server launched (in-memory, current process only) |

If a job shows `state:"failed"`: first `tail_job_log` for the message. If a job is still
`running` past its normal finish time, check `check_design_lock(design_path)` — an orphaned
`.lck` from a killed prior run makes it "hang" on a modal dialog (no console output).

## The one-call shortcut: run_tool_pipeline

To avoid threading `session_id`/`job_id` by hand and to save round-trips, chain a known sequence
in ONE tool call with `${name.field}` placeholders:

```
run_tool_pipeline(
  stop_on_error=True,
  steps=[
    {"tool":"start_powersi_session","args":{"spd_file":"<PATH>"}}" ,"save_as":"s"},
    {"tool":"powersi_save_document","args":{"session_id":"${s.session_id}","spd_file":"<OUT.spd>"}},
    {"tool":"powersi_set_frequency_sweep","args":{"session_id":"${s.session_id}","start":"1e6","end":"1e9"}},
    {"tool":"powersi_add_ports_auto","args":{"session_id":"${s.session_id}"}},
    {"tool":"powersi_run_session","args":{"session_id":"${s.session_id}"},"save_as":"run"},
    {"tool":"wait_for_job","args":{"job_id":"${run.job_id}","timeout_seconds":180}},
  ])
```

Rules: `save_as` stores a step's result so later steps read `${name.field}` (typed) or embed it in
a bigger string. Max 50 steps; no nesting. **Step-result keys: a step whose tool call RAISED
(bad/missing arg name, unknown session id, …) is recorded with an `error` key and NO `result` key,
counts toward `failed_count`, and with `stop_on_error=True` HALTS the pipeline.** A step that returns
normally has a `result` key — but `result` may itself be an `{"error": ...}` payload (e.g.
`get_job_status` on a stale id), which is a *succeeded* step; inspect `result` before trusting it.
So: to diagnose where a pipeline stopped, read each entry's `error` then `result` individually.
PREFER pipelines when the sequence is known: they keep `session_id`/`job_id` in one server lifetime
(where `wait_for_job` resolves) and collapse N round-trips into one call.

## Argument-name traps (wrong names → SILENT hang, no clean error)

All tool args are strict; passing a plausible-but-wrong name either raises `missing_argument` or,
worse, hangs ~20 min. The traps verified live: file tools are `source_file`/`destination_file`
(and `file_path` for delete) — NOT `source`/`destination`; PowerSI edge port is `positive_node`/
`negative_node` (NOT `positive_net`); frequency sweeps take `start`/`end` as PLAIN Hz strings
(`"1e6"`, NOT `"1MHz"`); Celsius/Clarity3D `*_run_session` require the project/design path AGAIN
as a second arg.

**FIXED — `list`/`dict` arguments sent as JSON strings now work.** If the calling
model emits a `list[...]`/`dict[...]`-typed argument (e.g. `generate_multilayer_stackup`'s
`layers`, `run_tool_pipeline`'s `steps`) as a JSON-encoded *string* rather than a native
array/object — a real, observed quirk of some open-weight models' tool-call emission (e.g.
qwen3-max via vLLM) — it is now transparently parsed back to a native list/dict for every tool
in this suite before validation, instead of failing with a pydantic `list_type`/`dict_type`
error. See `sigrity_mcp/core/argument_coercion_middleware.py` for the mechanism (one FastMCP
middleware, applied suite-wide) and `sigrity-cad`'s SKILL.md (Task 6) for the tool that
originally surfaced this. A parameter that legitimately accepts either a string or a list
(`Union[str, list[str]]`, e.g. `ref_des` in several PI tools) is unaffected either way.

## Domain index → which SKILL.md has the sequences + sample files

- **SI/Power-Aware** → `sigrity-si`: PowerSI (S-param, crosstalk, RLGC), BroadbandSPICE, SPDSIM.
- **Power Integrity** → `sigrity-pi`: PowerDC (IR-drop, E-T), XcitePI (chip parasitic), OptimizePI (decap).
- **Extraction** → `sigrity-extraction`: layout translators→.spd, XtractIM, Clarity3D, T2B, abcd/bem2d3.
- **CAD/Allegro** → `sigrity-cad`: SKILL PCB authoring, SPECCTRA autoroute, DRC, placement, manufacturing export, project creation, PSpice.
- **Thermal** → `sigrity-celsius`: Celsius2D/3D/CFD.
- **Platform** (this file): job/session/pipeline/file/license/install tools.

## REAL file assets (USE THESE PATHS — they exist and are the confirmed test inputs)

Copy read-only sources into the job scratch or a `runs/` target first (tools write next to/into
their job dir; never overwrite a shipped sample in place). `copy_file(src,dst,overwrite)` to stage.

| Purpose | Real path |
|---|---|
| Powered Allegro board (routed, has DRC state) | `C:\Cadence\SPB_22.1\tools\capture\samples\PCB-Layout\Fault-Detector\allegro\fault-detector_allegro_routed.brd` |
| Allegro board (unrouted) | `...\allegro\fault-detector_allegro.brd` |
| Allegro board (SPECCTRA variant) | `...\allegro\fault-detector_specctra.brd` |
| OrCAD Capture project | `C:\Cadence\SPB_22.1\tools\capture\samples\PCB-Layout\Fault-Detector\Fault-Detector.opj` |
| Sigrity PowerSI design (.spd) | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\powersi\psi_brd_demoshort.spd` |
| Sigrity PowerSI design (.spd) | `...\powerdc\Motherboard.spd` |
| PowerDC IR case (.spd) | `...\powerdc\IR_Package.spd` and `.pdcx` (`IR_Package.pdcx`) |
| PowerDC ET (co-sim) | `...\powerdc\Multi-board-ET.sdc` (use `IR_Package.spd` for IR-drop) |
| XcitePI chip parasitic (.gds+.map+.tcl) | `...\xcitepi\demo_decap.gds` + `demo1.map` (+ `demo_decap.tcl` = confirmed working macro) |
| XtractIM package workspace (.ximx) | `...\xtractim\Wirebond_EPA.ximx` (+ `Wirebond_EPA.spd`) |
| XtractIM 3D EM design | `...\clarity\43micro.spd` |
| OptimizePI decap case | `...\optimizepi\demo_OPI.spd` + `PDN_Verification.opix` + `demo_decap_library.xml` |
| Celsius3D thermo-stress case | `...\celsius3d\case.3dth` (+ `case.tcl`) |
| CelsiusCFD case | `...\celsiuscfd\pcb_pkg_sav.3dth` (+ `pcb_pkg_sav.tcl`) |
| Celsius2D board thermal ws | `...\celsius2d\demo_sim.pdcx` |
| AMM library source (legacy .xls — Excel COM needed!) | `C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\AMM\Demo_Resistor_lib1.xls` |
| IBIS model to check (.ibs) | `C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\SPEEDEM\EMI Simulation\Examples_PostSetup\IBIS\dram.ibs` |
| Touchstone .s4p (RI, SAFE for abcd) | `C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\Broadband SPICE\app1_drv.S4P` |
| Touchstone .s4p (MA/dB — CRASHES abcd, avoid as input) | `...\Broadband SPICE\channel.s4p` |
| Touchstone .s2p (for BBS / abcd) | `...\Broadband SPICE\spiral_10GHz.s2p` |
| DXF to import → new .brd | `C:\Cadence\SPB_22.1\doc\wb_tut\examples\Module_1\flag.dxf` + `flag_l.cnv` |
| PSpice circuit (.cir) | `C:\Cadence\SPB_22.1\share\orcad\examples\PSpice\TI\DRV8837\DRV8837-PSpiceFiles\SCHEMATIC1\trans\trans.cir` (note: its `.include` may reference absent paths — a self-contained `.cir` is needed for a clean run) |

## Known-blocked / defective tools — DO NOT burn time attempting, report the documented cause

- `run_spdsim_simulation` — blocked (must run as a PowerSI-Tcl child process; standalone fails "Skip license fetch").
- `run_specctra_import_session` — **crashes** (0xC0000005 / SPMHDB-238) on every import. Export+route is the durable half; import is a product bug.
- All four interchange tools (`run_cap2xml/dml2con/con2xml/apd2con`) — license-gated ("No Product License selected"); the FlexNet server is down on this machine.
- `run_t2b_conversion` — needs an external HSpice (not installed).
- `run_allegro_zrouter` — refuses (GUI-only, Qt, no headless path).
- `run_touchstone_deembed` (abcd) — segfaults on 4-port MA/dB files, silently no-ops on everything else; verify output exists.
- `capture_*` / `start_capture_session` — Capture batch Open hangs (install defect); `capture_handle_custom_launch_dialog` only clears the recovery dialog, not the Open hang.

## Reporting back (when asked to report findings/learning)

Per task: name the tool(s), the exact minimal call sequence (tool, key args, job poll, verify-step),
the result state + how you VERIFIED it, what was least obvious / what error you first hit and the
fix, and the single most common mistake to avoid. Be concrete and short. Do not claim success on
`state` alone — state the artifact you checked.
