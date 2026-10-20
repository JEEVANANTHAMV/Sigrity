# Sigrity MCP Toolkit — Complete Cadence Automation Reference

**Project:** `sigrity-mcp` · **FastMCP 4.0.4** · **Live tools: 207** · **Cadence installs:** Sigrity 2024.0 (`C:\Cadence\Sigrity2024.0`) + Allegro/OrCAD SPB 22.1 (`C:\Cadence\SPB_22.1`)
**Transport:** stdio (default) / http / sse · `python main.py --transport http --host 0.0.0.0 --port 8765 --path /mcp`
**Swagger UI / interactive console:** `http://localhost:8765/docs` · OpenAPI: `/openapi.json`
**Generated:** 2026-10-17

> Sigrity and Allegro/OrCAD ship **no first-party Python or REST API**. Every tool here either (a) generates a `.tcl` macro and runs it against the right Sigrity executable in batch mode, (b) generates a SKILL script and replays it in `allegro.exe -s`, or (c) drives a standalone CLI tool directly. This document catalogs **all 207 tools** — what each does, the exact Cadence executable it drives, how to invoke it, its verification status, and every known failure mode.

> **UPDATE (2026-10-17, later pass)**: 4 tools added since this document was generated
> (211 total) — `extract_capture_netlist_headless`, `author_capture_schematic_headless`
> (`domains/cad/capture_headless_tools.py`) and `run_netrev_import`/`run_netin_import`
> (`domains/cad/netlist_import_tools.py`). §5.5's description of Capture below (the
> `Open <project>` hang, "no CLI flag or documented workaround found") is SUPERSEDED:
> the hang is root-caused (an embedded Start Page's blocking network call through the
> system proxy, fixed via `ENABLE_CAPTURE_AUTOMATION=TRUE`, now automatic) and both
> reading and authoring a schematic now work fully headlessly via `tclsh.exe` loading
> Capture's own database DLL directly — see `core.tool_status.TOOL_STATUS_NOTES
> ["tclsh"]`/`["capture"]` for the complete current evidence, including why the
> `Capture.Application` COM interface and `syscap.exe` were both investigated and ruled
> out as alternatives. Capture's own Tcl-session batch invocation (the 12 tools in
> §5.5 itself) remains genuinely `known_blocked` as described — that specific mechanism
> was not fixed, it was superseded for its two main use cases.

---

## 0. How everything works (the 4 mental models)

Reading any tool in this report requires only these four concepts.

### 0.1 Compose-then-run sessions (the dominant pattern)
Most solvers are driven by an in-memory "session" — a Tcl script that is **composed of one line at a time** and then launched **once**. A single "flow" is therefore many MCP calls:

```
start_<solver>_session(...)        -> returns session_id, opens nothing
<name>_add_* / <name>_set_* (...)  -> each appends ONE sigrity:: line to the session
<name>_export_* (...)              -> also just appends a line
<name>_run_session(...)            -> ONLY this writes the macro & launches the exe
```
**Compose tools launch no process and do nothing until `*_run_session` is called.** Use `preview_tcl_session(session_id)` to inspect the accumulated script before firing, `close_tcl_session` to discard it, `list_tcl_sessions` to see open sessions.

### 0.2 Every `run_*` / `*_run_session` returns a job, not a result
Long-running tools launch as **tracked background jobs** and return `{job_id, state, job_dir, command}` **immediately** (state is almost always `"running"` at return time). You then poll with the platform job-lifecycle tools:

```
get_job_status(job_id)                 -> state: running / succeeded / failed
wait_for_job(job_id, timeout_seconds)  -> block until terminal or timeout
tail_job_log(job_id, max_lines)        -> last N lines of stdout+stderr
list_job_files(job_id)                 -> output files in the job dir
read_job_output_file(job_id, path)     -> read one output file (kind-aware parser)
cancel_job(job_id)                     -> force-kill a hung job
list_all_jobs(state="any")             -> audit every job this server launched
```

### 0.3 "Success" is an artifact, never an exit code
The single most important rule in this suite: **`state == "succeeded"` / `returncode == 0` is not proof the tool did anything.** Multiple tools exit cleanly on failure (PowerSI missing-save, XtractIM incomplete-setup, abcd silent no-op, Allegro silent no-ops, Capture fast-exit). **Always verify by the real output file** (a non-empty `.sNp`, `.epa`, `.brd`, `run.log` text, independent `report.exe` re-read), not by job state.

### 0.4 Verification status (the 57-entry ledger)
`core/tool_status.py` hand-maintains a per-executable status for the 57 executables that have been individually assessed:

| Status | Meaning |
|---|---|
| `confirmed_live` | Actually run against a real design on this install, successfully, ≥1× |
| `built_untested` | Built from local docs / real `-help` + unit-tested argv, but never run against real data here |
| `known_blocked` | Attempted live and found genuinely blocked (root cause documented, **not** a license issue) |
| `UNTRACKED` | Drives an executable that has **no** ledger entry at all (18 tools / 8 exes — see §10) |

**18 of the 207 tools are pure-Python** (jobs, licensing, files, sourcing, docs, skills) — status `N/A`.

---

## 1. Power Integrity (PI) — `domains/pi/`

PdN analysis: DC IR-drop, chip-PDN impedance/coupling, and decap/VRM placement optimization. Three solvers:

| Solver | Role | Exe | Batch invocation |
|---|---|---|---|
| **PowerDC** | DC IR-drop, electro-thermal, thermal | `PowerDC.exe` | `-b -tcl <script>` (the `-tcl` switch is **undocumented** in PowerDC's UG; confirmed empirically) |
| **XcitePI** | Decap / IO-model / power-integrity extraction | `XcitePI.exe` | `-b -tcl <script>` |
| **OptimizePI** | Decap/VRM placement optimization to a target impedance | `OptimizePI.exe` | `-b -export_report -tcl <script>` |

PowerTree is **not** a separate package — it's driven inside PowerDC via `sigrity::do OneStepPowerTree` (`powerdc_run_one_step_powertree`). All three are **GUI-class** (in `GUI_TOOL_NAMES`): even under `-b` they open a work window and route through the screenshot+dismiss path, so an early empty log is normal startup, not a hang.

### 1.1 PowerDC (15 tools)

| Tool | Does | Status |
|---|---|---|
| `start_powerdc_session(spd_file)` | Opens a doc + attaches the `.spd` layout | confirmed_live (mechanics) |
| `powerdc_set_simulation_mode(sid, ir_drop_analysis, e_t_co_simulation, thermal_only)` | `sigrity::set pdcSimMode` | ⚠ `-eTcoSimulation` flag **rejected** by PowerDC when tested |
| `powerdc_add_vrm(sid, power_net, ground_net, ref_des, voltage)` | `sigrity::add pdcVRM -auto -net {p,g} -ckt {R} -voltage {v}` | **BLOCKED** — see §1.5 |
| `powerdc_add_sink(sid, power_net, ground_net, ref_des, model, voltage, current, ...)` | `sigrity::add pdcSink -auto ...` | confirmed_live (not individually re-run) |
| `powerdc_add_interconnect(sid, power_net, ground_net, ref_des, resistance, ...)` | `sigrity::add pdcInter -auto -resistance {r}` | confirmed_live |
| `powerdc_mark_thermal_component(sid, ref_des)` | `sigrity::update circuit -setAsThermalComponent {1}` | confirmed_live |
| `powerdc_set_power_dissipation(sid, ref_des, watts=, power_map_file=, ...)` | `sigrity::update circuit -dissipation {...}` (exactly one of watts/map) | ⚠ emits misspelled `-outputTemmperatureMap` |
| `powerdc_set_thermal_test_board(sid, board_type, stackup, dimension, ...)` | `sigrity::update pdcTestBoard -type ...` (JEDEC tb) | confirmed_live |
| `powerdc_enable_autosave_results(sid, save_excel)` | `sigrity::update option -AutoSaveSimulationResult ...` | confirmed_live |
| `powerdc_save_workspace(sid, pdcx_file)` | `sigrity::save -w {path}` | confirmed_live |
| `powerdc_run_one_step_powertree(sid, vrm_sink_csv, extract_rules_xml, amm_library)` | `sigrity::do OneStepPowerTree ...` | confirmed_live |
| `powerdc_generate_signoff_report(sid, output_file, ...)` | `sigrity::do pdcReport -fileName {path}` (in-session) | confirmed_live |
| `powerdc_run_session(sid, spd_file=None)` | **Launches** PowerDC; appends `sigrity::begin simulation` | confirmed_live (the proven path) |
| `powerdc_export_signoff_report(case_file, report_type="all")` | **Single CLI** `-b <case> -Report -<type>`, no session | confirmed_live |

### 1.2 XcitePI (8 tools)

| Tool | Does | Status |
|---|---|---|
| `start_xcitepi_session(feature, tech_file)` | `xpi_set_feature` + `xpi_set_tech_file` | confirmed_live (IOME) |
| `xcitepi_open_layout(sid, layout_file, map_file=None)` | `xpi_open_file {layout} [{map}]` | ⚠ PME infeasible on shipped samples |
| `xcitepi_save_design(sid, xpi_file)` | `xpi_save_design` | confirmed_live |
| `xcitepi_set_spice_output(sid, output_file, style, extraction)` | `xpi_set_spice_output_path` + `xpi_set_spice_option` | confirmed_live |
| `xcitepi_generate_report(sid, output_file, scope)` | `xpi_report -{scope}` | confirmed_live |
| `xcitepi_save_iome_result(sid, result_file)` | `xpi_save_iome_result` | confirmed_live (IOME) |
| `xcitepi_run_session(sid)` | **Launches**: `xpi_start`/`xpi_close_design`/`xpi_exit` | confirmed_live (IOME); **PME blocked** |

### 1.3 OptimizePI (10 tools)

All emit `sigrity::`-Tcl; `start_optimizepi_session` selects a workflow key (`postLayout`, `preLayout`, `DeviceImpedanceChecking`, `LoopInductancesAnalysis`, `PinInductancesAnalysis`, `BestCapatitorLocationEstimation`), then `optimizepi_attach_layout`, `optimizepi_add_vrm`, `optimizepi_add_decap_candidate`, `optimizepi_add_impedance_observation`, `optimizepi_set_frequency_range`, `optimizepi_configure_optimization`, `optimizepi_generate_report`, `optimizepi_export_impedance_plot`, and finally **`optimizepi_run_session`** launches.

> **Status nuance:** `optimizepi` exe is `confirmed_live`, but **only** for the binary `-b -export_data` batch path against a saved `.opix`. The suite's own **Tcl-compose** path (`-b -tcl … -export_report`) was **never independently re-run** (no Tcl sample ships for it), so treat its exact `sigrity::` flag spellings as best-transcription.

### 1.4 PI usage example
```
sid  = start_powerdc_session("design.spd")
      powerdc_set_simulation_mode(sid, ir_drop_analysis=True)
      powerdc_add_sink(sid, "+3V3", "GND", ["U1","U2"], "Equal Current", current=1.2)
      powerdc_generate_signoff_report(sid, "out/report.html", result_table=True)
