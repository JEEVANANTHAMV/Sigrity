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

---

## END-TO-END EDA WORKFLOWS + PART RESOLUTION (read this FIRST for any design task)

This suite is a generic end-to-end EDA engine. For ANY task — build a board from scratch, take in an existing design (schematic / BOM / Gerber / IPC-2581 / DXF / STEP), analyze it, re-route it, edit it, DRC it, fabricate it, or run SI/PI/thermal — work the phases below. The phases are capability-dependent, not fixed: skip any phase whose inputs already exist. The ONE invariant rule for every task:

> **CHECK BEFORE THE NEXT STEP.** At the start of each phase, verify its inputs actually exist. If an input is missing, do NOT fabricate it and do NOT call a tool that needs it — **STOP and ask for the specific missing artifact** (name the part/file/format). Only when the gate passes, proceed to the next phase.

### The seven phases (entry point = the earliest phase that has no input yet)

| Phase | What runs | Gate — verify before proceeding |
|---|---|---|
| **0. Intake** | `run_capture_session` (OrCAD schematic) or `dxf2a` / `ipc2581_in` / `brd2dml` / `spif_specctra` / `allegro_new_blank_board` / open an existing `.brd` | Know the design intent (requirements doc / netlist / existing board). No netlist + no existing `.brd` → ask for a schematic file or netlist. |
| **1. Parts / libraries** | `create_sym` / `ipc2581_in` / `dxf2a` to import footprints; `diacheck`/`ibischk*` to validate models | **Every refdes in the netlist has an Allegro footprint (`.pdra`/`.d`) + OrCAD symbol (`.olb`).** If any refdes has no footprint → **STOP and list exactly which refdes/footprints are missing** (see "Part resolution" below). |
| **2. Schematic → board** | `capture` → netlist → `allegro` (create `.brd`), `allegro_create_net`, stackup via `generate_multilayer_stackup`, constraints/presets (`get_high_speed_constraint_preset`, `allegro_create_ecset`, `allegro_set_physical_constraint`) | Board exists with nets, stackup, and the interface constraint sets. A **nets-only board is NOT placeable** — nets are logical names with 0 pins (you cannot place/route/DRC/extract a net). |
| **3. Placement** | `placement.exe` (or manual `allegro_create_copper_shape` for pour/geometry) | Footprints present (Phase 1 gate) AND a board outline/mechanical constraint. No outline → ask or import a DXF. |
| **4. Route + DRC** | SPECCTRA auto-route (`spif_batch` export → `specctra` route → `run_allegro_specctra_import`) + `run_allegro_batch_drc` / `checkplus` / `run_allegro_report(report_code="drc")` | Placed parts (Phase 3). Judge success by `final.sts` `Completion` + `batch_drc.log` error count, never the raw `state`. |
| **5. Analysis** | translate to `.spd` (PowerSI BRD-bridge / `xtractim`) → `powerdc` (IR-drop/E-T), `optimizepi`, `powersi` (S-params/crosstalk), `xtractim`/`clarity3d` (3D EM), `psp_cmd` (SPICE/behavioral), `celsius*` (thermal), `aurora` (EMC pre-screen) | A `.spd` with placed+routed copper for the nets under study. No copper → **STOP: analysis is pending placement/routing** (not pending license, not a tool defect). Verify the `.spd` path you passed is YOUR staged file, not a sample. |
| **6. Fabrication / sign-off** | `run_allegro_generate_artwork` (Gerber), `run_allegro_ipc356_out` / `run_allegro_ipc2581_out` (manufacturing), `run_allegro_step_out` (3D), `run_allegro_pdf_out`, full DRC readback | DRC-clean (Phase 4). For formal EMC/ESD/surge PASS/FAIL (IEC 61000-4-x) that is a **lab/chamber** item — design-side pre-screen (AURORA/PSpice) is the automatable slice; say so rather than claiming a cert. |

### Part resolution — the gate that is different here

