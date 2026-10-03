---
name: sigrity-extraction
description: Sigrity Extraction domain — layout translators to .spd, XtractIM (EPA package extraction, workspace & session modes), Clarity3D (3D EM), T2B, and abcd/bem2d3 utility solvers. Verified live, easy-to-complex: exact minimal call sequences, verified artifacts, and the exact failure modes.
---

# Sigrity Extraction — verified sequences (Sigrity 2024.0)

Extraction = the domain that turns layout (`.dsn`/`.gds`/`.ndd`/`.asc`/`.rif`/`.zip`...) into `.spd`,
then extracts parasitics: XtractIM (2.5D/pg/EPA), Clarity3D (full-wave 3D), T2B (SPICE), plus the
standalone `abcd` (touchstone de-embed) and `bem2d3` (2D field) utility solvers.

All sequences below were exercised live on this machine, EASY → COMPLEX.
Job control (7 tools: `get_job_status` / `wait_for_job` / `tail_job_log` / `list_job_files` /
`read_job_output_file` / `cancel_job` / `list_all_jobs`) is in the platform skill.

## The two inviolable extraction rules (both violated here, see Tasks 1 & 5)

1. **`state:"succeeded"` + rc 0 ≠ artifacts exist.** Verify with `list_job_files(job_id)` —
   and know that some tools (XtractIM below) write results **outside `job_dir`**, so you must
   also check the input file's directory.
2. **Session mode is not a shortcut that always works.** XtractIM's compose mode can
   regenerate the workspace but the final `begin simulation` will still fail rc 0 if the
   rebuilt workspace's stackup isn't fully specified — see Task 3.

---

## Task 1 — EASY: `run_xtractim_workspace` (one tool call, no Tcl)

**Verified: 40 s wall, rc 0, real RLC matrices emitted.**

```
run_xtractim_workspace(workspace_xml="C:\Users\aicoe\Desktop\Sigrity\runs\t1_xtractim_ws\Wirebond_EPA.ximx")
→ { "job_id":"xtractim-91f66f4d36", "state":"running" }
wait_for_job(job_id="xtractim-91f66f4d36", timeout_seconds=180)
→ { "state":"succeeded", "returncode":0, "license_issue_suspected":false }
```

`XtractIM.exe -b <workspace-ximx>` is all it runs; `spd_override` (optional arg) re-points the
layout if you need it elsewhere.

### Verification — **job_dir is EMPTY**

`list_job_files("xtractim-91f66f4d36")` → only `job.json` + `run.log` (0 bytes).
**XtractIM writes its results next to the `.ximx`, not in the job dir.** The real artifacts
(2.4 min after start, ~40 s total wall):

```
t1_xtractim_ws\EPAResult_Wirebond_EPA_092626_192820_22996.eparesult
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinInductanceAll_LB.csv   (672 KB)
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinInductanceAll_LC.csv   (23 KB)
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinRLofEachNet_LB.csv
t1_xtractim_ws\Wirebond_EPA_20260926192820_PinRLofEachNet_LC.csv
t1_xtractim_ws\Wirebond_EPA_20260926192820_NetLoopInd.csv
t1_xtractim_ws\Wirebond_EPA_XtractIM.err
t1_xtractim_ws\EPAResult_...\Ref_Files\  (IC / LB / LC matrix files)
```

`NetLoopInd.csv` first data rows (the actual verified R/L/C content):
```
VDD_1,VSS,0.442200,44.981500,12.417300   # L(nH)  C(pF)  R(mOhm)
VDD_2,VSS,0.442000,45.068800,12.406600
```

`PinInductanceAll_LC.csv` first rows: `U1;VDDcore` header + 20 pin rows.

**Error+fix:** The job's own log file was 0 bytes — the `run` tool's `run.log` is where
`XtractIM.exe`'s stdout lands, but XtractIM writes **its** run log to
`<dir-of-ximx>\<layout-name>_<timestamp>_<pid>.log` (same dir as the input, not the job dir).
That file (`Wirebond_EPA_092626_192741_22996.log`) shows the full solver timeline:
`Fetch License` → `[Matrix File Name List]` → `Ending time = 09/26/2026 19:28:20`.

**Mistake #1 for Task 1:** trusting `list_job_files` and stopping there. The job dir will be
empty even for a fully successful run. **Check the directory of the `.ximx` input**, not the
job dir, before declaring the run done or "failed".

---

