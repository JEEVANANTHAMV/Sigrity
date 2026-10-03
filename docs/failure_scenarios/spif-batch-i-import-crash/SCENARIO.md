# `spif_batch -i` Session Import Hard Crash (SPMHDB-238)

**Slug**: `spif-batch-i-import-crash`
**Tool(s) affected**: `run_specctra_import_session` (spif_specctra_tools.py)
**Status category**: `crash`
**Pipeline stage**: specctra routing import (standalone-CLI path)

## Symptom

`spif_batch.exe -i board.brd routed.ses` (importing a routed SPECCTRA session back into an Allegro board via the standalone CLI) **hard-crashes every time** on this machine: exit code `3221225477` (`0xC0000005`, Windows access violation), `ERROR(SPMHDB-238): The design is corrupted...` in the log, and a real `spif_batch_P00122.1_AllegroMiniDump.dmp` written into the job dir. No GUI dialog is ever shown. The crash is deterministic, not a board-state problem, and no flag bypasses it.

## Root Cause

A **product-level crash in the SPB_22.1 build of `spif_batch.exe`** specifically — not a bug in this suite's wrapper. Live diagnosis ruled out every environmental cause:

- **No GUI dialog** — win32gui polling at 20ms intervals saw zero visible windows during the crash, so there is nothing for `DismissWatcher`/pywin32 to intercept or dismiss.
- **Not a `.brd`-state problem** — `dbdoctor -drc` reports "0 errors, 0 errors could be fixed" on the test board, and the crash reproduces identically on a fresh untouched copy (a clean "Variant A" board).
- **No flag bypasses it** — `spif_batch`'s full documented switch set is `-o|-r|-i|-c`, and `specctra.exe`'s documented startup options contain **no** session-import path at all, making `spif_batch -i` the only standalone-CLI route for getting a routed `.ses` back into a `.brd` — and that one route crashes, every time.

The export half of the same bridge works fine (`spif_batch -o board.brd board.dsn` produced a real ~85KB `.dsn` from the real sample board) — only the `-i`/import direction is broken.

A secondary, suite-level (not product-level) finding: because the worker crashes **and detaches** (the launcher process never reaps the crashed child), `get_job_status` never sees the `0xC0000005` code — it stays `state:"running"` / `returncode:null` **forever**, and `cancel_job` cannot kill the detached worker. So the suite's own `crash_signature()` check (which keys off a `0xC0000005`-family returncode) never fires for this specific job — the crash is only detectable via the on-disk `.dmp` artifact and the `SPMHDB-238` log line, not via `get_job_status`/`crash` field.

## Evidence

- `sigrity_mcp/domains/cad/spif_specctra_tools.py:26-44` (module docstring) — the full confirmed-broken finding with all three ruled-out environmental causes, the exit code, the `SPMHDB-238` log text, and the `.dmp` artifact.
- `sigrity_mcp/core/tool_status.py:671-676` (`spif_batch` entry) — "For importing routed sessions back into Allegro, use `run_allegro_specctra_import` … see the `allegro` entry's specctra-import note for the real hang this had and its live-verified fix."
- `sigrity_mcp/core/tool_status.py:217-219` (the `allegro` entry) — explicitly distinguishes this from the sibling hang bug: "NOT the same bug as `spif_batch -i`'s SPMHDB-238 crash (that one dies immediately with a readable error; this one hangs forever, 0% CPU, 0 new windows, run.log stuck at the 3-line startup banner forever)."
- `.forjinn/skills/sigrity-cad/SKILL.md:79-92` (Task 3, "the known-broken import") — full crash evidence: `"mh_appl_restore(): Nothing to restore"` / `"ERROR(SPMHDB-238): The design is corrupted…"` in the log, a real `spif_batch_P00122.1_AllegroMiniDump.dmp` in the job dir, and the job-state lie refinement: "`get_job_status` did **NOT** gain a `crash` field — the worker (`spif_batch.exe -i`) crashes/detaches and the launcher never reaps it, so `job.json` stays `state:"running"` / `returncode:null` forever. `crash_signature()` (core/jobs.py:243) only fires when `returncode` is a 0xC0000005-family code, which this detached crash never produces. So detect the crash by the **`.dmp` artifact + SPMHDB-238 log line**, not the `crash` field. `cancel_job` on it returns the zombie still `running` (can't kill the detached worker)."

## Pipeline Impact

Any pipeline stage that uses `run_specctra_import_session` (the standalone-CLI import) directly to get a routed `.ses` back into a `.brd` is **unusable** on this installation — it will always crash, always leave a zombie `running`-state job record that neither `wait_for_job` nor `cancel_job` ever resolves, and always leave a stale `.dmp` file in the job dir.

(Note: `run_placement_and_routing_assistance` (placement_routing_assistance_tools.py) does **not** use `run_specctra_import_session` — its `specctra_import` stage calls `run_allegro_specctra_import` (the working, script-replay path) directly, not the broken standalone-CLI route. Its caveat-carrying DRC stage (placement_routing_assistance_tools.py:141-160) is a general, documented best-effort handling for *any* import-stage failure — including a hypothetical future failure of the working path — not a workaround for this specific `spif_batch -i` crash.)

Because the standalone-CLI route is the **only** such route that exists (no alternate flag on `spif_batch`, no session-import option on `specctra.exe`), there is no in-suite in-place alternative besides switching to the completely different Allegro-script-replay approach — which is exactly what `run_allegro_specctra_import` is.