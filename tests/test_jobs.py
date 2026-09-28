import asyncio
import sys

import pytest

from sigrity_mcp.core import jobs as jobs_module
from sigrity_mcp.core.jobs import JobManager, JobRecord, crash_signature
from sigrity_mcp.core.errors import JobNotFoundError


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
    record = jm.cancel(job_id)
    assert record.state == "cancelled"


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
    jm.cancel(job_id)

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
