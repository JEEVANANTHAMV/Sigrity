# Nonzero Return Code on Genuine Success (a family, not one tool)

**Slug**: `nonzero-rc-on-success-family`
**Tool(s) affected**: a cross-cutting family of standalone Sigrity/Allegro executables — concretely `specctra.exe` (rc 4), `artwork.exe` (rc 1), `dxf2a.exe` (rc 1), `allegro dbdoctor / dbdoctor.exe` (rc 1). See also the individual scenario folders: `specctra-exe-exits-rc4-on-success`, `artwork-exe-exits-rc1-on-success`, `dxf2a-nonzero-exit-on-success`, `dbdoctor-exits-rc1-on-clean-check`.
**Status category**: `unreliable_intermittent` (per manifest row 96)
**Pipeline stage**: platform-wide / applies to any `run_*` job that is gated on `returncode == 0`

## Symptom

These tools exit with a **nonzero** return code **even when the underlying work fully succeeded**. The process produced its real, verified output; only the exit code is wrong. A caller that treats `returncode != 0` as failure (or that maps it to `state="failed"`) therefore **misreads a real success as a failure**.

Confirmed members of the family on this machine (from live runs and the per-tool notes):

- `specctra.exe` — returns exit code **4** on a fully successful headless autoroute (100% routed). See README:514 ("`specctra.exe` returns a nonzero exit code (confirmed 4) even on a fully successful route") and `tool_status.py:683`.
- `dxf2a.exe` — returns **returncode 1** on a fully successful run; the log ends `dxf2a complete.` See README:300-302 and `tool_status.py:821-823` ("exits with returncode 1 even on this fully successful run (log ends 'dxf2a complete.') — same nonzero-on-success pattern as allegro_dbdoctor/artwork.exe/specctra").
- `allegro dbdoctor` / `dbdoctor.exe` — returns **rc 1** on a clean check-only pass even when the check finds zero errors; the log ends with a `0 errors detected` / `0 warnings, 0 errors detected` style line.
- `artwork.exe` — returns **rc 1** on a successful photoplot; the real success signal is the produced `.art` file(s) plus `photoplot.log`.

Each individual folder above carries the per-tool specific completion evidence. This folder is the **unifying record** that the root cause is shared (product-level exit-code policy, not one bug) and therefore any pipeline/job code that gates on `returncode == 0` is wrong for all of them at once.

## Root Cause

These are standalone Cadence executables, not this suite's wrappers — the exit code is set by the product, not by any code in `sigrity_mcp`. The suite's `JobManager._watch` (jobs.py:266-267) maps `record.state = "succeeded" if returncode == 0 else "failed"`, so a nonzero-but-successful product exit is **translated into `state="failed"`** by the platform layer. The failure is thus not in the tool's real output, nor in the wrapper's file handling — it is the mismatch between the product's exit-code convention and the platform's "0 = success" assumption.

Two layers to keep separate:
1. **The product's exit-code convention** (specctra=4, artwork/dxf2a/dbdoctor=1) — external, not fixable in-suite.
2. **The platform's `rc==0 → succeeded` mapping** (jobs.py:266-267) — in-suite, but intentionally left as a literal rc mapping so the *log + artifact* is the source of truth (SKILL.md "rule 2": `succeeded`+rc0 is not the only truth; the log is).

## Evidence

- `sigrity_mcp/core/jobs.py:266-267` — the literal mapping: `elif record.state != "cancelled": record.state = "succeeded" if returncode == 0 else "failed"`. This is *why* a nonzero-on-success exit surfaces as `state="failed"` in `get_job_status`.
- `sigrity_mcp/core/tool_status.py:821-823` (`dxf2a` note) — "exits with returncode 1 even on this fully successful run (log ends 'dxf2a complete.') — same nonzero-on-success pattern as allegro_dbdoctor/artwork.exe/specctra elsewhere in this suite, don't trust job state alone".
- `sigrity_mcp/core/tool_status.py:683` (`run_specctra_autoroute` note) — "returns a nonzero exit code ... (on a fully successful route)".
- `README.md:300-302` — "`dxf2a.exe` exits with returncode 1 even on a fully successful run (same 'nonzero exit on real success' pattern already documented for `allegro_dbdoctor`/`artwork.exe`/`specctra`) — read the job log for 'dxf2a complete.', don't trust job state alone".
- `README.md:514` — "`specctra.exe` returns a nonzero exit code (confirmed 4) even on a fully successful route, so this pipeline does not gate on that job's pass/fail state".
- `.forjinn/skills/sigrity/SKILL.md:41-45` (rule 2) — "`state` is a liar in BOTH directions ... `succeeded`+rc0 ≠ the work happened ... AND `running` ≠ stuck. The log file is the only source of truth: `tail_job_log(job_id)` ... and confirm a real non-empty artifact."
- Individual per-tool folders: `specctra-exe-exits-rc4-on-success/`, `artwork-exe-exits-rc1-on-success/`, `dxf2a-nonzero-exit-on-success/`, `dbdoctor-exits-rc1-on-clean-check/`.

## Pipeline Impact

Any `run_tool_pipeline` (or manual flow) that **gates the next step on these tools' job `state`/`returncode`** will halt or report failure on a real success. Concretely: a pipeline chaining a SPECCTRA autoroute into a DRC pass and asserting `wait_for_job` returned `state="succeeded"` will stop on the specctra step (rc 4) even though the route is 100% complete. The `run_placement_and_routing_assistance` tool deliberately does not gate on the specctra job's pass/fail for exactly this reason (README:513-515). The general hazard: these tools must be **verified by log line + artifact**, never by exit code.