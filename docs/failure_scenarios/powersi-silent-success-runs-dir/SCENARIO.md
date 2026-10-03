# PowerSI Reports Success but `list_job_files` Shows No Artifact (Silent Success, Output in `runs/`)

**Slug**: `powersi-silent-success-runs-dir`
**Tool(s) affected**: `powersi_run_session` (PowerSI batch extraction; `sigrity_mcp/domains/si/powersi_tools.py`)
**Status category**: `unreliable_intermittent`
**Manifest**: #64

## What went wrong

`powersi_run_session` completes with `state: "succeeded"`, rc 0 — but the MCP job directory contains **no S-parameter output at all**. `list_job_files(job_id)` after success shows only `job.json`, `macro.tcl`, and a **0-byte** `run.log`. A caller that judges success by the job dir (or by the log) wrongly concludes the extraction produced nothing.

In reality the extraction usually DID run and produced a real (often tens-of-MB) `.sNp` file — it's just written to `C:\Users\aicoe\Desktop\Sigrity\runs\` (the configured `SIGRITY_WORKDIR`), **not** into the per-job dir the MCP wrapper reports. PowerSI batch runs also routinely write a 0-byte `run.log` and no stdout even on a perfect run, so the empty log carries zero information either way.

Compounding this, a *genuinely failed* run (e.g. missing `powersi_save_document` — see scenario `powersi-missing-save-document-empty-options`) presents the **identical** fingerprint: rc 0, empty `run.log`, empty job dir. The job dir and log cannot discriminate success from failure; only the artifact location can.

## Evidence

- `.forjinn/skills/sigrity-si/SKILL.md` (Task 2, "Error hit"): "list_job_files after succeeded showed only job.json, macro.tcl, run.log with a 0-byte run.log, ... That is NOT evidence the extraction produced nothing — it's this domain's silent-success fingerprint. The artifacts are in runs/ (the configured SIGRITY_WORKDIR), NOT in the job dir."
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 3, "Artifact naming"): "PowerSI names outputs `<design_basename>_<yyyymmdd>_<hhmmss>_<pid>_S.<N>p>` ... `list_job_files(job_id)` won't show it (it's in runs/, not the job dir) — instead glob `C:\Users\aicoe\Desktop\Sigrity\runs\<basename>_S.*p` after the job ends."
- `.forjinn/skills/sigrity-si/SKILL.md` ("PowerSI gotchas" #6): "Silent success is the norm. PowerSI batch runs frequently write a 0-byte run.log and no stdout even on a perfect run. Judge success by the appearance of a non-empty `<name>_S.<N>p` / `.spd` in runs/, never by the log or the exit code. And a failed run (e.g. missing-SPD case) looks IDENTICAL — same empty log, same rc 0 — so the artifact check is the only discriminator."
- Live artifacts cited (same flow, Task 3): `task3_fault_detector_092626_194507_12652_S.s68p` — 68 ports, 69,935,077 bytes — plus 9,193-byte `_S.ckt` SPICE netlist, all in `runs/` root; job itself was `succeeded` rc 0.

## Symptoms a caller observes

- `wait_for_job(job_id)` → `state: "succeeded"`, returncode 0
- `list_job_files(job_id)` → `job.json`, `macro.tcl`, `run.log` (0 bytes); **no** `.sNp`, no `.spd`, no `.ckt`
- Job dir looks identical whether the run truly succeeded or silently failed
