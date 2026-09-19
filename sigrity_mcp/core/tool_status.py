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
    "allegro_artwork": "confirmed_live",
    "allegro_gbplot": "built_untested",
    "allegro_designextractor": "known_blocked",
    "allegro_zrouter": "known_blocked",
    "allegro_diacheck": "built_untested",
    "allegro_diacompare": "built_untested",
    "con2xml": "known_blocked",
    "cap2xml": "known_blocked",
    "dml2con": "known_blocked",
    "apd2con": "known_blocked",
    "abcd": "known_blocked",
    "bem2d3": "built_untested",
    "xcitepi": "confirmed_live",
    "optimizepi": "confirmed_live",
    "xtractim": "confirmed_live",
    "dsn2spd": "confirmed_live",
    "spdsim": "known_blocked",
    "t2b": "known_blocked",
    "spif_batch": "confirmed_live",
    "specctra": "confirmed_live",
    "psp_cmd": "confirmed_live",
}
# NOTE: allegro_constraint_tools.py's and allegro_geometry_tools.py's individual SKILL
# calls all execute through the single "allegro" logical tool above (same session/
# process mechanics) — their own per-call reliability is finer-grained than this
# executable-keyed dict models, so it's documented in the "allegro" note below instead
# of as separate top-level entries here.

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
    "still technically unverified individually. FURTHER RESULTS from "
    "allegro_constraint_tools.py/allegro_geometry_tools.py, tested both directly and "
    "via two independent LLM-driven runs (both configured endpoints): "
    "`allegro_set_spacing_constraint`/`allegro_set_physical_constraint` "
    "(axlCNSSetSpacing/axlCNSSetPhysical) and `allegro_create_via` (axlDBCreateVia) all "
    "ran cleanly to completion (returncode 0, no hang) in every one of 3 independent "
    "live runs (1 direct + 2 LLM-driven) when combined with axlSaveDesign in the same "
    "session -- promoted to confirmed_live for the session-mechanics/no-hang claim "
    "(whether the constraint/via values landed exactly as specified was not separately "
    "verified by reading the modified board back, only that the session ran and exited "
    "cleanly). `allegro_assign_net` (axlDBAssignNet via a `(car (axlSelectByName ...))` "
    "resolver) was PREVIOUSLY (wrongly) reported here as known_blocked, based on a test "
    "where the session ran for several minutes with no save landing on disk. RE-TESTED "
    "this pass, run cleanly one Allegro launch at a time (the earlier long-running "
    "symptom turned out to be a self-inflicted artifact of firing off several "
    "overlapping diagnostic sessions at once, competing for a limited license seat -- "
    "not a bug in the SKILL call itself, the same class of false negative as the "
    "original axlDBCreateNet block): three independent live confirmations against fresh "
    "copies of the real sample board -- (1) a hand-written SKILL macro resolving "
    "R1.2/GND via axlSelectByName and calling axlDBAssignNet directly, (2) the exact "
    "production allegro_assign_net/allegro_save_design/allegro_run_session tool "
    "functions unmodified, and (3) independently re-reading the saved board with "
    "report.exe (bypassing SKILL entirely) both before (pristine board: "
    "'N00885,R1.2 R4.1 U1.1 U3.3') and after ('GND,...R1.2...' / 'N00885,R4.1 U1.1 U3.3' "
    "-- R1.2 genuinely moved nets on disk). PROMOTED to confirmed_live -- net "
    "reassignment via this tool is real and does persist. Also tested: Allegro's native "
    "`auto_route` Command:-prompt command "
    "(not SKILL -- the officially documented single-command SPECCTRA round-trip driver, "
    "`doc/algroroute/chap12.html`) as a possible fix for spif_batch -i's crash -- it "
    "also failed, with a crash-style negative return code, so this is not a working "
    "alternative either.",
    "capture": "FOLLOW-UP THIS PASS: a live user report of a real modal 'overwrite?' "
    "dialog needing a manual click, while re-running one of this suite's own diagnostic "
    "scripts, led to root-causing a genuine, previously-misdiagnosed failure mode: a "
    "`.lck` file left behind by a prior batch job that was killed (rather than exiting "
    "cleanly) causes the NEXT launch against that same design path to block forever on "
    "an interactive 'already open/locked, override?' dialog with zero console output — "
    "this was previously misread as a generic hang or license-fetch delay. Fixed via "
    "`clear_stale_design_lock`, now called automatically in `start_capture_session` "
    "(and `allegro_run_session`) before launch — proven live for Allegro: a planted "
    "fake stale lock was auto-cleared and the job completed in 5.3s instead of hanging. "
    "RE-TESTED Capture specifically with this fix in place, 3 clean runs in a row "
    "(fresh project-directory copy per run, to fully rule out lock confusion between "
    "runs): still genuinely non-deterministic — run 1 hung the full 90s wait with an "
    "empty log (had to be killed), runs 2 and 3 both reported 'succeeded' but in a "
    "suspicious 0.1s with a completely empty run.log, which is far too fast for a real "
    "open+script+close+exit cycle and matches this module's previously-documented "
    "'exits immediately with no output' failure mode rather than confirming real work "
    "happened. CONCLUSION: the stale-lock fix is real and directly proven for Allegro, "
    "and may explain some fraction of Capture's past non-determinism, but does NOT "
    "fully resolve it — something else about Capture's batch invocation remains broken "
    "or unconfirmed. Remains known_blocked; do not treat a fast 'succeeded' state alone "
    "as evidence the script's actual content (place parts, save, etc.) ran — check for "
    "real output/log content, not just the return code. Initially hit the same-looking 'Product Choices' dialog as allegro; "
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
    "separate, still-unresolved issue. RE-TESTED AGAIN with a full 5-minute wait "
    "(instead of 60s) specifically to allow time for a possible one-time approval "
    "dialog to be clicked through manually -- result was inconsistent across repeated "
    "attempts: one run completed cleanly in ~3.2s (open+save+close+exit, returncode 0), "
    "but the very next fresh attempt hung with an empty log for the full 5 minutes "
    "and had to be killed again. This confirms the original 'inconsistent behavior' "
    "characterization precisely -- it is not a simple one-time dialog that, once "
    "accepted, permanently fixes every subsequent run (unlike allegro.exe's product-"
    "chooser dialog, which really was one-time). Treat capture_run_session as "
    "genuinely non-deterministic on this machine, not reliably blocked or reliably "
    "working.",
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
    "allegro_zrouter": "INVESTIGATION EXHAUSTED this pass, CONFIRMED genuinely GUI-only "
    "-- demoted from built_untested to known_blocked, and `run_allegro_zrouter` now "
    "refuses to run rather than fabricate success. Three paths tried: (1) bare standalone "
    "`zrouter.exe` (the tool's original design) confirmed live to hang indefinitely -- "
    "it opens a modal GUI form with no CLI usage text, had to be killed; (2) the native "
    "`zrouter <control_file>` Command:-prompt command inside a batch Allegro session "
    "(the same mechanism auto_route uses) confirmed live to return cleanly (rc=0) but do "
    "NOTHING -- no Zrouter.log, no via created, board file unchanged -- a dangerous "
    "false-positive, not a working path; (3) `doc/zcoms/zchap.html`'s own \"Running "
    "zrouter\" section resolves why: it documents a strictly 5-step interactive GUI "
    "workflow (typing `zrouter` only OPENS the dialog; the connections-file/grid/via "
    "values must be typed into dialog fields and Run clicked manually) with no "
    "command-line or SKILL equivalent anywhere in the doc tree or the ~840-file SKILL "
    "function reference. A real Connections Control File grammar WAS confirmed and "
    "authored from that same doc section (see allegro_placement_tools.py's module "
    "docstring) but there is no way to feed it to zrouter non-interactively.",
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
    "spif_batch": "MAJOR CORRECTION to earlier research, which wrongly concluded no "
    "general trace-autorouting automation surface exists on this installation. "
    "`spif_batch.exe -o <board> <dsn>` (Allegro -> SPECCTRA .dsn export) is confirmed "
    "live: a real ~85KB .dsn was produced from a real sample board. `spif_batch.exe -i "
    "<board> <session.ses>` (importing a routed session back into Allegro) is "
    "confirmed BROKEN on this machine: it crashes every time with `ERROR(SPMHDB-238): "
    "The design is corrupted...` plus a real crash-dump file, reproduced identically "
    "in multiple directories/filenames — root cause not isolated (the error text's own "
    "stated cause, an ASCII-mode cross-platform copy, did not occur here). Treat the "
    "export direction as reliable and the import direction as known_blocked until this "
    "is root-caused. See spif_specctra_tools.py's module docstring.",
    "specctra": "MAJOR CORRECTION to earlier research (see spif_batch's note): "
    "`specctra.exe <dsn> -nog -do <script>.do -quit` (Cadence's real, fully headless, "
    "SPECCTRA-based PCB autorouter) is confirmed live TWICE — against Cadence's own "
    "shipped tutorial design (100% connected, 0 conflicts) and against this suite's own "
    "real sample board (75 nets, 163 connections, 100% connected, 0 conflicts, real "
    ".ses session file written), both via the actual MCP tool wrapper "
    "(run_specctra_autoroute), not just raw CLI. Note it returns a nonzero exit code "
    "(confirmed: 4) even on a fully successful route — read final.sts/route.sts for "
    "real completion statistics rather than trusting the return code alone.",
    "psp_cmd": "MAJOR CORRECTION to earlier research, which classified PSpice as "
    "GUI-only after `pspice.exe`/`pspiceaa.exe` both hung on `-help`. `psp_cmd.exe` is "
    "a separate, dedicated batch-simulation executable in the same tools/bin, "
    "confirmed live: a bare invocation prints 'Missing circuit file argument' and "
    "exits immediately (no hang), and running it against a real shipped OrCAD PSpice "
    "sample genuinely loaded and attempted simulation, failing only on that sample's "
    "own portability issue (a missing .include file from the original authoring "
    "machine) with a specific, readable diagnostic.",
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
    "spdsim": "ROOT CAUSE FURTHER NARROWED: tried both the original `-b` flag AND the "
    "`-as`/`-spice -run` flags documented in `doc/psi_ug/"
    "ch10_tcl_re_Calling_SPDSIM_in_PowerSI_Commands.html` (a page titled 'Invoke "
    "Subprocesses', describing SPDSIM as something PowerSI's own Tcl `exec` command "
    "launches) — both flag styles produced the identical 'Skip license fetch' then "
    "'Failed to open the file' failure, against TWO different real samples (the legacy "
    "PostInstallationCheck ESD_testcase0.spd AND a modern PowerSI 3D-EM sample, "
    "diff_via.spd). The consistent 'Skip license fetch' message (never seen on any "
    "other confirmed-working tool in this suite) plus the doc page's own framing "
    "strongly suggests SPDSIM.exe is designed to run only as a genuine child process "
    "spawned by a live PowerSI Tcl session (inheriting some license/IPC context a "
    "freshly-launched standalone process doesn't have) — not really an independently "
    "callable batch tool despite living in tools/bin and accepting CLI flags. A real "
    "fix would mean driving it via `sigrity::do exec \"...spdsim.exe\" -as \"file.spd\" "
    "&` INSIDE a PowerSI Tcl session (powersi_tools.py) rather than as its own "
    "submit_job call — not yet implemented.",
    "abcd": "ATTEMPTED LIVE against three different real Touchstone file combinations "
    "(two 4-port .s4p files cascaded — segfaulted, exit 139; a single 2-port capacitor "
    ".s2p with -tsfile alone — silent no-op, no output, no error; two 2-port capacitor "
    ".s2p files cascaded via -lefttsfile/-righttsfile, both relative and absolute "
    "-filepath — also silent no-op). Demoted from built_untested to known_blocked: "
    "confirmed real via -help, but every real invocation tried either crashed or did "
    "nothing, with zero diagnostic output either way — root cause not isolated, "
    "possibly a frequency-grid/port-count compatibility requirement between the files "
    "that isn't obvious from the tool's own error reporting (which in this case is "
    "simply absent).",
    "allegro_checkplus": "SCOPE CORRECTION: `doc/checkplus/chap2.html`'s own title is "
    "'Setting Up Allegro Design Entry HDL Rules Checker' — checkplus is a rules "
    "checker for Design Entry HDL / Concept-HDL (a separate, legacy Cadence SCHEMATIC "
    "tool), not for Allegro PCB `.brd` physical layouts at all. Its `-proj` argument is "
    "a DE-HDL project reference, not anything resolvable from a `.brd` or a plain "
    "directory path — this fully explains the earlier 'Project File does not exist' "
    "result and means this tool is likely not applicable to a Capture-based (not "
    "DE-HDL-based) design flow at all, independent of the project-reference-format "
    "question.",
    "allegro_gbplot": "ROOT CAUSE FOUND AND FIXED this pass: `doc/gcoms/gchap.html` "
    "documents the real syntax as `gbplot artwork_file_name [penplot_file_name] "
    "[-version]` — it takes an ALREADY-GENERATED Gerber `.art` artwork file, not a "
    "`.brd` directly (confirmed live: passing a `.brd`, as `run_allegro_gerber_plot` "
    "originally did, fails immediately with 'gbplot: Error opening parameter file.'). "
    "`run_allegro_gerber_plot` is now corrected to take an `artwork_file` argument (the "
    ".art output of `run_allegro_generate_artwork`, see `allegro_artwork` below) instead "
    "of a board file. Upgraded from known_blocked to built_untested — the fix is "
    "confirmed correct per the doc's own syntax, but gbplot itself (a legacy "
    "pen-plotter-format converter, not needed for standard Gerber/RS274X consumers) "
    "was not independently re-run against a real .art file this pass.",
    "allegro_artwork": "NEW this pass, CONFIRMED LIVE end-to-end — this is the real fix "
    "for Gerber export, which `allegro_gbplot` alone could never provide (see its own "
    "note). `artwork.exe` has a full, real `-help` usage banner ('Generates Gerber "
    "films from Allegro designs'); `-l <board>` lists film records already defined. The "
    "missing piece was authoring those film records at all — Allegro's Artwork Control "
    "Form normally does this interactively, but the real documented SKILL equivalent, "
    "`axlFilmCreate` (now wrapped as `allegro_create_film` in allegro_geometry_tools.py), "
    "does it headlessly. Full pipeline confirmed live THREE times against fresh copies "
    "of the real sample board, including once through the exact unmodified production "
    "tool functions (allegro_create_film -> allegro_save_design -> allegro_run_session "
    "-> run_allegro_generate_artwork): defining ETCH/TOP and ETCH/BOTTOM films, saving, "
    "then running `artwork.exe <board>` produced real `TOP.art` (12225 bytes) and "
    "`BOTTOM.art` (6052 bytes) files in genuine RS274X Gerber format (verified file "
    "content: 'G04 File Format: Gerber RS274X', real layer/offset/rotation records). "
    "NOTE: artwork.exe exits 1 ('ARTWORK had warnings') even on this fully successful "
    "run — the warnings ('Can't open parameter file ... using default values', "
    "'Photoplot outline rectangle not found; using drawing extents') are the tool "
    "falling back to sane defaults, not errors — read photoplot.log/check for the "
    "actual .art files before treating a nonzero exit as failure.",
}


def get_tool_status(name: str) -> dict:
    status = TOOL_STATUS.get(name, "built_untested")
    return {
        "status": status,
        "description": STATUS_DESCRIPTIONS[status],
        "note": TOOL_STATUS_NOTES.get(name),
    }
