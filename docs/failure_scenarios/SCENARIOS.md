# Sigrity MCP — Failure/Blocker Scenario Manifest

This file is the authoritative consolidated list of every failed, blocked, or unreliable
scenario in the Sigrity MCP codebase, extracted by 10 research agents from:
- `sigrity_mcp/core/tool_status.py` (889 lines, canonical per-tool status registry + notes)
- `.forjinn/skills/*/SKILL.md` (6 domain + 1 parent playbook, all verified-live evidence)
- `README.md` (949 lines, known gaps + corrections + eval results)
- domain source files under `sigrity_mcp/domains/<domain>/`

Each scenario is one folder in this directory: `docs/failure_scenarios/<slug>/` containing
`SCENARIO.md` (what went wrong + evidence) and `WORKAROUNDS.md` (what was tried, what works).

## Conventions

- **status_category** values:
  - `known_blocked` — genuinely blocked, no confirmed in-suite fix yet
  - `unreliable_intermittent` — works sometimes, fails sometimes; root cause partially understood
  - `precondition_error` — the tool/call is correct but a board/file/content precondition is unmet
  - `tool_bug_fixed` — was a real bug in this suite's wrapper, now fixed in code
  - `silent_noop` — tool reports success but produced no real output
  - `crash` — hard process crash (access violation, segfault)
  - `gui_only_no_batch` — the tool is GUI-only; a different headless path is the workaround
  - `built_untested` — implemented and self-documenting, but never run against a real sample
- **verified_workaround: None** means no confirmed in-suite workaround exists yet.
- **Pure FlexNet license scenarios are excluded** per the project's scope note.
  License-gated tools (con2xml/cap2xml/dml2con/apd2con) appear only to document their
  WORKAROUND path (use copyproject/xcon2project/PowerSI BRD-bridge instead).

---

## INDEX (by domain)

