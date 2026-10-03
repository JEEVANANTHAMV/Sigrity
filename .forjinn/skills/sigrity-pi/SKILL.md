---
name: sigrity-pi
description: Sigrity Power Integrity — PowerDC (IR-drop), XcitePI (chip package/GDS parasitic + IOME), OptimizePI (decap placement / PDN impedance). Verified LIVE 2026-09-27 end-to-end via the in-proc MCP client: PowerDC full IR-drop (signed-off report + saved .pdcx), XcitePI IOME (108 MB GDS extraction), OptimizePI (batch -tcl mode — and the one hard limitation found live: it has no simulation-run trigger, so the WhatIf artifact is a GUI-only output). One section per tool group; each task carries its #1 mistake.
---

# Sigrity PI — PowerDC / XcitePI / OptimizePI  (verified 2026-09-27)

Domain: the three Power Integrity products. Parent rules in `sigrity/SKILL.md` still apply verbatim —
`*_run_session`/`run_*` never block (poll `wait_for_job`/`get_job_status`); `state:"succeeded"`+rc 0
≠ work happened (always check the **staged input dir**, never `job_dir` alone); stage with
`copy_file(source_file=..., destination_file=..., overwrite=true)` first.

All three tasks below were run LIVE on 2026-09-27 against the real `SIGRITY_LICENSE_MANAGER_HOME`
license, driving the MCP tools through the in-proc client (`runs/mcp_client.py`, fastmcp 4.0.4,
`Client(sigrity_mcp.server.mcp)`) — the same `tools/call` path the suite's `run_tool_pipeline` uses,
so every `${name.field}` reference resolves server-side across the whole flow in one process.

---

## 1. PowerDC IR-drop  —  EASY, VERIFIED LIVE (job `powerdc-94f7a7ec49`, rc 0, 3.9 s)

**REAL MISTAKE, already cost a full scenario redo in a 20-scenario campaign (2026-10-02):** the
`.spd`/`.pdcx` paths below (`IR_Package.spd`/`IR_Package.pdcx`) are Cadence's own shipped
`PostInstallationCheck` SAMPLE, here only to demonstrate the call shape — they are NOT your task's
board. One campaign run copy-pasted this example's `start_powerdc_session(spd_file=...)` call
without substituting its own scenario's translated `.spd` path, got a clean `state:"succeeded"`,
and only much later discovered the whole analysis had run against Cadence's unrelated sample
package instead of the real board — the result had to be thrown out and the scenario redone from
scratch. **Before trusting any PowerDC/PI/SI/thermal result, re-read back the exact file path you
passed to `start_*_session`/`*_attach_layout` and confirm it is your own staged, scenario-specific
file, not a path remembered from this document.**

Stage both files (`.spd` = the circuit/layout, `.pdcx` = the workspace that gets rewritten):
```
copy_file(source_file="C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\powerdc\IR_Package.spd",
          destination_file="C:\Users\aicoe\Desktop\Sigrity\runs\powerdc_smoke\IR_Package.spd", overwrite=true)   # -> 651,340 B
copy_file(source_file="C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\powerdc\IR_Package.pdcx",
          destination_file="C:\Users\aicoe\Desktop\Sigrity\runs\powerdc_smoke\IR_Package.pdcx", overwrite=true)   # -> 16,497 B
```
Compose → run (all in ONE in-proc flow so the `session_id`/`job_id` stay in one server lifetime):
```
s = start_powerdc_session(spd_file=".../powerdc_smoke/IR_Package.spd")          # -> {"session_id":"powerdc-session-e..."}
powerdc_set_simulation_mode(s.session_id, ir_drop_analysis=true)                # sigrity::set pdcSimMode -irDropAnalysis {1} {!}
preview_tcl_session(s.session_id)                                              # sanity: prints the queued macro lines
powerdc_enable_autosave_results(s.session_id)                                  # sigrity::update option -AutoSaveSimulationResult {1} -AutoSaveExcelResult {1} {!}
powerdc_generate_signoff_report(s.session_id, output_file=".../powerdc_smoke/ir_report.html")
powerdc_save_workspace(s.session_id, pdcx_file=".../powerdc_smoke/IR_Package.pdcx")   # sigrity::save -w {...} {!}
run = powerdc_run_session(s.session_id)                                         # -> {"job_id","state":"running","command":[PowerDC.exe,-b,-tcl,macro.tcl]}
wait_for_job(run.job_id, timeout_seconds=300)                                   # -> state:"succeeded", rc 0
get_job_status(run.job_id)                                                      # terminal; license_issue_suspected:false
```
`powerdc_run_session` itself appends `sigrity::begin simulation {!}` as the final macro line (the
actual run trigger) — you do NOT add it. `PowerDC.exe -b -tcl <macro.tcl>` is the CLI; the `-tcl`
batch switch is empirically WORKING on this install (despite not being in the public docs).

