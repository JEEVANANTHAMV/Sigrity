import asyncio
import sys

import pytest

from sigrity_mcp.core import jobs as jobs_module
from sigrity_mcp.core import win32gui_helper
from sigrity_mcp.core.jobs import JobManager, JobRecord, crash_signature
from sigrity_mcp.core.errors import JobNotFoundError


class _FakeDismissWatcher:
    """Stand-in for win32gui_helper.DismissWatcher that needs no real Windows GUI --
    just records whether/when it was started and stopped, so the job-lifecycle wiring
    (start on submit, stop once the job ends) can be tested on any machine."""

    instances: list["_FakeDismissWatcher"] = []

    def __init__(self, pid):
        self.pid = pid
        self.stopped = False
        self.stop_calls = 0
        _FakeDismissWatcher.instances.append(self)

    def stop(self, join_timeout: float = 5.0) -> None:
        self.stopped = True
        self.stop_calls += 1


@pytest.fixture
def fake_dismiss_watcher(monkeypatch):
    _FakeDismissWatcher.instances.clear()

    def _spawn(pid, **kwargs):
        return _FakeDismissWatcher(pid)

    monkeypatch.setattr(jobs_module.win32gui_helper, "spawn_dismiss_watcher", _spawn)
    return _FakeDismissWatcher


@pytest.mark.asyncio
async def test_submit_wait_and_tail_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    record = await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "print('line1'); print('line2')"],
        job_dir=job_dir,
        job_id=job_id,
    )
    assert record.state == "running"

    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "succeeded"
    assert finished.returncode == 0

    lines = jm.tail_log(job_id, max_lines=10)
    assert "line1" in lines[0]
    assert "line2" in lines[1]

    files = jm.list_output_files(job_id)
    assert "run.log" in files
    assert "job.json" in files


@pytest.mark.asyncio
async def test_failing_process_marks_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "import sys; sys.exit(3)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "failed"
    assert finished.returncode == 3


@pytest.mark.asyncio
async def test_license_marker_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "print('Error: Unable to checkout FlexNet license')"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.license_issue_suspected is True


def test_unknown_job_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    with pytest.raises(JobNotFoundError):
        jm.get("does-not-exist")


@pytest.mark.asyncio
async def test_cancel_running_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    record, outcome = await jm.cancel(job_id)
    assert record.state == "cancelled"
    assert outcome == "killed"


@pytest.mark.asyncio
async def test_cancel_state_survives_watcher_completion(tmp_path, monkeypatch):
    # Regression: cancel() sets state="cancelled" synchronously, but the _watch() task
    # (already awaiting proc.wait() when kill() fires) used to unconditionally overwrite
    # that with "failed" once the killed process's exit code arrived a moment later --
    # discovered live against a real hung Allegro process (Phase B0.3). A cancelled job
    # must stay reported as cancelled, not get silently relabeled as a failure.
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    await jm.cancel(job_id)

    proc = jm._procs[job_id]
    await asyncio.wait_for(proc.wait(), timeout=10)
    # Give the _watch() task a beat to run past the now-resolved proc.wait().
    await asyncio.sleep(0.2)

    final = jm.get(job_id)
    assert final.state == "cancelled"


def _rec(tmp_path, returncode, tool="spif_batch"):
    log = tmp_path / "run.log"
    log.write_text("ERROR(SPMHDB-238): The design is corrupted.\n", encoding="utf-8")
    return JobRecord(job_id="j", tool=tool, command=[], job_dir=str(tmp_path),
                     state="failed", returncode=returncode, log_path=str(log))


def test_crash_signature_detects_nt_status(tmp_path):
    # The real spif_batch -i crash: unsigned 0xC0000005 + a non-empty log.
    sig = crash_signature(_rec(tmp_path, 3221225477))
    assert sig is not None and sig["is_crash"] is True
    assert sig["nt_status"] == "0xC0000005"
    assert "SPMHDB-238" in sig["message"]


def test_crash_signature_ignores_clean_error_exit(tmp_path):
    # A normal nonzero tool exit (e.g. specctra's rc=4 on a successful route) is not a crash.
    assert crash_signature(_rec(tmp_path, 4)) is None
    assert crash_signature(_rec(tmp_path, 2)) is None
    assert crash_signature(_rec(tmp_path, 0)) is None
    assert crash_signature(_rec(tmp_path, None)) is None