## Task 2 — MEDIUM: `translate_dsn_to_spd` (one tool call, positional args)

**Verified: 0.6 s, rc 0, real 724 KB .spd written.**

Stage the sample first:
```
copy_file("C:\Cadence\Sigrity2024.0\share\Translators\Samples\Dsn2Spd\demo.dsn",
          "C:\Users\aicoe\Desktop\Sigrity\runs\t2_dsn2spd\demo.dsn", overwrite=True)
```
Then:
```
translate_dsn_to_spd(dsn_file="C:\Users\aicoe\Desktop\Sigrity\runs\t2_dsn2spd\demo.dsn",
                     spd_file="C:\Users\aicoe\Desktop\Sigrity\runs\t2_dsn2spd\demo.spd")
→ { "job_id":"dsn2spd-eaad7a8526", "state":"running" }
wait_for_job(job_id="dsn2spd-eaad7a8526", timeout_seconds=180)
→ { "state":"succeeded", "returncode":0 }
```

`Dsn2Spd.exe -b <dsn> <spd>` is what runs. **Do NOT pass `log_file`** — it silently flips the
tool into log-replay mode, dropping explicit args and replaying a prior run's stored settings.

Verification — `.spd` written next to the input (the tool's output path), not job_dir:
```
t2_dsn2spd\demo.spd   (723 984 bytes, valid — "Title - SPEED2000 file for version 24.0.0...
                                translated from Cadence's DSN file")
t2_dsn2spd\demo.log   (6 717-byte tool log)
t2_dsn2spd\error.log  (0 bytes — a clean run produces an empty error.log, not an error)
```

**Mistake #1 for translators:** passing `log_file` thinking it "redirects output". It
overrides your explicit input/output, not appends. Never pass it for a fresh conversion.
Also: `translate_dsn_to_spd` takes **positional** args, not keyword flags — the tool name
is `dsn_file` / `spd_file`, but the actual CLI is `Dsn2Spd -b <in> <out>` (no `-dsn` / `-spd`).
If you confuse yourself about positional vs flag, check the generated `command` list in the
run return — it's the literal argv that was executed.

---

## Task 3 — COMPLEX: XtractIM **session mode** (compose a whole setup in one shot)

The full sequence, all 8 tools, in this exact order:

```
start_xtractim_session(spd_file="C:\Users\aicoe\Desktop\Sigrity\runs\t4_xtractim_session\Wirebond_EPA.spd")
→ { "session_id":"xtractim-session-b52f7bc0" }

xtractim_select_net(session_id="xtractim-session-b52f7bc0")          # defaults: net_name=None, selected=True → -all
xtractim_set_mode(session_id="xtractim-session-b52f7bc0", mode="EPA")
xtractim_set_package_type(session_id="xtractim-session-b52f7bc0", die=0, board=0, assembly=1)
xtractim_set_circuits(session_id="xtractim-session-b52f7bc0",
                      die_ref_des="U1", board_ref_des="BGA1",
                      component_ref_des_list=["C1","C2"])
xtractim_set_pg_analysis_options(session_id="xtractim-session-b52f7bc0")   # all defaults on
xtractim_process_and_save(session_id="xtractim-session-b52f7bc0",
                          workspace_file="C:\Users\aicoe\Desktop\Sigrity\runs\t4_xtractim_session\Wirebond_EPA.ximx")

xtractim_run_session(session_id="xtractim-session-b52f7bc0")
→ { "job_id":"xtractim-53ba14b533", "state":"running" }
wait_for_job(job_id="xtractim-53ba14b533", timeout_seconds=180)
→ { "state":"succeeded", "returncode":0 }   # 3 s wall
```

Preview the macro before you run it — the compose tools just append lines, nothing is
executed until `xtractim_run_session`. The generated `macro.tcl` (597 bytes) is the exact
sequence above rendered as `sigrity::` Tcl with `{!}` terminators (XtractIM uses them,
Clarity3D does not — see Task 4).

### The verified failure — rc 0 but no extraction

The job `succeeded` (rc 0) in 3 s. `list_job_files` shows only `macro.tcl`,
`macro_<timestamp>.log`, `run.log`, `job.json`. No RLC output. The macro log's last line:

```
[Run Tcl Command: sigrity::begin simulation]
→ Tcl Result(Line 11):
   Failed to run the simulation because of incomplete setup. Ensure that
   stackup is set up correctly and start the simulation again.
```

**The compose-mode workspace is regenerated (29 KB → 29 KB, `CircuitTopology="2"` changed)
but it's missing the detailed per-net geometry / stackup parameters that were in the
original hand-authored `.ximx`, so `begin simulation` bails out silently.**

Reproduced a second time (job `xtractim-4f8e65c43c`) with the identical error line.

**What actually worked (Task 1) is the workspace-XML mode** — the pre-built
`Wirebond_EPA.ximx` carries every net's `Selected="1"`, `ShapeSelected="1"`,
`RiseTime="100"`, `PercentageCoupling="5"`, plus `Advanced3DSettings` mesh sections.
The session-mode tools don't yet expose a way to re-create any of those fields, so the
resulting workspace is incomplete enough for the solver to reject.

**Mistake #1 for session mode:** treating it as a drop-in replacement for
`run_xtractim_workspace`. It's not — if you already have a good `.ximx`, **use it**
(Task 1). Session mode is for authoring a *new* setup for a different `.spd` layout, and
even then you must know the exact `sigrity::` commands that fully specify stackup /
per-net properties before you'll get past `begin simulation`.

**Second thing to know:** the `.spd` you open in session mode must be the same physical
layout the `.ximx` references — if you open `Wirebond_EPA.spd` but the session tool writes
its own workspace file to a different dir, the two won't line up and you get the same
"stackup not set up" error.

---

## Task 4 — COMPLEX: Clarity3D (full-wave 3D EM FEM)

**Known-blocked on this machine. Verified: fails before it can run.**

The sequence you'd use (matches the repo unit-test's happy path exactly):
```
start_clarity3d_session(design_file="<path>.3dem")
clarity3d_set_frequency_sweep(sid, bands=[{"type":"singlepoint","freq":"1e+09"}])
clarity3d_configure_local_resource(sid, cpus=8)
clarity3d_export_touchstone(sid, "<out.s4p>")
clarity3d_run_session(session_id=sid, design_file="<path>.3dem")
wait_for_job(job_id=<id>, timeout_seconds=180)
```