| # | slug | title (short) | status_category | verified_workaround? |
|---|------|---------------|-----------------|---------------------|
| CAD/Allegro — session & process |
| 1 | allegro-product-choices-dialog-hang | Product Choices dialog blocks headless launch | tool_bug_fixed | YES (default product + DismissWatcher) |
| 2 | allegro-stale-lck-file-lock-dialog-hang | Orphaned .lck → modal 'override?' dialog | tool_bug_fixed | YES (clear_stale_design_lock) |
| 3 | allegro-137s-watchdog-hang | rc -536870904 at ~137s, banner-only log | unreliable_intermittent | NO (retry; check_design_lock) |
| 4 | allegro-modal-qt-dialog-launch-hang | Unlabeled modal Qt dialog at launch | tool_bug_fixed | YES (auto DismissWatcher) |
| 5 | allegro-session-minutes-hang-no-dialog | Minutes-long hang, zero dialog windows | unreliable_intermittent | NO (suspect >30s; verify mtime) |
| 6 | allegro-overlapping-sessions-false-negative | License-seat contention false negative | tool_bug_fixed | YES (one launch at a time) |
| 7 | report-stale-board-mid-save | Report reads stale board during mid-save | precondition_error | YES (wait for terminal + mtime check) |
| CAD/Allegro — SPECCTRA & routing import |
| 8 | specctra-in-typo-indefinite-hang | 'specctra in' two-word typo → forever hang | tool_bug_fixed | YES (specctra_in one word) |
| 9 | spif-in-form-not-closed-silent-noop | spif_in dialog left open → 'Finish first' | tool_bug_fixed | YES (FORM spif_in CLOSE) |
| 10 | axlsavedesign-nocheck-keyword-silent-fail | axlSaveDesign ?noCheck → silent save fail | tool_bug_fixed | YES (?mode "nocheck") |
| 11 | spif-batch-i-import-crash | spif_batch -i SPMHDB-238 crash + zombie | crash | YES (run_allegro_specctra_import) |
| 12 | specctra-exe-exits-rc4-on-success | specctra rc 4 on full success | unreliable_intermittent | YES (read final.sts) |
| 13 | batch-drc-launcher-exits-early-state-lie | batch_drc state stays 'running' forever | unreliable_intermittent | YES (read batch_drc.log) |
| CAD/Allegro — stackup, copper, trace |
| 14 | stackup-layer-ordering-inverted | 'bottom' ordering inverts stackup | precondition_error | YES (queue top-to-bottom) |
| 15 | stackup-top-bottom-name-collision-silent-noop | TOP/BOTTOM name collision → silent no-op | silent_noop | YES (drop outer-layer names) |
| 16 | stackup-reference-plane-not-settable | No SKILL API for explicit ref plane | known_blocked | NO (order layers by adjacency) |
| 17 | stackup-plane-layer-no-copper-by-default | PLANE layer has zero copper | precondition_error | YES (allegro_create_copper_shape) |
| 18 | copper-shape-board-autoderive-disproven | axlDBGetShapes(OUTLINE) → nil | precondition_error | YES (explicit points from report) |
| 19 | axldel-object-net-deletes-logical-identity | axlDeleteObject on NET kills identity | tool_bug_fixed | YES (allegro_assign_net ripup) |
| 20 | createtrace-bare-layer-name-silent-nil | Bare layer "TOP" → silent nil | tool_bug_fixed | YES (auto ETCH/<layer>) |
| 21 | createtrace-zero-width-silent-default | No width → 0-width copper + DRC | tool_bug_fixed | YES (width required) |
| 22 | createtrace-self-overlapping-path-silent-nil | Self-overlapping path → silent nil | precondition_error | YES (pre-flight geometry check) |
| 23 | multi-branch-net-ripup-reroute-hang | Multi-branch ripup+refix → minutes hang | unreliable_intermittent | NO (use single-branch nets) |
| 24 | manual-reroute-dense-area-spacing-violations | Dense-area manual reroute → new violations | known_blocked | NO (iterate-and-recheck; prefer autorouter) |
| CAD/Allegro — extraction & placement |
| 25 | allegro-extracta-illegal-view-name | Invented view keywords → 'Illegal view name' | tool_bug_fixed | YES (real keywords from share/pcb/text/views/) |
| 26 | allegro-designextractor-needs-cpm-sdax | designextractor rejects raw .brd | known_blocked | YES (use run_allegro_extracta) |
| 27 | placement-no-package-keepin | 'No Package Keepin was found' | precondition_error | YES (board with Keepin defined) |
| 28 | module-instance-axlget-param-nil | axlDBCreateModuleInstance → nil | precondition_error | NO (board/library-path precondition) |
| 29 | zrouter-standalone-and-native-command-dead-ends | zrouter: 3 dead ends; only FORM replay works | gui_only_no_batch | YES (FORM script replay) |
| CAD/Allegro — manufacturing & mechanical |
| 30 | dxf2a-nonzero-exit-on-success | dxf2a rc 1 on success | unreliable_intermittent | YES (read 'dxf2a complete.') |
| 31 | dxf2a-attached-flag-syntax-rejected | -uMILS rejected; needs space-separated | precondition_error | YES (space-separated flags) |
| 32 | dxf2a-conductor-class-partial-layer-mapping | 'Invalid class CONDUCTOR.' → silent gap | known_blocked | NO (check log for unmapped layers) |
| 33 | dxf2a-relative-path-interactive-reprompt-loop | Relative path → unbounded prompt loop (200MB) | tool_bug_fixed | YES (absolute path resolution) |
| 34 | artwork-exe-exits-rc1-on-success | artwork.rc 1 on success | unreliable_intermittent | YES (read .art + photoplot.log) |
| 35 | gerber-no-films-silent-noop | No film records → artwork emits nothing | precondition_error | YES (allegro_create_film first) |
| 36 | gbplot-wrong-input-type | gbplot on .brd → 'Error opening parameter file' | tool_bug_fixed | YES (pass .art not .brd) |
| 37 | ipc2581-in-layer-stackup-import-failed | -x -g → 'Layer stackup import failed.' | known_blocked | NO (genuine partial-import limitation) |
| 38 | idf-idx-import-untested-no-sample-file | idf_in/idx_in never live-tested | built_untested | NO (no sample file on machine) |
| 39 | ibischk345-untested | ibischk3/4/5 built_untested | built_untested | NO (only ibischk6 confirmed) |
| 40 | generate-sim-variant-drc-disabled | Variant design has DRC deliberately off | precondition_error | YES (report.exe re-read, not DRC) |
| 41 | convert-gerber-no-batch-mode | convert_gerber.exe → interactive stdin loop | gui_only_no_batch | NO (use ipc2581_in for import) |
| 42 | eagle2cp-no-batch-mode | Eagle2Cp.exe → forcelabel prompt hang | gui_only_no_batch | NO (not wrapped) |
| 43 | stream-out-needs-predefined-films | stream_out needs film records; unwrapped | built_untested | NO (precondition pattern known) |
| 44 | checkplus-de-hdl-scope-not-brd | checkplus is DE-HDL checker, not .brd | known_blocked | NO (likely inapplicable to .brd flow) |
| 45 | allegro-batch-multiplexer-cannot-find-program | allegro_batch 'Cannot find program' | known_blocked | YES (call standalone exe directly) |
| 46 | dbdoctor-exits-rc1-on-clean-check | dbdoctor rc 1 on clean check-only | unreliable_intermittent | YES (read '0 errors detected' text) |
| CAD/Capture & schematic |
| 47 | capture-batch-open-hang | Capture Open<project> → 100% CPU, 0-byte log | unreliable_intermittent | NO (one 3.2s clean run; not reproducible) |
| 48 | capture-custom-launch-recovery-dialog | 'Capture Custom Launch' crash-recovery dialog | tool_bug_fixed | YES (auto_dismiss_recovery_dialog_if_stuck) |
| 49 | capture-succeeded-but-empty-log-fast-exit | 'succeeded' 0.1s, empty log, no real work | silent_noop | NO (verify log/file content) |
| 50 | generate-schematic-from-spec-capture-inherited-block | Inherits Capture known_blocked | known_blocked | NO (verify real log/file content) |
| 51 | pspice-gui-entrypoints-hang-on-help | pspice.exe/pspiceaa.exe → GUI-only | gui_only_no_batch | YES (psp_cmd.exe, confirmed live) |
| 52 | pspice-missing-include-absolute-path-portability | .include absolute path from authoring machine | precondition_error | YES (self-contained .cir) |
| 53 | schematic-checklist-heuristic-precision-unverified | Checklist heuristics coarse, unverified | unreliable_intermittent | NO (parsing verified; precision unverified) |
| 54 | copyproject-cpm-extension-not-appended | copyproject: no .cpm auto-appended | precondition_error | YES (include .cpm in name) |
| 55 | xcon2project-refproj-required-despite-brackets | -refproj required despite brackets | precondition_error | YES (always pass -refproj) |
| 56 | interchange-translators-license-gated-workaround | con2xml/cap2xml/dml2con/apd2con license-blocked | known_blocked | YES (copyproject/xcon2project/BRD-bridge) |
| 57 | syscap-headless-batch-mode-unconfirmed | syscap.exe: documented API, no confirmed batch | built_untested | NO (use copyproject/xcon2project) |
| PI (PowerDC/XcitePI/OptimizePI) |
| 58 | powerdc-vrm-auto-net-pair-not-specified | pdcVRM -auto -net → 'net pair not specified' | known_blocked | NO (GUI-only Net Class; 4 variations ruled out) |
| 59 | xcitepi-xpi-start-validity-check-indefinite-spin | xpi_start fail → infinite CPU spin | known_blocked | YES (reuse IOME macro; kill on validity fail) |
| 60 | xcitepi-subckt-staging-relative-path-fallback | Subckt staged elsewhere → 0 placements | precondition_error | YES (co-locate all inputs) |
| 61 | optimizepi-missing-simulation-trigger-no-whatif | No sim trigger → rc 0, no WhatIf artifact | known_blocked | NO (GUI only; extend run_session trigger) |
| 62 | amlibgen-init-excel-failed-com-dependency | AmLibGen [ERROR] Init excel failed | known_blocked | NO (needs Excel COM; .xlsx untested) |
| 63 | t2b-ibis-generation-needs-hspice | T2B → 'Spice run (TYP) aborted.' needs HSpice | known_blocked | NO (needs HSpice install) |
| SI (PowerSI/BroadbandSPICE/SPDSIM) |
| 64 | powersi-silent-success-runs-dir | 0-byte run.log; artifacts in runs/ not job dir | unreliable_intermittent | YES (glob runs/ for non-empty .sNp) |
| 65 | powersi-missing-save-document-empty-options | No save_document → empty Options.xml only | precondition_error | YES (powersi_save_document line 2) |
| 66 | powersi-frequency-suffix-parsing-error | "1MHz" → 'ending freq < starting' | precondition_error | YES (plain Hz "1e6") |
| 67 | powersi-license-issue-suspected-useless | flag useless; lmstat unreliable | known_blocked | NO (judge by artifact only) |
| 68 | spdsim-standalone-launch-fails-skip-license-fetch | SPDSIM standalone → 'Skip license fetch' | known_blocked | NO (needs to run as PowerSI child) |
| 69 | broadbandspice-output-next-to-cwd-not-jobdir | BBS writes to CWD, not job dir | unreliable_intermittent | YES (check BBSResult_<basename>/ in CWD) |
| 70 | broadbandspice-poor-overall-rating-misinterpretation | 'Poor' overall ≠ physics fail | known_blocked | YES (read Passivity/Causality rows) |
| Extraction (Clarity3D/XtractIM/abcd/bem2d3/SPDIF) |
| 71 | abcd-segfault-ma-format-4port | abcd segfault on MA/dB 4-port | crash | NO (pre-convert to RI — unverified) |
| 72 | abcd-silent-no-op-no-output | abcd rc 0, no output for any input | known_blocked | NO (unusable as cascade/de-embed) |
| 73 | abcd-file-path-spaces | file_path must be space-free dir | precondition_error | YES (space-free dir) |
| 74 | bem2d3-builtin-untested-no-sample | bem2d3 never run; no sample file | built_untested | NO (no sample on machine) |
| 75 | clarity3d-no-3dem-input-segfault | Clarity3D: no .3dem file; .spd → crash | known_blocked | NO (no .3dem on machine) |
| 76 | xtractim-session-mode-incomplete-setup | Session mode → 'incomplete setup' | unreliable_intermittent | YES (use run_xtractim_workspace) |
| 77 | xtractim-workspace-artifacts-outside-jobdir | XtractIM artifacts next to .ximx, not job dir | unreliable_intermittent | YES (check .ximx dir) |
| 78 | spdif-translator-ipc2581-unconfirmed | IPC-2581 → still parsing at 90s | built_untested | NO (DXF/Altium confirmed; IPC-2581 unconfirmed) |
| 79 | sp2spd-log-file-arg-flips-replay-mode | log_file → silent log-replay mode | known_blocked | YES (omit log_file for fresh conversion) |
| Thermal (Celsius) & Aurora |
| 80 | celsius3d-rerun-in-place-hang | Re-run with prior result folder → hang | known_blocked | YES (fresh copy per run) |
| 81 | celsius3d-post-completion-idle-stall | Post-solve: process never exits | known_blocked | YES (poll artifacts; kill PID) |
| 82 | celsiuscfd-rerun-in-place-hang-risk | CelsiusCFD likely same re-run risk | built_untested | YES (fresh copy; _clear_prior_celsius_results) |
| 83 | celsius2d-invalid-cfd-reference-domain-error | Celsius2D chip.pdcx → invalid CFD ref | precondition_error | YES (use demo_sim.pdcx) |
| 84 | celsius-studio-gui-only-no-batch-authoring | Celsius authoring is GUI-only | gui_only_no_batch | NO (build via CelsiusStudio GUI or PowerDC) |
| 85 | aurora-form-replay-reliability-unverified | Aurora FORM replay unverified | built_untested | NO (use standalone solver equivalents) |
| Platform (session/job/pipeline/file) |
| 86 | session-per-process-no-persistence | Sessions in-memory; lost on restart | known_blocked | YES (chain in one pipeline lifetime) |
| 87 | stale-session-id-error-payload-vs-real-error | Stale session → error payload, not raised | known_blocked | YES (inspect result['error'] per step) |
| 88 | job-state-running-lies-forever | state 'running' forever post-restart | known_blocked | NO (artifact check) |
| 89 | job-state-succeeded-lies | succeeded rc0 ≠ work happened | known_blocked | NO (artifact check in input dir) |
| 90 | job-wait-second-concurrent-wait-hangs | 2nd concurrent wait → Windows Proactor bug | tool_bug_fixed | YES (route through wait_for_job) |
| 91 | wait-for-job-session-local-not-tracking | wait_for_job session-local; 'not tracking' | known_blocked | YES (get_job_status; don't resubmit) |
| 92 | mcp-client-30s-roundtrip-cap | MCP client 30s cap masks real job state | known_blocked | YES (poll get_job_status; don't resubmit) |
| 93 | cancel-cannot-kill-detached-workers | cancel_job: detached zombies survive | known_blocked | NO (manual PID check + clear_stale_design_lock) |
| 94 | stall-watchdog-kills-genuine-finishers | Stall watchdog kills completed-but-idle jobs | known_blocked | YES (verify artifacts on stall_timeout_killed) |
| 95 | runaway-watchdog-kills-on-huge-log | Runaway log > 200MB → kill | known_blocked | NO (guard; inspect for loop pattern) |
| 96 | nonzero-rc-on-success-family | specctra rc4, artwork rc1, dxf2a rc1, dbdoctor rc1 | unreliable_intermittent | YES (tool-specific completion evidence) |
| 97 | pipeline-placeholder-double-substitution-trap | ${...} value re-substituted in later step | known_blocked | YES (whole-placeholder refs, not inline) |
| 98 | pipeline-raised-step-cannot-be-read | Raised step: 'error' only, no 'result' | known_blocked | YES (read error then result per step) |
| 99 | pipeline-argument-name-traps-silent-hang | Wrong arg name → ~20min silent hang | known_blocked | YES (source names from SKILL.md) |
| 100 | pipeline-max-steps-and-self-reference | Pipeline cap 50 steps; no nesting | known_blocked | YES (split >50 into sequential calls) |
| 101 | file-tools-arg-names-not-source-destination | file tools: source_file/destination_file/file_path | precondition_error | YES (exact arg names) |
| 102 | list-skills-empty-when-sql-dirs-wrong | list_skills empty if SIGRITY_SKILLS_DIR wrong | known_blocked | YES (fix SIGRITY_SKILLS_DIR) |
| Sourcing & eval |
| 103 | sourcing-zero-live-access | Sourcing tool: zero live verification | built_untested | NO (needs credentials + network) |
| 104 | arrow-avnet-low-confidence-endpoints | Arrow/Avnet endpoints: lower-confidence guesses | built_untested | NO (must be run with real credentials) |
| 105 | eval-harness-per-call-timeout | Eval 90s timeout fired on legitimate pipeline | tool_bug_fixed | YES (TOOL_TIMEOUT=180s; type-tagged errors) |
| 106 | eval-prompt-unfulfillable-file-copy | Prompt 'copy file first' — no copy tool existed | tool_bug_fixed | YES (pre-staged inputs; direct paths) |
| 107 | json-arg-coercion-middleware | LLM serializes lists as JSON strings → pydantic fail | tool_bug_fixed | YES (argument_coercion_middleware) |
| 108 | lmstat-unreachable-diagnostic-gap | lmstat unreachable but tools work | known_blocked | NO (per-tool judgment; curated tool_status) |
| 109 | sigritysuicon-misclassification | SigritySuiteCon: gtest binary, not GUI | tool_bug_fixed | N/A (doc correction only) |
| 110 | negative-rc-silent-license-abort-note | Negative rc + no output → ambiguous license note | known_blocked | NO (per-tool log/artifact inspection) |