def test_job_status_includes_crash_field_when_applicable(tmp_path):
    from sigrity_mcp.domains.platform.job_tools import _record_to_dict

    normal = _rec(tmp_path, 3)
    assert "crash" not in _record_to_dict(normal)

    crashed = _rec(tmp_path, 3221225477)
    out = _record_to_dict(crashed)
    assert out.get("crash", {}).get("nt_status") == "0xC0000005"


# --- job_stall_timeout_seconds watchdog (core.config) -----------------------------
#
# Regression coverage for a real gap found alongside the runaway-log killer: before
# this, a job whose log went completely silent (an undismissed dialog, a silent
# license wait, Celsius3D's confirmed post-completion idle-stall) had NO automatic
# recovery at all -- only a human polling get_job_status forever would ever notice.
# These tests use tiny timeouts (monkeypatched onto the shared `settings` singleton,
# auto-restored by monkeypatch) so they run fast and deterministically on any machine.


@pytest.mark.asyncio
async def test_stall_watchdog_kills_a_genuinely_silent_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module.settings, "job_stall_timeout_seconds", 0.3)
    monkeypatch.setattr(jobs_module.settings, "stall_watchdog_poll_seconds", 0.05)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        # Sleeps far longer than the stall timeout and never writes a single byte --
        # exactly the "undismissed dialog" / "silent license wait" shape.
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "failed"
    assert finished.stall_timeout_killed is True
    assert finished.runaway_log_killed is False


@pytest.mark.asyncio
async def test_stall_watchdog_does_not_kill_a_job_that_keeps_producing_output(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    # Stall timeout is shorter than the job's total runtime, but the job prints well
    # inside that window on every iteration -- each print must reset the "silent for
    # how long" clock, so this must finish as a genuine success, not get killed.
    monkeypatch.setattr(jobs_module.settings, "job_stall_timeout_seconds", 0.3)
    monkeypatch.setattr(jobs_module.settings, "stall_watchdog_poll_seconds", 0.05)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    script = (
        "import time\n"
        "for _ in range(6):\n"
        "    print('still working', flush=True)\n"
        "    time.sleep(0.1)\n"
    )
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", script],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "succeeded"
    assert finished.stall_timeout_killed is False


@pytest.mark.asyncio
async def test_stall_watchdog_disabled_when_timeout_is_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module.settings, "job_stall_timeout_seconds", 0)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "pass"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "succeeded"
    assert finished.stall_timeout_killed is False


@pytest.mark.asyncio
async def test_stall_timeout_seconds_override_kills_sooner_than_global_default(
    tmp_path, monkeypatch
):
    # Regression coverage for the per-job override: a job whose per-call
    # stall_timeout_seconds is short must be killed even while the global default
    # stays long -- this is how tclsession.run_session tightens the watchdog for
    # Allegro/Capture interactive sessions without affecting every other job type.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module.settings, "job_stall_timeout_seconds", 3600)
    monkeypatch.setattr(jobs_module.settings, "stall_watchdog_poll_seconds", 0.05)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
        stall_timeout_seconds=0.3,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "failed"
    assert finished.stall_timeout_killed is True


@pytest.mark.asyncio
async def test_stall_timeout_seconds_override_none_keeps_global_default(tmp_path, monkeypatch):
    # The flip side: passing no override must fall back to the global default exactly
    # as before this change (no regression for every non-Allegro/Capture job type).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module.settings, "job_stall_timeout_seconds", 0.3)
    monkeypatch.setattr(jobs_module.settings, "stall_watchdog_poll_seconds", 0.05)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
        stall_timeout_seconds=None,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "failed"
    assert finished.stall_timeout_killed is True


