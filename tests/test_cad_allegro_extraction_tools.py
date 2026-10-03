from dataclasses import dataclass

import pytest

from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_design_extractor


@pytest.mark.asyncio
async def test_run_allegro_design_extractor_default_pretty(fake_exe):
    result = await run_allegro_design_extractor("proj.cpm")
    assert result["command"][1:] == ["-p", "proj.cpm", "-f"]


@pytest.mark.asyncio
async def test_run_allegro_design_extractor_all_options(fake_exe):
    result = await run_allegro_design_extractor(
        "proj.sdax",
        output_file="out.json",
        pretty_format=False,
        elastic_url="http://localhost:9200",
        connectivity_server_as_source=True,
    )
    assert result["command"][1:] == [
        "-p", "proj.sdax", "-o", "out.json", "-u", "http://localhost:9200", "-c",
    ]


@pytest.mark.asyncio
async def test_run_allegro_extracta_bom(fake_exe, tmp_path):
    from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_extracta

    board = str(tmp_path / "test.brd")
    out = str(tmp_path / "test_bom.txt")
    result = await run_allegro_extracta(board, view_type="bom", output_file=out)
    assert result["output_file"] == out
    assert result["command"][1] == board
    assert result["command"][2] == result["command_file"]
    assert result["command"][3] == out


# Regression test for a real, live-confirmed bug: the built-in EXTRACTION_TEMPLATES
# used to contain invented view-name/field-name keywords ("NETS", "COMPONENTS",
# "PINS", "TESTPOINTS", "DRC", "COMP_LOCATION_X", ...) that real extracta.exe rejects
# with `ERROR(SPMHDX-10): Illegal view name.` for every single view_type -- this
# reproduced 100% of the time. The fix copies the real view/field keywords from
# Cadence's own shipped `share/pcb/text/views/*.txt` command files. Assert each
# generated command file opens with a real, Cadence-documented view keyword, not one of
# the old invented ones, so this can't silently regress.
REAL_VIEW_KEYWORDS = {
    "bom": "COMPONENT",
    "nets": "LOGICAL_PIN",
    "components": "COMPONENT",
    "pins": "COMPONENT_PIN",
    "testpoints": "COMPOSITE_PAD",
    "drc": "DRC_ERROR",
}

INVENTED_VIEW_KEYWORDS = {"NETS", "COMPONENTS", "PINS", "TESTPOINTS", "DRC"}


@pytest.mark.asyncio
@pytest.mark.parametrize("view_type", sorted(REAL_VIEW_KEYWORDS))
async def test_run_allegro_extracta_uses_real_view_keywords(fake_exe, tmp_path, view_type):
    from sigrity_mcp.domains.cad.allegro_extraction_tools import run_allegro_extracta

    board = str(tmp_path / "test.brd")
    result = await run_allegro_extracta(board, view_type=view_type)
    cmd_file_content = open(result["command_file"], encoding="utf-8").read()
    first_line = cmd_file_content.strip().splitlines()[0].strip()

    assert first_line == REAL_VIEW_KEYWORDS[view_type]
    assert first_line not in INVENTED_VIEW_KEYWORDS


# allegro_get_board_extent_points — regression coverage for a real, verified finding:
# the obvious "Drawing Extents" / extracta "A" header bounding box is NOT board-specific
# geometry (two structurally different real boards reported byte-identical extents while
# their real populated areas differed completely) -- it's the inherited drawing sheet
# size. The safe default is the real pin placement bounding box plus a margin, parsed
# from a real pins-view extracta output. These tests fake the extraction job and the
# wait, and feed real pins-view-shaped text, to isolate the parsing/margin math itself.


@dataclass
class _FakeJobRecord:
    state: str


class _FakeJobManager:
    def __init__(self, state: str):
        self._state = state

    async def wait(self, job_id, timeout):
        return _FakeJobRecord(state=self._state)


PINS_VIEW_SAMPLE = (
    "A!RECORD_TAG!GRAPHIC_DATA_NAME!GRAPHIC_DATA_NUMBER!GRAPHIC_DATA_1!GRAPHIC_DATA_2!"
    "GRAPHIC_DATA_3!GRAPHIC_DATA_4!GRAPHIC_DATA_5!GRAPHIC_DATA_6!GRAPHIC_DATA_7!"
    "GRAPHIC_DATA_8!GRAPHIC_DATA_9!GRAPHIC_DATA_10!\n"
    "J!board.brd!Fri Oct  2 21:34:46 2026!0.00!0.00!34000.00!22000.00!0.01!mils!"
    "FAULT-DETECTOR!26.722520 mil!12!UP TO DATE!\n"
    "S!C 00000001! 00000001!C1!1!8600.00!17200.00!PAD60CIR36D!SETV!\n"
    "S!C 00000001! 00000002!C1!2!8900.00!17200.00!PAD60CIR36D!GND!\n"
    "S!C 00000010! 00000001!C10!1!8500.00!16800.00!PAD60CIR36D!N08432!\n"
    "S!C 00000010! 00000002!C10!2!8800.00!14400.00!PAD60CIR36D!N08464!\n"
)


@pytest.mark.asyncio
async def test_allegro_get_board_extent_points_uses_real_pin_bbox_not_drawing_extents(
    tmp_path, monkeypatch
):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.allegro_extraction_tools as extraction_module

    output_file = str(tmp_path / "board_pins.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(PINS_VIEW_SAMPLE)

    async def _fake_run_allegro_extracta(board_file, view_type="bom"):
        assert view_type == "pins"
        return {"job_id": "fake-job-1", "output_file": output_file}

    monkeypatch.setattr(extraction_module, "run_allegro_extracta", _fake_run_allegro_extracta)
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManager(state="succeeded"))

    result = await extraction_module.allegro_get_board_extent_points(
        board_file="board.brd", margin=500.0
    )

    # Real pin extents from the sample: X 8500.00-8900.00, Y 14400.00-17200.00 --
    # NOT the "Drawing Extents" 0,0-34000,22000 that would appear in a real sum/J! row.
    assert result["real_pin_extent"] == {"xl": 8500.00, "yl": 14400.00, "xu": 8900.00, "yu": 17200.00}
    assert result["points"] == [
        [8000.00, 13900.00],
        [9400.00, 13900.00],
        [9400.00, 17700.00],
        [8000.00, 17700.00],
    ]
    assert result["pin_count"] == 4


@pytest.mark.asyncio
async def test_allegro_get_board_extent_points_reports_error_on_failed_extraction(monkeypatch):
    import sigrity_mcp.core.jobs as jobs_module
    import sigrity_mcp.domains.cad.allegro_extraction_tools as extraction_module

    async def _fake_run_allegro_extracta(board_file, view_type="bom"):
        return {"job_id": "fake-job-2", "output_file": "unused.txt"}

    monkeypatch.setattr(extraction_module, "run_allegro_extracta", _fake_run_allegro_extracta)
    monkeypatch.setattr(jobs_module, "job_manager", _FakeJobManager(state="failed"))

    result = await extraction_module.allegro_get_board_extent_points(board_file="board.brd")
    assert "error" in result
    assert "fake-job-2" in result["error"]


