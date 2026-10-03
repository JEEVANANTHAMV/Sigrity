# Workarounds: dbdoctor.exe Exits with Return Code 1 on Clean Check-Only Pass

## Verified Workaround

**Judge success by reading the dbdoctor log, not the return code.** After `run_allegro_dbdoctor` completes (regardless of `state` or `returncode`), read the log file in the job directory:

```
read_job_output_file(job_id, relative_path="dbdoctor.log")
```

Look for:
- `"N warnings, M errors detected"` — if M == 0, the check passed (warnings are not failures)
- `"0 errors could be fixed"` — confirms no errors
- If M > 0, there are real database errors that need investigation

Also note: **dbdoctor writes its report to the job directory, NOT the `-outfile` argument.** If you passed `-outfile`, that file will be 0 bytes. Always read `<job_dir>\dbdoctor.log` via `read_job_output_file`.

This is verified: "Read `<job_dir>\dbdoctor.log`" (`.forjinn/skills/sigrity-cad/SKILL.md:170`).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Read `dbdoctor.log` from job dir, judge by error count (not rc) | worked | `.forjinn/skills/sigrity-cad/SKILL.md:166-170`; `sigrity_mcp/core/tool_status.py:563-564` |
| 2 | Treat `returncode == 0` as success | didnt_work — rc 1 on clean pass with warnings | `sigrity_mcp/core/tool_status.py:563` |
| 3 | Read the `-outfile` argument path | didnt_work — file is 0 bytes; real report is in job dir | `.forjinn/skills/sigrity-cad/SKILL.md:168-170` |

## Prevention

1. **Never treat `returncode == 0` as the success criterion for `run_allegro_dbdoctor`.** Read the log and check the error count.
2. **Always read `<job_dir>\dbdoctor.log`** via `read_job_output_file(job_id, relative_path="dbdoctor.log")`. Do NOT rely on the `-outfile` argument — dbdoctor ignores it and writes to the job directory.
3. **In pipelines, add a step after `run_allegro_dbdoctor` that reads `dbdoctor.log`** and extracts the warning/error counts. Judge success by `errors == 0`, not by `returncode == 0`.
4. **Apply the same pattern to other nonzero-on-success tools**: `specctra.exe` (rc 4), `artwork.exe` (rc 1), `dxf2a.exe` (rc 1). For each, judge success by the tool-specific artifacts (log text, output files), not the exit code.
5. **Document this quirk in pipeline comments** so future operators don't "fix" it by treating rc 1 as a bug.

## Remaining Gaps

This is a **tool quirk**, not a bug. The dbdoctor binary is Cadence's, and its exit code convention is what it is. The secondary gotcha (report written to job dir, not `-outfile`) is also a tool behavior, not a fixable bug in the MCP suite.

A 25-year senior designer would consider this **fully acceptable** — the workaround (read the log, judge by error count) is simple, reliable, and documented. The only "gap" is cognitive: an operator unfamiliar with the quirk may misinterpret rc 1 as a failure or may look in the wrong place for the report (the `-outfile` path instead of the job dir). This is mitigated by:
- The SKILL.md playbook explicitly documenting both gotchas (rc 1 + job-dir report location)
- The tool_status.py note documenting the behavior
- This failure scenario manifest documenting the evidence

Full automation is not blocked — a pipeline can be written to read the log and judge by error count instead of the return code. No code changes are needed in the current implementation.
