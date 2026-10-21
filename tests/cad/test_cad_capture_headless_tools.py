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


def test_group_components_by_pkg_groups_and_preserves_order():
    from sigrity_mcp.domains.cad.capture_headless_tools import _group_components_by_pkg

    lib_a = "A.olb"
    lib_b = "B.olb"
    comps = [
        {"ref": "R1", "x": 1, "y": 1, "package": "POT", "library": lib_a},
        {"ref": "R2", "x": 2, "y": 1, "package": "RES"},            # default lib -> tool-level
        {"ref": "C1", "x": 3, "y": 1, "package": "POT", "library": lib_b},
        {"ref": "C2", "x": 4, "y": 1, "package": "POT", "library": lib_a},  # dup of R1 key
        {"ref": "U1", "x": 5, "y": 1, "package": "RES", "library": lib_b},
    ]
    groups = _group_components_by_pkg(comps)
    keys = [c.get("package") + "@" + c.get("library", "") for c in (g[0] for g in groups)]
    # Stable first-encountered order of distinct (library,package) keys.
    assert keys == ["POT@" + lib_a, "RES@", "POT@" + lib_b, "RES@" + lib_b]
    # The R1/C2 dup collapses into one group (2 members); the rest have 1 each.
    assert [len(g) for g in groups] == [2, 1, 1, 1]


@pytest.mark.asyncio
async def test_author_generated_script_emits_one_group_per_distinct_package(tmp_path, monkeypatch):
    """End-to-end guard: a 2-package BOM generates per-group handles (G0/G1) and each
    component instantiates from its OWN group's package/part/device -- the core fix."""
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    author_job_dir = tmp_path / "author_job"
    author_job_dir.mkdir()
    (author_job_dir / "run.log").write_text(
        "AUTHOR_SUMMARY placed=2 wires=0 output_size=10240\n", encoding="utf-8"
    )
    output_dsn = tmp_path / "out.dsn"
    output_dsn.write_bytes(b"fake dsn bytes")
    author_record = _FakeRecord(job_id="fake-author-g", job_dir=str(author_job_dir), command=["tclsh.exe"])

    annotate_job_dir = tmp_path / "annotate_job"
    annotate_job_dir.mkdir()
    (annotate_job_dir / "run.log").write_text(
        "ANNOTATE_SUMMARY annotated=2 requested=2\n", encoding="utf-8"
    )
    annotate_record = _FakeRecord(job_id="fake-annotate-g", job_dir=str(annotate_job_dir), command=["tclsh.exe"])

    seen_scripts = []
    calls = {"n": 0}

    async def _fake_submit_job(*, tool, tcl_script, tcl_arg_flag, script_filename, extra_env, **kwargs):
        calls["n"] += 1
        seen_scripts.append(tcl_script.render())
        return author_record if calls["n"] == 1 else annotate_record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(
        jobs_module, "job_manager",
        _FakeJobManagerMulti({"fake-author-g": author_record, "fake-annotate-g": annotate_record}),
    )
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    # Two distinct packages -> two distinct (library,package) groups.
    await author_capture_schematic_headless(
        output_dsn=str(output_dsn),
        library_file=str(tmp_path / "lib.olb"),
        components=[
            {"ref": "R1", "x": 1, "y": 1, "package": "POT"},
            {"ref": "C1", "x": 2, "y": 1, "package": "CAP", "library": str(tmp_path / "other.olb")},
        ],
    )

    author_script = seen_scripts[0]
    # Both distinct packages were resolved (one group each).
    assert "AUTHOR_PG0" in author_script
    assert "AUTHOR_PG1" in author_script
    # Group 0 -> POT, Group 1 -> CAP (by-name resolution requested).
    assert "$csPkgNM" in author_script
    # R1 (group 0) and C1 (group 1) instantiate from DIFFERENT group handles.
    assert "NewPlacedInst $lStatus $csRef $csPkgNM0 $lPart0 $lDevice0" in author_script
    assert "NewPlacedInst $lStatus $csRef $csPkgNM1 $lPart1 $lDevice1" in author_script
    # sanity: both per-group packages and the per-component placement are present
    assert "G0" in author_script and "G1" in author_script


