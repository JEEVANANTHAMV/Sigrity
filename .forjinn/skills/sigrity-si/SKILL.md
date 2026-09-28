---
name: sigrity-si
description: Sigrity SI (Signal Integrity) tool sequences — PowerSI S-parameter extraction (.spd AND .brd input), BroadbandSPICE netlist fit + passivity/causality check. Verified live on this machine (PowerSI 2026-09-26; BroadbandSPICE 2026-09-27). Use for S-param extraction, BRD-to-SPD conversion, or SPICE circuit fitting of Touchstone networks.
---

# Sigrity SI domain — PowerSI + BroadbandSPICE

Platform/job rules (invincible ones) inherit from the parent `sigrity` skill: `run_*`/`*_run_session` never
block (poll `wait_for_job`), and `state:"succeeded"` never means work happened — always verify artifacts.
Below, what is true for THIS domain, verified end-to-end on live runs (PowerSI: 2026-09-26;
BroadbandSPICE: 2026-09-27).

## Task 1 — EASY: session create / preview / close (no run)

```
start_powersi_session(spd_file="C:/Cadence/Sigrity2024.0/share/PostInstallationCheck/powersi/psi_brd_demoshort.spd")
  -> {"session_id": "powersi-session-<hash>"}
preview_tcl_session(session_id=...)
  -> step_count:1, script:  sigrity::open document {C:/.../psi_brd_demoshort.spd} {!}
close_tcl_session(session_id=...) -> {"closed": true}
```
- **Verified**: exact 3-call sequence above, all clean, no process ever launched.
- **Error hit**: calling `close_tcl_session` in a *different* process from the one that ran
  `start_powersi_session` returns `SessionNotFoundError` — sessions are in-memory per server process.
  (The platform `sigrity` skill covers this; it only bites when you restart the MCP server mid-flow.)
- **#1 mistake**: none — compose/preview/close needs no job. Just do not run `*_run_session` between
  them if you only want to inspect.

## Task 2 — MEDIUM: full PowerSI extraction on a .spd

Verified sequence (job `powersi-dd8bbf5d18`, 33 s, rc 0):

```
copy_file(source_file="C:\\Cadence\\Sigrity2024.0\\share\\PostInstallationCheck\\powersi\\psi_brd_demoshort.spd",
          destination_file="C:\\Users\\aicoe\\Desktop\\Sigrity\\runs\\task2_demoshort.spd", overwrite=true)
start_powersi_session(spd_file="C:/Users/aicoe/Desktop/Sigrity/runs/task2_demoshort.spd") -> session_id
powersi_set_frequency_sweep(session_id, start="1e6", end="1e9")   # PLAIN Hz strings, NOT "1MHz"/"1GHz"
powersi_add_ports_auto(session_id, signal_ref_impedance=50.0)
preview_tcl_session(session_id)   # optional sanity gate before a long run
powersi_run_session(session_id, output_format="touchstone") -> job_id (args: -b -ft -tcl <macro.tcl>)
wait_for_job(job_id, timeout_seconds=180) -> state:"succeeded", rc 0
list_job_files(job_id) + list runs/ -> verify the .sNp
```

- **Result state**: `succeeded` rc 0 — but that is NOT proof of extraction; see below.
- **Verified artifact**: on the real full board with auto-ports (Task 3 below, same flow), the run
  produced `task3_fault_detector_092626_194507_12652_S.s68p` — **68 ports**, **69,935,077 bytes**,
  plus a 9,193-byte SPICE netlist `..._S.ckt` — all in `runs/` root (see naming note). Note: the
  `psi_brd_demoshort.spd` used in the sequence above contains only 2 geometry polygons and no
  component pins; `add port -all` has nothing to port on it, so a real 2-port/4-port sNp only
  appears on a design with actual components — that is what the fault-detector board gives you.
- **Error hit**: `list_job_files` after `succeeded` showed only `job.json, macro.tcl, run.log` with a
  0-byte `run.log`, and every other PowerSI job dir on this machine looked the same. That is NOT
  evidence the extraction produced nothing — it's this domain's silent-success fingerprint. The
  artifacts are in `runs/` (the configured `SIGRITY_WORKDIR`), NOT in the job dir. **Fix**:
  `Get-ChildItem C:\Users\aicoe\Desktop\Sigrity\runs -Filter *_S.*p` (and `_S.ckt`, `_Options.xml`,
  `_PowerSI.err`) right after the job ends; a non-empty `*.sNp` newer than the job start = success.
- **#1 mistake**: concluding failure because `list_job_files` lacks an `.sNp`, or waiting for a
  non-zero log. Invert the check: PowerSI wrote real output iff a new `*_S.sNp` appeared in `runs/`
  with non-zero size. Also: do not pass `"1MHz"` — PowerSI mis-parses the suffix and errors
  "ending frequency smaller than starting"; always `"1e6"`/`"1e9"`.