`design_file` is a **required** arg to `clarity3d_run_session` (unlike `celsius3d_run_session`
which only takes session). The run tool appends both `sigrity::begin simulation -fileName {...}`
and `sigrity::end simulation -fileName {...}` — both are required, `end` is what blocks until
done.

### The verified failure — two independent problems

**Problem 1: no `.3dem` file exists on this machine.**
```
Get-ChildItem C:\Cadence\Sigrity2024.0\share -Recurse -Include *.3dem  → nothing
Get-ChildItem C:\Users\aicoe\Desktop\Sigrity\runs -Recurse -Include *.3dem → nothing
Get-ChildItem ... -Include *.spdb → nothing
```
Clarity3D's own docstring says its confirmed working sample uses `test2.3dem`. The sample
at `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\clarity\43micro.spd` (13 KB, `.spd`)
is the only Clarity3D-labeled file in the install — it's an input `.spd`, not a
`.3dem`, and the tool itself rejects it.

**Problem 2: when fed a `.spd` anyway, Clarity3DWorkbench segfaults with no error text.**
```
clarity3d_workbench-50c1aaeae9:
  macro line 3: sigrity::open file -file {C:/Cadence/.../43micro.spd}
  run.log (119 bytes total):
    "You are using the legacy command line syntax.
     Run \"Clarity3DWorkbench -h\" to know the details about the new one."
  macro_21160926_19300.log (171 bytes):
    "ERROR: File format is not supported.\n\n
     Cannot run the TCL command at line 3 because of syntax error.
     Correct the error and rerun the TCL command."
  PID 13292 is dead (Get-Process → null), state stays "running" in job.json,
  returncode never set.
```
A prior run (job `clarity3d_workbench-7076037627`, from an earlier
eval run) had the identical failure: `.dsp`/`.dsn` fed as design_file, state "cancelled",
`run.log` only 119 bytes (same banner), no result. The process doesn't clean up its own
stdout or exit code properly — you must `cancel_job` and then `kill /F` the PID if it
sticks.

**Mistake #1 for Clarity3D:** trying to use a `.spd` or `.dsn` as `design_file`.
Clarity3DWorkbench wants a `.3dem` (or internally a `spdb` binary). If you don't have a
`.3dem` on hand, **you can't run Clarity3D** — this is a file-format limitation, not a
license or HPC issue. Record it as a known-blocked state, don't burn time retrying.

---