This install ships software (Allegro, OrCAD, PowerDC, PowerSI, XtractIM, Clarity3D, PSpice), **not application-specific components**. A fresh install has only generic primitives (0201/0402/0603/0805 R/C/L padstacks, vias, generic connector shells). **Every application component in ANY design is vendor-supplied IP** (the chipmaker's licensed mechanical drawing) and is **not** in the install. So the Phase-1 gate is the universal "missing parts" check, for whatever the design is — not a fixed list:

1. **Derive the required-part list from the DESIGN, not from memory.** Read the netlist / BOM / schematic / requirements to enumerate every refdes + package. (If handed a BOM file, that IS the list.)
2. **Check each part** against the part-library roots:
   `C:\Cadence\SPB_22.1\share\pcbdw_lib\`, `...\share\library\`, `...\share\pcb\pcb_lib\`, `...\share\orcad\` — match by part number/name (footprint file extensions: Allegro `.pdra`/`.d`; OrCAD `.olb`).
3. **If any are missing, STOP and report the exact missing parts** (refdes, description, expected package, and the file format you need: Allegro `.pdra`/`.d` + `.olb`, or IPC-2581/STEP which this suite converts via `ipc2581_in`/`dxf2a`). Import them into `C:\Cadence\SPB_22.1\share\pcbdw_lib\` (or any folder on a `LIB_DIR`) and re-gate.
4. **Do NOT** invent a footprint, do NOT run placement/route/DRC/analysis on what isn't there, and do NOT label a missing part a license failure. The honest status is **pending component import** for the specific missing refdes.

### Capability boundaries (what the suite can and cannot do, for any task)
- **Can do, end-to-end, no external dependency:** board authoring (stackup/nets/constraints/copper shapes), DRC, Gerber/mfg export (Gerber/IPC-356/IPC-2581/STEP/PDF), PSpice behavioral/SPICE sim, PowerSI S-params/crosstalk, XtractIM/Clarity3D extraction, OptimizePI, Thermal.
- **Can do, gated on inputs:** placement (needs footprints + outline), SPECCTRA auto-route (needs placed board), PowerDC IR-drop (needs a `.spd` of placed+routed copper **and** PowerDC Net Classes — see the PowerDC pdcVRM caveat in `sigrity-cad` Task 7).
- **Cannot do from this desktop (state it, don't fake it):** formal EMC/ESD/surge chamber certification (IEC 61000-4-x Level pass/fail), and capturing a live interactive Allegro session that only exists as a GUI (use the batch/CLI/headless paths).

### Worked example (one real design, to show the gate in action)
For the NXP i.MX 8M Plus IP-camera board, Phase-1 derived this required-part list from the requirements doc and found it ABSENT in the libraries (34,815-file search, 2026-10-11). The gate would therefore STOP at Phase 1 and ask for these 18 before any place/route/analysis — this is an EXAMPLE of the generic gate, not a fixed list:

### Example part manifest (i.MX 8M Plus IP-camera only — NOT a fixed list, derive per design)

| # | Component | Mfg PN (spec) | Package | Notes |
|---|---|---|---|---|
| 1 | i.MX 8M Plus SoC | MIMX8ML8DVNLZAB | FCBGA 316-ball | NXP board-design-files package gives `.pdra` + `.olb` together |
| 2 | PMIC | NXP PCA9450B/C | BGA/QFN | VDD_ARM/SOC/DDR/IO |
| 3 | LPDDR4/4X DRAM | 2×2 GB, 32-bit | BGA | memory, up to 4000 MT/s |
| 4 | eMMC 5.1 | 16/32 GB HS400 | BGA | storage |
| 5 | Quad-SPI NOR | 32 MB @ 104 MHz | SOP/QFN | boot flash |
| 6 | MicroSD connector | UHS-I SDR104 socket | socket | + NVT4857UK level translator, multi-ch TVS |
| 7 | Image sensor | sony STARVIS 4K | + IRCUT actuator | on the 38×38 headboard |
| 8 | FPC / board-to-board | 30-pin shielded high-speed | connector footprint | between main SoC + sensor boards |
| 9 | GbE PHY | Realtek RTL8211F | QFN | RGMII 1.8V |
| 10 | RJ45 + magnetics | 1 kV integrated | module | + SRV05-4 TVS, common-mode chokes |
| 11 | PoE PD | TI TPS23753A (IEEE 802.3af/at) | + isolated transformer | 1.5 kV barrier, ORing, SMAJ15A, fuse, P-FET |
| 12 | SMD passives | 0201/0402 MLCC + R + L + ferrite beads; 10–22 µF bulk | standard | decoupling/filtering — the generic shells may already cover these |
| 13 | Crystals/osc | 24 MHz (±10ppm) / 32.768 kHz / 25 MHz + sensor-local 24/27 MHz | 3225/3215/5032 | clocking |
| 14 | Audio | TI/National WM8960 codec + Class-D 2W/8Ω amp + PDM mic header | QFN |  |
| 15 | IR-CUT / IR | TI DRV8837C (QFN) + 850 nm IR LED (1 A) | QFN + LED |  |
| 16 | Industrial I/O | isolated RS-485 (120 Ω) + optocoupler (5–24V) + 30V/1A SSR |  |  |
| 17 | Secure element | NXP EdgeLock SE050 | LQFP/DFN | tamper-proof keys |
| 18 | TVS / protection | SRV05-4, multi-channel TVS arrays, SMAJ15A |  |  |

When only a SUBSET of a design's parts is imported, state explicitly which refdes are present vs **pending component import** and gate the dependent place/route/PI phases on the missing ones. Do NOT invent a footprint; do NOT treat a missing part as a license failure. (For a DIFFERENT design, re-run "Part resolution" from its own netlist/BOM — this table does not apply to it.)

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
- All four interchange tools (`run_cap2xml/dml2con/con2xml/apd2con`) — on this machine they surface a FlexNet product-chooser at launch on this PREMIUM/no-license-required install (not a missing license); the GUI tool handler in `core.gui_tool_runner` is what drives them; see `sigrity-cad` Task 3 for the confirmed working SPECCTRA import as the primary interchange path.
- `run_t2b_conversion` — needs an external HSpice (not installed).
- `run_allegro_zrouter` — refuses (GUI-only, Qt, no headless path).
- `run_touchstone_deembed` (abcd) — segfaults on 4-port MA/dB files, silently no-ops on everything else; verify output exists.
- `capture_*` / `start_capture_session` — Capture batch Open hangs (install defect); `capture_handle_custom_launch_dialog` only clears the recovery dialog, not the Open hang.

## Reporting back (when asked to report findings/learning)

Per task: name the tool(s), the exact minimal call sequence (tool, key args, job poll, verify-step),
the result state + how you VERIFIED it, what was least obvious / what error you first hit and the
fix, and the single most common mistake to avoid. Be concrete and short. Do not claim success on
`state` alone — state the artifact you checked.
