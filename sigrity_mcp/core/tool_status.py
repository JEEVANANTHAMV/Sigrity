"""Curated, hand-maintained verification status per logical tool name.

`lmutil lmstat` has already been proven unreliable as a predictor of real tool
usability on this machine — PowerSI and PowerDC both fetch licenses and run
successfully, repeatedly, despite `lmstat` reporting the configured license server
unreachable. Building an automated "ping the license server per tool" status feature on
top of that already-unreliable signal would mislead callers, not help them. Worse, an
automated *launch-and-see* probe is actively risky for GUI-capable tools: a single
`allegro.exe -product help` probe (documented as print-and-exit) instead blocked
indefinitely on an interactive product-chooser dialog.

So instead of a live query, this module is a single source of truth for what has
actually been exercised, updated by hand as tools are tested — the same three-tier
distinction this project's README already draws in prose, made queryable here instead.
"""

from __future__ import annotations

from typing import Literal

ToolStatus = Literal["confirmed_live", "built_untested", "known_blocked"]

STATUS_DESCRIPTIONS: dict[ToolStatus, str] = {
    "confirmed_live": "Actually run against a real license and a real design on this "
    "machine, successfully, at least once.",
    "built_untested": "Implemented from documentation/sample scripts and covered by "
    "unit tests (argv/script construction), but never executed against a live license "
    "on this machine — treat exact flag/command spellings as best transcription, not "
    "guaranteed correct.",
    "known_blocked": "Attempted live and found genuinely blocked (a license issue, an "
    "unresolved interactive prompt, or similar) — see the note for specifics before "
    "retrying.",
}

# logical tool name (matches core.executables' registries) -> status.
# Anything not listed here is implicitly "built_untested" if registered in the
# executables registry at all, or simply unknown to this suite otherwise.
TOOL_STATUS: dict[str, ToolStatus] = {
    "powersi": "confirmed_live",
    "powerdc": "confirmed_live",
    "amlibgen": "known_blocked",
    "allegro": "confirmed_live",
    "capture": "known_blocked",
    "allegro_batch": "known_blocked",
    "allegro_report": "confirmed_live",
    "allegro_dbdoctor": "confirmed_live",
    "celsius3d": "confirmed_live",
    "celsiuscfd": "confirmed_live",
    "celsius2d": "confirmed_live",
    "allegro_batch_drc": "confirmed_live",
    "allegro_placement": "confirmed_live",
    "allegro_ncroute": "confirmed_live",
    "allegro_ipc2581_out": "confirmed_live",
    "allegro_ipc356_out": "confirmed_live",
    "allegro_step_out": "confirmed_live",
    "ibischk3": "built_untested",
    "ibischk4": "built_untested",
    "ibischk5": "built_untested",
    "ibischk6": "confirmed_live",
    "allegro_checkplus": "known_blocked",
    "allegro_designextractor": "known_blocked",
    "allegro_zrouter": "built_untested",
    "allegro_gbplot": "built_untested",
    "allegro_diacheck": "built_untested",
    "allegro_diacompare": "built_untested",
    "con2xml": "known_blocked",
    "cap2xml": "known_blocked",
    "dml2con": "known_blocked",
    "apd2con": "known_blocked",
    "abcd": "built_untested",
    "bem2d3": "built_untested",
    "xcitepi": "confirmed_live",
    "optimizepi": "confirmed_live",
    "xtractim": "confirmed_live",
    "dsn2spd": "confirmed_live",
    "spdsim": "known_blocked",
    "t2b": "known_blocked",
}