## Task 5 — `run_touchstone_deembed` (abcd) — confirmed live for 2-port, with a real gotcha

The earlier "effectively broken, no input class works" verdict for this tool was
wrong — root-caused and fixed. `abcd.exe` only resolves its `-tsfile`/`-lefttsfile`/
`-righttsfile`/`-duttsfile` arguments against `-filepath`'s value when that value ends
in a trailing path separator; without one it silently does nothing (rc 0, no output,
no error, `run.log` stays 0 bytes). `run_touchstone_deembed` now normalizes this
automatically, so this is no longer something a caller needs to work around:

```
run_touchstone_deembed(
    file_path="C:\Users\aicoe\Desktop\Sigrity\runs\t5_abcd",
    left_touchstone_file="cap.s2p",
    right_touchstone_file="cap.s2p",
    dut_touchstone_file="dut.s2p")
→ { "job_id":"abcd-...", "state":"running" }
wait_for_job(...) → { "state":"succeeded", "returncode":0 }
read_job_output_file(job_id, "dut.s2p")  # real, well-formed Touchstone output,
# header "! Cadence S Parameter Output From ABCD Version 1.0", values genuinely
# differ from the input
```

**Still verify the output file, don't trust rc 0 alone**: abcd exits 0 even on a
no-op, so a "succeeded" job with `returncode: 0` is not by itself proof the de-embed
ran — always confirm `dut_touchstone_file` exists and is non-empty.

**4-port S-parameter files remain unverified** (not confirmed broken, not confirmed
working): a real segfault was once seen on a specific 4-port magnitude/angle-format
file, but a later attempt to re-test it found the original input files no longer
present on this machine, so nothing was actually re-proven either way. If 4-port work
is needed, obtain real 4-port files first and test before relying on it.

---

## Sample files (all verified present on this machine)

| Purpose | Path |
|---|---|
| XtractIM workspace (EASY, use this) | `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\xtractim\Wirebond_EPA.ximx` |
| XtractIM .spd (for session mode) | `...\xtractim\Wirebond_EPA.spd` (+ `Wirebond_Pinbased.ximx`, `FlipChip_net-based.spd`/`.xml`, `wirebond.spd` in same dir) |
| Dsn2Spd .dsn | `C:\Cadence\Sigrity2024.0\share\Translators\Samples\Dsn2Spd\demo.dsn` |
| Clarity3D sample | NONE on this machine — `clarity3d_run_session` requires a `.3dem` (verified: recursive `*.3dem` search under `share` returns nothing); the only Clarity3D-labeled file `share\PostInstallationCheck\clarity\43micro.spd` is an XtractIM 3D EM design and is rejected by the tool (see Task 4) |
| Touchstone 2-port (confirmed working with abcd) | real Murata capacitor `.s2p` samples under `share\SpeedXP\` |
| Touchstone RI 4-port (unverified with abcd, not a known crash) | `C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\Broadband SPICE\app1_drv.S4P` |
| Touchstone RI 4-port (unverified with abcd, not a known crash) | `...\Broadband SPICE\CoupledLines_SplitPlane.s4p` |
| Touchstone MA/dB 4-port (once segfaulted abcd; unverified since) | `...\Broadband SPICE\channel.s4p` |

## One-line summary per tool (for quick recall)

- `run_xtractim_workspace(workspace_xml=…)` → rc 0 + artifacts **in the .ximx's directory, not job_dir**.
- `translate_dsn_to_spd(dsn, spd)` → rc 0 + `.spd` written to the `spd_file` path, never in job_dir.
- XtractIM session mode → rc 0, but `begin simulation` still fails "incomplete setup/stackup"
  — use Task 1 mode instead if you already have a good `.ximx`.
- `clarity3d_run_session(sid, design_file)` → needs `.3dem`, not available on this machine;
  feeding `.spd`/`.dsn` segfaults with empty log; record as known-blocked.
- `run_touchstone_deembed(file_path, dut, leftts, rightts)` → confirmed live for 2-port
  cascade/de-embed (the tool auto-normalizes `file_path` to end in a trailing
  separator, the one thing abcd itself requires); 4-port remains unverified. Always
  check the output file, not just rc 0 — abcd exits 0 on a no-op too.
- `run_xhatch_field_solver(in, out, -xhatchmode y, ...)` → `bem2d3.exe`, standalone 2D
  solver for rigid-flex x-hatched ground; not exercised in this report, same job-pattern.
