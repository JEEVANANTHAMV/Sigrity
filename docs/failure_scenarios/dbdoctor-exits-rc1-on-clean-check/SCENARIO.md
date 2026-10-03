# dbdoctor.exe Exits with Return Code 1 on Clean Check-Only Pass

**Slug**: `dbdoctor-exits-rc1-on-clean-check`
**Tool(s) affected**: `run_allegro_dbdoctor`
**Status category**: `unreliable_intermittent`
**Pipeline stage**: analysis

## Symptom

`dbdoctor.exe -check_only <board>` exits with **return code 1** even on a **clean check-only pass** where there are 0 errors. The job reports `state:"failed"` with `returncode:1`, which looks like a genuine failure. However, the actual check completed successfully: the log shows `"1 warnings, 0 errors detected"` (or `"0 errors could be fixed"`), confirming the database integrity check ran and found no errors.

The rc 1 is NOT a failure indicator. It appears to be dbdoctor's way of signaling "there was something to report" (even if that something is just warnings) rather than "the check failed." A truly clean run (0 warnings, 0 errors) may exit 0, but a run with warnings but no errors exits 1.

This is easily misdiagnosed as a database corruption, a tool crash, or a failure, leading operators to:
1. Investigate a "failure" that is actually a clean pass with warnings
2. Re-run the check unnecessarily
3. Report a false failure in the pipeline

## Root Cause

Not documented in this codebase why dbdoctor uses rc 1 for a clean check with warnings. The likely interpretation: dbdoctor's exit code convention is:
- rc 0: check completed, 0 warnings, 0 errors
- rc 1: check completed, warnings present (but 0 errors) — "had warnings"
- rc 2+: check completed, errors present (or check failed)

This is consistent with the `artwork.exe` pattern (rc 1 = "had warnings", not a failure) and the `dxf2a.exe` pattern (rc 1 on success). The common thread: these Cadence binaries use rc 1 to mean "completed with warnings" rather than "completed cleanly."

The tool_status.py note confirms: "Note it exits non-zero (1) even for a clean check-only pass with only warnings — don't treat any non-zero return code from this tool as a hard failure without reading its output first."

## Evidence

- `sigrity_mcp/core/tool_status.py:560-564` — "`allegro_dbdoctor`: Confirmed genuinely headless, no dialog: `dbdoctor.exe -check_only <real .brd sample>` ran a real orphan-record check end-to-end and reported its result ('1 warnings, 0 errors detected'). Note it exits non-zero (1) even for a clean check-only pass with only warnings — don't treat any non-zero return code from this tool as a hard failure without reading its output first."
- `.forjinn/skills/sigrity-cad/SKILL.md:155-170` — "Task 5... `run_allegro_dbdoctor` → `state:"failed"` rc 1. So: placeholders thread results between steps, `wait_for_job` works inside a pipeline, and the two exit behaviors are distinct (report rc 0, dbdoctor rc 1)."
- `.forjinn/skills/sigrity-cad/SKILL.md:166-170` — "dbdoctor artifact gotcha: `check_only=True` (default) + a board whose DRC is OUT OF DATE exits **rc 1** and reports in the **job dir** `dbdoctor.log` (→ `WARNING(SPMHDB-42): Run batch DRC to regenerate DRC errs`; `1 warnings, 0 errors detected, 0 errors could be fixed`). The `-outfile` path I passed stayed **0 bytes** — dbdoctor writes its real report to the job dir, not the `-outfile` arg. Read `<job_dir>\dbdoctor.log`."
- `.forjinn/skills/sigrity-cad/SKILL.md:549` — Cross-cutting note: "`run_allegro_batch_drc` → `get_job_status` stays `running`/`rc null` forever → read `batch_drc.log`/`dbdoctor.log`."

## Pipeline Impact

Blocks the **analysis** stage if the pipeline trusts `returncode` or `state` to determine success. A pipeline that checks for `state:"succeeded"` or `returncode == 0` will incorrectly classify a clean dbdoctor run (with warnings) as failed and may:
1. Retrying the check (wasting time)
2. Reporting a false database-corruption alarm
3. Aborting the pipeline at the dbdoctor step

The actual check IS done correctly — the log contains real integrity-check results. The problem is purely in the exit code interpretation.

Additionally, there is a **secondary artifact gotcha**: dbdoctor writes its real report to the **job directory** (`dbdoctor.log` in `job_dir`), NOT to the `-outfile` argument path. If the caller passes `-outfile` and then reads from that path, they will find a 0-byte file and may misinterpret this as a failure.