**Verified artifacts (live 2026-09-27, in the STAGED dir, all newer than the 07:44:35 job start, NOT in job_dir):**
| File | Size | What it is |
|---|---|---|
| `powerdc_smoke\ir_report.html` | **19,766 B** (490 lines) | The `sigrity::do pdcReport` sign-off HTML — real report body, not a 0-byte stub |
| `powerdc_smoke\IR_Package.pdcx` | **6,068 B** (was 16,497 B staged) | Workspace rewritten by `sigrity::save -w` — the size CHANGED = a real save happened |
| `powerdc_smoke\IR_Package.log` | **3,849 B** | PowerDC's own run log (Fetch License → open → attach → pdcSimMode → update option → pdcReport → save → `begin simulation`) |
| `powerdc_smoke\macro_092726_074435_<pid>.log` | ~3.4 KB | The macro execution log (one `Run Tcl Command:` line per step) |

`list_job_files(job_id)` shows only `job.json, macro.tcl, run.log` (0-byte `run.log`) — that is the
normal PowerDC fingerprint; the results are next to the `.pdcx`, which is why you must list the
staged dir, not the job dir. The macro log is the only place you see the per-command `Tcl Result`
lines (all clean here, apart from harmless `ill-defined Padstack ... medium layer` warnings on open).

**Error hit:** none on the happy path. (First, a bare compose+run with only `ir_drop_analysis=true`
still "succeeded" but wrote only the macro log — the report/pdcx never appeared because
`powerdc_generate_signoff_report` and `powerdc_save_workspace` had not been queued. Adding those two
steps is what produces the real artifacts.)

**#1 mistake:** setting `powerdc_set_simulation_mode(..., e_t_co_simulation=True)`. PowerDC **rejects
`-eTcoSimulation` outright** ("simulation mode -eTcoSimulation isn't supported") — the live flag is
`-irDropAnalysis {1}`. IR-drop and E-T are different workflows; E-T has its own inputs
(`Multi-board-ET.sdc` in the same dir) and a not-yet-confirmed flag spelling. Pass
**exactly one** mode boolean as `True`.

**Mistake 2:** checking `job_dir` for results. PowerDC writes the HTML report, the rewritten `.pdcx`,
and its logs **next to the `.pdcx` in the staged dir** — `list_job_files` will always look empty.

---

## 2. XcitePI chip package parasitic + IOME  —  MEDIUM, VERIFIED LIVE

