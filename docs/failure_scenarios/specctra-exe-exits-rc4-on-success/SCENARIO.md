# specctra.exe Exits with Return Code 4 on Full Success

**Slug**: `specctra-exe-exits-rc4-on-success`
**Tool(s) affected**: `run_specctra_autoroute`
**Status category**: `unreliable_intermittent`
**Pipeline stage**: design (routing)

## Symptom

`specctra.exe` exits with **return code 4** even on a **fully successful** autoroute. The MCP job system reports `state:"failed"` with `returncode:4`, which looks exactly like a genuine failure. However, the actual route completed successfully: the `.sts` files (`final.sts`, `route.sts`) contain real completion statistics (e.g., `Completion = 100.00%`, `Unconnections = 0`), and the `routed.ses` session file is written with real routing data.

The return code 4 is NOT a failure indicator — it is specctra's normal exit code for a successful run (or perhaps for "completed with warnings" that are actually benign). There is no documented reason for rc 4 specifically; it is simply the code specctra returns on success.

This is easily misdiagnosed as a routing failure, leading operators to:
1. Abandon a successful route and re-run
2. Investigate a "failure" that doesn't exist
3. Trust `state:"failed"` in the job record and abort the pipeline

## Root Cause

Not documented in this codebase why specctra uses rc 4 specifically. It is a quirk of the `specctra.exe` binary — its exit code convention does not follow the Windows/Unix standard (0 = success). The exact meaning of rc 4 (success? success with warnings? some internal status code?) is not stated in any file in this codebase. What IS confirmed: rc 4 occurs on **full success** (100% connected, 0 unconnections, real `.ses` file written), so it must not be treated as a failure.

This is part of a broader pattern in this suite: several tools exit with non-zero codes on success (specctra rc 4, artwork.exe rc 1, dxf2a rc 1, dbdoctor rc 1). The common thread is that these Cadence binaries use non-standard exit code conventions.

## Evidence

- `sigrity_mcp/core/tool_status.py:677-685` — "`specctra.exe <dsn> -nog -do <script>.do -quit` (Cadence's real, fully headless, SPECCTRA-based PCB autorouter) is confirmed live TWICE — against Cadence's own shipped tutorial design (100% connected, 0 conflicts) and against this suite's own real sample board (75 nets, 163 connections, 100% connected, 0 conflicts, real .ses session file written), both via the actual MCP tool wrapper (run_specctra_autoroute), not just raw CLI. Note it returns a nonzero exit code (confirmed: 4) even on a fully successful route — read final.sts/route.sts for real completion statistics rather than trusting the return code alone."
- `.forjinn/skills/sigrity-cad/SKILL.md:71-75` — "GOTCHA (the one to know for this tool): `specctra.exe` exits **rc 4 EVEN ON FULL SUCCESS**. `wait_for_job` reports `state:"failed"`, rc 4 — that is the documented normal exit, NOT a failure. Never treat rc 4 as an error. Judge success by the `.sts` files."
- `.forjinn/skills/sigrity-cad/SKILL.md:76-78` — "Verified artifact: `final.sts` → `Completion   =  100.00%   Unconnections = 0`, `Nets=75 Connections=163`, `Routed length=451495.010`, per-layer TOP/BOTTOM routing tables. All written into the runs dir: `routed.ses` (48,872 B, real), `best.wir` (34,831 B), `final.sts`, `route.sts`."

## Pipeline Impact

Blocks the **design (routing)** stage if the pipeline trusts `returncode` or `state` to determine success. A pipeline that checks for `state:"succeeded"` or `returncode == 0` will incorrectly classify a successful SPECCTRA route as failed and may:
1. Retrying (wasting time and license resources)
2. Aborting the pipeline (preventing the SPECCTRA import step)
3. Reporting a false failure to the operator

The actual routing work IS done correctly — the `.ses`, `.wir`, and `.sts` files are all written. The problem is purely in the exit code interpretation.
