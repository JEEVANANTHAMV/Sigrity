from dataclasses import dataclass
from pathlib import Path

import pytest

from sigrity_mcp.domains.cad.capture_headless_tools import (
    author_capture_schematic_headless,
    generate_capture_pcb_netlist,
)


@dataclass
class _FakeRecord:
    job_id: str
    job_dir: str
    command: list
    state: str = "succeeded"
    returncode: int | None = 0


class _FakeJobManagerMulti:
    """Resolves each job_id to its own pre-built fake record -- needed because
    author_capture_schematic_headless submits TWO jobs (author, then annotate) in one
    call, each of which must independently resolve to its own run.log content."""

    def __init__(self, records: dict[str, _FakeRecord]):
        self._records = records

    async def wait(self, job_id, timeout):
        return self._records[job_id]

    def get(self, job_id):
        return self._records[job_id]


@pytest.mark.asyncio
async def test_generate_capture_pcb_netlist_command_and_success(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    out_dir = tmp_path / "pst"
    out_dir.mkdir()
    for name, content in (
        ("pstchip.dat", "chip"),
        ("pstxprt.dat", "PART_NAME\n R1 'X':;\n"),
        ("pstxnet.dat", "net"),
    ):
        (out_dir / name).write_text(content, encoding="utf-8")
    (out_dir / "netlist.log").write_text("packaging the design view...", encoding="utf-8")

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    record = _FakeRecord(job_id="fake-pstswp", job_dir=str(job_dir), command=["pstswp.exe"])

    async def _fake_submit_job(*args, **kwargs):
        return record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManagerMulti({"fake-pstswp": record}))
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    result = await generate_capture_pcb_netlist(
        dsn_file=str(tmp_path / "design.dsn"), output_dir=str(out_dir)
    )
    assert result["complete"] is True
    assert set(result["pst_files"]) == {"pstchip.dat", "pstxprt.dat", "pstxnet.dat"}
    assert "error" not in result


