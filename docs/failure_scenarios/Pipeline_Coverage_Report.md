# Sigrity MCP — Design-to-Production Automation Coverage Report

Authoritative coverage assessment for the question: *Can this MCP automate the COMPLETE
PCB automation flow (design → analysis → production) at the accuracy of a 25-year senior
designer, and where exactly does it fall short?* All claims below are grounded in
`docs/failure_scenarios/SCENARIOS.md` (the consolidated 110-scenario manifest),
`.forjinn/skills/sigrity/SKILL.md` (verified-live playbooks), `README.md` (live-validation
evidence + known gaps), and the actual tool source in `sigrity_mcp/domains/*/`. Status
labels use the manifest's vocabulary: `confirmed_live`, `built_untested`, `known_blocked`,
`gui_only_no_batch`, plus `unreliable_intermittent` / `precondition_error` / `silent_noop`
/ `crash` where the underlying scenario category matters.

## Executive Summary

From the point a CAD-native design exists (an Allegro `.brd`, DXF outline, or IPC-2581
file) through PI/SI/thermal/multiphysics signoff to every manufacturing output, roughly
90% of the flow is genuinely automatable — the SPECCTRA autoroute bridge (100% routed,
0 conflicts, on two real designs), batch DRC, Gerber/IPC-2581/IPC-356/STEP/PDF/IDF/DML/IBIS
export, PowerDC IR-drop, PowerSI S-parameter extraction with passivity checking, XtractIM,
Celsius 3D/CFD/2D solves, auto-placement, Z-Router fanout, and Constraint Manager setup are
all `confirmed_live` or have verified workarounds, and 12/12 multi-model end-to-end eval
tasks reached a correct, honestly-verified final answer. The flow is **not** fully
automatable end-to-end, for six specific, documented reasons: (1) schematic authoring from
scratch — OrCAD Capture batch is `known_blocked` (non-deterministic Open hang, re-proven
after the licensing fix), so requirement→schematic needs a pre-existing template project
plus manual content; (2) the SPECCTRA routed session cannot be re-imported into the `.brd`
(`spif_batch -i` crashes, SPMHDB-238), so the post-route DRC stage can only honestly
check pre-routing placement state; (3) several analysis tools fail from missing third-party
dependencies on this machine — T2B IBIS-from-SPICE needs HSpice, AmLibGen needs Excel COM;
(4) the interchange translators (con2xml/cap2xml/dml2con/apd2con) are license-gated with no
product license selected; (5) component sourcing has zero live access; and (6) a suite-wide
"the state is a liar" reliability layer (job `state` both over- and under-reports real
progress) that is survivable with documented per-tool artifact-check workarounds but which a
senior designer would not sign off as "accurate" without human verification of every
`state:"succeeded"`. The honest bottom line: **this suite automates the analysis and
production backend of a PCB project at production grade, and the mechanical front-end
(board creation from DXF/IPC-2581, placement, fanout, autoroute, constraints, DRC) at high
but not signoff grade; the schematic front-end and the route-reimport step are the two hard
gaps, and no amount of re-sequencing around `run_tool_pipeline` closes them — they require
either a real Cadence-side fix, a license grant, or a human at the GUI.**

## The Complete PCB Automation Pipeline

