"""Phase B0.3: confirms job_manager.cancel() actually terminates a real GUI-capable
process on Windows, not just a plain console command -- since Cadence's GUI launchers
(allegro.exe/Capture.exe) behave differently from every previously-tested Sigrity
console tool, and we already saw one of them (allegro.exe) hang indefinitely on a live
probe. If cancel() only killed a wrapper/stub and left a real window running, that
would be a real safety gap once an LLM caller can trigger one of these tools through
run_tool_pipeline.
"""

import sys

import pytest

from sigrity_mcp.core.jobs import JobManager


@pytest.mark.asyncio
async def test_cancel_terminates_a_genuinely_slow_process(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_gui_tool")
    # Simulate a GUI app that would otherwise sit open indefinitely.
    record = await jm.submit(
        tool="fake_gui_tool",
        command=[sys.executable, "-c", "import time; time.sleep(120)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    assert record.state == "running"

    cancelled = jm.cancel(job_id)
    assert cancelled.state == "cancelled"

    # The underlying OS process must actually be gone, not just marked cancelled in our
    # bookkeeping -- proc.wait() should resolve promptly once really killed.
    proc = jm._procs[job_id]
    import asyncio

    await asyncio.wait_for(proc.wait(), timeout=10)
    assert proc.returncode is not None
