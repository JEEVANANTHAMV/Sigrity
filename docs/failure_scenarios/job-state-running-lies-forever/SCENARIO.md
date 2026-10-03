# Scenario: job-state-running-lies-forever

**Manifest entry:** #88 — "state 'running' forever post-restart"
**Status category:** `known_blocked`
**Verified workaround:** NO in-suite state fix — verify by artifact/log check instead

## What goes wrong

`JobRecord.state` (`core/jobs.py:62-93`) is only ever updated in ONE place: the `_watch()`
coroutine, which runs `await proc.wait()` and then writes the final state + `returncode` +
`ended_at` to both the in-memory dict and `job.json` (via `record.save()`, `core/jobs.py:235-273`).
For the lifetime of ONE server process that works: a running job's dict entry flips to
`succeeded`/`failed`/`timeout`/`cancelled` the moment the OS reports the child process ended.

The lie happens across a **server process boundary**:

1. **`job.json` is written only at submission and at final state.** `submit()` calls
   `record.save()` with `state="running"` right after launching the process
   (`core/jobs.py:136,156`), and the next `save()` doesn't happen until `_watch()` finishes
   (line 273). There is no intermediate "still running" heartbeat write.
2. **The MCP server restarts** (crash, user restart, transport switch) while a job is still
   genuinely running in the background — the child process was launched via
   `asyncio.create_subprocess_exec` and keeps running independently; only the *tracking*
   (`JobManager._jobs` dict, `_procs` dict, the `_watch` task, `DismissWatcher`) dies with the
   server process. There is no pidfile, no service, no external supervisor; `job_manager` is a
   module-level singleton (`core/jobs.py:340`).
3. **After the restart, `JobManager.get(job_id)` cannot find the job in memory** (`core/jobs.py:275-277`)
   and falls back to reading `job.json` off disk (`core/jobs.py:278-282`) — which says
   `state: "running"`, because that was the last value written there before the crash.
   Nothing in this suite will ever update that file: the `_watch` task that owns
   `proc.wait()` is gone, and no code path re-adopts an orphaned, already-running PID (there is
   no "is pid X still alive?" re-check anywhere in `jobs.py` — `wait()` explicitly does the
   OPPOSITE, see below).

Result: `get_job_status(job_id)` on that orphaned job, in the new server process, returns
`state: "running"` **forever**, with a `pid` that may be long gone or (worse, same-machine
Windows PID reuse) a PID that now belongs to some unrelated process. The `returncode` field
stays `null`. This is distinct from the sibling scenario `job-state-succeeded-lies` (which is
about rc 0 within one server lifetime) — this one is specifically the *stale persisted
state* shape, and the manifest scopes it as "post-restart".

The code is *aware* this exists but deliberately does NOT try to "fix" the lie: `JobManager.wait()`
(`core/jobs.py:285-305`) checks `self._procs.get(job_id)` — the in-memory handle — and if there is
no live process handle AND the (disk-reloaded) record says `state == "running"`, it does not wait
on anything nor check the PID; it raises:

> `JobStillRunningError: Job '<id>' is running in a process this server instance is not tracking
> (likely a previous server run) — poll status()/tail_log() instead.` (`core/jobs.py:288-293`)

So the suite's own designed answer to a cross-restart "running" job is "we can't see it anymore,
stop polling us for it, use the log/files on disk" — the `state` field itself is never corrected
in-place. `list_all_jobs` (in `domains/platform/job_tools.py:142-148`) is in-memory-only
("in-memory, current process only" per SKILL.md's job-tools table) and will not even show the
orphaned job at all.

## Evidence

- `core/jobs.py:68` — `state: str = "pending"` comment: "pending -> running -> succeeded|failed|timeout"; only `_watch()` (the sole writer of terminal state) exists to perform the terminal transition.
- `core/jobs.py:108-159` — `submit()`: `state="running"` set at construction (line 136), `record.save()` (line 156) is the last write before the process is handed to `_watch()`; no heartbeat writes afterward.
- `core/jobs.py:235-273` — `_watch()`: `returncode = await proc.wait()` is the only path to a terminal `record.state`; `record.save()` (line 273) is the only other `save()` call apart from `submit()`'s and `cancel()`'s (line 314).
- `core/jobs.py:275-283` — `get()`: in-memory miss → read `job.json` from `settings.resolve_workdir()/job_id/job.json` → reconstruct a `JobRecord` from disk. This is exactly the code path that returns the stale `running` record after a restart; nothing updates it further.
- `core/jobs.py:285-305` — `wait()`: `proc = self._procs.get(job_id)`; `if proc is None: if record.state == "running": raise JobStillRunningError(...)` — the suite's explicit, documented acknowledgement that a disk-only `running` job cannot be tracked by this instance, plus its prescribed response ("poll status()/tail_log() instead"). Note: per `job_tools.py:74-83`, `wait_for_job` catches `JobNotFoundError` but NOT `JobStillRunningError` — that one propagates to the MCP client as a raised tool error, which is itself a useful (if blunt) signal that the job is not this server's to track.
- `core/jobs.py:143-148` — `asyncio.create_subprocess_exec(...)` with no `start_new_session`/detached-process handling documented as creating anything the new server process could re-attach to; the child's lifetime is OS-level, independent of `JobManager`.
- `.forjinn/skills/sigrity/SKILL.md`, Rule 2 opening sentence — "`state` is a liar in BOTH directions ... AND `running` ≠ stuck (batch_drc/ibischk launchers exit while `job.json` still says running; Celsius3D idles forever AFTER a successful solve)." (The batch_drc/ibischk parenthetical is a one-lifetime shape of the same "state field not authoritative" principle, documented under the same Rule 2; the cross-restart shape is the one captured by `JobStillRunningError`.)
- `domains/platform/job_tools.py:142-148` — `list_all_jobs` docstring: "List every job this server instance has launched since it started" — post-restart, an orphaned job is simply absent from this list, compounding the confusion (a job that `get_job_status` will happily report as `running` doesn't appear in `list_all_jobs`).
- `core/process.py:63-113` — `submit_job` → `job_manager.submit`: no persistence mechanism beyond what `submit` itself does; nothing in `process.py` adds a cross-restart tracking path.
