# Workarounds: cancel-cannot-kill-detached-workers

**Verified workaround: NO** in-suite fix — the confirmed caller-side escape hatch is a manual,
OS-level PID check/kill, plus `clear_stale_design_lock` if the job in question was a
GUI-session-type tool (Allegro/Capture).

## What works (verified, caller-side only)

1. **After calling `cancel_job(job_id)` — especially if the job is one you suspect was (a)
   submitted by an earlier server lifetime, or (b) a tool that's documented to spawn its own child
   workers (e.g. `SPDSIM`, per `core/tool_status.py:769-770`) — do NOT trust the returned
   `JobRecord`/`_record_to_dict` output as proof the OS process(es) actually died.** The returned
   dict (`domains/platform/job_tools.py:131-138` → `job_tools.py:20-61`) will look *identical*
   whether `cancel()` actually killed a live process, found no live handle (`proc is None` after a
   server restart) and silently did nothing, or found the record already non-`running` and
   silently did nothing (`core/jobs.py:310-316`). There is no `cancelled: false`/`kill_failed`
   flag to check for — the only honest signal is to go around the suite and check the OS
   directly.
2. **Check/kill the PID at the OS level.** `JobRecord`/`job.json` carries the top-level
   `pid` (`core/jobs.py:69`, written by `record.save()` even on the stale-across-restart shape).
   Use an OS-level tool (e.g. Windows `tasklist <pid>`, or Task Manager) to see whether that PID
   is actually still a live process. If it is still alive — `cancel_job` did not actually kill
   it (the `proc is None` no-op path was hit) — kill it manually by PID at the OS level. Also
   inspect for *child* PIDs descended from it (e.g. `tasklist /FI "PID eq <parent>"` won't show
   children directly; Task Manager's process tree, or `wmic process get ProcessId,ParentProcessId`,
   is how a caller actually enumerates the detached worker tree this suite has no visibility into)
   — kill those manually too, since NO kill path in `core/jobs.py` (`cancel()`,
   `size_watchdog()`, `stall_watchdog()`) touches anything but the immediate child PID.
3. **If the job was a `tool="allegro"`/`tool="capture"` session job** (an interactive-GUI-launch
   type, the only type that gets a `DismissWatcher`, per `core/tclsession.py:194-197`), after
   confirming the top-level PID is actually gone, call `check_design_lock(design_path)`
   (`domains/platform/file_tools.py:67-71`) — a killed (not cleanly-exited) GUI session is
   exactly what orphans a `<design>.lck` file (see `core/tclsession.py:35-57`,
   `clear_stale_design_lock`'s docstring: "if the process that created it is killed ... rather
   than exiting cleanly, that `.lck` file is orphaned. The NEXT batch launch against that same
   design path then hits a real modal 'this design appears to be open/locked, override?' dialog").
   If `lock_exists` is `True`, `delete_file` the `.lck` (or note that the suite's own launch path
   for `allegro`/`capture` session jobs calls `clear_stale_design_lock` automatically before
   launch — grep shows it's wired into `start_capture_session` and the Allegro run-session path,
   per `core/tool_status.py:465-466` — so this manual step mostly matters if you're re-launching
   the SAME design via a *non*-session, direct `run_*` tool that doesn't auto-clear).

## What does NOT work / is out of scope

- No in-suite API kills a *process tree* (no `taskkill /T`-equivalent anywhere in
  `core/jobs.py`/`core/process.py`), no API re-adopts an orphaned PID so that a *later*
  `cancel_job` in a new server process could actually reach it, and no API reports back
  "the kill I just performed found no live handle" vs. "the kill I just performed succeeded."
  All three of these would be the natural in-suite fixes, and none of them exist — which is why
  this stays `known_blocked` with `verified_workaround: NO` in the manifest (the "manual PID
  check + clear_stale_design_lock" listed in the manifest INDEX is precisely the caller-side
  escape hatch described above, explicitly NOT an in-suite feature).
- Do NOT interpret `cancel_job` returning a `JobRecord` whose `state` is still `"running"` (the
  stale-across-restart shape) as "cancel failed, retry `cancel_job`" — retrying does the exact
  same `proc is None` no-op again. The only thing that actually resolves a stale, orphaned,
  still-`running`-on-OS process is the OS-level manual kill in point 2.