def test_author_generated_script_interleaves_getlib_remove_lib_per_group():
    """Regression guard for the ORDBDLL-1021 "one open lib at a time" constraint
    (this installed DLL build returns 1021 for a 2nd GetLib of a different path
    while the first lib's handle is still open -- see
    sigrity_mcp/domains/cad/capture_headless_tools.py's module +
    _build_author_script docstrings, and runs/olb_union_fix_report.md). Two
    distinct vendor .olbs, one part each (the typical SamacSys/UltraLibrarian
    one-.olb-per-part shape): every group's $lSession RemoveLib MUST appear
    BEFORE the next group's $lSession GetLib, and the FIRST group's GetLib MUST
    precede NewSchematic/NewPage (a design page created before any GetLib has
    ever run in the session poisons the lib-directory cache independently).
    """
    from sigrity_mcp.domains.cad.capture_headless_tools import _build_author_script

    rendered = (
        _build_author_script(
            design_name="T",
            library_file="C:/fake/a.olb",
            components=[
                {"ref": "U0", "x": 1, "y": 1, "library": "C:/fake/a.olb"},
                {"ref": "U1", "x": 4, "y": 1, "library": "C:/fake/b.olb"},
                {"ref": "U2", "x": 7, "y": 1, "library": "C:/fake/c.olb"},
            ],
            wires=[],
            output_dsn="C:/fake/out.dsn",
            package_name=None,
        )
        .render()
    )
    i_get0 = rendered.index("$lSession GetLib $csLib0")
    i_get1 = rendered.index("$lSession GetLib $csLib1")
    i_get2 = rendered.index("$lSession GetLib $csLib2")
    i_rmv0 = rendered.index("RemoveLib $lLib0")
    i_rmv1 = rendered.index("RemoveLib $lLib1")
    i_rmv2 = rendered.index("RemoveLib $lLib2")
    i_newpage = rendered.index("NewPage $lStatus $csPage")
    # No two distinct libraries ever open simultaneously.
    assert i_rmv0 < i_get1
    assert i_rmv1 < i_get2
    # The first GetLib happens before the page exists (not after it, not with the
    # page's own DboSchematic/DboPage handle already created first).
    assert i_get0 < i_newpage
    # A dangling MarkAllLibForSave against an already-closed $lLib (the old,
    # silently-broken line) must not reappear.
    assert "MarkAllLibForSave" not in rendered



def test_author_generated_script_emits_get_pin_xy_for_pin_resolved_wires():
    """Regression guard for the pin-resolved wire shape + coordinate-lookup helper.

    A wire entry of the form {"pin1":{"part_index","pin"},"pin2":{"part_index","pin"}}
    must generate a `get_pin_xy <page> <index> <pin>` call for EACH endpoint (resolving
    a placed part's named pin to its page-space hot-spot via DboPortInst_sGetHotSpotX/Y),
    NOT a docxy/granularity-scaled raw coordinate — the whole point of the shape is to
    aim the wire at real pin locations instead of hand-supplied numbers. Confirmed live:
    a wire drawn between two parts' resolved pin hot-spots was saved, reopened, and both
    pins independently reported the same net name (N00041) — see capture_headless_
    tools.py's `_get_pin_xy_proc_tcl` docstring for the full coordinate-space evidence.
    """
    from sigrity_mcp.domains.cad.capture_headless_tools import _build_author_script

    rendered = (
        _build_author_script(
            design_name="T",
            library_file="C:/fake/a.olb",
            components=[{"ref": "U0", "x": 1, "y": 1}, {"ref": "U1", "x": 4, "y": 1}],
            wires=[
                {"pin1": {"part_index": 0, "pin": "F22"}, "pin2": {"part_index": 1, "pin": "39"}},
            ],
            output_dsn="C:/fake/out.dsn",
            package_name=None,
        )
        .render()
    )
    # The coordinate-lookup helper proc is emitted (shared helper).
    assert "proc get_pin_xy {page partIndex pinname}" in rendered
    assert "global lStatus" in rendered  # globals must be declared inside the proc
    # Each endpoint resolves via get_pin_xy with its 0-based placement index + pin name.
    assert "get_pin_xy $lPage 0 {F22}" in rendered
    assert "get_pin_xy $lPage 1 {39}" in rendered
    # The Hot Spot (not Start Point) is the getter used for the wire attachment point.
    assert "DboPortInst_sGetHotSpotX" in rendered
    assert "DboPortInst_sGetHotSpotY" in rendered
    # A pin-resolved endpoint must NOT be docxy/granularity-scaled (it is already in
    # page-space) -- there is no `docxy` call anywhere in this script's wire block.
    assert "docxy" not in rendered.split("set wire_count 0", 1)[1]
    # The raw x1/y1/x2/y2 form still works alongside (back-compat). The get_pin_xy
    # proc is a shared helper always emitted (so it appears in raw-wire scripts too),
    # but a RAW wire must use docxy, NOT a get_pin_xy CALL -- check the call count.
    rendered_raw = (
        _build_author_script(
            design_name="T",
            library_file="C:/fake/a.olb",
            components=[{"ref": "U0", "x": 1, "y": 1}],
            wires=[{"x1": 10, "y1": 10, "x2": 30, "y2": 10}],
            output_dsn="C:/fake/out2.dsn",
            package_name=None,
        )
        .render()
    )
    assert "set wp1 [docxy $gran 10 10]" in rendered_raw
    # No get_pin_xy CALL in the raw-wire script (the proc is present, but never invoked:
    # a call looks like "[get_pin_xy $lPage ...", the proc def looks like "proc get_pin_xy").
    raw_wire_section = rendered_raw.split("set wire_count 0", 1)[1]
    assert "[get_pin_xy" not in raw_wire_section
    # And the pin-resolved script DOES have the call (one per endpoint).
    pin_wire_section = rendered.split("set wire_count 0", 1)[1]
    assert rendered.count("get_pin_xy $lPage") == 2
    assert "[get_pin_xy" in pin_wire_section


