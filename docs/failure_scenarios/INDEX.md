# Sigrity MCP — Failed Scenarios Documentation

This directory documents every failed, blocked, or unreliable scenario in the Sigrity MCP
codebase, extracted from `core/tool_status.py`, the skill playbooks, the README, and domain
source files. For each scenario, a dedicated folder contains `SCENARIO.md` (what went wrong,
root cause, evidence) and `WORKAROUNDS.md` (what was tried, what works, prevention, remaining
gaps).

**Generated**: 2026-10-02
**Total scenarios**: 110
**Source evidence**: `sigrity_mcp/core/tool_status.py`, `.forjinn/skills/*/SKILL.md`, `README.md`, domain source files

## How to use this documentation

Find the scenario by tool name in the [Scenario Index](#scenario-index) below — each row links a
stable slug to its `docs/failure_scenarios/<slug>/` folder. Inside that folder, `SCENARIO.md`
describes what went wrong, the root cause, and the raw evidence, while `WORKAROUNDS.md` lists the
attempts, the confirmed fix, prevention guidance, and the remaining gaps. The
`status_category` cell tells you the nature of the failure (see the legend in
[Status Category Summary](#status-category-summary)) so you can quickly judge whether a fix
exists, whether the tool is merely unreliable, or whether a precondition was unmet.

## Status Category Summary

| Category | Count | Meaning |
|----------|-------|---------|
| known_blocked | 39 | Genuinely blocked, no confirmed in-suite fix |
| unreliable_intermittent | 15 | Works sometimes, fails sometimes |
| precondition_error | 19 | Tool correct, board/file precondition unmet |
| tool_bug_fixed | 19 | Was a suite bug, now fixed in code |
| silent_noop | 2 | Reports success but produced no output |
| crash | 4 | Hard process crash |
| gui_only_no_batch | 5 | GUI-only; different headless path is the workaround |
| built_untested | 11 | Implemented but never run against a real sample |

## Verified Workaround Summary

| Metric | Count |
|--------|-------|
| Scenarios with a verified workaround | 69 |
| Scenarios without a verified workaround | 56 |
| Scenarios with N/A | 1 |

## Scenario Index

### CAD / Allegro — Session & Process (7)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 1 | allegro-product-choices-dialog-hang | Product Choices dialog blocks headless launch | tool_bug_fixed | YES |
| 2 | allegro-stale-lck-file-lock-dialog-hang | Orphaned .lck → modal 'override?' dialog | tool_bug_fixed | YES |
| 3 | allegro-137s-watchdog-hang | rc -536870904 at ~137s, banner-only log | unreliable_intermittent | NO |
| 4 | allegro-modal-qt-dialog-launch-hang | Unlabeled modal Qt dialog at launch | tool_bug_fixed | YES |
| 5 | allegro-session-minutes-hang-no-dialog | Minutes-long hang, zero dialog windows | unreliable_intermittent | NO |
| 6 | allegro-overlapping-sessions-false-negative | License-seat contention false negative | tool_bug_fixed | YES |
| 7 | report-stale-board-mid-save | Report reads stale board during mid-save | precondition_error | YES |

### CAD / Allegro — SPECCTRA & Routing (5)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 8 | specctra-in-typo-indefinite-hang | 'specctra in' two-word typo → forever hang | tool_bug_fixed | YES |
| 9 | spif-in-form-not-closed-silent-noop | spif_in dialog left open → 'Finish first' | tool_bug_fixed | YES |
| 10 | axlsavedesign-nocheck-keyword-silent-fail | axlSaveDesign ?noCheck → silent save fail | tool_bug_fixed | YES |
| 11 | spif-batch-i-import-crash | spif_batch -i SPMHDB-238 crash + zombie | crash | YES |
| 12 | specctra-exe-exits-rc4-on-success | specctra rc 4 on full success | unreliable_intermittent | YES |
| 13 | batch-drc-launcher-exits-early-state-lie | batch_drc state stays 'running' forever | unreliable_intermittent | YES |

### CAD / Allegro — Stackup, Copper, Trace (10)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 14 | stackup-layer-ordering-inverted | 'bottom' ordering inverts stackup | precondition_error | YES |
| 15 | stackup-top-bottom-name-collision-silent-noop | TOP/BOTTOM name collision → silent no-op | silent_noop | YES |
| 16 | stackup-reference-plane-not-settable | No SKILL API for explicit ref plane | known_blocked | NO |
| 17 | stackup-plane-layer-no-copper-by-default | PLANE layer has zero copper | precondition_error | YES |
| 18 | copper-shape-board-autoderive-disproven | axlDBGetShapes(OUTLINE) → nil | precondition_error | YES |
| 19 | axldel-object-net-deletes-logical-identity | axlDeleteObject on NET kills identity | tool_bug_fixed | YES |
| 20 | createtrace-bare-layer-name-silent-nil | Bare layer "TOP" → silent nil | tool_bug_fixed | YES |
| 21 | createtrace-zero-width-silent-default | No width → 0-width copper + DRC | tool_bug_fixed | YES |
| 22 | createtrace-self-overlapping-path-silent-nil | Self-overlapping path → silent nil | precondition_error | YES |
| 23 | multi-branch-net-ripup-reroute-hang | Multi-branch ripup+refix → minutes hang | unreliable_intermittent | NO |
| 24 | manual-reroute-dense-area-spacing-violations | Dense-area manual reroute → new violations | known_blocked | NO |

### CAD / Allegro — Extraction & Placement (6)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 25 | allegro-extracta-illegal-view-name | Invented view keywords → 'Illegal view name' | tool_bug_fixed | YES |
| 26 | allegro-designextractor-needs-cpm-sdax | designextractor rejects raw .brd | known_blocked | YES |
| 27 | placement-no-package-keepin | 'No Package Keepin was found' | precondition_error | YES |
| 28 | module-instance-axlget-param-nil | axlDBCreateModuleInstance → nil | precondition_error | NO |
| 29 | zrouter-standalone-and-native-command-dead-ends | zrouter: 3 dead ends; only FORM replay works | gui_only_no_batch | YES |

### CAD / Allegro — Manufacturing & Mechanical (14)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 30 | dxf2a-nonzero-exit-on-success | dxf2a rc 1 on success | unreliable_intermittent | YES |
| 31 | dxf2a-attached-flag-syntax-rejected | -uMILS rejected; needs space-separated | precondition_error | YES |
| 32 | dxf2a-conductor-class-partial-layer-mapping | 'Invalid class CONDUCTOR.' → silent gap | known_blocked | NO |
| 33 | dxf2a-relative-path-interactive-reprompt-loop | Relative path → unbounded prompt loop (200MB) | tool_bug_fixed | YES |
| 34 | artwork-exe-exits-rc1-on-success | artwork.rc 1 on success | unreliable_intermittent | YES |
| 35 | gerber-no-films-silent-noop | No film records → artwork emits nothing | precondition_error | YES |
| 36 | gbplot-wrong-input-type | gbplot on .brd → 'Error opening parameter file' | tool_bug_fixed | YES |
| 37 | ipc2581-in-layer-stackup-import-failed | -x -g → 'Layer stackup import failed.' | known_blocked | NO |
| 38 | idf-idx-import-untested-no-sample-file | idf_in/idx_in never live-tested | built_untested | NO |
| 39 | ibischk345-untested | ibischk3/4/5 built_untested | built_untested | NO |
| 40 | generate-sim-variant-drc-disabled | Variant design has DRC deliberately off | precondition_error | YES |
| 41 | convert-gerber-no-batch-mode | convert_gerber.exe → interactive stdin loop | gui_only_no_batch | NO |
| 42 | eagle2cp-no-batch-mode | Eagle2Cp.exe → forcelabel prompt hang | gui_only_no_batch | NO |
| 43 | stream-out-needs-predefined-films | stream_out needs film records; unwrapped | built_untested | NO |

### CAD / Checkplus (1)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 44 | checkplus-de-hdl-scope-not-brd | checkplus is DE-HDL checker, not .brd | known_blocked | NO |

### CAD / Capture & Schematic (11)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 45 | allegro-batch-multiplexer-cannot-find-program | allegro_batch 'Cannot find program' | known_blocked | YES |
| 46 | dbdoctor-exits-rc1-on-clean-check | dbdoctor rc 1 on clean check-only | unreliable_intermittent | YES |
| 47 | capture-batch-open-hang | Capture Open<project> → 100% CPU, 0-byte log | unreliable_intermittent | NO |
| 48 | capture-custom-launch-recovery-dialog | 'Capture Custom Launch' crash-recovery dialog | tool_bug_fixed | YES |
| 49 | capture-succeeded-but-empty-log-fast-exit | 'succeeded' 0.1s, empty log, no real work | silent_noop | NO |
| 50 | generate-schematic-from-spec-capture-inherited-block | Inherits Capture known_blocked | known_blocked | NO |
| 51 | pspice-gui-entrypoints-hang-on-help | pspice.exe/pspiceaa.exe → GUI-only | gui_only_no_batch | YES |
| 52 | pspice-missing-include-absolute-path-portability | .include absolute path from authoring machine | precondition_error | YES |
| 53 | schematic-checklist-heuristic-precision-unverified | Checklist heuristics coarse, unverified | unreliable_intermittent | NO |
| 54 | copyproject-cpm-extension-not-appended | copyproject: no .cpm auto-appended | precondition_error | YES |
| 55 | xcon2project-refproj-required-despite-brackets | -refproj required despite brackets | precondition_error | YES |
| 56 | interchange-translators-license-gated-workaround | con2xml/cap2xml/dml2con/apd2con license-blocked | known_blocked | YES |
| 57 | syscap-headless-batch-mode-unconfirmed | syscap.exe: documented API, no confirmed batch | built_untested | NO |

### PI (PowerDC/XcitePI/OptimizePI) (6)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 58 | powerdc-vrm-auto-net-pair-not-specified | pdcVRM -auto -net → 'net pair not specified' | known_blocked | NO |
| 59 | xcitepi-xpi-start-validity-check-indefinite-spin | xpi_start fail → infinite CPU spin | known_blocked | YES |
| 60 | xcitepi-subckt-staging-relative-path-fallback | Subckt staged elsewhere → 0 placements | precondition_error | YES |
| 61 | optimizepi-missing-simulation-trigger-no-whatif | No sim trigger → rc 0, no WhatIf artifact | known_blocked | NO |
| 62 | amlibgen-init-excel-failed-com-dependency | AmLibGen [ERROR] Init excel failed | known_blocked | NO |
| 63 | t2b-ibis-generation-needs-hspice | T2B → 'Spice run (TYP) aborted.' needs HSpice | known_blocked | NO |

### SI (PowerSI/BroadbandSPICE/SPDSIM) (8)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 64 | powersi-silent-success-runs-dir | 0-byte run.log; artifacts in runs/ not job dir | unreliable_intermittent | YES |
| 65 | powersi-missing-save-document-empty-options | No save_document → empty Options.xml only | precondition_error | YES |
| 66 | powersi-frequency-suffix-parsing-error | "1MHz" → 'ending freq < starting' | precondition_error | YES |
| 67 | powersi-license-issue-suspected-useless | flag useless; lmstat unreliable | known_blocked | NO |
| 68 | spdsim-standalone-launch-fails-skip-license-fetch | SPDSIM standalone → 'Skip license fetch' | known_blocked | NO |
| 69 | broadbandspice-output-next-to-cwd-not-jobdir | BBS writes to CWD, not job dir | unreliable_intermittent | YES |
| 70 | broadbandspice-poor-overall-rating-misinterpretation | 'Poor' overall ≠ physics fail | known_blocked | YES |

### Extraction (Clarity3D/XtractIM/abcd/bem2d3/SPDIF) (8)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 71 | abcd-segfault-ma-format-4port | abcd segfault on MA/dB 4-port | crash | NO |
| 72 | abcd-silent-no-op-no-output | abcd rc 0, no output for any input | known_blocked | NO |
| 73 | abcd-file-path-spaces | file_path must be space-free dir | precondition_error | YES |
| 74 | bem2d3-builtin-untested-no-sample | bem2d3 never run; no sample file | built_untested | NO |
| 75 | clarity3d-no-3dem-input-segfault | Clarity3D: no .3dem file; .spd → crash | known_blocked | NO |
| 76 | xtractim-session-mode-incomplete-setup | Session mode → 'incomplete setup' | unreliable_intermittent | YES |
| 77 | xtractim-workspace-artifacts-outside-jobdir | XtractIM artifacts next to .ximx, not job dir | unreliable_intermittent | YES |
| 78 | spdif-translator-ipc2581-unconfirmed | IPC-2581 → still parsing at 90s | built_untested | NO |
| 79 | sp2spd-log-file-arg-flips-replay-mode | log_file → silent log-replay mode | known_blocked | YES |

### Thermal (Celsius) & Aurora (6)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 80 | celsius3d-rerun-in-place-hang | Re-run with prior result folder → hang | known_blocked | YES |
| 81 | celsius3d-post-completion-idle-stall | Post-solve: process never exits | known_blocked | YES |
| 82 | celsiuscfd-rerun-in-place-hang-risk | CelsiusCFD likely same re-run risk | built_untested | YES |
| 83 | celsius2d-invalid-cfd-reference-domain-error | Celsius2D chip.pdcx → invalid CFD ref | precondition_error | YES |
| 84 | celsius-studio-gui-only-no-batch-authoring | Celsius authoring is GUI-only | gui_only_no_batch | NO |
| 85 | aurora-form-replay-reliability-unverified | Aurora FORM replay unverified | built_untested | NO |

### Platform — Session/Job (12)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 86 | session-per-process-no-persistence | Sessions in-memory; lost on restart | known_blocked | YES |
| 87 | stale-session-id-error-payload-vs-real-error | Stale session → error payload, not raised | known_blocked | YES |
| 88 | job-state-running-lies-forever | state 'running' forever post-restart | known_blocked | NO |
| 89 | job-state-succeeded-lies | succeeded rc0 ≠ work happened | known_blocked | NO |
| 90 | job-wait-second-concurrent-wait-hangs | 2nd concurrent wait → Windows Proactor bug | tool_bug_fixed | YES |
| 91 | wait-for-job-session-local-not-tracking | wait_for_job session-local; 'not tracking' | known_blocked | YES |
| 92 | mcp-client-30s-roundtrip-cap | MCP client 30s cap masks real job state | known_blocked | YES |
| 93 | cancel-cannot-kill-detached-workers | cancel_job: detached zombies survive | known_blocked | NO |
| 94 | stall-watchdog-kills-genuine-finishers | Stall watchdog kills completed-but-idle jobs | known_blocked | YES |
| 95 | runaway-watchdog-kills-on-huge-log | Runaway log > 200MB → kill | known_blocked | NO |
| 96 | nonzero-rc-on-success-family | specctra rc4, artwork rc1, dxf2a rc1, dbdoctor rc1 | unreliable_intermittent | YES |

### Platform — Pipeline (13)

| # | Slug | Title | Category | Verified WR |
|---|------|-------|----------|-------------|
| 97 | pipeline-placeholder-double-substitution-trap | ${...} value re-substituted in later step | known_blocked | YES |
| 98 | pipeline-raised-step-cannot-be-read | Raised step: 'error' only, no 'result' | known_blocked | YES |
| 99 | pipeline-argument-name-traps-silent-hang | Wrong arg name → ~20min silent hang | known_blocked | YES |
| 100 | pipeline-max-steps-and-self-reference | Pipeline cap 50 steps; no nesting | known_blocked | YES |
| 101 | file-tools-arg-names-not-source-destination | file tools: source_file/destination_file/file_path | precondition_error | YES |
| 102 | list-skills-empty-when-sql-dirs-wrong | list_skills empty if SIGRITY_SKILLS_DIR wrong | known_blocked | YES |
| 103 | sourcing-zero-live-access | Sourcing tool: zero live verification | built_untested | NO |
| 104 | arrow-avnet-low-confidence-endpoints | Arrow/Avnet endpoints: lower-confidence guesses | built_untested | NO |
| 105 | eval-harness-per-call-timeout | Eval 90s timeout fired on legitimate pipeline | tool_bug_fixed | YES |
| 106 | eval-prompt-unfulfillable-file-copy | Prompt 'copy file first' — no copy tool existed | tool_bug_fixed | YES |
| 107 | json-arg-coercion-middleware | LLM serializes lists as JSON strings → pydantic fail | tool_bug_fixed | YES |
| 108 | lmstat-unreachable-diagnostic-gap | lmstat unreachable but tools work | known_blocked | NO |
| 109 | sigritysuicon-misclassification | SigritySuiteCon: gtest binary, not GUI | tool_bug_fixed | N/A |
| 110 | negative-rc-silent-license-abort-note | Negative rc + no output → ambiguous license note | known_blocked | NO |

## Cross-Reference: Common Causes

These are the recurring root-cause *patterns* across the 110 scenarios. Use this to quickly find
every scenario that shares a failure mode. (Several scenarios map to more than one pattern; each
row lists the scenarios whose primary signature is that pattern.)

- **Nonzero exit code on success** — a tool returns rc ≠ 0 (or 0) even when the work completed,
  so status checking alone is misleading. Affects **6** scenarios:
  `specctra-exe-exits-rc4-on-success`, `dxf2a-nonzero-exit-on-success`,
  `artwork-exe-exits-rc1-on-success`, `dbdoctor-exits-rc1-on-clean-check`,
  `nonzero-rc-on-success-family`, `negative-rc-silent-license-abort-note`
- **State is a liar in both directions** — reported job/process state ('running', 'succeeded')
  does not reflect reality either way: a stuck 'running' that is actually done, or a 'succeeded'
  rc 0 that did no work. Affects **4** scenarios:
  `batch-drc-launcher-exits-early-state-lie`, `job-state-running-lies-forever`,
  `job-state-succeeded-lies`, `cancel-cannot-kill-detached-workers`
- **Artifact location is not job_dir** — output is written somewhere other than the expected job
  directory (runs/ subdir, CWD, next to `.ximx`), so a missing-file check in job dir gives a false
  negative. Affects **3** scenarios:
  `powersi-silent-success-runs-dir`, `broadbandspice-output-next-to-cwd-not-jobdir`,
  `xtractim-workspace-artifacts-outside-jobdir`
- **Modal dialog hang at launch** — a modal (often unlabeled) dialog appears at tool launch and
  blocks the headless process until dismissed. Affects **5** scenarios:
  `allegro-product-choices-dialog-hang`, `allegro-stale-lck-file-lock-dialog-hang`,
  `allegro-modal-qt-dialog-launch-hang`, `capture-custom-launch-recovery-dialog`,
  `allegro-137s-watchdog-hang`
- **Interactive stdin loop on bad path** — a bad/relative path or a GUI-only entry point sends the
  tool into an unbounded stdin/interactive prompt loop instead of returning an error. Affects **3**
  scenarios:
  `dxf2a-relative-path-interactive-reprompt-loop`, `convert-gerber-no-batch-mode`,
  `eagle2cp-no-batch-mode`
- **GUI-only, no batch surface** — the capability exists only in the GUI; the wrapped executable is
  interactive or a GUI launcher with no headless path. Affects **4** scenarios:
  `zrouter-standalone-and-native-command-dead-ends`, `convert-gerber-no-batch-mode`,
  `eagle2cp-no-batch-mode`, `celsius-studio-gui-only-no-batch-authoring`
  (plus `pspice-gui-entrypoints-hang-on-help`, whose workaround is the headless `psp_cmd.exe`)
- **Silent no-op** — the tool reports success but produced no actual output or made no change.
  Affects **4** scenarios: `stackup-top-bottom-name-collision-silent-noop`,
  `gerber-no-films-silent-noop`, `abcd-silent-no-op-no-output`,
  `capture-succeeded-but-empty-log-fast-exit`
- **Inherited / cascading block** — a higher-level scenario is blocked because a lower-level tool
  it depends on is itself blocked. Affects **1** scenario:
  `generate-schematic-from-spec-capture-inherited-block`
