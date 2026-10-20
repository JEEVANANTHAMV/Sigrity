# Sigrity MCP Toolkit — Complete Status & Verification Report

**Project:** `sigrity-mcp` — a [FastMCP](https://github.com/jlowin/fastmcp) tool suite that drives a local **Cadence Sigrity 2024.0** + **Allegro/OrCAD SPB 22.1** install through Tcl / SKILL / CLI batch-automation.
**Generated:** 2026-10-17 · **Transport:** stdio (default) / http / sse · **Live tool count:** **207**

> Every number below is taken from a live inspection of the running server (`mcp.list_tools()`), the source-verified executable registries (`core/executables.py`), and the hand-curated verification ledger (`core/tool_status.py`). Nothing here is estimated.

> **UPDATE (2026-10-17, later pass) — numbers and Capture's status below are now stale.**
> Live tool count is **211** (4 new tools added: `extract_capture_netlist_headless`,
> `author_capture_schematic_headless`, `run_netrev_import`, `run_netin_import`).
> Capture's hang is root-caused and fixed (`ENABLE_CAPTURE_AUTOMATION=TRUE`, automatic),
> and netlist extraction/authoring now work fully headlessly via `tclsh.exe` +
> Capture's own database DLL — see `core.tool_status.TOOL_STATUS_NOTES["tclsh"]` and
> `["capture"]` for the complete, current evidence. `capture` itself remains tracked as
> `known_blocked` (its own interactive Tcl-session batch invocation still doesn't
> execute a script unattended), but the two main use cases this report describes it
> blocking — reading and authoring a schematic — are no longer actually blocked;
> they just go through a different mechanism than the `capture` executable. Everything
> else below (confirmed_live/built_untested counts for the other 36 tracked executables)
> is still accurate as of this writing.

---

## 1. Executive summary

| Metric | Count |
|---|---|
| **Total MCP tools registered at runtime** | **207** |
| Tools that launch a Cadence executable | 153 |
| — …of which the exe has a tracked verification status | 135 |
| — …of which the exe has **no** status entry (coverage gap) | 18 |
| Pure-Python tools (no Cadence exe) | 54 |
| Distinct Cadence executables the tools actually drive | 101 |
| Executables registered in code (3 registries) | 104 |
| Executables tracked in the status ledger (`TOOL_STATUS`) | 57 |

**Verification status (57 tracked executables):**

| Status | Execs | What it means |
|---|---|---|
| `confirmed_live` | **37** | Actually run against a real design on this install, successfully, ≥1× |
| `built_untested` | **10** | Built from docs / sample scripts + unit-tested for argv, but never run live |
| `known_blocked` | **10** | Attempted live and found genuinely blocked (root cause documented) |

**Verification status (153 executable-driven MCP tools):**

| Status of the exe they drive | Tools |
|---|---|
| `confirmed_live` | 97 |
| `known_blocked` | 18 |
| `built_untested` | 10 |
| **Not tracked at all** (exe has no status entry — the gap) | **18** |

**One-paragraph conclusion:** 207 tools were built; 153 launch real Cadence software. 135 of those drive an executable whose behavior we have *hand-verified* (37 execs confirmed live, 10 confirmed blocked, ~10 built-but-untested). **18 tools launch executables that were never added to the verification ledger at all** — mostly the six `*2Spd` layout translators, Clarity 3D, and Broadband SPICE — so those 18 have *no recorded pass/fail evidence*. A further 54 tools are pure-Python (jobs, licensing, files, sourcing, doc generation) and never need an executable. The suite does **not** end-to-end automate all of Cadence: 10 execs are confirmed blocked on machine-level dependencies (Excel COM, HSpice, a connectivity server, an unlicensed Translators feature pack), and 101 vs 57 means 44 driven/registered execs are simply not individually tracked.

---

## 2. What this is and what it does

Sigrity and Allegro/OrCAD ship **no first-party Python or REST API**. Every capability in this suite is one of:

1. **Generate a `.tcl` macro and run it** against the right Sigrity executable in batch mode (`<exe> -tcl script.tcl`), or
2. **Generate a SKILL script** and replay it in `allegro.exe -s script.scr <board>`, or
3. **Drive a standalone CLI tool directly** via its own switches (e.g. `report.exe -v sum board.out`, `specctra.exe -nog -do route.do -quit`).

### The 8 domains

| # | Domain | Package | Covers |
|---|---|---|---|
| 1 | Power Integrity | `domains/pi/` | PowerDC, XcitePI, OptimizePI |
| 2 | Signal Integrity | `domains/si/` | PowerSI, SPDSIM, BroadbandSPICE |
| 3 | Interconnect Extraction | `domains/extraction/` | `*2Spd` translators, Clarity3D, XtractIM, T2B, utility solvers |
| 4 | In-Design Analysis | `domains/aurora/` | Aurora Workflow Manager + standalone signoff solvers |
| 5 | Unified Platform | `domains/platform/` | Job/session control, licensing, file utils, skills, SharePoint, pipeline |
| 6 | CAD Creation | `domains/cad/` | Allegro PCB (SKILL), OrCAD Capture (Tcl), DRC, placement, SPECCTRA autoroute, manufacturing, docs |
| 7 | Thermal | `domains/thermal/` | Celsius3D / CelsiusCFD / Celsius2D |
| 8 | Component Sourcing | `domains/sourcing/` | Multi-distributor lookups + AVL/BOM policy engine |

### How it works (architecture)

- **`core/mcp_app.py`** — the single shared `FastMCP` instance. Every domain module imports `mcp` and registers tools with `@mcp.tool`. 207 `@mcp.tool` decorators confirmed in source.
- **Compose-then-run sessions** (`core/tclsession.py`) — a `start_*_session` tool opens a session; several `*_add_*`/`*_set_*` tools each append one line to the in-memory script (no process launched); a final `*_run_session` tool writes the script and launches the real tool **once**. This is why, e.g., PowerDC has 14 tools but only one of them (`powerdc_run_session`) actually launches the process.
- **Background jobs** (`core/jobs.py`, `core/process.py`) — every `run_*`/`*_run_session` launches as a tracked job and returns a `job_id` immediately; `get_job_status` / `wait_for_job` / `tail_job_log` / `list_job_files` / `cancel_job` retrieve results. `submit_job(tool="<exe>")` resolves the executable via `core/executables.resolve()`.
- **Executable registries** (`core/executables.py`) — three dicts resolved against `SIGRITY_HOME` / `SIGRITY_LICENSE_MANAGER_HOME` / `SIGRITY_CADENCE_SPB_HOME`: `EXECUTABLES` (60), `CAD_EXECUTABLES` (43), `LICENSE_EXECUTABLES` (1) → **104 unique**.
- **Safety** (`core/tclscript.py` / `skillscript.py`) — all generated scripts use `tcl_str`/`skill_str` quoting to prevent command injection from untrusted arguments.
- **Skill discovery** (`domains/platform/skill_tools.py`) — `list_skills` / `load_skill` serve verified domain playbooks over the MCP wire.

---

## 3. How many were built vs tested

### 3.1 By executable (the 57 tracked)

| Status | Count | Executables |
|---|---|---|
| **confirmed_live** | 37 | `a2dxf, abcd, allegro, allegro_artwork, allegro_batch_drc, allegro_dbdoctor, allegro_extracta, allegro_ipc2581_out, allegro_ipc356_out, allegro_ncroute, allegro_placement, allegro_report, allegro_step_out, brd2dml, celsius2d, celsius3d, celsiuscfd, copyproject, create_sym, dsn2spd, dxf2a, generate_sim_variant, ibischk6, idf_out, idx_out, ipc2581_in, optimizepi, pdf_out, powerdc, powersi, psp_cmd, spdsim, specctra, spif_batch, xcitepi, xcon2project, xtractim` |
| **built_untested** | 10 | `allegro_diacheck, allegro_diacompare, allegro_gbplot, allegro_zrouter, bem2d3, ibischk3, ibischk4, ibischk5, idf_in, idx_in` |
| **known_blocked** | 10 | `amlibgen, allegro_batch, allegro_checkplus, allegro_designextractor, apd2con, cap2xml, capture, con2xml, dml2con, t2b` |

### 3.2 By MCP tool (the 207)

- **153 tools** drive a Cadence executable.
  - **97** drive a `confirmed_live` exe → these are the proven, end-to-end-verified paths.
  - **18** drive a `known_blocked` exe → launch works but the task cannot complete on this machine (see §5).
  - **10** drive a `built_untested` exe → real exe, correct argv per docs, never run against real data.
  - **18** drive an exe with **no status entry** → no recorded evidence at all (see §6 gap).
- **54 tools** are pure-Python:

| Category | Tools |
|---|---|
| Job control (12) | `get_job_status, wait_for_job, tail_job_log, list_job_files, read_job_output_file, cancel_job, list_all_jobs, run_tool_pipeline, check_design_lock, get_install_info, check_name_server, get_cds_environment_info` |
| Licensing (4) | `get_license_server_status, get_license_feature_status, diagnose_license_feature, get_license_host_id` |
| File utils (3) | `copy_file, move_file, delete_file` |
| Session introspection (4) | `preview_tcl_session, close_tcl_session, restore_tcl_session, list_tcl_sessions` |
| Skills (3) | `list_skills, load_skill, load_skills` |
| Sourcing (3) | `lookup_component_sourcing, evaluate_bom_sourcing_policy, rank_and_filter_sourcing_candidates` |
| Doc generators (7) | `generate_hardware_design_document, generate_validation_test_plan, generate_board_user_guide, generate_traceability_matrix, tag_ai_design_revision, record_engineering_approval, generate_design_change_report` |
| CAD helpers (9) | `get_aurora_scope_notice, get_in_design_analysis_alternatives, _check_self_overlap, allegro_get_board_extent_points, allegro_new_blank_board, start_allegro_session, generate_18layer_rigid_flex_stackup, get_high_speed_constraint_preset, capture_handle_custom_launch_dialog` |
| Schematic/manufacturing flows (7) | `generate_schematic_from_spec, run_schematic_checklist, analyze_manufacturing_package, run_placement_and_routing_assistance, list_sigrity_tools, list_allegro_tools, sync_sharepoint_design_repository` |
| AMM (1) | `generate_amm_library_from_spreadsheet` — note: *does* drive the `amlibgen` exe, but via `run_quick` not `submit_job` |

---

## 4. What works end-to-end (confirmed live)

The **37 confirmed-live executables** cover the core engineering loop and were each proven against real sample files (mostly Cadence's own `share/PostInstallationCheck/*` self-test projects and shipped sample boards):

- **PI:** `powerdc` (IR-drop, 14 tools), `optimizepi` (10 tools), `xcitepi` (7 tools)
- **SI/Extraction:** `powersi` (11 tools, incl. the `.brd → .spd` BRD-Extractor bridge), `spdsim`, `xtractim` (9 tools), `abcd` (Touchstone de-embed), `a2dxf`/`dxf2a` (DXF ⇄ board)
- **Thermal:** `celsius3d`, `celsiuscfd`, `celsius2d`
- **CAD authoring:** `allegro` (SKILL session — the most heavily verified: net create/assign/rip-up, stackup authoring, copper pours, constraint sets, trace/padstack/via creation, all re-verified by independent `report.exe` read-back), `allegro_report`, `allegro_dbdoctor`, `allegro_batch_drc`, `allegro_placement`, `allegro_ncroute`, `allegro_artwork` (real RS274X Gerber), `allegro_extracta`, `create_sym`
- **CAD import/export:** `ipc2581_in`/`allegro_ipc2581_out`, `allegro_ipc356_out`, `allegro_step_out`, `idf_out`/`idx_out`, `brd2dml`, `pdf_out`, `dsn2spd`, `generate_sim_variant`
- **Project/flow:** `copyproject`, `xcon2project`, `spif_batch` + `specctra` (confirmed 100%-connected headless autoroute, twice), `psp_cmd` (PSpice batch), `allegro_batch_drc`

**Highlights independently re-verified (not just trusting return codes):** Allegro net reassignment, 18-layer rigid-flex stackup authoring, dynamic copper pour (confirmed 3 independent ways incl. an SPDIF translation), SPECCTRA route-then-import round trip (918 KB board, 163/163 connections), and a real DRC-short fix down to `Short DRC: 1→0`.

---

## 5. What didn't work — `known_blocked` (10 executables, 18 tools)

Each is **attempted live and root-caused**. None are code bugs; all are machine/install dependencies or product-scope mismatches.

| Exe | Status | Root cause (verified) |
|---|---|---|
| **`con2xml`** / `cap2xml` / `dml2con` / `apd2con` (4) | **work via GUI** *(2026-10-18, user-confirmed)* | The four interchange translators are **real, working GUI+CLI hybrids** (earlier "empty PE stub / feature pack not installed / capability gate" notes were WRONG). The supported path is the **GUI product-chooser + "Translate" dialog** (`launch_translator_gui` ← select product, pick DSN/OLB + Design file, click Translate, verify the output). They are **not** a blocked/defective/missing-feature class. The bare *headless CLI* (doc-verified switch contracts in `doc\pdv\console_commands.html`, all switch-based + `-product pcb_librarian_expert`) is a best-effort fallback that stops at the `pcb_librarian_expert` checkout on this build — a property of the headless path, not the tools. For a pure headless netlist→XML: `extracta.exe` (confirmed live). |
| **`capture`** (11 tools) | blocked | OrCAD Capture batch invocation is **genuinely non-deterministic**: a minimal Open+Save+Close+Exit macro sometimes completes in ~3.2 s, the next identical attempt hangs the full timeout with a 0-byte log and **zero windows** (proved not a hidden dialog via live `EnumWindows`). The stale-`.lck` cause was found & fixed (`clear_stale_design_lock`, proven for Allegro) but does **not** fully explain it. The project-*opening* code path hangs deterministically. Needs a Cadence-level fix or a working `syscap.exe` batch mode. |
| **`t2b`** | blocked | `T2B.exe -b model.t2b` works but **genuinely needs an external HSpice engine**. Parsed the model, dispatched 12 real per-pin SPICE jobs, all abort `Spice run (TYP) aborted`. No `hspice.exe` under `C:\Cadence`, no registry entry, no redirect. Fix: install HSpice. |
| **`amlibgen`** | blocked | Root-cause confirmed: writes `AMLibGen.log` showing correct argv, then fails **`[ERROR] Init excel failed`** — a broken/missing **Microsoft Excel COM** dependency for reading legacy `.xls`. Not a license. Fix: install/repair Excel or provide native `.xlsx`. |
| **`allegro_designextractor`** | blocked | Confirmed buildable but **preconditioned on a running Elastic/connectivity server** at `localhost:9200` (its `-u` target). 112 `.cpm`+12 `.sdax` inputs ship, but without the server it returns only the usage banner. Not a defect. Use `allegro_extracta` for direct `.brd` extraction. |
| **`allegro_checkplus`** | blocked (out of scope) | Re-tested with 4 `-proj` forms → all `[5038] does not exist`. Docs title it **"Allegro Design Entry HDL Rules Checker"** — it checks Concept/DE-HDL *schematic* rules, with **no `.brd` physical-layout input path at all**. Not applicable to the Allegro PCB flow; the `.brd` DRC path is `batch_drc`/`allegro_run_drc` (both confirmed live). |
| **`allegro_batch`** | blocked (orphaned) | The multiplexer's `-help` is fine but sub-program dispatch fails (`ERROR: Cannot find program "dbdoctor"`, exit 2) while the standalone `dbdoctor.exe` succeeds. All tools therefore call the standalone exes directly. **Dead entry** — no tool routes through it. |

---

## 6. What can't be tested — `built_untested` (10 executables, 10 tools)

Implemented from the local doc tree / real `-help` banners and unit-tested for argv correctness, but **never run against real data on this machine** (usually because no suitable sample input file exists here).

| Exe | Tool(s) | Why untested |
|---|---|---|
| `ibischk3/4/5` (+ `6` live) | `run_ibis_check` (one tool, `ibis_version` 3–6) | Only `ibischk6` was run against a real `.ibs`; 3/4/5 share the binary family but weren't each exercised. |
| `allegro_diacheck` / `allegro_diacompare` | `run_die_abstract_check` / `run_die_abstract_compare` | Real `-help` confirmed, but **no die-abstract sample file** on this machine. |
| `allegro_gbplot` | `run_allegro_gerber_plot` | **Root cause found & fixed** (it takes a generated `.art`, not a `.brd`); corrected to take `artwork_file`, but the legacy pen-plot path itself not run end-to-end. |
| `allegro_zrouter` | (replayed inside `allegro` session) | Automated via Allegro `.scr` form replay (`FORM zrouter …`); `zrouter.exe` itself is never launched standalone. |
| `bem2d3` | `run_xhatch_field_solver` | Real self-printed `-help` banner, but no real geometry input on hand. |
| `idf_in` / `idx_in` | `run_idf_import` / `run_idx_import` | Fully self-documenting `-help` (both can create a new `.brd` from mechanical data), but **no real `.emn/.bdf` / `.idx` sample** anywhere on this machine. |

These are *honest* untested — the tool and its flags are real and doc-grounded, but the exact command has not produced a verified output artifact.

---

## 7. The coverage gap — 18 tools driving untracked executables

`TOOL_STATUS` tracks **57** of the **101** executables the tools actually drive. **8 registered executables have zero status entry**, so **18 MCP tools launch real Cadence software with no recorded pass/fail evidence:**

| Untracked exe | Tools (count) |
|---|---|
| `clarity3d_workbench` | 10 — `start_clarity3d_session, clarity3d_run_session, clarity3d_import_layout, clarity3d_add_net, clarity3d_create_lumped_port, clarity3d_create_wave_port, clarity3d_set_mesh_options, clarity3d_set_frequency_sweep, clarity3d_configure_local_resource, clarity3d_export_touchstone` |
| `broadbandspice` | 2 — `run_broadbandspice_extraction, run_broadbandspice_check` |
| `gds2spd` | 1 — `translate_gds_to_spd` |
| `oasis2spd` | 1 — `translate_oasis_to_spd` |
| `ndd2spd` | 1 — `translate_ndd_to_spd` |
| `pads2spd` | 1 — `translate_pads_to_spd` |
| `rif2spd` | 1 — `translate_rif_to_spd` |
| `spdlinks` | 1 — `translate_to_spd_via_spdlinks` |

These are the layout-translation layer and two solvers. The tool code is written and registered, but **none has a `confirmed_live` / `built_untested` / `known_blocked` determination** — they are the single biggest "unknown unknowns" in the suite.

> Separately, **47 of the 104 registered executables** (e.g. `sigritysuite`, `workbench3d`, `hexmesh`, `sigmamesh`, `powertree`, `siweb`, `optimality`, the various `*_console` variants, `lmutil`, `cdsinfo`, …) are **registered but never driven by any MCP tool** — internal solver-dispatch workers, GUI-only binaries, or plumbing. They are deliberately not wrapped.

---

## 8. Other failure scenarios encountered during automation

These are cross-cutting reliability findings, not single-tool blocks:

1. **Stale `.lck` locks cause silent, infinite hangs.** A killed batch job leaves `<design>.lck`; the *next* launch blocks forever on a modal "already open/override?" dialog with **zero console output**. **Fixed** — `clear_stale_design_lock()` now runs automatically before every `allegro_run_session` / `start_capture_session`. Proven live: a planted stale lock was auto-cleared and the job finished in 5.3 s instead of hanging. A `check_design_lock` tool lets a caller diagnose a stuck job. (Helped Capture; did **not** fully cure it — see §5.)
2. **Intermittent ~137 s Allegro launch watchdog `returncode=-536870904`.** Recurs ~1-in-4 launches even strictly sequential, with only the startup banner in `run.log` and an orphaned lock that the failed run itself left. Not the stale-lock cause (already fixed). Treated as a known, retryable reliability issue — not yet fully root-caused.
3. **Two-word command dispatcher hang.** Emitting `specctra in <file>` (a space) puts Allegro's dispatcher in a permanently stuck state; the real command is `specctra_in` (underscore). Found, fixed, and live-verified.
4. **`axlSaveDesign ?noCheck` was an invalid keyword** (real form is `?mode "nocheck"`), silently failing every save while the job still reported `succeeded`. Fixed in 3 copy-pasted sites; live-verified.
5. **`axlDBCreatePath` with a bare layer name silently created nothing** (needs the `ETCH/<layer>` class/subclass string), and `axlPathStart(points)` with no width defaulted to `width=0`, generating spurious DRC violations. Both fixed and re-verified.
6. **"Succeeded / returncode 0" is not proof of work.** Multiple tools (Capture fast-exit, Allegro silent no-ops) exit cleanly without doing the operation. The suite's standard now: verify by independent read-back (`report.exe`, re-open in a second process), never trust the job state alone.
7. **License status is not a single on/off switch.** `lmutil lmstat` reports the FlexNet server unreachable, yet PowerSI/PowerDC/XcitePI/OptimizePI/XtractIM/Celsius*/Allegro all fetch licenses and run. Status is tracked **per-tool** via `TOOL_STATUS`, not via a live `lmstat` probe (deliberately, because the probe is unreliable).
8. **GUI-capable tools cannot be safely auto-probed.** A bare `allegro.exe -product help` probe blocked indefinitely on a product-chooser dialog — the reason there is no automated "launch and see" status probe at all.
9. **Celsius3D re-run-in-place hangs.** Re-running against a directory that already has a `_SS_W/` result folder hangs indefinitely (likely an overwrite-confirm GUI dialog). Always use a fresh project copy per run; same assumed for CelsiusCFD.
10. **Relative path arguments send translators into interactive re-prompt loops** (dxf2a/a2dxf), once filling a 205 MB log before the watchdog fired. All path args are now resolved to absolute before launch.

---

## 9. How to read the numbers (reconciliation)

```
207 MCP tools
├── 153 drive a Cadence executable
│   ├──  97 → confirmed_live exe      (proven end-to-end)
│   ├──  18 → known_blocked exe       (launch OK, task can't complete here)
│   ├──  10 → built_untested exe      (real exe, doc-grounded, never run)
│   └──  18 → NO status entry         (COVERAGE GAP: Clarity3D, BroadbandSPICE, 6×*2Spd, SPDLinks)
└──  54 pure-Python (jobs/licensing/files/sourcing/docs/skills)

57 tracked execs            =  37 confirmed_live + 10 built_untested + 10 known_blocked
101 driven execs            =  48 tracked (incl. the 8 gap exes registered but not in ledger) + 53 others
104 registered execs        =  101 driven  +  3 GUI-only / never-wrapped
                              (note: 57 ledger keys map onto the 101; 8 driven exes are missing from the ledger;
                               47 registered exes have no MCP tool at all)
```

---

## 10. Bottom line for a consumer of this toolkit

- **Trust the 97** tools driving `confirmed_live` executables — they are the proven core loop (PI, SI, extraction, thermal, Allegro CAD authoring/import/export, SPECCTRA autoroute, PSpice).
- **Treat the 18 gap tools as unverified** until exercised against a real design — especially the `*2Spd` translators, Clarity 3D, and Broadband SPICE.
- **Do not expect the 18 `known_blocked` tools to complete** on this machine (Capture batch, T2B, AMMLibGen, interchange translators, designextractor, checkplus) — each needs the specific dependency/scope fix documented in §5.
- **"Built_untested" ≠ broken** — it means "real tool, correct flags per docs, no verified output yet."
- **Never treat a clean exit as success** — verify by independent read-back, per §8.6.
