# Workarounds: batch_drc.exe Launcher Exits Early, Job State Stays "running" Forever

## Verified Workaround

**Do NOT `wait_for_job` on a `run_allegro_batch_drc` job. Instead, poll the job directory for the DRC log files and read them.**

The correct pattern:
1. `run_allegro_batch_drc(board_file=..., nographic=true)` → get `job_id` and `job_dir`
2. **Do NOT call `wait_for_job(job_id)`** — it will time out because the state never reaches a terminal value
3. After a reasonable delay (e.g., 5-15 seconds, or poll `list_job_files` until `batch_drc.log` appears), read the DRC results directly:
   - `read_job_output_file(job_id, relative_path="batch_drc.log")` → look for `"DRC update completed"` and the error count
   - `read_job_output_file(job_id, relative_path="dbdoctor.log")` → look for `Original DRC errors` / `Updated DRC errors` / `DRC done; N errors detected.`

This is verified: "Detect completion by reading `batch_drc.log` for 'DRC update completed' (and the error count in `dbdoctor.log`). Do not `wait_for_job` indefinitely on this job." (`.forjinn/skills/sigrity-cad/SKILL.md:48-50`)

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | `wait_for_job(job_id, timeout_seconds=180)` | didnt_work — job state never reaches terminal, times out | `.forjinn/skills/sigrity-cad/SKILL.md:38,48-49` |
| 2 | Read `batch_drc.log` / `dbdoctor.log` from job dir for completion | worked | `.forjinn/skills/sigrity-cad/SKILL.md:42-50` |
| 3 | `list_job_files(job_id)` to check for log file existence | worked (polling signal) | `.forjinn/skills/sigrity-cad/SKILL.md:39` |
| 4 | `tail_job_log(job_id)` | didnt_work — returns 0 lines (empty `run.log`) | `.forjinn/skills/sigrity-cad/SKILL.md:46` |

## Prevention

1. **Never `wait_for_job` on a `run_allegro_batch_drc` job.** This is the #1 mistake documented in the SKILL.md playbook.
2. **After submitting a DRC job, poll `list_job_files(job_id)`** for the presence of `batch_drc.log` (indicating the DRC worker has started writing output).
3. **Once `batch_drc.log` exists, read it** via `read_job_output_file` and look for the `"DRC update completed"` line and the error count.
4. **Also read `dbdoctor.log`** for the `Original DRC errors` / `Updated DRC errors` / `DRC done; N errors detected.` lines.
5. **In pipelines via `run_tool_pipeline`, do NOT include a `wait_for_job` step for DRC jobs.** Instead, add a short delay step (or a `list_job_files` poll step) followed by a `read_job_output_file` step to extract the DRC results.
6. **Document this in pipeline comments** so future operators don't "fix" it by adding a `wait_for_job` that will time out.

## Remaining Gaps

This is a **tool architecture limitation**, not a fixable bug. `batch_drc.exe` is designed to detach its worker process, and the MCP job system tracks the parent process. There is no mechanism within the current job system to track a detached child process.

Possible future improvements (not currently implemented):
- **Polling-based completion detection**: the MCP suite could add a `wait_for_job_with_log_polling` variant that checks for the log file's existence and content as the completion signal, rather than relying on the process exit code.
- **Job state override**: if the MCP suite detects that `batch_drc.log` exists with a completion marker, it could update the job's `state` to `succeeded` even though the parent process has already exited.
- **Use a wrapper script**: instead of calling `batch_drc.exe` directly, call a wrapper that `wait`s on the detached child and exits with the child's exit code. This would make the parent process's exit code meaningful.

A 25-year senior designer would consider the current workaround (read the logs) **fully acceptable** — it is simple, reliable, and documented. The "gap" is a UX issue: the job state is misleading. This is mitigated by:
- The SKILL.md playbook explicitly documenting the pattern
- This failure scenario manifest documenting the evidence
- The cross-cutting notes in SKILL.md listing all three state-lie scenarios

Full automation is not blocked — a pipeline can be written to poll the log files instead of waiting for job state. No code changes are strictly required, but a UX improvement (automatic log-based completion detection) would reduce the cognitive burden on operators.
