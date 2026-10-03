# batch_drc.exe Launcher Exits Early, Job State Stays "running" Forever

**Slug**: `batch-drc-launcher-exits-early-state-lie`
**Tool(s) affected**: `run_allegro_batch_drc`
**Status category**: `unreliable_intermittent`
**Pipeline stage**: analysis (DRC)

## Symptom

`run_allegro_batch_drc` submits a job, but the job's `state` **never transitions to a terminal state** (`succeeded` or `failed`). `get_job_status(job_id)` returns `state:"running"` with `returncode:null` indefinitely, even though the DRC work has actually completed. The `job.json` file never flips to a terminal state because the launcher process (`batch_drc.exe`) **detaches** — it spawns the real DRC worker as a child process and exits, so the parent process (which the job system tracks) is no longer the one doing the work.

The actual DRC results ARE produced: `batch_drc.log` and `dbdoctor.log` are written to the job directory with real DRC statistics. But the job system has no way to detect completion because the tracked process has already exited.

Specifically:
- `get_job_status(job_id)` → `state:"running"`, `returncode:null` (forever)
- `list_job_files(job_id)` → `batch_drc.log`, `dbdoctor.log`, `job.json`, `run.log` already exist
- `tail_job_log(job_id)` → 0 lines (the empty `run.log` — useless)
- The real output is in `batch_drc.log` and `dbdoctor.log`, readable via `read_job_output_file`

## Root Cause

`batch_drc.exe` is a **launcher/multiplexer**, not the actual DRC engine. When invoked, it:
1. Spawns the real DRC worker as a detached child process
2. Exits immediately (the parent process terminates)
3. The child process continues running, writing `batch_drc.log` and `dbdoctor.log` to the job directory

The MCP job system tracks the **parent** process (`batch_drc.exe`). When the parent exits, the job system should mark the job as complete. However, because the parent exits with code 0 (or simply detaches), the job's `returncode` is captured as `null` (the parent's exit code is not a meaningful completion signal for the real work). The `job.json` is never updated to a terminal state because the process the job system is tracking has already terminated, and the job system has no mechanism to track the detached child.

This is a **state lie**: the job's `state` field (`"running"`) is inaccurate — the work is done, but the state doesn't reflect it.

## Evidence

- `.forjinn/skills/sigrity-cad/SKILL.md:33-50` — "Task 2 — MEDIUM: `run_allegro_batch_drc` — the 'launcher-exits-early' state lie. `get_job_status` returned `running` / `returncode:null` (the launcher detached; `job.json` never flipped to a terminal state) while `list_job_files` already showed `batch_drc.log` + `dbdoctor.log`. Read them, not the state... The `state` lie reproduced exactly... Do not `wait_for_job` indefinitely on this job."
- `.forjinn/skills/sigrity-cad/SKILL.md:48-50` — "#1 mistake: waiting for `state` to become `succeeded`/`failed` — it never does. Detect completion by reading `batch_drc.log` for 'DRC update completed' (and the error count in `dbdoctor.log`)."
- `.forjinn/skills/sigrity-cad/SKILL.md:46-47` — "Error hit: `tail_job_log(job_id)` returned 0 lines (the empty `run.log`) — useless here. The real output is `batch_drc.log` / `dbdoctor.log` in the job dir, read via `read_job_output_file`."
- `.forjinn/skills/sigrity-cad/SKILL.md:547-549` — Cross-cutting note: "`run_allegro_batch_drc` → `get_job_status` stays `running`/`rc null` forever → read `batch_drc.log`/`dbdoctor.log`."
- `sigrity_mcp/core/tool_status.py:565-566` — "`allegro_batch_drc`: Confirmed live against a real .brd sample on this machine: `batch_drc.exe -nographic <board>` exited 0 with 'Batch DRC checking done.'"

Note: The tool_status note says "exited 0" — this is the raw CLI exit code of batch_drc.exe. The MCP job system's `state` field is a separate abstraction that does not reflect this exit code due to the detachment behavior.

## Pipeline Impact

Blocks the **analysis (DRC)** stage if the pipeline relies on `state` or `wait_for_job` to detect DRC completion. A pipeline that does `wait_for_job(job_id, timeout_seconds=180)` on a `run_allegro_batch_drc` job will time out (the job never reaches a terminal state), wasting 3 minutes and potentially aborting the pipeline. The DRC work IS done, but the pipeline cannot detect it through the normal job-state mechanism.

This is particularly dangerous because:
1. The job directory contains real, correct DRC results — the work is done
2. The job state says `running` — the pipeline thinks the work is still in progress
3. A timeout-based wait will fail, potentially aborting a pipeline that should have continued
4. The operator may re-run the DRC unnecessarily, wasting time
