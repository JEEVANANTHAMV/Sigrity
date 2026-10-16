from dataclasses import dataclass

import pytest

from sigrity_mcp.domains.cad.allegro_drc_tools import run_allegro_batch_drc, run_allegro_checkplus


@pytest.mark.asyncio
async def test_run_allegro_batch_drc_default_nographic(fake_exe):
    result = await run_allegro_batch_drc("board.brd")
    assert result["command"][1:] == ["-nographic", "board.brd"]
    # fake_exe's command exits almost instantly (real terminal state), so the bounded
    # poll should resolve to a real state with no "detached launcher" note.
    assert result["state"] in ("succeeded", "failed")
    assert "note" not in result


@pytest.mark.asyncio
async def test_run_allegro_batch_drc_with_output_and_graphic(fake_exe):
    result = await run_allegro_batch_drc("board.brd", output_file="drc.txt", nographic=False)
    assert result["command"][1:] == ["board.brd", "drc.txt"]


# Regression coverage for a real, intermittent failure mode: batch_drc.exe's launcher
# process detaches before its own job record reaches a terminal state, even though the
# real DRC work finished and wrote its completion marker to batch_drc.log. Confirmed
# live against real on-disk job artifacts (a complete batch_drc.log ending "DRC update
# completed" + state:"running"/returncode:null forever). These tests fake submit_job
# and job_manager directly so the polling LOGIC is exercised deterministically, with no
# real subprocess or sleep involved.


@dataclass
class _FakeRecord:
    job_id: str
    job_dir: str
    command: list
    state: str = "running"
    returncode: int | None = None


class _FakeJobManagerAlwaysRunning:
    def __init__(self, record):
        self._record = record

    def get(self, job_id):
        return self._record


@pytest.mark.asyncio
async def test_run_allegro_batch_drc_detects_detached_launcher_via_log_marker(
    tmp_path, monkeypatch
):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.allegro_drc_tools as drc_module

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "batch_drc.log").write_text("... DRC update completed\n", encoding="utf-8")
    fake_record = _FakeRecord(job_id="fake-job", job_dir=str(job_dir), command=["batch_drc.exe"])

    async def _fake_submit_job(*args, **kwargs):
        return fake_record

    monkeypatch.setattr(drc_module, "submit_job", _fake_submit_job)
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManagerAlwaysRunning(fake_record))

    result = await run_allegro_batch_drc("board.brd", poll_timeout_seconds=5.0)
    assert "DRC update completed" in result["note"]
    assert result["state"] == "running"  # unchanged -- job record itself never resolved


@pytest.mark.asyncio
async def test_run_allegro_batch_drc_preserves_original_behavior_when_neither_resolves(
    tmp_path, monkeypatch
):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.allegro_drc_tools as drc_module

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    # No batch_drc.log at all -- neither a terminal state nor the completion marker
    # ever appears within the poll window.
    fake_record = _FakeRecord(job_id="fake-job-2", job_dir=str(job_dir), command=["batch_drc.exe"])

    async def _fake_submit_job(*args, **kwargs):
        return fake_record

    monkeypatch.setattr(drc_module, "submit_job", _fake_submit_job)
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManagerAlwaysRunning(fake_record))

    result = await run_allegro_batch_drc("board.brd", poll_timeout_seconds=0.2)
    assert result["state"] == "running"
    assert "note" not in result


@pytest.mark.asyncio
async def test_run_allegro_checkplus_minimal(fake_exe):
    result = await run_allegro_checkplus("proj")
    assert result["command"][1:] == ["-proj", "proj"]


@pytest.mark.asyncio
async def test_run_allegro_checkplus_all_options(fake_exe):
    result = await run_allegro_checkplus(
        "proj",
        verbose=True,
        max_messages=50,
        include_path="C:/inc",
        env_file="env.txt",
        rule_file="rules.txt",
    )
    assert result["command"][1:] == [
        "-proj", "proj", "-verbose", "-max_messages", "50",
        "-I", "C:/inc", "-r", "env.txt", "-r", "rules.txt",
    ]