# Free-text detail for any status worth explaining beyond STATUS_DESCRIPTIONS' generic
# wording — mainly for known_blocked entries, so a caller knows what to actually do.
TOOL_STATUS_NOTES: dict[str, str] = {
    "amlibgen": "RETESTED, root cause now CONFIRMED and it is NOT a license issue: "
    "AmLibGen.exe writes its own log file (`AMLibGen.log`, in its process's launch "
    "directory, not the job's own directory — this tool goes through core.process."
    "run_quick, not submit_job, so it inherits this server's own cwd rather than a "
    "per-job scratch dir) showing it receives the exact command line correctly, begins "
    "processing the source spreadsheet, then fails with '[ERROR] Init excel failed' — "
    "consistent with a broken/missing Microsoft Excel COM automation dependency on this "
    "machine for reading legacy .xls files, not a FlexNet/license problem and not a CLI "
    "flag error (the flags in generate_amm_library_from_spreadsheet are confirmed "
    "correct — the tool parsed and acted on them). Needs Excel installed/repaired on "
    "this machine (or a native .xlsx source, if AmLibGen supports one, to bypass "
    "whatever legacy .xls COM path is failing) to fully confirm end-to-end — flag this "
    "for the user, it is not something a license grant fixes.",
    "allegro": "Was initially blocked by an interactive 'Product Choices' license-tier "
    "chooser dialog on every launch (confirmed not a license failure -- Sigrity Aurora "
    "and other tiers were genuinely listed as available choices); resolved by the user "
    "setting a default product interactively once. Now confirmed live for the "
    "session/query mechanics: `allegro.exe -s script.scr <real .brd>` loads the board "
    "and a `skill (axlCurrentDesign)` query executed and returned correctly, followed by "
    "a clean `quit`-triggered exit, all within ~20s. RE-TESTED after the user reported "
    "licensing issues resolved: `allegro_create_net` (`axlDBCreateNet`) against a real "
    "board now completes cleanly in ~5.6s (returncode 0) -- previously this hung past "
    "two minutes in the same session shape, so the earlier block really was "
    "license/queue-related, not a bug in the SKILL call itself. Only `allegro_create_net` "
    "was independently re-confirmed this way; `allegro_create_component`/"
    "`allegro_create_board_outline`/`allegro_create_stackup`/`allegro_save_design`/"
    "`allegro_run_drc` use the same session mechanics and the same axl* API family but "
    "were not each individually re-run -- reasonable to expect they now also work, but "
    "still technically unverified individually.",
    "capture": "Initially hit the same-looking 'Product Choices' dialog as allegro; "
    "after the user's fix, a bare `Capture.exe` launch (no arguments) now opens cleanly. "
    "However, the batch-script invocation (`-product=<name> script.tcl`) remains "
    "unreliable: repeated attempts inconsistently opened Capture's own default/tutorial "
    "project instead of running the given script, exited immediately with no output, or "
    "triggered a 'Capture Custom Launch' dialog -- which Cadence's own docs describe as "
    "a crash-recovery prompt ('displayed only after Capture fails at launching for the "
    "first time'), not a license chooser. Root cause not isolated (a Tcl syntax issue in "
    "the probe script, a version-specific CLI quirk, or something else) -- see "
    "capture_tools.py's module docstring. RE-TESTED after the user reported licensing "
    "issues resolved, against a real shipped sample project "
    "(tools/capture/samples/PCB-Layout/Fault-Detector/Fault-Detector.opj) with a minimal "
    "Open+Save+Close+Exit macro: the process launched (confirmed correct argv) but was "
    "still running with an empty log after 60s and had to be force-killed -- this rules "
    "out licensing as the cause definitively; the batch-invocation unreliability is a "
    "separate, still-unresolved issue.",
    "allegro_batch": "The multiplexer's own -help and '<program> -help' output is fine "
    "(genuinely headless, no dialog), but actually dispatching a sub-program through it "
    "is unreliable: `allegro_batch dbdoctor -check_only <real .brd>` failed immediately "
    "with 'ERROR: Cannot find program \"dbdoctor\"' (exit 2), while the identical "
    "operation via the standalone `dbdoctor.exe` succeeded. Tools call each underlying "
    "standalone exe directly (allegro_report, allegro_dbdoctor, ...) instead of routing "
    "through this multiplexer.",
    "allegro_report": "Confirmed genuinely headless, no dialog: `report.exe -v sum "
    "<real .brd sample> out.txt` produced a real, correct summary report end-to-end "
    "(package/pin/DRC/drill/connection statistics all present and accurate).",
    "celsius3d": "Confirmed live end-to-end against a real Cadence sample project on "
    "its FIRST run (share/PostInstallationCheck/celsius3d/case.3dth+case.tcl): "
    "`Celsius3D.exe -tcl case.tcl` exited 0, log showed 'Stress engine started and "
    "completed successfully!', and real numeric displacement/strain/stress results "
    "were written to case_Result_Summary.dat/.json in ~20-30s. IMPORTANT CAVEAT found "
    "via the multi-model eval harness (thermal_celsius3d_signoff task, both endpoints) "
    "and independently reproduced with a direct `timeout 20 Celsius3D.exe -tcl "
    "case.tcl` (exit 124): re-running against a project directory that already has a "
    "prior run's result folder (e.g. `<name>_SS_W/`) HANGS INDEFINITELY with an empty "
    "log — very likely a GUI overwrite-confirmation dialog, the same class of issue as "
    "Allegro/Capture's 'Product Choices' dialog. Always use a fresh copy of the project "
    "per run; never re-run in place. See celsius3d_tools.py's module docstring.",
    "celsiuscfd": "Confirmed live end-to-end against a real Cadence sample project on "
    "its FIRST run (share/PostInstallationCheck/celsiuscfd/pcb_pkg_sav.3dth+.tcl): "
    "`CelsiusCFD.exe -tcl pcb_pkg_sav.tcl` exited 0, log showed 'CelsiusECSolver is "
    "completed' and a real .cfd network file was generated. Not independently re-tested "
    "against an already-simulated project directory, but given Celsius3D's confirmed "
    "same-family hang in that scenario (see celsius3d's note), treat CelsiusCFD as "
    "likely subject to the same re-run-in-place risk until proven otherwise — use a "
    "fresh project copy per run.",
    "celsius2d": "Confirmed live against a real Cadence sample workspace "
    "(share/PostInstallationCheck/celsius2d/demo_sim.pdcx): `Celsius2D.exe -b -XIMSAVE "
    "-r demo_sim.pdcx` exited 0 with 'Simulation succeed' and full thermal+stress engine "
    "logs. A second sample (chip.pdcx) failed with a real domain-content error (an "
    "invalid referenced CFD file), not a launch/license/syntax failure — confirming "
    "errors surface as readable diagnostics rather than silently.",
    "allegro_dbdoctor": "Confirmed genuinely headless, no dialog: `dbdoctor.exe "
    "-check_only <real .brd sample>` ran a real orphan-record check end-to-end and "
    "reported its result ('1 warnings, 0 errors detected'). Note it exits non-zero "
    "(1) even for a clean check-only pass with only warnings — don't treat any non-zero "
    "return code from this tool as a hard failure without reading its output first.",
    "allegro_batch_drc": "Confirmed live against a real .brd sample on this machine: "
    "`batch_drc.exe -nographic <board>` exited 0 with 'Batch DRC checking done.'",
    "allegro_placement": "Confirmed live against a real .brd sample: `placement.exe "
    "<board> <out>` ran the genuine Allegro auto-place engine (real algorithm log with "
    "real weight/rotation parameters), but this specific sample board failed with "
    "'Error: No Package Keepin was found' — a board-authoring precondition (the board "
    "needs a defined placement keep-in area), not a wrapper or licensing problem. Retry "
    "against a board that already has a Package Keepin defined.",
    "allegro_ncroute": "Confirmed live against a real .brd sample: `ncroute.exe -o "
    "<out> <board>` exited 0 with 'Program completed. Done.'",
    "allegro_ipc2581_out": "Confirmed live against a real .brd sample: `ipc2581_out.exe "
    "-o <out> <board>` exited 0 with 'a2ipc2581 complete.'",
    "allegro_ipc356_out": "Confirmed live against a real .brd sample: `ipc356_out.exe "
    "<board> <out>` exited 0 with 'Successfully generated file'.",
    "allegro_step_out": "Confirmed live against a real .brd sample: `step_out.exe -o "
    "<out> <board>` exited 0 with 'step_out complete.'",
    "ibischk6": "Confirmed live: `ibischk6.exe <real .ibs sample>` ran and correctly "
    "found real syntax errors/warnings in the sample model, exiting with its own "
    "'File Failed' verdict — that's the checker doing its job on a model with genuine "
    "issues, not a tool failure. ibischk3/4/5 share the same binary family/CLI shape "
    "but were not independently run.",
    "allegro_checkplus": "Attempted live against a real shipped example project "
    "(tools/checkplus_exp/concept/examples/physical, which has its own cp.dat) — failed "
    "both as a bare directory path and would also fail as a raw .brd: checkplus prints "
    "`**Error! [5038] Project File '<value>' does not exist` and a `**Warning! [5015] "
    "Missing '<cwd>/checkplus/cp.dat'` that ignores -proj's value for that specific "
    "check. This means -proj resolves through some CDS project-registration convention "
    "(not a plain filesystem path) that wasn't isolated from the doc tree. Not a license "
    "or launch problem — the tool runs and prints real, readable diagnostics — but the "
    "correct project_file value for it is still unconfirmed.",
    "allegro_designextractor": "Attempted live: passing a raw .brd is confirmed rejected "
    "outright (immediate usage-banner re-print) — designextractor genuinely requires a "
    "populated .cpm/.sdax project file per its own -help text. No populated instance of "
    "either format was found on this machine (only unfilled @project@.cpm templates "
    "under share/cdssetup/pcbdw/workspaces/) to test end-to-end.",
    "abcd": "Confirmed via `abcd.exe -help`'s full self-printed usage banner (real "
    "flag names/semantics), but not run against real Touchstone files on this machine — "
    "no ready S-parameter file pair was on hand to test cascading/de-embedding "
    "end-to-end.",
    "bem2d3": "Confirmed via `bem2d3.exe -help`'s full self-printed usage banner (real "
    "flag names/semantics, tool's own banner still calls itself 'BEM2D2' internally), "
    "but not run against a real geometry input file on this machine.",
    "xcitepi": "Confirmed live end-to-end against a real Cadence sample "
    "(share/PostInstallationCheck/xcitepi/demo_decap.tcl + demo_decap.gds): "
    "`XcitePI.exe -b -tcl demo_decap.tcl` exited 0 and produced a real SPICE netlist "
    "(demo_decap.sp/_RLCK.sp) and IOME performance result "
    "(demo_decap_IOMESimResult.txt/.csv) via genuine `xpi_*` Tcl commands — a real full "
    "chip parasitic extraction ran to completion per its own engine log.",
    "optimizepi": "Confirmed live for OptimizePI.exe's own `-b -export_data` batch mode "
    "against a saved .opix workspace: using the complete real Cadence sample directory "
    "(share/PostInstallationCheck/optimizepi/), it fetched a license and reported "
    "'Simulation succeed', saving demo.spd. NOTE: this confirms the underlying "
    "OptimizePI.exe binary/license/batch-launch path works, but optimizepi_tools.py's "
    "own `sigrity::`-Tcl compose vocabulary (a different, session-based invocation "
    "style, `-b -tcl <script> -export_report`) was not independently re-run this same "
    "way — no Tcl-scripted sample shipped for OptimizePI to test that exact path "
    "against.",
    "xtractim": "Confirmed live end-to-end against a real Cadence sample "
    "(share/PostInstallationCheck/xtractim/Wirebond_EPA.ximx): `XtractIM.exe -b "
    "Wirebond_EPA.ximx` exited 0 and ran a genuine full-wave RLC extraction (real "
    "S600.2 solver engine log with frequency sweep, matrix size, and timing detail).",
    "dsn2spd": "Confirmed live against a real Cadence sample "
    "(share/Translators/Samples/Dsn2Spd/demo.dsn): `Dsn2Spd.exe -b demo.dsn demo.spd` "
    "exited 0, produced a real 723KB .spd file, and its own log itemized all 59 real "
    "components processed with no errors.",
    "t2b": "Attempted live against a real Cadence sample "
    "(share/SpeedXP/Samples/T2B/Example1/buffer.t2b + buffer.sp + hspice.mod): "
    "`T2B.exe -b buffer.t2b` genuinely launched, parsed the model, and dispatched real "
    "per-pin SPICE analysis jobs (rutout/rdtout/a00out/... .spi) — but every one aborted "
    "with 'Spice run (TYP) aborted.', ending in 'IBIS File Generation failed!'. T2B "
    "shells out to an external SPICE engine (HSpice, per the driver filenames and "
    "`hspice.mod` sample file) to characterize each buffer model — that engine is not "
    "installed/working on this machine. This is confirmed NOT a Cadence Sigrity license "
    "problem (T2B itself ran fine, no license-fetch failure) — it needs a working "
    "HSpice (or Cadence-integrated equivalent) install to actually produce output.",
    "spdsim": "Attempted live against a real Cadence sample "
    "(share/PostInstallationCheck/spdsim/ESD_testcase0.spd, a legacy SPEED2000-format "
    "text .spd): `SPDSIM.exe -b ESD_testcase0.spd` printed 'Skip license fetch' then "
    "'Failed to open the file ESD_testcase0.spd' despite the file existing at that exact "
    "path with the same byte size as the shipped original. Root cause not isolated — "
    "possibly this legacy text-format .spd needs a newer/converted form SPDSIM expects, "
    "or a working-directory/permissions quirk. Not a license issue ('Skip license "
    "fetch' suggests it didn't even get that far, or skipped it deliberately for this "
    "call shape) — needs further investigation with a different sample file.",
}


def get_tool_status(name: str) -> dict:
    status = TOOL_STATUS.get(name, "built_untested")
    return {
        "status": status,
        "description": STATUS_DESCRIPTIONS[status],
        "note": TOOL_STATUS_NOTES.get(name),
    }
