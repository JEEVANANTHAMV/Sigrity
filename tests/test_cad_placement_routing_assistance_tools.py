from dataclasses import dataclass
from typing import Optional

import pytest

from sigrity_mcp.domains.cad import placement_routing_assistance_tools as prat


@dataclass
class FakeRecord:
    state: str
    returncode: Optional[int] = 0
    job_dir: str = "."


def _fake_job_result(job_id: str) -> dict:
    return {"job_id": job_id, "state": "running", "job_dir": ".", "command": []}


@pytest.mark.asyncio
async def test_pipeline_aborts_early_when_placement_fails(monkeypatch, tmp_path):
    async def fake_placement(*args, **kwargs):
        return _fake_job_result("placement-1")

    records = {"placement-1": FakeRecord(state="failed", returncode=1)}

    async def fake_wait(job_id, timeout):
        return records[job_id]

    monkeypatch.setattr(prat, "run_allegro_placement", fake_placement)
    monkeypatch.setattr(prat.job_manager, "wait", fake_wait)

    result = await prat.run_placement_and_routing_assistance(str(tmp_path / "board.brd"))

    assert "error" in result
    assert len(result["stages"]) == 1
    assert result["stages"][0]["stage"] == "placement"
    assert result["final_drc"] is None


@pytest.mark.asyncio
async def test_pipeline_continues_past_nonzero_autoroute_exit_and_reports_import_failure(monkeypatch, tmp_path):
    board = tmp_path / "board.brd"
    board.write_text("fake board", encoding="utf-8")

    calls = []

    async def fake_placement(*args, **kwargs):
        calls.append("placement")
        return _fake_job_result("placement-1")

    async def fake_export(board_file, dsn_file=None):
        calls.append("export")
        return _fake_job_result("export-1")

    async def fake_autoroute(dsn_file, do_file, graphics=False):
        calls.append("autoroute")
        return _fake_job_result("autoroute-1")

    async def fake_import(board_file, session_file):
        calls.append("import")
        return _fake_job_result("import-1")

    async def fake_drc(board_file, output_file=None, nographic=True):
        calls.append("drc")
        return _fake_job_result("drc-1")

    records = {
        "placement-1": FakeRecord(state="succeeded", returncode=0, job_dir=str(tmp_path)),
        "export-1": FakeRecord(state="succeeded", returncode=0, job_dir=str(tmp_path)),
        # specctra.exe returns nonzero even on a real successful route - job is "failed"
        # but the pipeline must not treat that as a hard stop.
        "autoroute-1": FakeRecord(state="failed", returncode=4, job_dir=str(tmp_path)),
        "import-1": FakeRecord(state="failed", returncode=-1, job_dir=str(tmp_path)),
        "drc-1": FakeRecord(state="succeeded", returncode=0, job_dir=str(tmp_path)),
    }

    async def fake_wait(job_id, timeout):
        return records[job_id]

    monkeypatch.setattr(prat, "run_allegro_placement", fake_placement)
    monkeypatch.setattr(prat, "run_spif_export_to_specctra", fake_export)
    monkeypatch.setattr(prat, "run_specctra_autoroute", fake_autoroute)
    monkeypatch.setattr(prat, "run_specctra_import_session", fake_import)
    monkeypatch.setattr(prat, "run_allegro_batch_drc", fake_drc)
    monkeypatch.setattr(prat.job_manager, "wait", fake_wait)

    result = await prat.run_placement_and_routing_assistance(str(board))

    assert calls == ["placement", "export", "autoroute", "import", "drc"]
    stage_names = [s["stage"] for s in result["stages"]]
    assert stage_names == ["placement", "specctra_export", "specctra_autoroute", "specctra_import", "post_route_drc"]
    assert result["final_drc"]["state"] == "succeeded"
    assert "caveat" in result["final_drc"]
    assert result["board_checked_by_drc"] == str(board)