def test_record_to_dict_surfaces_runaway_and_stall_kill_reasons(tmp_path):
    from sigrity_mcp.domains.platform.job_tools import _record_to_dict

    normal = _rec(tmp_path, 0)
    out = _record_to_dict(normal)
    assert out["runaway_log_killed"] is False
    assert out["stall_timeout_killed"] is False
    assert "note" not in out

    runaway = _rec(tmp_path, 1)
    runaway.runaway_log_killed = True
    out = _record_to_dict(runaway)
    assert out["runaway_log_killed"] is True
    assert "max_log_bytes" in out["note"]

    stalled = _rec(tmp_path, 1)
    stalled.stall_timeout_killed = True
    out = _record_to_dict(stalled)
    assert out["stall_timeout_killed"] is True
    assert "silent" in out["note"]


# --- dismiss_dialogs wiring (core.win32gui_helper.DismissWatcher auto-start/stop) -------
#
# Regression coverage for the real, confirmed-live hang this closes: an interactive
# Allegro session job (`allegro.exe -s <script> <board>`) can raise a modal startup
# dialog with nothing present to click it, and previously the only way to avoid an
# indefinite hang was for the calling LLM agent (or a hand-written script) to separately
# remember to poll `win32gui_helper.auto_dismiss_dialogs(pid)` concurrently -- which a
# plain MCP tool caller has no way to do. These tests don't need a real Windows GUI; they
# swap in `_FakeDismissWatcher` for `win32gui_helper.spawn_dismiss_watcher` and just check
# the job-lifecycle wiring: started when `dismiss_dialogs=True`, never started otherwise,
# and always stopped once the job stops being "running" (succeeded/failed/cancelled).


@pytest.mark.asyncio
async def test_submit_with_dismiss_dialogs_starts_and_stops_watcher(
    tmp_path, monkeypatch, fake_dismiss_watcher
):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("allegro")
    await jm.submit(
        tool="allegro",
        command=[sys.executable, "-c", "print('ok')"],
        job_dir=job_dir,
        job_id=job_id,
        dismiss_dialogs=True,
    )
    assert len(fake_dismiss_watcher.instances) == 1
    watcher = fake_dismiss_watcher.instances[0]
    assert watcher.pid == jm.get(job_id).pid
    assert watcher.stopped is False

    await jm.wait(job_id, timeout=10)
    # _stop_dismiss_watcher hands the blocking .stop() off to the default executor so it
    # never blocks the event loop -- give that scheduled call a beat to actually run.
    for _ in range(50):
        if watcher.stopped:
            break
        await asyncio.sleep(0.05)
    assert watcher.stopped is True


@pytest.mark.asyncio
async def test_submit_without_dismiss_dialogs_never_starts_watcher(
    tmp_path, monkeypatch, fake_dismiss_watcher
):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("allegro_report")
    await jm.submit(
        tool="allegro_report",
        command=[sys.executable, "-c", "print('ok')"],
        job_dir=job_dir,
        job_id=job_id,
    )
    await jm.wait(job_id, timeout=10)
    assert fake_dismiss_watcher.instances == []


