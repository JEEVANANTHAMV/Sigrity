import sys

import pytest

from sigrity_mcp.core.jobs import JobManager
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