@pytest.mark.asyncio
async def test_author_pin_resolved_wire_validation_both_shapes_rejected(tmp_path, monkeypatch):
    """A wire carrying BOTH the raw (x1..y2) and the pin-resolved (pin1/pin2) keys must
    be rejected up-front (ValueError), BEFORE any job is submitted."""
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    reached = {"n": 0}
    job_dir = tmp_path / "vjob"
    job_dir.mkdir()
    (job_dir / "run.log").write_text(
        "AUTHOR_SUMMARY placed=2 wires=1 output_size=1\n"
        "ANNOTATE_SUMMARY annotated=2 requested=2\n", encoding="utf-8"
    )
    output_dsn = tmp_path / "vout.dsn"
    output_dsn.write_bytes(b"fake")
    record = _FakeRecord(job_id="v", job_dir=str(job_dir), command=["tclsh.exe"])

    async def _fake_submit_job(*args, **kwargs):
        reached["n"] += 1
        return record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(
        jobs_module, "job_manager", _FakeJobManagerMulti({"v": record})
    )
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    with pytest.raises(ValueError, match="EITHER"):
        await author_capture_schematic_headless(
            output_dsn=str(output_dsn),
            library_file="C:/fake/a.olb",
            components=[{"ref": "U0", "x": 1, "y": 1}, {"ref": "U1", "x": 4, "y": 1}],
            wires=[
                {"x1": 1, "y1": 1, "x2": 2, "y2": 2,
                 "pin1": {"part_index": 0, "pin": "1"},
                 "pin2": {"part_index": 1, "pin": "1"}},
            ],
        )
    assert reached["n"] == 0, "rejected wire must not reach submit_job"


@pytest.mark.asyncio
async def test_author_pin_resolved_wire_validation_valid_reaches_submit(tmp_path, monkeypatch):
    """A well-formed pin-resolved wire (part_index+pin on both endpoints) passes
    validation and reaches the submit path."""
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.capture_headless_tools as mod

    reached = {"n": 0}
    job_dir = tmp_path / "vjob2"
    job_dir.mkdir()
    (job_dir / "run.log").write_text(
        "AUTHOR_SUMMARY placed=2 wires=1 output_size=1\n"
        "ANNOTATE_SUMMARY annotated=2 requested=2\n", encoding="utf-8"
    )
    output_dsn = tmp_path / "vout2.dsn"
    output_dsn.write_bytes(b"fake")
    record = _FakeRecord(job_id="v2", job_dir=str(job_dir), command=["tclsh.exe"])

    async def _fake_submit_job(*args, **kwargs):
        reached["n"] += 1
        return record

    monkeypatch.setattr(mod, "submit_job", _fake_submit_job)
    monkeypatch.setattr(
        jobs_module, "job_manager", _FakeJobManagerMulti({"v2": record})
    )
    monkeypatch.setattr(mod, "job_manager", jobs_module.job_manager)

    await author_capture_schematic_headless(
        output_dsn=str(output_dsn),
        library_file="C:/fake/a.olb",
        components=[{"ref": "U0", "x": 1, "y": 1}, {"ref": "U1", "x": 4, "y": 1}],
        wires=[{"pin1": {"part_index": 0, "pin": "1"},
                "pin2": {"part_index": 1, "pin": "1"}}],
    )
    assert reached["n"] >= 1, "valid pin-resolved wire must reach submit_job"


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