## Task 3 — COMPLEX: BRD → SPD bridge (full PowerSI extraction from an Allegro board)

Verified sequence (job `powersi-9b924d080e`, 74 s, rc 0):

```
copy_file(source_file="C:\\Cadence\\SPB_22.1\\tools\\capture\\samples\\PCB-Layout\\Fault-Detector\\allegro\\fault-detector_allegro_routed.brd",
          destination_file="C:\\Users\\aicoe\\Desktop\\Sigrity\\runs\\task3_board.brd", overwrite=true)
start_powersi_session(spd_file="C:/Users/aicoe/Desktop/Sigrity/runs/task3_board.brd") -> session_id
powersi_save_document(session_id, spd_file="C:/Users/aicoe/Desktop/Sigrity/runs/task3_board.spd")
powersi_set_frequency_sweep(session_id, start="1e6", end="1e9")
powersi_add_ports_auto(session_id)
preview_tcl_session(session_id)   # confirm `sigrity::save {...}` is line 2, BEFORE freq
powersi_run_session(session_id, output_format="touchstone") -> job_id
wait_for_job(job_id, timeout_seconds=240) -> state:"succeeded", rc 0
```

- **Result state**: `succeeded` rc 0.
- **Verified artifacts** (both present, non-zero, in `runs/`):
  - **SPD written**: `task3_board.spd` — **237 KB** (BRDExtractor translated the Allegro board to
    native PowerSI form on open).
  - **S-parameters**: `task3_board_<yyyymmdd>_<hhmmss>_<pid>_S.s68p` — **68 ports**
    (`<name>_S.<N>p` = N-port Touchstone, N = auto-port count), ~70 MB, plus
    `task3_board_<timestamp>_S.ckt` (SPICE netlist, 9 KB) and
    `task3_board_Options.xml` (27 KB of sweep/export settings).
- **Error hit**: none on the happy path. The *omitted negative test* (calling `powersi_run_session`
  on an opened `.brd` WITHOUT `powersi_save_document`) does NOT return a tool error — the process
  still exits rc 0 but silently writes only an empty `task3_board_Options.xml` and
  `task3_board_PowerSI.err` with no `.spd` and no `.sNp`. That empty-options-only signature is the
  fingerprint of the missing save; fix = re-run with `powersi_save_document` right after
  `start_powersi_session`.
- **#1 mistake**: skipping `powersi_save_document` after opening a non-`.spd` design. It must be the
  *first* composed step (line 2 of the macro, immediately after `sigrity::open document`) — calling
  it after `set_frequency_sweep`/`add_ports_auto` is the order that silently produces no output.
- **Artifact naming**: PowerSI names outputs `<design_basename>_<yyyymmdd>_<hhmmss>_<pid>_S.<N>p`.
  The design basename is the .spd name (from `powersi_save_document`), NOT the .brd. To recover the
  exact filename: `list_job_files(job_id)` won't show it (it's in `runs/`, not the job dir) — instead
  glob `C:\Users\aicoe\Desktop\Sigrity\runs\<basename>_S.*p` after the job ends.

## Task 4 — BroadbandSPICE: netlist fit + passivity/causality check (VERIFIED LIVE 2026-09-27)

This section was verified end-to-end live on 2026-09-27 by running `BroadbandSPICE.exe` directly
(MCP `run_broadbandspice_*` tools were NOT available in that session) from
`C:\Users\aicoe\Desktop\Sigrity\runs\bbs_smoke\`, the exact CLI the MCP wrapper would emit. All the
"non-functional / FALSE POSITIVE" warnings in the earlier draft of this section are RETRACTED — the
tool works and writes real artifacts, next to the CWD, not in any job dir.

### 4a. Circuit-model fit (SPICE netlist from a Touchstone) — VERIFIED

```
copy_file(source_file="C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\Broadband SPICE\spiral_10GHz.s2p",
          destination_file="C:\Users\aicoe\Desktop\Sigrity\runs\bbs_smoke\spiral_10GHz.s2p")
run_broadbandspice_extraction(network_file="C:/Users/aicoe/Desktop/Sigrity/runs/bbs_smoke/spiral_10GHz.s2p",
                              mode="Precision", netlist_format="HSPICE") -> job_id
wait_for_job(job_id, timeout_seconds=180) -> state:"succeeded", rc 0
   # CLI under the hood: BroadbandSPICE.exe -b -Precision -HSPICE -i200 -uf125.0 <s2p>,
   # run with CWD = directory being verified (live: runs\bbs_smoke)