| # | Stage | Tool(s) | Automation status | Failing scenarios (manifest #) | Verified workaround? |
|---|-------|---------|-------------------|-------------------------------|---------------------|
| 1 | Requirement → Schematic Project Creation | `allegro_copy_project` (`copyproject.exe`), `allegro_package_xcon_project` (`xcon2project.exe`); the from-nothing leads `syscap.exe`/`dsxmltoschematic.exe` are documented but NOT wrapped | `allegro_copy_project` **confirmed_live** (fresh CPM + full project tree + "SUCCESS(COPYPROJ-67)"); `allegro_package_xcon_project` confirmed_live; true from-scratch creation = **known_blocked** (syscap headless mode unconfirmed) | 54 (`.cpm` not auto-appended), 55 (`-refproj` required despite brackets), 56 (interchange license-gated — affects .xcon→project path), 57 (syscap batch unconfirmed) | YES for copy/xcon (include `.cpm`; always pass `-refproj`; use BRD-bridge instead of license-gated translators); NO for true new-from-zero |
| 2 | Schematic Authoring (components, wires, pins, netlist) | `capture_*` suite (`start_capture_session`…`capture_run_session`), `generate_schematic_from_spec` (one-call composer of place-part/wire/pin/annotate/netlist/save); `allegro_create_symbol` for library symbols | **known_blocked** — Capture batch Open hangs (100% CPU / empty log, then suspicious 0.1s "succeeded" with no real work); `generate_schematic_from_spec` inherits the block verbatim. Symbol authoring: `allegro_create_symbol` **confirmed_live** (real 2.9MB `.psm`, dbdoctor-verified) | 47 (Open hang, unreliable_intermittent), 48 (crash-recovery dialog — fixed via auto-dismiss), 49 (silent_noop "succeeded"), 50 (spec generator inherits block), 53 (checklist heuristics unverified) | NO in-suite for real Capture batch; the only path that works is a pre-existing project via stage 1. `auto_dismiss_recovery_dialog_if_stuck` is verified but does not fix the Open hang |
| 3 | Schematic Verification (ERC / design rules / checklist) | `capture_check_design_rules` (ERC matrix), `run_schematic_checklist` (heuristics over `report.exe` net/BOM CSV), `run_allegro_checkplus` (DE-HDL rules checker) | `run_schematic_checklist`: **built_untested** for heuristic precision (parsing is live + unit-tested against real CSV); `capture_check_design_rules`: **built_untested** (Capture batch blocked); `run_allegro_checkplus`: **known_blocked / likely inapplicable** (it's a Design Entry HDL checker, not a `.brd` checker) | 53 (heuristic precision unverified), 44 (checkplus scope mismatch — DE-HDL, not `.brd`) | Y for the checklist's *parsing* (real fixtures); N for heuristic precision; N for a real `.brd`-applicable DRC-style rules check |
| 4 | PSpice Batch Simulation | `run_pspice_simulation` (`psp_cmd.exe`); `pspice.exe`/`pspiceaa.exe` are correctly unwrapped (GUI-only) | **confirmed_live** — headless, real diagnostics, ran a shipped sample; failed only on the sample's own missing `.include` path (board-file precondition, not a tool problem) | 51 (GUI entrypoints hang — gui_only_no_batch), 52 (absolute-path `.include` portability — precondition) | YES (use `psp_cmd.exe`; write a self-contained `.cir` with no external `.include`) |
| 5 | PCB Board Creation | `allegro_import_dxf` (`dxf2a.exe`), `allegro_new_blank_board` (filesystem copy of `2layer.brd` template), `run_ipc2581_import` (`ipc2581_in.exe`), `run_idf_import`/`run_idx_import` (`idf_in.exe`/`idx_in.exe` — import direction can create a new `.brd` per their own `-help`) | DXF: **confirmed_live** (real 203KB `.brd`, re-verified by `report.exe`); blank board: **confirmed_live** (plain copy, no Cadence process); IPC-2581: **confirmed_live** export-import round-trip tool exists, but `-x -g` (with layer/stackup) import fails — partial import; IDF/IDX import: **built_untested** (no sample on machine) | 30 (dxf2a rc 1 on success), 31 (attached flag syntax rejected — use space-separated), 32 (conductor-class partial-layer mapping — silent gap, NO workaround), 33 (relative path → 200MB prompt loop — fixed by abs path resolution), 37 (IPC-2581 `-x -g` "Layer stackup import failed" — NO workaround), 38 (IDF/IDX import untested) | YES for dxf2a quirks (read "dxf2a complete." from log; space-separated flags; absolute paths), blank board, and basic `ipc2581_in`; **NO** for importing with full layer stackup (`-x -g`) or anything IDF/IDX import |
| 6 | Stackup Definition (multi-layer / rigid-flex) | `allegro_create_stackup`, `generate_multilayer_stackup`, `generate_18layer_rigid_flex_stackup` (session tools, SKILL-built) | **built_untested** (signatures verified against local SKILL docs; not each exercised live) with four documented landmines | 14 ("bottom" inverts layer order — queue top-to-bottom), 15 (TOP/BOTTOM name collision → silent no-op — drop outer names), 16 (no SKILL API for explicit reference plane — **known_blocked**, order layers by adjacency instead), 17 (PLANE layer has zero copper by default — `allegro_create_copper_shape` fills it) | YES for 14/15/17 (all documented + in-code); **NO** for 16 (genuine product limitation) |
| 7 | Component Placement (auto-placement) | `run_allegro_placement` (`placement.exe` — the real Allegro auto-place engine) | **confirmed_live** — ran the genuine algorithm against the sample board (real weight/rotation log); failed only on that board's missing "Package Keepin" — a board-authoring precondition, not a wrapper bug | 27 ("No Package Keepin was found" — precondition), 28 (`axlDBCreateModuleInstance`→nil — **known_blocked**, board/library-path precondition, NO workaround), 18 (copper-shape board-autoderive disproven — `allegro_get_board_extent_points` + explicit points instead) | YES for 27 (define Keepin in the board first) and 20–22 (see stage 14 helpers); **NO** for 28 as long as `axlGetParam("library:<footprint>")` returns nil on the board |
| 8 | Constraint Setup (spacing / physical / electrical) | `allegro_set_spacing_constraint` (`axlCNSSetSpacing`), `allegro_set_physical_constraint` (`axlCNSSetPhysical`), `allegro_create_ecset` (`axlCNSEcsetCreate`), `allegro_get_net_constraint` (`axlCnsNetFlattened`), `get_high_speed_constraint_preset` (DDR4/5, PCIe Gen4/5, USB4, MIPI, 1000BASE-T presets) | `allegro_set_spacing_constraint`/`allegro_set_physical_constraint`: **confirmed_live** (3 independent live runs, direct + 2 LLM-driven). `allegro_create_ecset`: **built_untested**. Constraint sets are real (~60 documented `axlCNS*` functions) | no dedicated constraint scenarios in the manifest other than the stackup adjacency workaround (#16) and the CSV/XML import non-surface (no scripted import — SKILL-only) | YES for spacing/physical (confirmed); partial for electrical sets (real API, unexercised; no import surface for pre-made rule files) |
| 9 | Fanout (Z-Router) | `run_allegro_zrouter` — Allegro batch script (`.scr`) FORM replay: open `zrouter` dialog, set Connections Control File, grid spacing, execute, save | **confirmed via FORM-replay workaround** — the tool itself is GUI-driven (`zrouter` opens a dialog; only FORM replay makes it headless); Connections Control File grammar documented in `allegro_placement_tools.py` | 29 (zrouter: 3 dead ends — standalone and native command; only FORM replay works) | YES (FORM script replay — that is exactly what `run_allegro_zrouter` is) |
| 10 | Autorouting (SPECCTRA) | `run_spif_export_to_specctra` (`spif_batch.exe -o` → `.dsn`), `run_specctra_autoroute` (`specctra.exe -nog -do <script>.do -quit`), one-call `run_placement_and_routing_assistance` | **confirmed_live** — 100% connected, 0 conflicts, twice: Cadence's shipped tutorial design and this suite's own 75-net/163-connection sample board, both through the real MCP wrapper; produces a real `.ses` session. `specctra.exe` returns rc 4 even on full success — the pipeline deliberately does NOT gate on exit code | 8 (`specctra in` two-word typo → forever hang — one-word fix), 12 (rc 4 on success — read `final.sts`), 23 (multi-branch ripup+re-route hangs — use single-branch nets) | YES for export+route (read `route.sts`/`final.sts`; never trust rc); **NO** for the import half (see stage 11) |
| 11 | Route Import (session → `.brd`) | `run_allegro_specctra_import` (Allegro-native `specctra in <session.ses>` via batch-script replay), `run_specctra_import_session` (`spif_batch -i`) | Mixed/genuinely broken: `run_specctra_import_session` (**spif_batch -i**) is **confirmed broken** (`ERROR(SPMHDB-238): The design is corrupted` + access violation + zombie process, every time); `run_allegro_specctra_import` is the in-code workaround path (native `specctra in`, `?mode "nocheck"`, `FORM spif_in CLOSE`) but the underlying product-side import defect is not isolated, so re-import of routed geometry is **not dependably achieved** | 11 (`spif_batch -i` crash), 9 (spif_in form not closed → silent no-op — `FORM spif_in CLOSE`), 10 (`axlSaveDesign ?noCheck` silent save fail — `?mode "nocheck"`), 7 (report reading stale board mid-save — wait for terminal + mtime) | The `?mode "nocheck"` + `FORM CLOSE` + `final.sts`-read fixes are all verified for their own symptoms; but the SPMHDB-238 import failure has **no verified in-suite workaround** — `run_placement_and_routing_assistance` still attempts the import and, when it fails, its final DRC carries an explicit `caveat` that it checked the **pre-routing** board |
| 12 | DRC (batch DRC) | `run_allegro_batch_drc` (`batch_drc.exe -nographic`), `allegro_run_drc` (session, `axlDRCUpdate`) | **confirmed_live** — "Batch DRC checking done." on the real sample board. Known quirk: the launcher can exit while `job.json` still says `running` | 13 (batch_drc launcher exits early — state lies; read `batch_drc.log`), 21 (0-width trace → DRC violation — width is now a required arg), 40 (sim-variant design has DRC deliberately disabled — use `report.exe` re-read) | YES (read `batch_drc.log`; `batch_mode=True`; don't DRC a `generate_sim_variant` output as if it were the real board) |
| 13 | Routing Quality Analysis (per-net length, short detection) | `allegro_get_net_length` (session, per-net copper length), `run_allegro_gerber_report`-style `tail`/`read_job_output_file` on DRC reports, `analyze_manufacturing_package` (structural completeness only — explicitly NOT electrical DFM) | **built_untested** as a dedicated quality gate: `allegro_get_net_length` is signature-verified but not exercised live as a signoff gate; there is no wrapped per-net length/timing/short-detection report beyond batch DRC counts | no direct scenario (closest: 23, 24 routing re-work; 70 "Poor" rating ≠ physics fail for BBS) | N (no verified per-net quality gate; DRC count + `report.exe` + `extracta` text is the best available) |
| 14 | Manual Rip-up-and-Re-fix | `allegro_delete_connect` (ripped via `allegro_assign_net` net reassignment — the verified safe ripup path), `allegro_create_trace` (`axlDBCreatePath`, **confirmed_live**), `allegro_create_via` (**confirmed_live** via `allegro_create_ecset`/constraint context), `allegro_create_simple_padstack` (**confirmed_live**), `allegro_place_module_instance` (correctly implemented, precondition-limited) | Mixed: trace/via/`axlAssignNet`/`axlSaveDesign` mechanics all **confirmed_live** (real dbids returned, `R1.2` net reassignment persisted to disk, independently re-read by `report.exe`). `allegro_place_module_instance` hit a real board-content precondition (footprint not resolvable via `axlGetParam`) | 19 (`axlDeleteObject` on a NET kills logical identity — use `allegro_assign_net` ripup), 20 (bare layer name → silent nil — auto `ETCH/<layer>`), 21 (0-width trace silent), 22 (self-overlapping path → silent nil — pre-flight geometry check), 23 (multi-branch ripup+re-route hang — **NO** workaround, use single-branch nets), 24 (dense-area manual re-route spawns new spacing violations — **known_blocked**, no workaround, iterate + re-check or prefer autorouter), 28 (module-instance nil) | YES for safe ripup (net reassignment), trace/via/padstack creation (all confirmed), width/layer-name/path fixes; **NO** for multi-branch net re-route and dense-area re-route quality |
| 15 | PowerDC IR-Drop Analysis | PowerDC session tools (`start_powerdc_session`…`powerdc_run_session`, `powerdc_generate_signoff_report`) | **confirmed_live** (real license + real `.spd`/`.pdcx` sample, full run) | 58 (`pdcVRM -auto -net` → "net pair not specified" — **known_blocked**, GUI-only Net Class, 4 command variations ruled out, NO workaround) | YES for the general IR flow (real sample run + signoff report); **NO** for automatic VRM net-pair specification — that step still needs the GUI Net Class |
| 16 | XcitePI Chip Package Parasitic | XcitePI session tools (`start_xcitepi_session`…`xcitepi_run_session`) | **confirmed_live** (real `.gds`+`.map`+`.tcl` sample run) | 59 (`xpi_start` validity-check fail → infinite CPU spin — **known_blocked** but with a verified workaround: reuse the IOME macro + kill on validity failure), 60 (Subckt staged in a different dir → 0 placements — co-locate all inputs) | YES (both documented, in-code: kill-on-spin, co-located inputs) |
| 17 | OptimizePI Decap Optimization | OptimizePI session tools (`start_optimizepi_session`…`optimizepi_run_session`) | **confirmed_live** for the session/run mechanics | 61 (no simulation trigger → rc 0 with **no** WhatIf artifact — **known_blocked**, GUI-only trigger, NO verified in-suite workaround) | **NO** — a headless OptimizePI run can complete "successfully" (rc 0) while producing no decap optimization artifact at all; the artifact check is the only guard |
| 18 | PowerSI S-Parameter Extraction | PowerSI session tools (**the confirmed CAD→analysis bridge**: `start_powersi_session` accepts a real `.brd` directly via built-in BRDExtractor; `powersi_save_document` is required immediately after — confirmed live, real 237KB `.spd`, reached "begin simulation") | **confirmed_live** | 64 (0-byte `run.log`; artifacts land in `runs/` not the job dir — glob `runs/` for non-empty `.sNp`), 65 (no `save_document` → empty `Options.xml` only — always call it line 2), 66 (frequency "1MHz" parsing error — plain Hz `"1e6"`), 67 (license-flag useless / lmstat unreliable — judge by artifact only), 78 (IPC-2581 → SPDIF still parsing at 90s — **built_untested**; DXF + Altium confirmed) | YES (4 of 5 fully documented + in-code: artifact-glob, save_document-first, plain-Hz, judge-by-artifact); IPC-2581 import unconfirmed (still parsing, not stalled) |
| 19 | BroadbandSPICE Netlist Fit + Passivity Check | `run_broadbandspice_extraction`, `run_broadbandspice_check` | **confirmed_live** (real sample S4P run) | 69 (BBS writes results to CWD, not job dir — check `BBSResult_<basename>/`), 70 ("Poor" overall rating ≠ physics failure — read the Passivity/Causality rows, not the headline) | YES (both documented) |
| 20 | Clarity3D 3D EM | Clarity3D session tools (`start_clarity3d_session`…`clarity3d_run_session`) | **known_blocked for real inputs** — the Tcl run mechanics are real, but no `.3dem` input exists on this machine and a `.spd` input **crashes**; `start_clarity3d_session`/run flow is otherwise documented against the `43micro.spd` sample shape | 75 (no `.3dem` on machine; `.spd` → segfault — **NO** in-suite workaround) | NO for Clarity3D as a working 3D-EM extractor on this install; the practical fallback for return-path 3D parasitics is the documented XtractIM/PowerSI path |
| 21 | XtractIM RLC Extraction | `run_xtractim_workspace`, `start_xtractim_session` + `xtractim_*` add/set tools | **confirmed_live** (real `.ximx` sample) | 76 (session-mode "incomplete setup" — use `run_xtractim_workspace` instead), 77 (artifacts write next to the `.ximx`, not into the job dir — check the `.ximx` dir) | YES (both documented) |
| 22 | T2B IBIS Model | `run_t2b_conversion` | **known_blocked** — T2B itself launches, parses the model, and dispatches real per-pin SPICE jobs; every one aborts because no HSpice install exists (the Cadence license fetch succeeds — this is a missing third-party dependency, not a Sigrity issue) | 63 (T2B needs HSpice — **known_blocked**, **NO** in-suite workaround short of installing HSpice) | NO |
| 23 | Celsius3D Electrothermal/Stress | `start_celsius3d_session` + `celsius3d_run_session` | **confirmed_live** — real displacement/strain/stress values written to `case_Result_Summary.dat`/`.json`, exit 0. Two real, documented re-run hazards | 80 (re-run into a directory that already has a result folder → infinite hang — **fresh project copy per run**, verified), 81 (post-solve process idles forever and never exits — poll for artifacts, then kill the PID by hand) | YES for both (fresh-copy-per-run is in-code; artifact-poll-then-kill is documented — the kill step is manual PID) |
| 24 | CelsiusCFD Thermal | `start_celsiuscfd_session` + `celsiuscfd_run_session` | **confirmed_live** for a first run ("CelsiusECSolver is completed", real `.cfd` file); re-run risk treated as equivalent to Celsius3D's | 82 (re-run-in-place hang risk — **built_untested** but pre-emptively guarded with fresh-copy + `_clear_prior_celsius_results` in code) | YES (fresh copy per run, same pattern as Celsius3D's verified fix) |
| 25 | Celsius2D Thermal | `run_celsius2d_workspace` (single CLI tool: `Celsius2D.exe -b -XIMSAVE -r <workspace>.pdcx`) | **confirmed_live** — "Simulation succeed", full thermal+stress engine log | 83 (chip.pdcx → "invalid CFD reference domain" — use the working `demo_sim.pdcx` sample) | YES (use a known-good `.pdcx`) |
| 26 | Aurora In-Design Analysis | `run_aurora_workflow` (Allegro Workflow Manager, all 6 checks: impedance/coupling/crosstalk/return-path/reflection/IR-drop, via `.scr` FORM replay), `get_in_design_analysis_alternatives` (maps each check to a standalone solver) | **built_untested** — the standalone equivalents are all separately confirmed live (PowerDC/Powersi/Celsius3D/XtractIM), but the Aurora FORM-replay path itself has never been verified end-to-end | 85 (Aurora FORM replay reliability unverified — **built_untested**) | N for the FORM replay itself; Y in the sense that every single Aurora check has a confirmed-live standalone alternative this suite already runs |
| 27 | Gerber / RS274X Export | `allegro_create_film` (`axlFilmCreate`) → `run_allegro_generate_artwork` (`artwork.exe`); optional `run_allegro_gerber_plot` (`gbplot.exe`, `.art`→legacy `.plt`/`.ctl`) | **confirmed_live** — 3 live runs including the exact production chain (`allegro_create_film` → `allegro_save_design` → `run_session` → `run_allegro_generate_artwork`), producing genuine `TOP.art`/`BOTTOM.art` with real `G04 File Format: Gerber RS274X` records | 35 (no film records → `artwork.exe` emits nothing — call `allegro_create_film` first), 34 (`artwork.exe` rc 1 on success — read `.art` + `photoplot.log`), 36 (`gbplot.exe` on a `.brd` → wrong-input-type error — pass the `.art`), 43 (`stream_out`/GDSII needs predefined film records — `built_untested`, precondition pattern known, not yet run live) | YES (all four — film-first, rc-ignoring via log/artifact check, `.art`-not-`.brd` for gbplot; `stream_out` itself is a separate untested step, not a blocker for this RS274X path) |
| 28 | IPC-2581 Export | `run_ipc2581_export` (`ipc2581_out.exe`) | **confirmed_live** ("a2ipc2581 complete.") | none specific to export (import-side issues are scenario #37, stage 5) | N/A |
| 29 | IPC-356 Export | `run_ipc356_export` (`ipc356_out.exe`) | **confirmed_live** ("Successfully generated file") | none | N/A |
| 30 | STEP / 3D Export | `run_step_export` (`step_out.exe`) | **confirmed_live** ("step_out complete.") | none | N/A |
| 31 | PDF Export | `run_pdf_export` (`pdf_out.exe`) | **confirmed_live** (verified real `%PDF-1.7` bytes) | none | N/A |
| 32 | Mechanical Exchange (IDF/IDX) | `run_idf_export`/`run_idx_export` (`idf_out.exe`/`idx_out.exe`); `run_idf_import`/`run_idx_import` (`idf_in.exe`/`idx_in.exe`) | Export: **confirmed_live** (both run bare against a real board, zero preconditions). Import: **built_untested** (real, self-documenting `-help` banners including the ability to create a new `.brd`; no `.emn`/`.bdf`/`.idx` sample on this machine) | 38 (IDF/IDX import never live-tested — no sample) | N for export; no verified live run for import |
| 33 | DML Export | `run_dml_export` (`brd2dml.exe`) | **confirmed_live** | 56 (the *import*-direction equivalent `dml2con` is license-gated — but `brd2dml` export itself is unaffected) | N/A |
| 34 | DXF Export | `allegro_export_dxf` (`a2dxf.exe`) | **confirmed_live** (real valid 6.4KB DXF, `SECTION`/`HEADER`/`$ACADVER`/`ENTITIES`/`EOF` verified) | 30/31/33 (the dxf2a import-side quirks also inform a2dxf path handling — absolute paths, space-separated flags, rc-1-on-success) | YES |
| 35 | IBIS Model Validation | `run_ibis_check` (`ibischk3`/`4`/`5`/`6.exe`) | `ibischk6`: **confirmed_live** (real syntax errors/warnings actually found in a shipped `.ibs` — the checker doing its job). `ibischk3`/`4`/`5`: **built_untested** | 39 (only v6 confirmed), 46 (`dbdoctor`-style rc-1-on-clean-check pattern applies to the checkers' exit-code interpretation in general) | YES for v6 (read the log, not the rc); v3/4/5 need a live run before they can be trusted for older IBIS revisions |
| 36 | Component Sourcing | `lookup_component_sourcing` (DigiKey/Mouser/Farnell/Arrow/Avnet concurrent), `evaluate_bom_sourcing_policy`, `rank_and_filter_sourcing_candidates` | **built_untested — weakest-verified tool in the entire suite**: built purely from vendors' public developer-portal docs, **zero** live access (this machine has no internet and no API credentials); DigiKey/Mouser/Farnell endpoint shapes are reasonably documented, Arrow/Avnet explicitly lower-confidence in-code | 103 (zero live access), 104 (Arrow/Avnet lower-confidence endpoints) | **NO** — a unconfigured vendor returns `not_configured` rather than failing, but nothing here has ever produced a real quote, stock count, or lead time on this machine |
| 37 | Documentation Generation (HDD, test plan, traceability) | `generate_hardware_design_document`, `generate_validation_test_plan`, `generate_board_user_guide`, `generate_traceability_matrix`; `tag_ai_design_revision`/`record_engineering_approval`/`generate_design_change_report` (audit trail) | **built_untested** — generation logic is real and structured, but these are document-composition tools never exercised against a real shipped design in a live run (the eval suite exercised CAD/PI/manufacturing/thermal tasks, not document generation) | none specific — no scenario in the manifest targets these tools | N (not yet exercised; no evidence either way beyond code review) |
| 38 | Manufacturing Package Analysis | `analyze_manufacturing_package` | **confirmed** (unit-tested against real `G04 File Format: Gerber RS274X` / `<IPC-2581 xmlns="...">` / `IPC-D-356 Output File from Allegro` signatures from real files this suite itself produced) — explicitly a **structural completeness/well-formedness gate only, not an electrical DFM check** (no batch/SKILL DFM surface exists; `dfa_dlg.exe` remains GUI-only) | none (it's a verified gate, not a failing tool) | N/A — this IS the workaround for "is the production output package complete/valid" questions |

**Suite-wide reliability layer (affects every stage above, not one row):**

| Concern | Manifest # | Workaround | Verified |
|---|---|---|---|
| MCP client 30s round-trip cap masks real job state | 92 | Poll `get_job_status`; do NOT resubmit | YES |
| `cancel_job` cannot kill detached workers | 93 | Manual PID check + `clear_stale_design_lock` | YES (partially — the kill itself is manual) |
| Stall watchdog kills genuine-but-idle finishers | 94 | Verify artifacts before treating `stall_timeout_killed` as a real failure | YES |
| Runaway watchdog kills on >200MB log | 95 | Guard; inspect for prompt-loop pattern (dxf2a relative-path class, scenario 33) | YES (as a guard, not a cure) |
| The whole "nonzero rc / rc 0 / state-running" family | 96 + 12, 30, 34, 46 | Tool-specific completion evidence (`final.sts` / `batch_drc.log` / `.art` / "0 errors detected" text) | YES, documented per-tool |
| Sessions are in-memory, lost on server restart | 86 | Chain the whole flow inside one `run_tool_pipeline` lifetime — where `wait_for_job` also resolves | YES |
| Stale session id returns an `error` *payload*, not a raised error | 87 | Inspect `result['error']` per step before trusting a `succeeded` pipeline step | YES |
| Job state `running`/`succeeded` both lie independently | 88, 89 | Artifact check in/near the input file's directory — never job `state` alone | YES (as discipline; no code change) |
| `wait_for_job` is session-local; "not tracking" on a restarted server | 91 | `get_job_status` polling; don't resubmit | YES |
| Pipeline `${...}` double-substitution, raised-step shape, argument-name traps, 50-step cap | 97, 98, 99, 100 | Whole-placeholder refs (never inline-in-a-string), read then `error` then `result` per step, argument names only from SKILL.md, split >50 steps into sequential calls | YES (all documented, in-code where applicable) |
| Negative return code + no log text = ambiguous license vs. other abort | 110 | Per-tool log/artifact inspection; no single generic fix exists | **NO** (judgment-based, per-tool) |
| `lmstat`/FlexNet server is unreachable yet most tools still work fine | 108 | Treat license status strictly per-tool/per-feature, never as one on/off switch — the "no license" reading would have wrongly written off PowerSI/PowerDC/XcitePI/OptimizePI/XtractIM/Dsn2Spd/Celsius3D/CelsiusCFD/Celsius2D and all the new CAD batch tools | YES (as documented discipline; the `license_issue_suspected` flag itself is known unreliable, scenario 67) |

## Automation Gaps That Block Full End-to-End

Ordered as encountered in a real project:

1. **Schematic authoring, from scratch or near-scratch (stages 1–3).** OrCAD Capture's batch
   `Open` is `known_blocked`: the same macro that finished cleanly in 3.2s on one run hung
   the full wait with a 0-byte log on the next identical retry, and two re-test runs after
   the stale-lock fix "succeeded" in 0.1s with completely empty logs — too fast for real
   work. `generate_schematic_from_spec` composes this correctly but inherits the block
   verbatim; there is no verified in-suite workaround. **A blank-project schematic cannot be
   authored by this suite today.** Mitigation that IS verified: `allegro_copy_project`
   produces a complete, real, freshly-timestamped project from a template headlessly — so
   the suite can *instantiate* a project, and a human (or a pre-saved template that already
   contains the intended content) must supply the actual component/wire/pin content. ERC
   (`capture_check_design_rules`) and the schematic rule checklist are consequently the least
   trustworthy verification stage: `run_schematic_checklist`'s parsing is real but its five
   heuristics' precision is unverified, and `run_allegro_checkplus` turned out to be a
   Design-Entry-HDL checker, not a `.brd` checker at all.

2. **SPECCTRA routed-session re-import (stage 11).** `spif_batch.exe -i` crashes with
   `ERROR(SPMHDB-238): The design is corrupted` plus an access violation and a zombie
   process, on every attempt. `run_allegro_specctra_import` (the native `specctra in`
   replay, `?mode "nocheck"`, `FORM spif_in CLOSE`) is the in-code path, and the
   two verified fixes for the related no-op/silent-fail symptoms (scenarios 8, 9, 10) are
   real — but the underlying corruption crash is a product-side defect with no isolated root
   cause and no verified in-suite fix. `run_placement_and_routing_assistance` handles this
   honestly: it still attempts the import, and when it fails its final DRC pass carries an
   explicit `caveat` stating it checked the **pre-routing** board, not the new routing.
   **Net effect: the suite can place, fan out, and generate a fully routed SPECCTRA session —
   it cannot dependably bring that routing back into a `.brd`** for downstream DRC or
   manufacturing output on this installation.

3. **Stackup reference-plane assignment (stage 6).** No SKILL API exists to set an explicit
   reference plane — `known_blocked`, no workaround; the only documented mitigation is
   ordering layers by physical adjacency, which is a design-choice nudge, not an equivalent.

4. **T2B IBIS-from-SPICE (stage 22).** T2B itself works — it launches, parses the model,
   and dispatches real per-pin SPICE characterization jobs — but every job aborts because
   this machine has no HSpice install. The Cadence license fetch succeeds; this is purely a
   missing third-party dependency. `known_blocked`, no in-suite workaround.

5. **OptimizePI decap-optimization trigger (stage 17).** A headless OptimizePI run returns
   rc 0 and **none of the WhatIf/optimization artifacts** when no simulation trigger fires —
   and the trigger is GUI-only today. `known_blocked`, no verified in-suite workaround; the
   only guard is artifact-presence checking, which correctly flags the failure but doesn't
   produce the result.

6. **PowerDC automated VRM net-pair specification (stage 15).** `pdcVRM -auto -net` fails
   with "net pair not specified"; four command variations were tried and ruled out; the
   Net Class step is GUI-only. `known_blocked`, no in-suite workaround — the general IR
   flow works fine with a pre-assigned net class, but auto-deriving it is not reproducible
   headlessly.

7. **Interchange translators (stage 1, and any `.xcon`/DML→Concept-HDL bridge).**
   `con2xml`/`cap2xml`/`dml2con`/`apd2con` all fail immediately with "No Product License
   selected… Translation cancelled" — a genuine license grant is what's missing, not a code
   fix. The verified workarounds are `copyproject`/`xcon2project` (both `confirmed_live`)
   and, for layout data flowing into Sigrity analysis, the PowerSI BRD-bridge (also
   `confirmed_live`) — so the *project* and *layout* directions of interchange are covered;
   the Concept-HDL/DML⇄XML directions are the gap.

8. **Clarity3D 3D-EM as a working extractor on this machine (stage 20).** No `.3dem` input
   file exists on this machine, and a `.spd` input segfaults the solver — `known_blocked`,
   no in-suite workaround. The documented fallback for return-path 3D parasitics is the
   XtractIM/PowerSI path, both `confirmed_live`.

9. **AmLibGen AMM-library generation (a platform-domain tool, not one of the 38 stages, but
   relevant to a production signoff flow).** `[ERROR] Init excel failed` — a broken/missing
   Microsoft Excel COM dependency for reading legacy `.xls`, not a license issue. A native
   `.xlsx` source "might sidestep this if AmLibGen supports one — untested." `known_blocked`
   with an untested possible mitigation.

10. **Component sourcing (stage 36).** Zero live access — no internet, no vendor API
    credentials on this machine. `not_configured` is returned instead of a failure for each
    unconfigured vendor, which is honest, but the entire stage has never produced a real
    result. `built_untested`, no workaround short of credentials + network.

11. **IDF/IDX import (stage 5/32), IBIS check v3/4/5 (stage 35), Aurora FORM replay
    (stage 26), `bem2d3` x-hatch solver, `stream_out` GDSII export, `convert_gerber`/
    `Eagle2Cp` import (GUI-only, `known_blocked` with the documented import workaround being
    `ipc2581_in` or the PowerSI SPDIF path), and the document-generation tools (stage 37):
    all real, but none have ever been run against a real file on this
    machine, so every one of them is a latent, unproven stage until first exercised.

12. **Suite-wide: unreliable job `state` reporting (all stages).** `succeeded`+rc0 ≠ work
    happened (PowerSI missing its trigger; `abcd` no-ops; OptimizePI missing its artifact)
    AND `running` ≠ stuck (`batch_drc` launcher exits early; Celsius3D idles after a real
    solve). This is fully survivable — every instance has a documented, mostly-verified
    artifact-inspection workaround (see the reliability table above) — but it means **no
    stage in this suite is safe to sign off on `state` alone**. A human (or a strict
    artifact-checking outer loop) must confirm the real output before any stage counts as
    done. This is the single most important "accuracy of a 25-year senior designer"
    qualifier in this report: the suite is instrumented for *detection* of silent failure
    better than most test harnesses are, but it does not eliminate the need to verify.

## What a 25-Year Senior Designer Would Flag

**Acceptable risk — retry, or verify-then-accept, not a showstopper:**

- **Allegro/Capture launch flakiness (scenarios 1–6, 47).** The `.lck` orphan → modal
  "override?" dialog has a verified fix (`clear_stale_design_lock`, proven live: planted
  fake lock, job completed in 5.3s instead of hanging). The remaining 137s-watchdog rc and
  "minutes-long hang with zero dialogs" cases are intermittent, partially understood, and
  treated operationally as "watchdog at ~30s + `check_design_lock` + one retry, and if it
  recurs twice, don't keep polling — escalate." Any production EDA install has
  occasionally-flaky license-seat/launch behavior; a retry-with-verification policy is a
  normal, acceptable engineering control. A 25-year veteran would write this into the
  runbook and move on.
- **Every "nonzero exit code on actual success" quirk (scenarios 12, 30, 34, 46, 96 —
  `specctra` rc 4, `dxf2a` rc 1, `artwork` rc 1, `dbdoctor` rc 1).** A veteran has spent
  decades writing "trust the log, not the exit code" wrappers around tools that lie about
  their own success. The suite already does exactly this, per-tool, with the specific
  completion string documented in each case. This is a *solved* problem here, not a
  residual risk.
- **`state:"running"`/`state:"succeeded"` lying in both directions (scenarios 88, 89, 13).**
  Veteran treatment: treat any `state` as a *hint*, never a verdict; the artifact is the
  verdict. The suite's own "three inviolable rules" playbook codifies exactly this, with
  per-tool artifact locations documented (PowerSI in `runs/`, XtractIM next to the `.ximx`,
  Celsius next to the input project, PowerDC next to the `.pdcx`). A senior designer would
  accept this *as long as* the verify-artifact step is mandatory and automated, which the
  playbook makes explicit. The residual risk is purely one of discipline: if a caller
  (human or LLM) reads `state:"succeeded"` and stops looking, the suite's own
  `caveat`/`note` fields are the only thing standing in their way — the suite is designed
  for a careful operator, not a careless one.
- **Intermittent Capture "succeeded"-but-empty-log (scenario 49).** A suspicious 0.1s
  "success" with a 0-byte log is a well-known class of EDA-tool lie; the documented
  discipline — check the log/file content, never trust returncode — is exactly what a
  veteran applies to every EDA tool they use.

**Genuine showstoppers — things a senior designer would reject a "fully automated" claim
over:**

- **No verified headless path to originate a real schematic's content (stage 2).** You can
  instantiate a project headlessly from a template, and you can author PCB geometry
  headlessly — but the schematic content itself, the actual electrical design, either came
  from a template someone already hand-built, or requires a human at Capture. For a
  "blank design to production" claim, this is the single hardest "no": a schematic is
  where the design intent lives, and it is the one stage this suite cannot originate.
- **The routed result never reliably gets back into the `.brd` (stage 11).** Autorouting
  works, and works well (100%, 0 conflicts, twice) — but if the routing can't be
  re-imported, then the post-route DRC you run is checking the *placement-only* board, the
  Gerber/IPC-2581/STEP you export is exporting a board that is **not actually routed
  according to its own new routing**, and every downstream signoff (and the factory
  itself) is operating on pre-routing geometry. No amount of "90% of stages work" rescues
  this: **a manufacturing output that doesn't contain the routing this suite just did is
  a manufacturing output that's wrong**, full stop.
- **Signoff-grade analysis tools that can silently do nothing (stage 17 OptimizePI artifact,
  stage 15 PowerDC auto net-pair, and by extension the general "rc 0, no output" class).**
  A senior designer signs off IR-drop / decap optimization on *an artifact with real
  numbers in it*, never on "the tool exited 0." The suite's artifact-check discipline
  catches these as failures rather than false successes (the multi-model eval explicitly
  praised the models for refusing to claim success without a real result), but the
  underlying capability — producing the artifact headlessly — is still missing for those
  specific steps. A veteran would not put a "100% automated signoff" stamp on a flow whose
  signoff artifacts can only be produced with the GUI open.
- **Third-party dependency gaps on this specific machine (HSpice for T2B, Excel COM for
  AmLibGen).** A senior designer wouldn't call these "the MCP is broken" — they're "this
  machine isn't a complete factory environment" — but they *do* block "complete flow on
  this machine" claims, and they'd be flagged loudly as "we cannot claim T2B/IBIS-from-SPICE
  or spreadsheet-driven AMM-library generation works here, at all, until HSpice/Excel is
  present."
- **Zero-liveness stages presented alongside confirmed-live ones (sourcing, document
  generation, Clifford-stage `built_untested` exports/imports).** A veteran is specifically
  wary of a status board that looks all-green because "implemented" is indistinguishable
  from "proven." The manifest's discipline about this (every `built_untested` tool was
  still built against a real local install with a real `-help`/doc page, sourcing is
  explicitly called out as worst-in-suite) is exactly the right mitigation — but the
  claim "this automates the complete flow" has to be read as "this automates every stage
  that has a confirmed or live-verified execution path," and sourcing/documentation/
  Clifford-stage imports have never crossed that line.

**The honest verdict a veteran would give:** "You could hand me this on a fully-provisioned
machine (HSpice, Excel, a real IPC-2581 with stackup, a working license for the interchange
tools) and a human at the Capture and PowerDC-Net-Class and OptimizePI-trigger steps, and
I'd let it run most of a real project unattended — the PI/SI/thermal/multiphysics backend
and the placement/fanout/autoroute/DRC/manufacturing machinery is the real deal, verified
on real boards, with unusually good failure-detection discipline. I would NOT let it claim
to be 'the complete flow from a blank sheet of paper' while the schematic content, the
routed-result re-import, and the signoff-artifact triggers are still where a human has to
be."

## Recommended Next Steps (prioritized)

Ordered by how much "fully automatable" each one moves, not by ease:

1. **Fix or work around SPECCTRA session re-import (SPMHDB-238), or build the equivalent
   route-application path from verified primitives.** This is the single highest-leverage
   fix: every downstream stage (DRC, Gerber, IPC-2581, STEP, the factory) currently
   operates on pre-routing geometry whenever import fails. Options, in order of preference:
   (a) root-cause the `spif_batch -i` corruption on this install / test a Cadence patch;
   (b) build a re-import via the already-`confirmed_live` SKILL primitives (`axlDBCreatePath`
   / `axlCreateVia` / `axlAssignNet` — all individually verified to write real dbids that
   persist to disk, per scenarios 19–22's fixes) that reads the SPECCTRA `.ses`/`.dsn` route
   solution and re-creates the geometry in the `.brd` directly, bypassing the broken
   product-side import entirely. Until this is done, **no manufacturing output from this
   suite should be treated as "containing the routing it just did."**
2. **Root-cause OrCAD Capture's batch-invocation non-determinism** (verified not to be a
   licensing or stale-lock issue). One clean 3.2s run followed by a full-timeout hang with
   an empty log, plus two 0.1s empty-log "successes," on the identical macro and project
   copy, is a real unreproducible-but-repeatable defect in what is *the* gate to schematic
   authoring. Until fixed, every claim about "requirement → schematic" automation is capped
   at "instantiate project from template + human authors content."
3. **Implement the simulation trigger for headless OptimizePI** (extend `run_session` to
   fire the same trigger the GUI uses), so a headless run actually produces the WhatIf
   decap-optimization artifact instead of exiting 0 silently. Same shape of fix, lower
   stakes than #1/#2 (a PI nicety, not a manufacturing-output correctness issue), but it
   closes a real "silent success with no artifact" hole in the signoff flow.
4. **Add PowerDC's Net Class / VRM net-pair auto-derivation as a real batch surface** (or
   document, with test evidence, the exact pre-assignment sequence that makes the existing
   `pdcVRM -auto -net` variant work) — four variations have already been ruled out, so this
   needs a targeted investigation, not another "try a flag" pass.
5. **Provision and re-verify the third-party-dependent tools: HSpice (T2B) and Excel COM
   (AmLibGen).** Both are unambiguously "tool works, dependency missing" — the fix is
   an environment action plus a live re-run, not a code change. Cheap relative to their
   pipeline position (IBIS-from-SPICE is a gate for signal-integrity signoff on any design
   with real I/Os).
6. **Live-test the `built_untested` Clifford-stage items against real sample files** —
   specifically IDF/IDX import (the export direction is already confirmed; import has never
   been exercised), IPC-2581 *full* import with `-x -g` (layer/stackup — the one documented
   partial-import failure), IBIS check v3/4/5 (v6 is confirmed; three older spec
   generations are not), and the Aurora FORM-replay path (`run_aurora_workflow`) end-to-end.
   None require new code — every one is "find or make a real input file, run it, read the
   real output." This converts a whole set of "real and self-documenting but never
   proven" stages into confirmed or definitively-blocked ones, which is exactly the
   distinction a senior designer insists on.
7. **Get real credentials + a network path for component sourcing and run one real
   multi-vendor lookup end-to-end.** The Arrow/Avnet endpoints are explicitly lower
   confidence even in the code; a single real run would collapse the entire stage from
   "documented but zero live evidence" to either confirmed or concretely-broken-with-a-name
   on the specific vendor that failed.
8. **Execute the document-generation tools (`generate_hardware_design_document`,
   validation/bring-up test plan, board user guide, traceability matrix) against a real,
   already-analyzed board from an actual completed run in this suite, and diff the
   generated documents against what an engineer would expect.** These are the deliverables
   a 25-year senior designer would scrutinize most closely in a "did the automation
   actually produce usable documentation" audit, and they have zero live-run evidence
   today.
9. **Add a mandatory, code-enforced artifact-check step to `run_tool_pipeline`** (or a
   thin wrapper around it): after each step that claims `succeeded`, automatically verify
   the documented real artifact exists and is non-empty before letting the next step
   proceed — rather than leaving that discipline to the caller reading `note`/`caveat`
   fields. The suite already knows, per tool, *where* the real artifact lives (PowerSI in
   `runs/`, XtractIM next to the `.ximx`, etc.); encoding that check into the pipeline
   itself is the difference between "the suite can detect silent failure if the operator
   remembers to look" and "the suite refuses to move forward on a silent failure," which
   is the difference between a careful-human tool and an autonomous one.
10. **Investigate, as a documented experiment (not a wrapped capability until it's proven):
    `syscap.exe`'s (System Capture) headless Tcl mode and `dsxmltoschematic.exe`** — both
    are documented from-nothing schematic-project-creation paths that the suite has
    deliberately left unwrapped for lack of a confirmed non-interactive launch. If either
    can be proven headless with a real run, this partially closes the stage-2 gap even
    before Capture's own batch reliability is fixed, and it would be the strongest single
    "we found a way to do the thing we said was GUI-only" result possible in this suite —
    matching the pattern of the three already-proven "GUI-only" conclusions that later
    research passes correctly overrode (SPECCTRA, Constraint Manager, PSpice).

## Scenario Index by Pipeline Stage

All 110 manifest scenarios, mapped to their pipeline stage. "Y" = the manifest lists a
verified in-suite workaround; "N" = none confirmed in-suite (a documented mitigation that
isn't a full in-suite fix, or a precondition-only note, is marked "N (partial)").

| Stage | Scenario slug(s) | Status category | Verified workaround? |
|---|---|---|---|
| Session/process (all Allegro stages) | allegro-product-choices-dialog-hang; allegro-stale-lck-file-lock-dialog-hang; allegro-modal-qt-dialog-launch-hang; allegro-overlapping-sessions-false-negative | tool_bug_fixed | Y |
| Session/process | allegro-137s-watchdog-hang; allegro-session-minutes-hang-no-dialog | unreliable_intermittent | N (retry / check_design_lock; not a true in-suite fix) |
| Session/process | report-stale-board-mid-save | precondition_error | Y |
| Stackup (stage 6) | stackup-layer-ordering-inverted; stackup-top-bottom-name-collision-silent-noop; stackup-plane-layer-no-copper-by-default | precondition_error / silent_noop | Y |
| Stackup | stackup-reference-plane-not-settable | known_blocked | N |
| Trace/via/placement (stages 7, 14) | copper-shape-board-autoderive-disproven; createtrace-bare-layer-name-silent-nil; createtrace-zero-width-silent-default; createtrace-self-overlapping-path-silent-nil; axldel-object-net-deletes-logical-identity | precondition_error / tool_bug_fixed | Y |
| Trace/via | multi-branch-net-ripup-reroute-hang | unreliable_intermittent | N (single-branch nets only) |
| Trace/via | manual-reroute-dense-area-spacing-violations | known_blocked | N (iterate+recheck; prefer autorouter) |
| Placement (stage 7) | placement-no-package-keepin; module-instance-axlget-param-nil; allegro-extracta-illegal-view-name; allegro-designextractor-needs-cpm-sdax | precondition_error / known_blocked / tool_bug_fixed | Y for Keepin/extracta-view/extracta-path; **N** for module-instance-axlget-param-nil |
| Fanout (stage 9) | zrouter-standalone-and-native-command-dead-ends | gui_only_no_batch | Y (FORM script replay) |
| Autoroute (stage 10) | specctra-in-typo-indefinite-hang; specctra-exe-exits-rc4-on-success | tool_bug_fixed / unreliable_intermittent | Y |
| Route import (stage 11) | spif-in-form-not-closed-silent-noop; axlsavedesign-nocheck-keyword-silent-fail | tool_bug_fixed | Y (for the no-op/save-fail symptoms individually) |
| Route import | spif-batch-i-import-crash | crash | N (the `run_allegro_specctra_import` path is the *attempt*, not a verified cure for SPMHDB-238) |
| DRC (stage 12) | batch-drc-launcher-exits-early-state-lie | unreliable_intermittent | Y (read `batch_drc.log`) |
| DRC | generate-sim-variant-drc-disabled | precondition_error | Y (report.exe re-read instead) |
| Board creation / mechanical (stages 5, 32, 34) | dxf2a-nonzero-exit-on-success; dxf2a-attached-flag-syntax-rejected; dxf2a-relative-path-interactive-reprompt-loop | unreliable_intermittent / precondition_error / tool_bug_fixed | Y |
| Board creation | dxf2a-conductor-class-partial-layer-mapping | known_blocked | N (check log for unmapped layers) |
| Board creation (IPC-2581, stage 5/28) | ipc2581-in-layer-stackup-import-failed | known_blocked | N (genuine partial-import limitation) |
| Mechanical exchange (stage 32) | idf-idx-import-untested-no-sample-file | built_untested | N (no sample file) |
| Gerber (stage 27) | artwork-exe-exits-rc1-on-success; gerber-no-films-silent-noop; gbplot-wrong-input-type | unreliable_intermittent / precondition_error / tool_bug_fixed | Y |
| Gerber import (blocked alternate path) | convert-gerber-no-batch-mode; eagle2cp-no-batch-mode | gui_only_no_batch | Y (use `ipc2581_in`/PowerSI SPDIF for import instead — the import *direction* works, the specific tool is GUI-only) |
| GDSII stream-out (adjacent to stage 27) | stream-out-needs-predefined-films | built_untested | N (precondition pattern known — predefined film records, the same class solved for Gerber via `allegro_create_film` — but not yet exercised live) |
| DE-HDL rule checking (wrong tool for this flow, stage 3 adjacent) | checkplus-de-hdl-scope-not-brd | known_blocked | N (scope mismatch, not a fixable-in-suite issue) |
| Multiplexer (all Allegro standalone-CLI stages) | allegro-batch-multiplexer-cannot-find-program | known_blocked | Y (call the standalone exe directly — which is exactly what this suite does) |
| dbdoctor (stage 35 adjacent) | dbdoctor-exits-rc1-on-clean-check | unreliable_intermittent | Y (read "0 errors detected" text) |
| Schematic project creation (stage 1) | copyproject-cpm-extension-not-appended; xcon2project-refproj-required-despite-brackets | precondition_error | Y |
| Schematic project creation / interchange (stage 1) | interchange-translators-license-gated-workaround | known_blocked | Y (copyproject/xcon2project/PowerSI BRD-bridge) |
| Schematic project creation / syscap | syscap-headless-batch-mode-unconfirmed | built_untested | N (use copyproject/xcon2project) |
| Schematic authoring (stage 2) | capture-batch-open-hang | unreliable_intermittent | **N** |
| Schematic authoring | capture-custom-launch-recovery-dialog | tool_bug_fixed | Y (auto-dismiss — does not fix the Open hang itself) |
| Schematic authoring | capture-succeeded-but-empty-log-fast-exit | silent_noop | N (verify log/file content — discipline, not a fix) |
| Schematic authoring / generation | generate-schematic-from-spec-capture-inherited-block | known_blocked | N (inherits the Capture block) |
| Schematic authoring / PSpice (stage 4) | pspice-gui-entrypoints-hang-on-help | gui_only_no_batch | Y (`psp_cmd.exe`) |
| Schematic authoring / PSpice | pspice-missing-include-absolute-path-portability | precondition_error | Y (self-contained `.cir`) |
| Schematic verification (stage 3) | schematic-checklist-heuristic-precision-unverified | unreliable_intermittent | N (parsing verified; heuristic precision unverified) |
| PowerDC (stage 15) | powerdc-vrm-auto-net-pair-not-specified | known_blocked | N |
| XcitePI (stage 16) | xcitepi-xpi-start-validity-check-indefinite-spin | known_blocked | Y (reuse IOME macro; kill on validity fail) |
| XcitePI | xcitepi-subckt-staging-relative-path-fallback | precondition_error | Y (co-locate all inputs) |
| OptimizePI (stage 17) | optimizepi-missing-simulation-trigger-no-whatif | known_blocked | N |
| AmLibGen (platform, stage 37-adjacent) | amlibgen-init-excel-failed-com-dependency | known_blocked | N (Excel COM; `.xlsx` untested) |
| T2B (stage 22) | t2b-ibis-generation-needs-hspice | known_blocked | N (HSpice install required) |
| PowerSI (stage 18) | powersi-silent-success-runs-dir; powersi-missing-save-document-empty-options; powersi-frequency-suffix-parsing-error | unreliable_intermittent / precondition_error | Y |
| PowerSI | powersi-license-issue-suspected-useless | known_blocked | N (judge by artifact only) |
| SPDSIM (stage 18 adjacent) | spdsim-standalone-launch-fails-skip-license-fetch | known_blocked | N (must run as a PowerSI Tcl child) |
| BroadbandSPICE (stage 19) | broadbandspice-output-next-to-cwd-not-jobdir | unreliable_intermittent | Y |
| BroadbandSPICE | broadbandspice-poor-overall-rating-misinterpretation | known_blocked | Y (read Passivity/Causality rows) |
| abcd (utility solver, extraction) | abcd-segfault-ma-format-4port; abcd-silent-no-op-no-output | crash / known_blocked | N (pre-convert to RI — unverified) |
| abcd | abcd-file-path-spaces | precondition_error | Y (space-free dir) |
| bem2d3 (utility solver, stage 6-adjacent rigid-flex) | bem2d3-builtin-untested-no-sample | built_untested | N (no sample file) |
| Clarity3D (stage 20) | clarity3d-no-3dem-input-segfault | known_blocked | N (no `.3dem` on machine) |
| XtractIM (stage 21) | xtractim-session-mode-incomplete-setup; xtractim-workspace-artifacts-outside-jobdir | unreliable_intermittent | Y |
| SPDIF translator (stages 5/18 import) | spdif-translator-ipc2581-unconfirmed | built_untested | N (DXF/Altium confirmed; IPC-2581 unconfirmed) |
| SPDIF translator | sp2spd-log-file-arg-flips-replay-mode | known_blocked | Y (omit `log_file` for a fresh conversion) |
| Celsius3D (stage 23) | celsius3d-rerun-in-place-hang; celsius3d-post-completion-idle-stall | known_blocked | Y (fresh copy per run; poll artifacts + kill PID) |
| CelsiusCFD (stage 24) | celsiuscfd-rerun-in-place-hang-risk | built_untested | Y (fresh copy + `_clear_prior_celsius_results` — same verified pattern as Celsius3D, not independently re-proven) |
| Celsius2D (stage 25) | celsius2d-invalid-cfd-reference-domain-error | precondition_error | Y (use `demo_sim.pdcx`) |
| Celsius authoring | celsius-studio-gui-only-no-batch-authoring | gui_only_no_batch | N (build via CelsiusStudio GUI or PowerDC's own thermal features) |
| Aurora (stage 26) | aurora-form-replay-reliability-unverified | built_untested | N (use the standalone solver equivalents, which are confirmed live) |
| Platform: sessions/jobs (all stages) | session-per-process-no-persistence; stale-session-id-error-payload-vs-real-error; job-state-running-lies-forever; job-state-succeeded-lies | known_blocked | Y for the first two (chain in one pipeline; inspect `result['error']`); **N** for the two `state`-lies beyond the artifact-check discipline |
| Platform: jobs | job-wait-second-concurrent-wait-hangs | tool_bug_fixed | Y (route through `wait_for_job`) |
| Platform: jobs | wait-for-job-session-local-not-tracking; mcp-client-30s-roundtrip-cap | known_blocked | Y (poll `get_job_status`; don't resubmit) |
| Platform: jobs | cancel-cannot-kill-detached-workers | known_blocked | N (manual PID check + `clear_stale_design_lock`) |
| Platform: watchdogs | stall-watchdog-kills-genuine-finishers | known_blocked | Y (verify artifacts on `stall_timeout_killed`) |
| Platform: watchdogs | runaway-watchdog-kills-on-huge-log | known_blocked | N (guard + inspect for loop pattern) |
| Platform: rc-on-success family | nonzero-rc-on-success-family | unreliable_intermittent | Y (tool-specific completion evidence) |
| Platform: pipeline | pipeline-placeholder-double-substitution-trap; pipeline-raised-step-cannot-be-read; pipeline-argument-name-traps-silent-hang; pipeline-max-steps-and-self-reference | known_blocked | Y |
| Platform: files | file-tools-arg-names-not-source-destination; list-skills-empty-when-sql-dirs-wrong | precondition_error / known_blocked | Y |
| Sourcing (stage 36) | sourcing-zero-live-access; arrow-avnet-low-confidence-endpoints | built_untested | N (needs credentials + network) |
| Eval harness (all stages, test infrastructure) | eval-harness-per-call-timeout; eval-prompt-unfulfillable-file-copy; json-arg-coercion-middleware | tool_bug_fixed | Y |
| License diagnostics (all stages) | lmstat-unreachable-diagnostic-gap | known_blocked | N (per-tool judgment; curated `tool_status`) |
| Platform classification fix | sigritysuicon-misclassification | tool_bug_fixed | N/A (doc correction only) |
| License/abort ambiguity (all stages) | negative-rc-silent-license-abort-note | known_blocked | N (per-tool log/artifact inspection, judgment-based) |