@pytest.mark.asyncio
async def test_cancel_stops_dismiss_watcher_immediately(tmp_path, monkeypatch, fake_dismiss_watcher):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("allegro")
    await jm.submit(
        tool="allegro",
        command=[sys.executable, "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
        dismiss_dialogs=True,
    )
    watcher = fake_dismiss_watcher.instances[0]
    assert watcher.stopped is False

    await jm.cancel(job_id)
    # Hands off to the executor the same way the normal completion path does (see
    # _stop_dismiss_watcher) -- give the scheduled call a beat to actually run, same as
    # test_submit_with_dismiss_dialogs_starts_and_stops_watcher above.
    for _ in range(50):
        if watcher.stopped:
            break
        await asyncio.sleep(0.05)
    assert watcher.stopped is True

    proc = jm._procs[job_id]
    await asyncio.wait_for(proc.wait(), timeout=10)


def test_dismiss_watcher_stop_is_idempotent_across_cancel_and_watch(tmp_path):
    # cancel() and _watch()'s completion path both call _stop_dismiss_watcher() for the
    # same job_id -- the second call must be a harmless no-op (dict.pop default), not an
    # error, regardless of call order.
    jm = JobManager()
    jm._dismiss_watchers["job-1"] = _FakeDismissWatcher(pid=123)
    jm._stop_dismiss_watcher("job-1")
    jm._stop_dismiss_watcher("job-1")  # must not raise
    assert "job-1" not in jm._dismiss_watchers


# --- get()/wait() correcting a stale "running" state via PID liveness --------------
#
# Regression coverage for a real gap: a job submitted by an earlier server process
# (restarted/crashed before the job finished) has no entry in self._jobs or self._procs
# in the NEW server instance -- get()'s disk-fallback branch used to return the stale
# "running" record verbatim, forever, with no way for a caller to ever learn the truth.
#
# _pid_alive() itself is a thin ctypes.OpenProcess wrapper verified once, directly,
# against this test process's own PID (always genuinely alive) and an arbitrarily huge
# PID number (never a real process). get()/wait()'s own branching logic is then tested
# with _pid_alive() monkeypatched to a fixed answer -- real PIDs are not reused
# deterministically (the whole point of the OS's reuse hazard this suite already
# accepts), so a real spawn-and-reap PID is flaky under a full test-suite run's process
# churn; monkeypatching isolates what these tests actually assert (get()/wait()'s
# control flow), not the OS's PID bookkeeping.


def test_pid_alive_sanity_check():
    import os

    assert jobs_module._pid_alive(os.getpid()) is True
    assert jobs_module._pid_alive(999_999_999) is False


def _write_stale_running_job_json(tmp_path, job_id: str, pid: int) -> None:
    from sigrity_mcp.core.config import settings

    job_dir = settings.resolve_workdir() / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    record = JobRecord(
        job_id=job_id, tool="fake_tool", command=[], job_dir=str(job_dir),
        state="running", pid=pid, started_at=0.0, log_path=str(job_dir / "run.log"),
    )
    (job_dir / "job.json").write_text(
        __import__("json").dumps(__import__("dataclasses").asdict(record)), encoding="utf-8"
    )


def test_get_corrects_stale_running_state_when_pid_is_dead(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module, "_pid_alive", lambda pid: False)
    _write_stale_running_job_json(tmp_path, "fake_tool-dead", 123456)

    jm = JobManager()
    record = jm.get("fake_tool-dead")
    assert record.state == "failed"
    assert record.returncode is None

    # The correction is persisted, not just returned once.
    reread = jm.get("fake_tool-dead")
    assert reread.state == "failed"


def test_get_leaves_running_state_when_pid_is_alive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module, "_pid_alive", lambda pid: True)
    _write_stale_running_job_json(tmp_path, "fake_tool-alive", 123456)

    jm = JobManager()
    record = jm.get("fake_tool-alive")
    assert record.state == "running"


@pytest.mark.asyncio
async def test_wait_resolves_orphaned_but_finished_job_instead_of_raising(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module, "_pid_alive", lambda pid: False)
    _write_stale_running_job_json(tmp_path, "fake_tool-orphan", 123456)

    jm = JobManager()
    # No entry in jm._procs for this job_id -- simulates "this server instance never
    # submitted it" exactly like a restart would.
    record = await jm.wait("fake_tool-orphan", timeout=1.0)
    assert record.state == "failed"


@pytest.mark.asyncio
async def test_wait_still_raises_when_untracked_process_is_genuinely_alive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(jobs_module, "_pid_alive", lambda pid: True)
    _write_stale_running_job_json(tmp_path, "fake_tool-alive2", 123456)

    jm = JobManager()
    with pytest.raises(jobs_module.JobStillRunningError):
        await jm.wait("fake_tool-alive2", timeout=1.0)


# --- cancel() outcome classification ------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_outcome_no_live_handle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    # A record in memory with state="running" but deliberately no entry in jm._procs --
    # simulates "this server instance didn't submit this job".
    jm._jobs[job_id] = JobRecord(
        job_id=job_id, tool="fake_tool", command=[], job_dir=str(job_dir),
        state="running", pid=999999,
    )
    record, outcome = await jm.cancel(job_id)
    assert outcome == "no-live-handle"
    assert record.state == "running"  # unchanged -- no kill was performed


@pytest.mark.asyncio
async def test_cancel_outcome_already_terminal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_tool")
    await jm.submit(
        tool="fake_tool", command=[sys.executable, "-c", "pass"], job_dir=job_dir, job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=10)
    assert finished.state == "succeeded"

    record, outcome = await jm.cancel(job_id)
    assert outcome == "already-terminal"