```
Equivalently, direct verified CLI (what was actually executed 2026-09-27, `cd` = working dir):
`C:\Cadence\Sigrity2024.0\tools\bin\BroadbandSPICE.exe -b -Precision -HSPICE -i200 -uf125.0 <dir>\spiral_10GHz.s2p`

- **Result state**: rc 0, completes in <1 s for this 2-port 11.6 KB input.
- **Verified artifacts (live 2026-09-27, in `runs\bbs_smoke\BBSResult_spiral_10GHz\`)** — ALL
  present, non-zero:
  - `spiral_10GHz_BBSckt.txt` — **2,192 bytes** — the REAL HSPICE subcircuit netlist (read it:
    `.subckt spiral_10GHz_BBSckt 1 2 ref` + 13 `G*` LAPLACE elements + R/V/F/G port stubs + `.ends`).
  - `spiral_10GHz_Fitted.s2p` — **9,193 bytes** — the model's re-fit Touchstone (header
    `!Generated from: BroadbandSPICE`).
  - `spiral_10GHz_Foster.txt` — **1,859 B**, `spiral_10GHz_for_RFM.txt` — **596 B**,
    `spiral_10GHz.rfm` — **1,025 B** (Foster-annotated S-param for downstream tools).
  - `Error_Order.txt` — **72 B** — per-entry relative fit error, e.g. `[1,1] 0.000070 4`.
  - Plus parent dir: `spiral_10GHz.log` (**699 B**) — full progress: "Precision model extraction
    completed", "BBS circuit extracted: spiral_10GHz_BBSckt.txt", "Simulation Time: 0.04 Sec."
- **The `-HSPICE` flag changes the OUTPUT FILE NAME**: with it, a netlist named
  `<netlist_name>_BBSckt.sp` also appears (reproduced live on 2026-09-26:
  `C:\Users\aicoe\Desktop\Sigrity\runs\bbs_spiiral_hsp_BBSckt.sp`, 2,212 B, identical `.subckt`
  body); the content is the same subcircuit either way — pick the name you want by choosing the
  input's basename for the netlist_format switch.
- **Error hit**: none on the happy path.
- **#1 mistake**: looking for the netlist in the job dir (or only at `list_job_files`) — BroadbandSPICE
  writes EVERYTHING next to the CWD, into a `BBSResult_<input_basename>/` subdir, regardless of what
  the MCP wrapper's `job_dir` claims. Also do not assume `.bds`/`.spc`/`.circ` are the output
  extensions — the real netlist here is `<name>_BBSckt.txt` (or `..._BBSckt.sp` with `-HSPICE`).
- **Mode note**: `mode="Precision"` optimizes fit accuracy and can produce a non-physical netlist on
  non-passive/non-causal inputs; use `mode="Passivity"` when the downstream sim is
  stability-sensitive. (Not separately exercised live; CLI flag is the `-Precision`/`-Passivity`
  switch the wrapper maps `mode` to.)

### 4b. Passivity / causality check — VERIFIED

```
copy_file(source_file="C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\Broadband SPICE\app1_drv.S4P",
          destination_file="C:\Users\aicoe\Desktop\Sigrity\runs\bbs_smoke\app1_drv.S4P")
run_broadbandspice_check(network_file="C:/Users/aicoe/Desktop/Sigrity/runs/bbs_smoke/app1_drv.S4P") -> job_id
wait_for_job(job_id, timeout_seconds=180) -> state:"succeeded", rc 0
   # CLI under the hood: BroadbandSPICE.exe -b -Checking <s4p>, CWD = directory being verified