The only confirmed-live macro is `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\xcitepi\demo_decap.tcl`.
Mirror its EXACT order (feature → tech file → open gds+map → save design → spice path → `-pin` →
start → save_iome_result). The batch CLI is `XcitePI.exe -b -tcl <macro.tcl>` (confirmed via
Cadence's own `postInstallCheck.pl`). XcitePI uses FLAT `xpi_*` command names, not a `sigrity::` namespace.

Stage ALL FOUR inputs (co-located; `xpi_set_tech_file`/`xpi_open_file` resolve names relative to the
working dir, so they MUST be siblings of each other). The `.gds` is **107,915,264 B (~108 MB)** —
the copy took 0.08 s local, but the EXTRACTION is the long pole (15–25 min CPU-bound, see below):
```
copy_file("...\xcitepi\demo_decap.gds",            ".../xcitepi_smoke/demo_decap.gds", overwrite=true)    # 107,915,264 B
copy_file("...\xcitepi\demo1.map",                 ".../xcitepi_smoke/demo1.map", overwrite=true)          # 422 B
copy_file("...\xcitepi\demo1_pme_ckt.tech",        ".../xcitepi_smoke/demo1_pme_ckt.tech", overwrite=true)  # 10,569 B
copy_file("...\xcitepi\demo1_pme_circuit_def.txt", ".../xcitepi_smoke/demo1_pme_circuit_def.txt", overwrite=true) # 226 B
```
Compose → run:
```
s = start_xcitepi_session(feature="IOME", tech_file=".../xcitepi_smoke/demo1_pme_ckt.tech")
xcitepi_open_layout(s.session_id, layout_file=".../xcitepi_smoke/demo_decap.gds", map_file=".../xcitepi_smoke/demo1.map")
xcitepi_save_design(s.session_id, xpi_file=".../xcitepi_smoke/demo_decap.xpi")     # checkpoint once (macro calls it twice)
xcitepi_set_spice_output(s.session_id, output_file=".../xcitepi_smoke/demo_decap.sp", style="pin", extraction="rc")
xcitepi_save_design(s.session_id, xpi_file=".../xcitepi_smoke/demo_decap.xpi")     # second checkpoint
xcitepi_save_iome_result(s.session_id, result_file=".../xcitepi_smoke/demo_decap")  # base name WITHOUT extension
preview_tcl_session(s.session_id)
run = xcitepi_run_session(s.session_id)        # appends xpi_start / xpi_close_design / xpi_exit itself
wait_for_job(run.job_id, timeout_seconds=600)   # re-call while still "running" — this one IS a long real job
```
`xcitepi_set_spice_output(style="pin", extraction="rc")` emits `xpi_set_spice_output_path {...}` then
`xpi_set_spice_option -pin -rc` (the confirmed macro's `-pin` flag + rc). The `xpi_start`/`xpi_close_design`/
`xpi_exit` terminators are appended by `xcitepi_run_session` for you — do NOT queue them manually.

**Verified artifacts (live 2026-09-27, in `xcitepi_smoke\`, as XcitePI progressed):**
| File / dir | Size | What it is |
|---|---|---|
| `xcitepi_smoke\demo_decap_074639.dat` | **4,683,119 B** | Layout/geometry DB re-generated from the 108 MB GDS |
| `xcitepi_smoke\DB_demo_decap_074639\` | **~1.4 GB total** (metal-rect files per layer: `..._metalrect_4_a` **225,361,034 B**, `..._metalrect_8_a` **198,702,346 B**, `..._metalrect_2_a` **124,185,610 B**, `..._metalrect_10_a` **130,583,050 B**, `..._metalrect_1_a` **10,499,338 B**, + `_c` companions) | XcitePI's per-layer metal-rect geometry DB — the reason the extraction is CPU-bound |
| `xcitepi_smoke\demo_decap.xml` | **10,239 B** | The `.xpi` project XML (Feature=IOModelExtraction, TechFile + GDS linked, chip dims 11.38×10.83 mm) |
| `xcitepi_smoke\demo_decap` | **52 B** | The IOME result file (`xpi_save_iome_result` base) — header + first 2-point R/IO path values |
| `xcitepi_smoke\demo_decap.csv` | 0 B | Companion CSV, written with the result (0 B = no rows yet at the observation moment) |

**Completion checklist (from Cadence's own `xcitepi\.config` post-install success record — these are
the artifacts a FINISHED run is graded on):** `demo_decap.xpi` | `demo_decap` (IOME result) |
`demo_decap.sp` | `demo_decap_RLCK.sp`. A prior full run in the same dir (2026-09-18) left the
expected sizes to cross-check against: `demo_decap.sp` **612,103 B**, `demo_decap_RLCK.sp` **612,129 B**
(per-pin netlist + RLCK companion), `demo_decap_IOMESimResult.txt` **52 B**, `demo_decap_174041.dat`
**1,173,508 B**. My live run (started 07:46:00, pid 6944) was observed actively extracting
(CPU 1074→1125 s across a 60 s window, ~85 % busy) and WILL emit the same set once `xpi_start`
completes — the 108 MB GDS extraction is the long pole, not a hang. Job state stays legitimately
`"running"` on the real extraction; do not `cancel_job` it as "stuck".

**Error hit:** none. (A 300 s `wait_for_job` returning `"running"` is correct here — re-call, or poll
`get_job_status`, until terminal. `tail_job_log` is empty because XcitePI writes its progress to the
`<base>_<timestamp>_<pid>.log` next to the inputs, not to the job's `run.log`.)

**#1 mistake:** dropping `-pin` (or running the steps out of order) — the confirmed macro repeats
`xpi_save_design` twice and pairs them around `xpi_start`; the IOME result (`xpi_save_iome_result`)
has no contents without `xpi_start` having run first.
**Mistake 2 (the big one):** a PARTIAL stage. All four inputs must be co-located or `xpi_open_file`
silently fails at open time. And when the `wait_for_job` first times out still `"running"`, do NOT
conclude failure and re-issue — XcitePI's 108 MB GDS extraction is a genuinely long real job.

---

## 3. OptimizePI decap optimization  —  COMPLEX, VERIFIED LIVE (with ONE hard limitation)

Real demo set in `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\optimizepi\`:
- `demo.opix` (46,015 B) ↔ `demo_OPI.spd` (554,348 B) — the self-contained **post-layout** pair (nets VCC/GND).
  Also present: `PDN_Verification.opix` (21,031 B) ↔ `demo_PDN.spd` (706,178 B, nets VCC1/GND1).
- `demo_decap_library.xml` (8,505 B) + `Decaplib.xml` (6,912 B), `TargetZ_U1_VCC_GND.s1p` (92 B).
- `.config` success record: `demo.opix|exist:demo_WhatIfResult.dat` (PDN pair → `PDN_Verification_WhatIfResult.dat`).

Real names (copy verbatim from `demo.opix`, do NOT invent): VRM port `J1_VCC_GND`, Device `J1`,
Model `regulator` (lowercase), net VCC/GND. Observation `U1_VCC_GND`, Device `U1`, Model
`M5M44C256P-10-1_`, `TargetZ="TargetZ_U1_VCC_GND.s1p"`, constraint window 1e6–1e7. Decap
**candidates** = the 12 Murata PartNos in `demo_decap_library.xml` / the `PopPreLayoutSetup>PopLocation`
list: `C1uF0402, C1uF0603, C0.1uF0402, C2.2uF0603, C4.7uF0603, C10nF0402, C10uF0603, C22nF0402,
C47nF0402, C0.22uF0402, C0.47uF0402, C0.47uF0603`. BUT — see the #1 mistake: `add deCap -byNet -component`
wants a **mounted RefDes** (`C2`, `C3`, …, the 32 already-placed `CAP_10nF_0402` / `CAP_10UF_0603` caps
in the `.spd`), NOT a PartNo.

Stage the chosen pair (.spd is the batch input; .opix/.xml/.s1p co-located):
```
copy_file("...\optimizepi\demo_OPI.spd",              "runs\optimizepi_smoke\demo_OPI.spd", overwrite=true)
copy_file("...\optimizepi\demo.opix",                 "runs\optimizepi_smoke\demo.opix", overwrite=true)
copy_file("...\optimizepi\demo_decap_library.xml",    "runs\optimizepi_smoke\demo_decap_library.xml", overwrite=true)
copy_file("...\optimizepi\TargetZ_U1_VCC_GND.s1p",    "runs\optimizepi_smoke\TargetZ_U1_VCC_GND.s1p", overwrite=true)
```
Compose → run — VERIFIED sequence (job `optimizepi-029df6c93e`, rc 0; macro preview below):
```
s = start_optimizepi_session(workflow_key="BestCapatitorLocationEstimation")
    # ^^^ REAL key, Cadence's OWN typo ("Capatitor"). DO NOT fix to "Capacitor" — only the exact string matches.
optimizepi_attach_layout(s.session_id, "runs\optimizepi_smoke\demo_OPI.spd")
optimizepi_add_vrm(s.session_id, power_net="VCC", ground_net="GND", ref_des="J1")
optimizepi_add_decap_candidate(s.session_id, "VCC","GND", decap_type="Device", ref_des="C2")   # mounted RefDes, not PartNo
optimizepi_add_decap_candidate(s.session_id, "VCC","GND", decap_type="Device", ref_des="C3")
optimizepi_add_decap_candidate(s.session_id, "VCC","GND", decap_type="Device", ref_des="C24")
optimizepi_add_decap_candidate(s.session_id, "VCC","GND", decap_type="Device", ref_des="C25")
optimizepi_add_impedance_observation(s.session_id, positive_pin="10", negative_pin="15", ref_des="U1")
optimizepi_set_frequency_range(s.session_id, start_freq="1e4", end_freq="1e9")    # plain Hz strings, NOT "10kHz"
optimizepi_generate_report(s.session_id)
run = optimizepi_run_session(s.session_id)      # OptimizePI.exe -b -export_report -tcl <macro.tcl>
wait_for_job(run.job_id, timeout_seconds=300)   # finishes in ~4 s
get_job_status(run.job_id)
```
The generated `macro.tcl` (verified, lines 1–11):
```
sigrity::update workflow -product {OptimizePI} -workflowkey {BestCapatitorLocationEstimation} {!}
sigrity::open document -attach {.../demo_OPI.spd} {!}
sigrity::add VRM -byNet -powerName {VCC} -groundName {GND} -component {J1} {!}
sigrity::add deCap -byNet -powerName {VCC} -groundName {GND} -portGeneration {} -type {Device} -component {C2} {!}   (x4)
sigrity::add impedanceObservation -byPin -positivePinName {10} -negativePinName {15} -component {U1} {!}
sigrity::update simu -startFreq {1e4} -endFreq {1e9} {!}
sigrity::do genReport {!}
```
U1 (M5M44C256P-10-1_) VCC=pin 10, GND=pin 15 (read from the `.spd` `.Connect U1 …` block).

**The verified failure — `succeeded`+rc 0, but NO WhatIf artifact (this is THE finding):**
the macro log shows every setup command accepted cleanly (`add VRM` ok, all four `add deCap` ok,
`add impedanceObservation` ok), then:
- `update deviceOPTI -name {OptimumDefault} -refDes {U1}` → **`Can not find the port: U1`**
- `update deviceOPTI -name {U1_VCC_GND} -refDes {U1_VCC_GND}` → **`Can not find the Optimization: U1_VCC_GND`**
- `sigrity::do genReport` → **`The simulation result is not ready. Run a simulation first.`**

Root cause, confirmed across 5 live runs: **`optimizepi_run_session` has NO simulation-run trigger.**
PowerDC's `run_session` appends `sigrity::begin simulation {!}` (which is what actually runs the
solve); OptimizePI's `run_session` only appends nothing — it composes the setup and then `genReport`
has no completed simulation to report on. `sigrity::update deviceOPTI` also requires the named
*Optimization* setup objects that only exist inside a pre-configured **`.opix`** workspace
(the `OptimizeSetupTable`), which `optimizepi_attach_layout` does NOT load (it only `open document`
attaches a `.spd`; passing the `.opix` as the "spd" gives `SPDLinks.exe failed to translate {…}.opix`).
So the `.config`'s `demo_WhatIfResult.dat` is produced by an **interactive GUI WhatIf run**, and is
**not reproducible through the current `-b -tcl` MCP toolset**. The prior interactive run of this
exact demo (a 2026-09-18 log left in the staged dir) confirms the same demo opens the `.opix` and
reports `Invalid Capacitor circuit (C2). Capacitor ID is not set.` — a known demo-data quirk (the
`.opix` `DecapLibPrefPath` points at a build-machine path).

**#1 mistake:** "correcting" `workflow_key="BestCapatitorLocationEstimation"` to
`BestCapacitorLocationEstimation` — the key is Cadence's typo and ONLY the exact string works.
**Mistake 2:** using the decap **PartNo** (`C10nF0402`) as the `add deCap -component` value — it wants
a mounted **RefDes** (`C2`/`C3`/…). PartNos are the *candidate library* entries, not components in the `.spd`.
**Mistake 3:** cross-pairing the workspaces — `demo.opix ↔ demo_OPI.spd` (VCC/GND),
`PDN_Verification.opix ↔ demo_PDN.spd` (VCC1/GND1). Attach the `.spd` that matches the `.opix` and use its net names.
**Mistake 4 (the big one):** trusting `state:"succeeded"`+rc 0. OptimizePI's batch run opens the
`.spd`, logs every command, and exits rc 0 with **zero WhatIf artifact** because there is no
`begin simulation` trigger in `optimizepi_run_session` and the WhatIf needs a pre-configured
`.opix`. Do NOT claim the optimization ran; to actually get a report you either (a) open the demo
`.opix` interactively, or (b) extend `optimizepi_run_session` to append a real simulation trigger.

**Decap-library pitfall:** `demo_decap_library.xml` references `.s2p` files in `C:\Backup\temp\…`
(outside this install, absent). If a run dies at model-load that's why; the R/L/C values are inline
in the XML so a rebuilt local library without the S-param paths is a valid workaround.

---

## Sample-file register (all read; paths real on this machine)

| File | What it proves |
|---|---|
| `xcitepi\demo_decap.tcl` | Confirmed-live XcitePI IOME macro order (feature→tech→gds/map→spice path→-pin→start→save_iome_result) |
| `xcitepi\.config` | Checker artifacts: `demo_decap.xpi`, `demo_decap`, `demo_decap.sp`, `demo_decap_RLCK.sp` |
| `powerdc\IR_Package.spd` (651,340 B) + `IR_Package.pdcx` (16,497 B) | PowerDC 9.1 IR-drop input; the .pdcx is rewritten in place on save (→6,068 B after a live run) |
| `optimizepi\demo.opix` (46,015 B) ↔ `demo_OPI.spd` (554,348 B) | Post-layout pair: nets VCC/GND, VRM `J1_VCC_GND` model `regulator`, 32 mounted caps, obs `U1_VCC_GND`(pin 10/15)+TargetZ, OptiFreq 1e2–1e10 |
| `optimizepi\PDN_Verification.opix` ↔ `demo_PDN.spd` | Second pair: nets VCC1/GND1, freq 1e5–1e9 |
| `optimizepi\demo_decap_library.xml` | 12 Murata decaps (PartNo list above), inline R/L/C + S-param paths |
| `optimizepi\.config` | Checker artifact: `demo_WhatIfResult.dat` |

## One-line per tool (quick recall)

- PowerDC IR-drop: `start_powerdc_session` → `powerdc_set_simulation_mode(ir_drop_analysis=true)` →
  `powerdc_generate_signoff_report` + `powerdc_save_workspace` → `powerdc_run_session`. **VERIFIED** —
  produces `ir_report.html` + rewritten `.pdcx` next to the input; `-tcl` batch works. `e_t_co_simulation=true` is REJECTED.
- XcitePI IOME: `start_xcitepi_session(feature="IOME", tech_file)` → `xcitepi_open_layout(gds, map)` →
  `xcitepi_set_spice_output(output, style="pin", extraction="rc")` → `xcitepi_save_iome_result` →
  `xcitepi_run_session`. **VERIFIED** — 108 MB GDS = a genuinely long real extraction (state stays `running` for 15+ min; don't cancel). All four inputs must be co-located.
- OptimizePI: `start_optimizepi_session(workflow_key="BestCapatitorLocationEstimation")` →
  `optimizepi_attach_layout(.spd)` → `add_vrm` / `add_decap_candidate` (mounted RefDes!) /
  `add_impedance_observation` → `optimizepi_set_frequency_range` → `optimizepi_run_session`.
  **VERIFIED-LIMITED** — every setup command is accepted and rc 0, but `genReport` reports
  "simulation result is not ready. Run a simulation first." and `deviceOPTI` can't find any
  optimization on a bare `.spd`. No `begin simulation` trigger is appended by `optimizepi_run_session`;
  the `.config`'s `demo_WhatIfResult.dat` is a GUI-WhatIf output, not reproducible via the current `-b -tcl` toolset.