job  = powerdc_run_session(sid)
      wait_for_job(job.job_id); list_job_files(job.job_id)   # judge by artifacts,NOT state
```

### 1.5 PI failures & caveats

- **`powerdc_add_vrm` is the real, documented blocker.** Its `sigrity::add pdcVRM -auto -net {p,g}` **always** fails with `The net pair '…' is not specified.` (read from PowerDC's per-command `macro_<ts>_<pid>.log` next to the `.spd`, since `run.log` is empty here). Ruled out: real copper vs none, `+` vs plain net names, flag order vs Cadence's own `MB.tcl`, `-auto` vs `-a`. **Leading (unconfirmed) cause:** `-auto -net` resolves against **pre-defined PowerDC Net Classes** (`PowerNets`/`GroundNets`), not raw net-name strings — and the only documented base-classification action (Net Manager → Classify → As Power/Ground) is **GUI-only**. So a raw SPDIF-translated `.spd` with no Net-Class setup may *never* satisfy `-auto -net`. Do **not** read a `pdcVRM` failure as "missing copper."
- **XcitePI PME not feasible** on any shipped sample (empty `<BumpPadPorts>`, missing `.dat` DB) — the flattened batch GDS open never matches a named `.bump_pad` cell. A full 108 MB IOME GDS run takes **15–25 min** and stays `running`; do not kill it as stuck.
- **XcitePI `xpi_start` validity-check failure = indefinite CPU spin** (~25–86% a core, 65+ min, zero log growth) that only a manual kill ends. Treat it as permanently hung.
- **XcitePI `.include subckt`** resolves relative to the **job CWD**, not the tech-file dir — stage the subckt file into the job dir.
- **PowerDC `-tcl` is undocumented**; the `-b -tcl` form is convention, not in the UG. `powerdc_set_power_dissipation` emits a misspelled flag.

### PI tool count: **34**

---

## 2. Signal Integrity (SI) — `domains/si/`

| Solver | Role | Exe | Invocation |
|---|---|---|---|
| **PowerSI** | 2.5D/3D S-param, RLGC, resonance, crosstalk | `PowerSI.exe` | `-b [-ft|-fb|-fbt] -tcl <script> [layout.spd]` |
| **SPDSIM** | Legacy SPEED2000 transient field solver | `SPDSIM.exe` | `-b <file.spd>` (CLI only, **no** Tcl) |
| **BroadbandSPICE** | S-param → SPICE model fit / passivity check | `BroadbandSPICE.exe` | `-b -<mode> …` (CLI only, **no** Tcl) |

The standard flow: `start_powersi_session` (the `.brd→.spd` bridge via the built-in SPDIF translator) → `powersi_save_document` → compose mode/sweep/ports/exports → `powersi_run_session` → consume the exported `.sNp`, optionally feed into `run_broadbandspice_extraction`.

### 2.1 PowerSI (12 tools) — all `confirmed_live`

| Tool | Does |
|---|---|
| `start_powersi_session(spd_file)` | `sigrity::open document <path>` — opens **any** foreign format (`.brd`/`.mcm`/Altium/IPC-2581/ODB++/DXF) via the built-in translator |
| `powersi_save_document(sid, spd_file)` | `sigrity::save` — **mandatory** step 2; only "save immediately after open" is verified |
| `powersi_set_mode(sid, mode)` | `sigrity::update option -mode` — `extraction`/`resonance`/`spatial`/`3DFEMExtraction`/… |
| `powersi_set_frequency_sweep(sid, start, end, use_afs=True)` | `sigrity::update freq -start <hz> -end <hz>` — **client-side Hz validation** |
| `powersi_add_ports_auto(sid, ref_des, signal_ref_impedance, power_ref_impedance)` | `sigrity::add port -all …` |
| `powersi_add_edge_port(sid, name, positive_node, negative_node, width, reference_impedance)` | `sigrity::add EdgePort …` (`name` is only a cosmetic comment) |
| `powersi_add_excitation(sid, positive_net, negative_net, source_circuit, amplitude)` | `sigrity::excitation add …` |
| `powersi_export_network(sid, network_name, output_file, matrix_type, frequency)` | `sigrity::export network … -type {S\|Z\|Y}` (runs inside `run_session`) |
| `powersi_export_rlgc(sid, network_name, output_file, resistance, inductance, conductance, capacitance)` | `sigrity::export NetworkRLGC …` |
| `powersi_generate_html_report(sid)` | `sigrity::do GenReport` |
| `powersi_run_session(sid, spd_file=None, output_format="touchstone")` | **Only tool that launches**; appends `sigrity::begin simulation` |

### 2.2 SPDSIM (1 tool) — `confirmed_live`

| Tool | Does |
|---|---|
| `run_spdsim_simulation(spd_file, save_interval_steps, minimized_window, logs)` | `SPDSIM.exe -b <file.spd>` standalone; the `.spd` must be authored in the GUI-only SPDGEN (not wrapped) |

### 2.3 BroadbandSPICE (2 tools) — **UNTRACKED (no status entry)**

| Tool | Does |
|---|---|
| `run_broadbandspice_extraction(network_file, mode="Passivity", netlist_format="HSPICE", output_circuit_file, max_iterations=200, upper_frequency_ghz=125.0, ignore_threshold)` | Fits an RLC circuit model to a `.sNp`/`.bnp` (the natural downstream consumer of a PowerSI export) |
| `run_broadbandspice_check(network_file)` | Passivity/causality health-check before committing to a fit |

### 2.4 SI failures & caveats (the domain's real traps)

- **PowerSI frequency format** — the #1 gotcha: `start`/`end` must be **plain Hz** (`"1e6"`, not `"1MHz"`). A suffixed string makes PowerSI emit the misleading error `"The ending frequency should not be smaller than the starting frequency"`. `powersi_set_frequency_sweep` pre-validates to prevent this.
- **PowerSI ordering** — `powersi_run_session` throws a **pre-launch `ValueError`** if you opened a non-`.spd` and never called `powersi_save_document` (PowerSI refuses silently: rc 0, empty `Options.xml`, **no** `.sNp`). If the save line exists but is **not immediately after** the open, it only *warns* and then still fails silently. Only the exact `open`→`save` adjacency is proven.
- **PowerSI success = a file, not a code** — both success and missing-save produce rc 0 + empty log. The only reliable signal is a non-empty `*_S.<N>p` in the **workdir root** (`artifact_dir`, not `job_dir`).
- **SPDSIM misdiagnosis corrected** — `"Skip license fetch"` and `"Failed to open the file"` log lines are benign; a clean run with CWD = the `.spd`'s folder reaches 99% with real `C.CUR`/`V.CUR`/`dc.out`.
- **BroadbandSPICE location trap** — output lands **next to the input network file's own directory**, not `job_dir`; if staged from elsewhere, `list_job_files` shows nothing. Its fitting modes attach to their dash (`-Passivity`, `-i200`, `-uf125.0`, `-cf:<path>`), while Checking mode is space-separated (`-b -Checking <file>`).

### SI tool count: **15**

---

## 3. Thermal (Celsius) — `domains/thermal/`

| Solver | Role | Exe | Invocation |
|---|---|---|---|
| **Celsius3D** | 3D electro-thermal stress (displacement/strain/stress) | `Celsius3D.exe` | `-tcl <script>` |
| **CelsiusCFD** | Steady-state package CFD (`.cfd`) | `CelsiusCFD.exe` | `-tcl <script>` |
| **Celsius2D** | 2D board thermal + stress | `Celsius2D.exe` | `-b -XIMSAVE -r <file.pdcx>` (no Tcl) |

All three exes are `confirmed_live`. **None of them author a project** — the `.3dth` (3D/CFD) or `.pdcx` (2D) must already be fully built (materials, power, boundary conditions, mesh) in `CelsiusStudio.exe`'s GUI or via PowerDC's thermal features; these tools only **run** an already-built project.

| Tool (signature) | Does | Status |
|---|---|---|
| `start_celsius3d_session(project_file)` | `sigrity::configure version` + `sigrity::open file` (no launch) | confirmed_live |
| `celsius3d_run_session(sid, project_file, clean_prior_results=True)` | **Launches** `Celsius3D.exe -tcl`; results in `<stem>_SS_W` (`SR3d.dat`, `case_Result_Summary.dat/.json`) | confirmed_live |
| `start_celsiuscfd_session(project_file)` | opens a `.3dth` CFD project (no launch) | confirmed_live |
| `celsiuscfd_set_solver_cpu_percentage(sid, cpu_percentage)` | `sigrity::update CFDSolverOptions -SolverCPUPercentage {n}` | confirmed_live |
| `celsiuscfd_run_session(sid, project_file, clean_prior_results=True)` | **Launches**; results in `<stem>_EX_CFD` (`.cfd`) | confirmed_live |
| `run_celsius2d_workspace(pdcx_file, save_excel_result=True)` | `Celsius2D.exe -b -XIMSAVE -r <pdcx>` standalone | confirmed_live |

### Celsius failures
- **Celsius3D post-completion exit stall** — the solve completes (~20–30 s, real results) but the process idles forever with an undismissable Qt "Unsaved Project" window (even on a fresh first run). **Gate on `SR3d.dat` + `case_Result_Summary.dat` at real size, then kill.** Do not gate on `state=='succeeded'`.
- **Re-run-in-place hang** — re-running against a dir with a prior `<name>_SS_W/` folder hangs indefinitely (reproduced: `timeout 20` → exit 124); always use a **fresh project copy**.
- **Celsius2D** content errors surface as readable diagnostics (e.g. "invalid referenced CFD file"), not silent failures.

### Thermal tool count: **6**

---

## 4. Interconnect Extraction — `domains/extraction/`

Three classes: layout **translators** (foreign format → `.spd`), extraction **solvers** (XtractIM, Clarity3D, T2B), and **utility solvers** (abcd, bem2d3).

### 4.1 Layout translators → `.spd` (7 tools)

| Tool | Input → output | Status |
|---|---|---|
| `translate_gds_to_spd(gds_file, spd_file, map_file, tech_file, log_file)` | GDSII → `.spd` | **UNTRACKED** |
| `translate_oasis_to_spd(oasis_file, spd_file, ...)` | OASIS → `.spd` | **UNTRACKED** |
| `translate_ndd_to_spd(ndd_file, spd_file, log_file)` | NDD → `.spd` | **UNTRACKED** |
| `translate_pads_to_spd(asc_file, spd_file, log_file)` | PADS ASCII → `.spd` | **UNTRACKED** |
| `translate_rif_to_spd(rif_file, spd_file, log_file)` | RIF → `.spd` | **UNTRACKED** |
| `translate_dsn_to_spd(dsn_file, spd_file, log_file)` | Allegro `.dsn` → `.spd` | **confirmed_live** (real 723 KB `.spd`, 59 comps itemized) |
| `translate_to_spd_via_spdlinks(input_file, spd_file, format, log_file)` | broad 3rd-party formats (dbr/brd/zip/pcr/ftf/…) via `SPDLinks.exe` | **UNTRACKED** |

> All translators: passing `log_file` switches to replay mode (`-b -log <log>`) where the stored settings **silently override** explicit format/map/tech args. For `.brd`/Altium/IPC-2581/ODB++/DXF, prefer the PowerSI `start_powersi_session`→`powersi_save_document` bridge, not these.

### 4.2 Extraction solvers

**Clarity3D** (full-wave 3D FEM, `Clarity3DWorkbench.exe --NoUI -tcl <script>`) — **all UNTRACKED**. Tools: `start_clarity3d_session(design_file)`, `clarity3d_import_layout`, `clarity3d_add_net`, `clarity3d_create_lumped_port`, `clarity3d_create_wave_port`, `clarity3d_set_mesh_options`, `clarity3d_set_frequency_sweep`, `clarity3d_configure_local_resource`, `clarity3d_export_touchstone`, `clarity3d_run_session` (**10 tools**).

**XtractIM** (2.5D/3D package/PCB parasitic extraction, `confirmed_live`) — 9 tools: `run_xtractim_workspace(xml, spd_override)` (preferred `.ximx` batch mode), `start_xtractim_session`, `xtractim_select_net`, `xtractim_set_mode`, `xtractim_set_package_type`, `xtractim_set_circuits`, `xtractim_set_pg_analysis_options`, `xtractim_process_and_save`, `xtractim_run_session` (Tcl session).

**T2B** (SPICE → IBIS behavioral model, `.t2b` control file) — `run_t2b_conversion(t2b_file, check_ibis, validation_file, num_licenses, resume, skip_to_validation, wait_timeout)` — **known_blocked** (§4.4).

### 4.3 Utility solvers
| Tool | Does | Status |
|---|---|---|
| `run_touchstone_deembed(file_path, dut_touchstone_file, touchstone_file, left_touchstone_file, right_touchstone_file)` | `abcd.exe` Touchstone cascade/de-embed | confirmed_live (2-port); 4-port untested |
| `run_xhatch_field_solver(input_file, output_file, xhatch_mode, ...)` | `bem2d3.exe` 2D field solver, rigid-flex x-hatch | built_untested (`-help` only) |

### 4.4 Extraction failures
- **Clarity3D input-format gate** — accepts **only `.3dem`/`.spdb`**; any other format makes `Clarity3DWorkbench.exe` **segfault and leave the job stuck at `running` forever** (no exit code). The wrapper raises `ValueError` up front to avoid that.
- **xtractim session mode can "succeed" with nothing** — rc 0 + `succeeded` is **not** proof; read the macro log for `incomplete setup`/`stackup` and confirm RLC artifacts exist, or prefer `run_xtractim_workspace` with a `.ximx`. Results also land next to the input file, not `job_dir`.
- **T2B needs an external HSpice** (re-tested 2026-10-11) — it parsed the model and dispatched 12 real per-pin SPICE jobs, every one aborting `Spice run (TYP) aborted.` No `hspice.exe`, no `HKCR\HSpice.*` COM registration, no redirect. Genuinely blocked on the missing dependency (not a license fix).
- **abcd** — rc 0 is **never** proof (silent no-op if `-filepath` lacks a trailing separator; the tool auto-normalizes this). 4-port files untested (an earlier segfault was seen, then the inputs vanished). **bem2d3** — never run against real geometry.

### Extraction tool count: **7 + 10 + 9 + 1 + 2 = 29**

---

## 5. CAD Creation (Allegro / OrCAD) — `domains/cad/`

The largest domain (SPB 22.1). Two invocation styles: **standalone-CLI** (`submit_job`) and **SKILL/Tcl sessions** (`start_*_session` → compose → `*_run_session`). The Allegro SKILL path (`allegro.exe -s macro.scr <board>`) is the **most heavily verified mechanics in the whole suite** — net create/assign/rip-up, 18-layer stackups, dynamic copper pours, constraint sets, trace/padstack/via creation — each independently re-verified by `report.exe`/`extracta` read-back.

Modules A–C (SKILL sessions) and M/N (Capture & interchange) are the headline ones; the rest are standalone-CLI.

### 5.1 Allegro SKILL session — core (A) `allegro_tools.py`
`start_allegro_session`, `allegro_create_net`, `allegro_create_nets`, `allegro_create_component`, `allegro_create_board_outline`, `allegro_create_stackup`, `allegro_set_variable`, `allegro_run_drc`, `allegro_save_design`, **`allegro_run_session`** (the launcher).

### 5.2 Allegro geometry authoring (B) `allegro_geometry_tools.py`
`allegro_create_trace` (width **required**, layer auto-`ETCH/`, self-overlap check), `allegro_create_via`, `allegro_create_simple_padstack`, `allegro_place_module_instance` *(blocked on library-path precondition)*, `allegro_assign_net` (`ripup=True` for non-destructive rip-up), `allegro_delete_connect` *(CAUTION: NET-type is destructive — deletes the net's identity, not just etch)*, `allegro_create_copper_shape`, `allegro_create_film`, `allegro_get_module_instance_location` *(untested)*, `allegro_get_net_length` *(untested)*.

### 5.3 Constraint Manager (C) `allegro_constraint_tools.py`
`allegro_set_spacing_constraint`, `allegro_set_physical_constraint`, `allegro_create_ecset`, `allegro_get_net_constraint`.

### 5.4 Standalone-CLI CAD tools
- **Batch/report (D):** `run_allegro_report` (37 report codes), `run_allegro_dbdoctor`
- **DRC (E):** `run_allegro_batch_drc`, `run_allegro_checkplus` *(known_blocked — DE-HDL scope, no `.brd` path)*
- **Placement (F):** `run_allegro_placement`, `run_allegro_ncroute`, `run_allegro_zrouter` *(built_untested, script-replay)*
- **Manufacturing (G):** `run_ipc2581_export`, `run_ipc356_export`, `run_step_export`, `run_allegro_generate_artwork` (Gerber RS274X), `run_allegro_gerber_plot` *(built_untested)*, `run_ipc2581_import`, `run_idf_export`, `run_idx_export`, `run_idf_import` *(untested)*, `run_idx_import` *(untested)*, `run_dml_export`, `run_pdf_export`
- **Library (H):** `run_ibis_check` (one tool, `ibis_version` 3–6), `run_die_abstract_check` *(untested)*, `run_die_abstract_compare` *(untested)*, `allegro_create_symbol`
- **Extraction (I):** `run_allegro_design_extractor` *(known_blocked — needs a running connectivity server @ `localhost:9200`, not a missing input; use `allegro_extracta` instead)*, `run_allegro_extracta` (6 views), `allegro_get_board_extent_points`
- **SPECCTRA routing bridge (J):** `run_spif_export_to_specctra` (`.brd→.dsn`), `run_specctra_autoroute` (**nonzero exit 4 even on success** — 100%-connected/0-conflict proven twice), `run_allegro_specctra_import` (the **recommended** import, drives `specctra_in`), `run_specctra_import_session` (**confirmed BROKEN** — `spif_batch.exe -i` deterministic product crash SPMHDB-238; do not use)
- **Import/new-board (K):** `allegro_import_dxf` (`dxf2a`, creates a new `.brd`, **nonzero exit on success**), `allegro_export_dxf`, `allegro_new_blank_board` (copies the shipped 2-layer template)
- **Project creation (L):** `allegro_copy_project` (`copyproject`), `allegro_package_xcon_project` (`xcon2project`), `allegro_generate_sim_variant` (DRC deliberately off on the variant)
- **PSpice (P):** `run_pspice_simulation` (`psp_cmd.exe`, confirmed_live)

### 5.5 OrCAD Capture — Tcl session (M) → **known_blocked (all 12 tools)**
`start_capture_session`, `capture_select_page`, `capture_place_part`, `capture_place_wire`, `capture_place_pin`, `capture_set_property`, `capture_handle_custom_launch_dialog`, `capture_annotate`, `capture_check_design_rules`, `capture_create_netlist`, `capture_save`, `capture_run_session`.

> **The exact Capture issue:** the wrappers are internally correct (argv, absolute paths, `File::Exit`, dialog auto-dismiss, stale-lock cleanup all consistent) — the block is that **Capture's CLI has no headless "run-and-exit" mode.** The only script-replay path (`Capture.exe <script.tcl>`) replays into a **still-initializing GUI** whose first Tcl `Open <project>` step **hangs deterministically** (0-byte log, 100% CPU, zero windows — `Capture.exe -version` still works, proving the binary isn't dead). This produces three signatures: long hang, "succeeded" in ~0.1 s with an empty log, or falling back to the tutorial project. The stale-`.lck` fix is a **no-op** for this (no `.lck` is ever written). `capture_handle_custom_launch_dialog` patches only the *separate, narrower* "Capture Custom Launch" crash-recovery dialog, not the main `Open` hang. Fix = a working `syscap.exe` batch mode or a Cadence-level patch — **not** fixable in this wrapper.

### 5.6 Interchange translators (4 tools) → **work via the GUI** (not a blocked/defective class)
`run_con2xml`, `run_cap2xml`, `run_dml2con`, `run_apd2con` — **2026-10-18 (user-confirmed): these WORK via the GUI**, so they are **not a blocked/defective class** (the earlier "empty PE stub / capability gate / unsatisfied license" notes were wrong). They are GUI+CLI hybrids; the supported path is the **GUI product-chooser + "Translate" dialog** (select product, pick DSN/OLB + Design file, click Translate, verify the output) — drive it via `launch_translator_gui`. The bare **headless CLI** is a best-effort fallback only: the doc-verified switch contracts (in `doc\pdv\console_commands.html`, all switch-based + `-product pcb_librarian_expert`) stop at the `pcb_librarian_expert` checkout on this build when driven bare — a property of the headless invocation path, not the tools, and not the recommended way to run them. For a pure headless netlist→XML: `run_allegro_extracta` (confirmed live).

### 5.7 Higher-level composite tools (Q–T)
`run_schematic_checklist` (rule engine over `report.exe` net/bom CSV), `generate_schematic_from_spec` *(one-call Capture composition — **inherits known_blocked**)*, `run_placement_and_routing_assistance` (placement → SPIF export → SPECCTRA autoroute → import → post-route DRC, per-stage status), `analyze_manufacturing_package` (structural well-formedness of Gerber/IPC-2581/IPC-356 — **not** an electrical DFM check).

### 5.8 Document & audit/governance tools (U–V) — pure Python
`generate_hardware_design_document`, `generate_validation_test_plan`, `generate_board_user_guide`, `generate_traceability_matrix` (markdown deliverables); `tag_ai_design_revision`, `record_engineering_approval` (APPROVED/REJECTED/CHANGES_REQUESTED), `generate_design_change_report` (AI-revision watermarking + human sign-off gate).

### 5.9 Rigid-flex stackup & high-speed presets (R)
`generate_18layer_rigid_flex_stackup(...)` *(static definition dict + a human-readable `.scr` preview — not executable SKILL)* · `generate_multilayer_stackup(session_id, layers)` *(queues one `axlXSectionCreate` per layer, TOP-to-BOTTOM input order; a layer named `TOP`/`BOTTOM` is silently skipped as a collision — the real 18-layer authoring is `confirmed_live`)* · `get_high_speed_constraint_preset(interface_type, net_class_name)` *(DDR4/DDR5/PCIE_GEN4/GEN5/USB4/MIPI_DPHY/ETHERNET_1G/EMMC_HS400/SD_UHS1_SDR104/QSPI_NOR)*.

### 5.10 CAD failures & caveats
- **SKILL return values don't land in `run.log`** — verify by independent `report.exe`/`extracta` read-back, never by log text or `state`.
- **`allegro_run_session` ~1-in-4 flaky hang** (`returncode=-536870904` after ~137 s, banner-only log, orphaned `.lck`) — a separate, not-fully-root-caused reliability issue; retry, don't treat as a hard blocker. DismissWatcher auto-clears the resulting stale lock.
- **Nonzero-exit-on-success** — `dxf2a`, `specctra` (rc 4), `artwork` all report failure-ish codes on a real success; read the job log for the completion marker, not the code.
- **`spif_batch.exe -i` is a deterministic product crash** (`SPMHDB-238`) — use `run_allegro_specctra_import` (the `specctra_in` script-replay path, live-verified end-to-end) instead.
- **`axlDBCreateTrace`/`axlPathStart` silent no-ops** — fixed: width is now required, layer is auto-prefixed `ETCH/`; bare-layer/zero-width forms previously created nothing while still returning rc 0.
- **Capture batch** — see §5.5 (machine-level `Open` defect, not a wrapper bug).
- **Interchange translators** — see §5.6 (**work via the GUI**: product-chooser + Translate dialog, user-confirmed `launch_translator_gui` is the supported path); the bare headless CLI is a best-effort fallback that stops at the `pcb_librarian_expert` checkout on this build — these are **not** a blocked/defective/missing-feature class.

### CAD tool count: **83**

---

## 6. Platform, Skills & Job Utilities — `domains/platform/`

The "glue" every other domain relies on: FlexNet license status, install/env introspection, the cross-tool job lifecycle, AMM library generation, generic file ops, SharePoint sync, skill discovery, and a declarative pipeline orchestrator. **Pure-Python except** `generate_amm_library_from_spreadsheet` (launches `AmLibGen.exe`) and the license/env tools (launch `lmutil`/`cdsinfo`/`mpsinfo`).

### 6.1 Job lifecycle (shared by every domain) — pure Python
`get_job_status`, `wait_for_job`, `tail_job_log`, `list_job_files`, `read_job_output_file`, `cancel_job`, `list_all_jobs`, `list_sigrity_tools`, `list_allegro_tools`, `get_install_info`, `check_design_lock`.

### 6.2 Tcl session introspection — pure Python
`preview_tcl_session`, `close_tcl_session`, `restore_tcl_session` (self-heals a composed session after a server restart from its on-disk snapshot), `list_tcl_sessions`.

### 6.3 Skill discovery — pure Python
`list_skills` (call **first** each task), `load_skill` / `load_skills` (fetch the full verified playbook for one domain).

### 6.4 Sigrity X / license / environment
| Tool | Exe / how | Status |
|---|---|---|
| `generate_amm_library_from_spreadsheet(source_file, destination_library, worksheet, header_row, component_type, ...)` | `run_quick("amlibgen")` → `AmLibGen.exe` (120 s); auto-converts `.xls→.xlsx` via LibreOffice/`xlrd` if Excel COM missing | **known_blocked** — `[ERROR] Init excel failed` (broken/Missing Excel COM, **not** a license or flag error; fix = install Excel or pass native `.xlsx`) |
| `get_license_server_status(license_file)` | `lmutil lmstat -a -c <spec>` (30 s) | ⚠ **proven unreliable on this install** — informational only, never a run-gate |
| `get_license_feature_status(feature_name, license_file)` | `lmutil lmstat -f <feature>` | ⚠ same |
| `diagnose_license_feature(feature_name, license_file)` | `lmutil lmdiag -c <spec> <feature>` | untracked |
| `get_license_host_id()` | `lmutil lmhostid` | untracked |
| `check_name_server()` | `mpsinfo -c1` (15 s) | untracked |
| `get_cds_environment_info(lookup_entry)` | `cdsinfo -show` / `-lookup` (15 s) | untracked |

### 6.5 File ops, sync, orchestration — pure Python
`copy_file` (stages a read-only sample before a run), `move_file`, `delete_file` *(destructive, no undo)*, `sync_sharepoint_design_repository(site_id_or_url, remote_folder_path, local_destination_dir, graph_access_token, file_extensions)` *(Microsoft Graph via `httpx`, or a local folder-mirror if the "remote" path is a real existing folder; token from arg or `SHAREPOINT_ACCESS_TOKEN` env)*, and **`run_tool_pipeline(steps, stop_on_error=True)`** — runs a declarative list of up to 50 `{tool, args, save_as}` MCP calls in one shot, threading results between steps via `${step.field}` placeholders (with a `difflib` "did-you-mean" unknown-arg guard). It **cannot** call itself, and do **not** use it when you need to inspect intermediate results first.

### Platform tool count: **31**

---

## 7. Component Sourcing & Policy — `domains/sourcing/`

Multi-distributor lookup behind one tool, plus a pure-Python AVL/vendor-policy engine. **Data boundary:** only the bare `part_number`/`manufacturer` string leaves the machine; no design/BOM data does.

| Tool | Does | Status |
|---|---|---|
| `lookup_component_sourcing(part_number, manufacturer, vendors)` | Concurrent (`asyncio.gather`, one round-trip) stock/lead-time/price/lifecycle/datasheet across **DigiKey, Mouser, Farnell/element14, Arrow, Avnet** | pure Python; the whole module is **built_untested by design** (transcribed from each vendor's public portal docs, **zero** live access — no internet, no credentials here) |
| `evaluate_bom_sourcing_policy(bom_items, policy_config)` | In-memory rule engine: per-line AVL/lifecycle/lead-time/stock/RoHS compliance + `critical_violations` | N/A (pure Python) |
| `rank_and_filter_sourcing_candidates(part_candidates, policy_config)` | Scores/ranks alternates, returns `top_recommendation` | N/A (pure Python) |

### Sourcing caveats
- A vendor with **no credentials** returns `status: "not_configured"` **for that vendor only** — the call still queries the configured ones (graceful degradation, not a global error). A vendor's network/HTTP failure is captured as `status: "error"`, not raised. Unknown vendor names are filtered and reported in `unknown_vendors_ignored`.
- Per-vendor confidence (per the module docstring): DigiKey > Mouser > Farnell > Arrow > Avnet. Treat every endpoint path / field name / auth flow as a best-effort transcription until real credentials are configured.
- The FORJINN "vendor-preference rule engine" over the preferred list is **explicitly descoped** — this tool always queries every configured vendor.

### Sourcing tool count: **3**

---

## 8. Design Sync (Aurora) — `domains/aurora/`

Drives Sigrity Aurora's **six in-design SI/PI checks** (Impedance, Coupling, Crosstalk, ReturnPath, Reflection, IRDrop) through `allegro.exe`'s Workflow Manager `FORM` script-replay (the same mechanism as `run_allegro_zrouter`), plus standalone-solver equivalents for post-layout batch analysis.

| Tool | Does | Status |
|---|---|---|
| `get_aurora_scope_notice()` | Static scope: what's possible, supported workflow types, available modes (in-design script-replay + standalone equivalents) | N/A (pure Python) |
| `get_in_design_analysis_alternatives()` | Maps each of the 6 Aurora checks to its confirmed standalone solver (PowerSI, PowerDC, Clarity3D/XtractIM, …) | N/A (pure Python) |
| `run_aurora_workflow(board_file, workflow_type="Crosstalk", output_file)` | Composes `aurora_workflow.scr` (`setwindow pcb` → `workflow manager` → `FORM workflow …` → `axlSaveDesign` → `quit`), launches `allegro.exe -s aurora_workflow.scr <board>` as a job | exe `allegro` = confirmed_live; **Aurora's own `FORM` field names are built_untested** |

### Aurora caveats
- **Only proof a check ran is the proprietary result file** for that workflow (e.g. `.xtalkida` for Crosstalk) at real size next to the board — absence = silent no-op. Do **not** gate on `state=='succeeded'`/`returncode`.
- The `Product Choices` product-tier chooser dialog is one-time on Allegro — confirm it was answered once before relying on Aurora automation. `run_aurora_workflow` calls `clear_stale_design_lock` up front (a fresh stale lock from a prior failure can still re-create the hang).
- For **decision-critical signoff**, prefer the standalone equivalents (`get_in_design_analysis_alternatives`), which ride the already-confirmed-live solvers.

### Aurora tool count: **3**

---

## 9. Grand totals

| Domain | Tools |
|---|---|
| Power Integrity (PI) | 34 |
| Signal Integrity (SI) | 15 |
| Thermal (Celsius) | 6 |
| Interconnect Extraction | 29 |
| CAD Creation (Allegro/OrCAD) | 83 |
| Platform, Skills & Jobs | 31 |
| Component Sourcing | 3 |
| Design Sync (Aurora) | 3 |
| **Total (domain modules)** | **204** |
| Plus 3 shared helpers | 3 |
| **Total exposed by the server** | **207** |

*Verification ledger (57 tracked executables): **37** `confirmed_live` · **10** `built_untested` · **10** `known_blocked`.*
*By tool: **97** confirmed_live · **18** known_blocked · **10** built_untested · **18** untracked (gap, §10) · **54** pure-Python (N/A). These sum to 197 exe-driven tools + 10 more that drive an untracked-but-ledger-exe = 207.*

---

## 10. The coverage gap — 18 tools driving 8 untracked executables

The 57-entry ledger does not cover every executable the tools actually launch. These **8** have **no** status entry, so the **18 tools** below launch real Cadence software with **no recorded pass/fail evidence** (treat as `built_untested`-by-convention, not `confirmed_live`):

| Untracked exe | Tools (count) |
|---|---|
| `clarity3d_workbench` | 10 — all `clarity3d_*` |
| `broadbandspice` | 2 — `run_broadbandspice_extraction`, `run_broadbandspice_check` |
| `gds2spd` | 1 — `translate_gds_to_spd` |
| `oasis2spd` | 1 — `translate_oasis_to_spd` |
| `ndd2spd` | 1 — `translate_ndd_to_spd` |
| `pads2spd` | 1 — `translate_pads_to_spd` |
| `rif2spd` | 1 — `translate_rif_to_spd` |
| `spdlinks` | 1 — `translate_to_spd_via_spdlinks` |

Of the 104 registered executables, 47 have **no MCP tool at all** (GUI-only or internal dispatch workers — deliberately not wrapped).

---

## 11. Cross-cutting failure scenarios (read before trusting any tool)

1. **Stale `.lck` → silent infinite hang.** A killed job leaves `<design>.lck`; the next launch blocks forever on a "already open/override?" dialog with zero console output. **Fixed** — `clear_stale_design_lock()` runs automatically before every `allegro_run_session`/`start_capture_session`; `check_design_lock` diagnoses a stuck job. *(Proven for Allegro; a no-op for the Capture `Open` defect, §5.5.)*
2. **Allegro `allegro_run_session` ~1-in-4 flaky watchdog** — `returncode=-536870904` after ~137 s, banner-only log. Separate, not fully root-caused; retry.
3. **`specctra in` (space) permanently sticks the dispatcher** — the real command is `specctra_in` (underscore). Found, fixed, live-verified.
4. **`axlSaveDesign ?noCheck` is an invalid keyword** (real form `?mode "nocheck"`) — silently failed every save while the job still reported `succeeded`. Fixed in 3 sites.
5. **Bare layer name / zero-width `axlDBCreatePath` silently created nothing** while returning rc 0 — both fixed (width required, layer auto-`ETCH/`).
6. **"Succeeded / rc 0" is not proof of work** — PowerSI missing-save, XtractIM incomplete-setup, abcd silent no-op, Allegro no-ops, and Capture fast-exit all exit clean doing nothing. **Always verify by the real artifact.**
7. **License status is not on/off** — `lmutil lmstat` reports the FlexNet server unreachable yet most solvers fetch licenses and run. Per-tool status (the ledger), not a live `lmstat` probe, is authoritative.
8. **GUI tools can't be safely auto-probed** — a bare `allegro.exe -product help` blocked indefinitely on a product-chooser dialog; hence no automated "launch-and-see" probe exists.
9. **Celsius3D/CFD re-run-in-place** hangs — always a fresh project copy.
10. **Relative path args send translators into interactive re-prompt loops** (dxf2a/a2dxf) — all path args are resolved to absolute before launch.

---

## 12. Quick start

```powershell
# deps (editable install via uv) + tests
python -m uv sync
python -m uv run pytest -q

# stdio (Claude Code / local launcher) — the default in mcp.json
python -m uv run python main.py

# network (remote client) + Swagger UI live-testing console
python main.py --transport http --host 0.0.0.0 --port 8765 --path /mcp
# -> http://localhost:8765/docs   (Swagger UI "Try it out" for all 207 tools)
# -> http://localhost:8765/openapi.json
# -> http://localhost:8765/mcp    (the MCP endpoint)
```

**Config** (`.env.example`): `SIGRITY_HOME` (default `C:\Cadence\Sigrity2024.0`), `SIGRITY_LICENSE_MANAGER_HOME` (default `C:\Cadence\LicenseManager`), `SIGRITY_LICENSE_FILE` (default `5280@localhost`), `SIGRITY_WORKDIR` (default `runs/`), `SIGRITY_CADENCE_SPB_HOME`.

**Every task should start:** `list_skills()` → `load_skill('sigrity')` → `load_skill('<domain>')` → then that domain's tools. **Every `run_*`/`*_run_session` ends with:** `wait_for_job` → `list_job_files`/`tail_job_log` → verify the **artifact**, not the state.