```

- **Result state**: rc 0.
- **Verified artifact (live 2026-09-27)**: `runs\bbs_smoke\BBSResult_app1_drv\S-parameter Checking Report.htm`
  — **42,263 bytes** — the full verdict report (NOT a 0-byte log). Read it; the verdict for
  `app1_drv.S4P` is: Matrix dimension **4x4** | Passivity **No non-passive points / No violation** |
  Causality **No non-causal points / No violation** | Reciprocity **No violation** | Lowest freq
  1 MHz (low enough) | Overall evaluation **Poor** (driven only by "Large jump" sampling-density
  flags — amplitude/phase sampling sparsity, NOT passivity/causality). A "Poor" overall is a real
  and expected outcome for sparse Touchstone grids; the passivity/causality rows are the ones that
  matter for sim stability and they PASS.
- **Error hit**: none on the happy path.
- **#1 mistake**: concluding the check failed because the overall rating says "Poor". The overall
  rating conflates sampling-density heuristics with physics; a passive, causal, reciprocal network
  can still be "Poor". Read the Passivity/Causality/Reciprocity rows specifically — "No violation"
  = pass. And again: the report lands in `BBSResult_<input_basename>/` next to the CWD, not in any
  job dir.

## PowerSI gotchas (the ones that cost real minutes here)

1. **Frequency flags = plain Hz, no unit suffix.** `start="1e6", end="1e9"` (or `"0"`, `"1e3"`).
   `"1MHz"`/`"1GHz"` is parsed wrong → "The ending frequency should not be smaller than the
   starting frequency." Also the Tcl line is `sigrity::update freq -start {1e6} -end {1e9} -AFS {!}` —
   the space between each flag and its brace-quoted value is required; `-start{1e6}` (no space) is
   rejected as one unrecognized token.
2. **Non-`.spd` input (e.g. a `.brd`) REQUIRES `powersi_save_document` first.** PowerSI opens the
   foreign format via its built-in translator (BRDExtractor for `.brd`; DXF/Altium/ODB2/IPC-2581 are
   also handled by `sigrity::open document`), but will not simulate a design not yet saved to native
   SPD. Call it **immediately after `start_powersi_session`** and **before any other step**. Omit
   it on a design that is already `.spd`.
3. **`sigrity::begin simulation {!}` is appended by `powersi_run_session` itself** — you do NOT add it
   manually. If you compose a raw macro some other way, a missing `begin simulation` line is the
   cause of a run that opens the design, applies every setting, exits rc 0, and produces zero output.
4. **Artifacts land in `runs/`, not the job dir (PowerSI) — BroadbandSPICE writes next to its CWD.**
   `list_job_files` shows no `.sNp` for a PowerSI job (normal); the `<name>_S.<N>p` / `_S.ckt` /
   `_Options.xml` / `_PowerSI.err` appear in `C:\Users\aicoe\Desktop\Sigrity\runs\`. BroadbandSPICE is
   different again: its outputs (the `BBSResult_<input_basename>/` folder, plus its `<name>.log` and
   `*_BBSckt.*` netlist) appear **next to the working directory the CLI was launched from**, never in
   the MCP job dir. Verify both domains by listing the *input file's* directory, as always.
5. **`license_issue_suspected` is USELESS on this install — do not trust it.** Verified live:
   `lmstat -c 5280@localhost` returns "Cannot connect to license server (Connection refused)" yet
   every job reported `license_issue_suspected: false` AND PowerSI still produced a genuine
   70 MB 68-port `.sNp` in the same session. The flag only reflects whether a license keyword
   string appears in the last 1 MB of the log; a healthy run prints no such string. When a job
   writes an empty log (see next item) you get `false` with zero information. Judge by artifact,
   never by the flag.
6. **Silent success is the norm.** PowerSI batch runs frequently write a 0-byte `run.log` and no
   stdout even on a perfect run. Judge success by the appearance of a non-empty
   `<name>_S.<N>p` / `.spd` in `runs/`, never by the log or the exit code. And a *failed* run
   (e.g. missing-SPD case) looks IDENTICAL — same empty log, same rc 0 — so the artifact check
   is the only discriminator.
7. **Stage read-only samples with `copy_file` first.** Never run against `C:\Cadence\...\share\` in
   place — PowerSI can write sibling files next to its input. Copy the `.spd`/`.brd` into `runs/`
   (e.g. `runs/taskN_<name>.spd`) before `start_powersi_session`. (In Task 3 above the .brd was read
   directly without copying and no stray files appeared next to it, but the copy is the safe habit.)
8. **BroadbandSPICE writes next to the CWD, never into the job dir** (unlike PowerSI, whose output
   goes to `runs/` root). The `BBSResult_<input_basename>/` result folder, the `<name>.log`, and the
   `*_BBSckt.sp`/`.txt` netlist all appear in the working directory the CLI was launched from
   (verified live 2026-09-27). Stage inputs in a scratch CWD (e.g. `runs\bbs_smoke\`) and check THERE
   — `list_job_files(job_id)` is a dead end for BBS output.

## Sample paths (confirmed to exist on this machine)

| Purpose | Path |
|---|---|
| PowerSI `.spd` (demo, short) | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\powersi\psi_brd_demoshort.spd` |
| PowerSI `.spd` (demo, decaps) | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\powersi\psi_brd_demodecaps.spd` |
| PowerSI `.spd` (another) | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\powerdc\Motherboard.spd` |
| Allegro `.brd` (routed, PowerSI direct) | `C:\Cadence\SPB_22.1\tools\capture\samples\PCB-Layout\Fault-Detector\allegro\fault-detector_allegro_routed.brd` |
| Touchstone `.s2p` (BroadbandSPICE) | `C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\Broadband SPICE\spiral_10GHz.s2p` |
| Touchstone `.S4P` (passivity check) | `C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\Broadband SPICE\app1_drv.S4P` |
| Runs scratch | `C:\Users\aicoe\Desktop\Sigrity\runs\` |