@pytest.mark.asyncio
async def test_generate_capture_pcb_netlist_incomplete_reports_error(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    out_dir = tmp_path / "pst"
    out_dir.mkdir()
    # Only 2 of 3 required files present -> incomplete.
    (out_dir / "pstchip.dat").write_text("chip", encoding="utf-8")
    (out_dir / "pstxprt.dat").write_text("part", encoding="utf-8")

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    record = _FakeRecord(job_id="fake-pstswp-2", job_dir=str(job_dir), command=["pstswp.exe"])

    async def _fake_submit_job(*args, **kwargs):
        return record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManagerMulti({"fake-pstswp-2": record}))
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    result = await generate_capture_pcb_netlist(
        dsn_file=str(tmp_path / "design.dsn"), output_dir=str(out_dir)
    )
    assert result["complete"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_generate_capture_pcb_netlist_command_args(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    job_dir = tmp_path / "job2"
    job_dir.mkdir()
    captured = {}

    async def _fake_submit_job(*, tool, build_args):
        captured["tool"] = tool
        captured["build_args"] = build_args
        return _FakeRecord(job_id="fake-args", job_dir=str(job_dir), command=[tool, *build_args])

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    record = _FakeRecord(job_id="fake-args", job_dir=str(job_dir), command=[])
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManagerMulti({"fake-args": record}))
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    await generate_capture_pcb_netlist(
        dsn_file=str(tmp_path / "d.dsn"),
        output_dir=str(tmp_path / "out"),
        max_versions=5,
        max_name_length=64,
    )
    assert captured["tool"] == "pstswp"
    args = captured["build_args"]
    assert args[0] == "-pst"
    assert args[args.index("-v") + 1] == "5"
    assert args[args.index("-l") + 1] == "64"
    assert args[args.index("-d") + 1] == str(Path(tmp_path / "d.dsn").resolve())


@pytest.mark.asyncio
async def test_author_schematic_runs_second_annotate_pass_on_success(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    author_job_dir = tmp_path / "author_job"
    author_job_dir.mkdir()
    (author_job_dir / "run.log").write_text(
        "AUTHOR_PACKAGE=POT\nAUTHOR_SUMMARY placed=2 wires=1 output_size=10240\n",
        encoding="utf-8",
    )
    output_dsn = tmp_path / "out.dsn"
    output_dsn.write_bytes(b"fake dsn bytes")
    author_record = _FakeRecord(
        job_id="fake-author", job_dir=str(author_job_dir), command=["tclsh.exe"]
    )

    annotate_job_dir = tmp_path / "annotate_job"
    annotate_job_dir.mkdir()
    (annotate_job_dir / "run.log").write_text(
        "ANNOTATE_SUMMARY annotated=2 requested=2\n", encoding="utf-8"
    )
    annotate_record = _FakeRecord(
        job_id="fake-annotate", job_dir=str(annotate_job_dir), command=["tclsh.exe"]
    )

    calls = {"n": 0}

    async def _fake_submit_job(*args, **kwargs):
        calls["n"] += 1
        return author_record if calls["n"] == 1 else annotate_record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(
        jobs_module,
        "job_manager",
        _FakeJobManagerMulti({"fake-author": author_record, "fake-annotate": annotate_record}),
    )
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    result = await author_capture_schematic_headless(
        output_dsn=str(output_dsn),
        library_file=str(tmp_path / "lib.olb"),
        components=[{"ref": "R1", "x": 100, "y": 100}, {"ref": "R2", "x": 300, "y": 100}],
    )

    assert calls["n"] == 2, "expected both the author pass and the annotate pass to run"
    assert result["placed"] == 2
    assert result["annotate_annotated"] == 2
    assert result["annotate_requested"] == 2
    assert result["annotate_state"] == "succeeded"


@pytest.mark.asyncio
async def test_author_schematic_skips_annotate_pass_when_nothing_placed(tmp_path, monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    author_job_dir = tmp_path / "author_job"
    author_job_dir.mkdir()
    (author_job_dir / "run.log").write_text(
        "AUTHOR_WARN: placement of {R1} failed: boom\nAUTHOR_SUMMARY placed=0 wires=0 output_size=10240\n",
        encoding="utf-8",
    )
    output_dsn = tmp_path / "out.dsn"
    output_dsn.write_bytes(b"fake dsn bytes")
    author_record = _FakeRecord(
        job_id="fake-author-2", job_dir=str(author_job_dir), command=["tclsh.exe"]
    )

    calls = {"n": 0}

    async def _fake_submit_job(*args, **kwargs):
        calls["n"] += 1
        return author_record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(
        jobs_module, "job_manager", _FakeJobManagerMulti({"fake-author-2": author_record})
    )
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    result = await author_capture_schematic_headless(
        output_dsn=str(output_dsn),
        library_file=str(tmp_path / "lib.olb"),
        components=[{"ref": "R1", "x": 100, "y": 100}],
    )

    assert calls["n"] == 1, "annotate pass must NOT run when nothing was placed"
    assert "annotate_job_id" not in result


def test_annotate_script_uses_two_arg_occurrence_setters():
    # Regression guard: DboInstOccurrence_SetReference/SetDesignator take exactly 2 args
    # (self, value) -- the 3-arg form with a status object raises "Wrong # args",
    # confirmed live. Make sure the generated script never regresses to the 3-arg form.
    from sigrity_mcp.domains.cad.capture_headless_tools import _build_annotate_script

    rendered = _build_annotate_script("C:/fake/design.dsn", ["R1", "R2"]).render()
    assert "DboInstOccurrence_SetReference $occ $csRef}" in rendered
    assert "DboInstOccurrence_SetReference $occ $csRef $lStatus" not in rendered
    assert "DboInstOccurrence_SetDesignator $occ $csDesignator $lStatus" not in rendered
    assert "DboDesign_GetRootOccurrence" in rendered
    assert "DboInstOccurrence_GetInstOccurrence" in rendered
    assert "{R1} {R2}" in rendered or "{R1} {R2}".replace(" ", "") in rendered.replace(" ", "")
