# Clarity3D Has No .3dem Input; Feeding .spd Segfaults with an Empty Log

**Slug**: `clarity3d-no-3dem-input-segfault`
**Tool(s) affected**: `start_clarity3d_session` / `clarity3d_*` compose tools / `clarity3d_run_session` (`clarity3d_workbench`, logical tool for `Clarity3DWorkbench.exe`)
**Status category**: `known_blocked`
**Pipeline stage**: extraction (full-wave 3D EM FEM)

## Symptom

Clarity3D **cannot be run at all on this machine** because:
1. **No `.3dem` (or internally `spdb`) design file exists on the machine.** A recursive search under `C:\Cadence\Sigrity2024.0\share` and `runs/` for `*.3dem` and `*.spdb` returns nothing.
2. **The only Clarity3D-labeled file in the install is rejected.** `C:\Cadence\Sigrity2024.0\share\PostInstallationCheck\clarity\43micro.spd` (13 KB) is an input `.spd`, not a `.3dem`, and the tool rejects it.
3. **When fed a `.spd` anyway, `Clarity3DWorkbench` segfaults with no useful error** — the macro log records `ERROR: File format is not supported.` / syntax error, the process PID is dead, and `job.json` state is left stuck at `"running"` with no return code set.

So the failure is **before it can run**: a file-format precondition (a `.3dem`) is unmet, and the tool's degradation on a wrong-format input is a hard, uncleaned crash.

## Root Cause

`Clarity3DWorkbench` requires a **`.3dem`** (or its internal `spdb` binary) as `design_file`. This is a **file-format limitation, not a license or HPC issue.** Two compounding problems:

- **No valid input is available.** Clarity3D's own docstring names `test2.3dem` as its confirmed-working sample, but no such file is present in this install or on disk. The shipped `43micro.spd` is an XtractIM 3D-EM design, not a Clarity3D `.3dem`.
- **Wrong-format input → uncleaned process death.** Feeding `.spd`/`.dsn` leads to `ERROR: File format is not supported.` at the `sigrity::open file` line, and the Workbench process dies without cleaning up its own stdout or exit code — `job.json` state stays `"running"`, `returncode` is never set, the 119-byte `run.log` is just the "legacy command line syntax" banner, and the macro log (171 bytes) is the only place the real error appears.

## Evidence

- `.forjinn/skills/sigrity-extraction/SKILL.md:182-237` (Task 4) — "**Known-blocked on this machine. Verified: fails before it can run.** … **Problem 1: no `.3dem` file exists on this machine.**" (recursive `*.3dem`/`*.spdb` searches → nothing). "**Problem 2: when fed a `.spd` anyway, Clarity3DWorkbench segfaults with no error text.** … `run.log (119 bytes total): 'You are using the legacy command line syntax…' … macro_21160926_19300.log (171 bytes): 'ERROR: File format is not supported.\n\nCannot run the TCL command at line 3 because of syntax error…' PID 13292 is dead (Get-Process → null), state stays 'running' in job.json, returncode never set. … **this is a file-format limitation, not a license or HPC issue.**"
- `.forjinn/skills/sigrity-extraction/SKILL.md:234-237` — "**Mistake #1 for Clarity3D:** trying to use a `.spd` or `.dsn` as `design_file`. Clarity3DWorkbench wants a `.3dem` (or internally a `spdb` binary). If you don't have a `.3dem` on hand, **you can't run Clarity3D** … Record it as a known-blocked state, don't burn time retrying."
- `.forjinn/skills/sigrity-extraction/SKILL.md:282` — sample table: "Clarity3D sample | **NONE on this machine** — `clarity3d_run_session` requires a `.3dem` (verified: recursive `*.3dem` search under `share` returns nothing); the only Clarity3D-labeled file `share\PostInstallationCheck\clarity\43micro.spd` is an XtractIM 3D EM design and is rejected by the tool."
- `.forjinn/skills/sigrity-extraction/SKILL.md:294-295` — one-line: "`clarity3d_run_session(sid, design_file)` → needs `.3dem`, not available on this machine; feeding `.spd`/`.dsn` segfaults with empty log; record as known-blocked."
- `sigrity_mcp/domains/extraction/clarity3d_tools.py:62-70` (`start_clarity3d_session`) and `:205-216` (`clarity3d_run_session`) — `design_file` is a **required** arg to `clarity3d_run_session` (distinct from `celsius3d_run_session`); the run appends `sigrity::begin simulation -fileName` **and** `sigrity::end simulation -fileName` (both required; `end` blocks until done).
- `sigrity_mcp/domains/extraction/clarity3d_tools.py:6-16` (module docstring) — confirmed sample uses `sigrity::open file -file {test2.3dem}`; Clarity3D lines do **not** use the `{!}` terminator (unlike PowerSI/XtractIM).

## Pipeline Impact

Clarity3D is **fully unavailable** on this machine — not intermittent, a hard precondition (no `.3dem` input) plus an unclean crash on wrong-format input. Any full-wave 3D EM extraction pipeline step is blocked. A secondary operational hazard is the **stuck `"running"` job state**: because the dead process never sets a return code, `job.json`/`get_job_status` can report `"running"` indefinitely for a process that is actually dead, so a pipeline waiting on `wait_for_job` will hit its timeout rather than a clean `failed` — requiring manual `cancel_job` + `kill /F <pid>`.
