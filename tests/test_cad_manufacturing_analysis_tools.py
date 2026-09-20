import pytest

from sigrity_mcp.domains.cad.manufacturing_analysis_tools import analyze_manufacturing_package

REAL_GERBER_HEADER = """G04 ================== begin FILE IDENTIFICATION RECORD ==================*
G04 Layout Name:  C:/board.brd*
G04 Film Name:    TOP*
G04 File Format:  Gerber RS274X*
G04 File Origin:  Cadence Allegro 22.1-P001*
G04 Origin Date:  Fri Sep 18 22:37:52 2026*
G04 *
G04 Layer:  ETCH/TOP*
G04 *
G04 ================== end FILE IDENTIFICATION RECORD ====================*
%FSLAX25Y25*MOIN*%
G54D10*
G01X800000Y1460000D02*
"""

REAL_IPC2581 = """<?xml version = "1.0" encoding = "UTF-8"?>
<IPC-2581 revision="B" xmlns="http://webstds.ipc.org/2581">
  <Ecad name="Design">
    <CadData>
      <Step name="board">
        <Profile/>
      </Step>
    </CadData>
  </Ecad>
</IPC-2581>
"""

REAL_IPC356 = """P  JOB   C:/board.brd
P  FORM  F
P  CODE  00
C
C  IPC-D-356 Output File from Allegro
C  IPC File Date: Fri Sep 18 22:59:22 2026
C
"""

BOM_REPORT = """Bill of Material Report
C:/board.brd
Fri Sep 18 23:37:17 2026

SYM_NAME,COMP_DEVICE_TYPE,COMP_VALUE,COMP_TOL,COMP_CLASS,REFDES
CAP300,C_CAP300_C,C,,IC,C1
RES400,R_RES400_R,R,,IC,R1
"""


@pytest.mark.asyncio
async def test_well_formed_package_reports_no_issues(tmp_path):
    gerber = tmp_path / "TOP.art"
    gerber.write_text(REAL_GERBER_HEADER, encoding="utf-8")
    ipc2581 = tmp_path / "board_ipc2581.xml"
    ipc2581.write_text(REAL_IPC2581, encoding="utf-8")
    ipc356 = tmp_path / "out.ipc356"
    ipc356.write_text(REAL_IPC356, encoding="utf-8")
    bom = tmp_path / "bom.rpt"
    bom.write_text(BOM_REPORT, encoding="utf-8")

    result = await analyze_manufacturing_package(
        gerber_files=[str(gerber)],
        ipc2581_file=str(ipc2581),
        ipc356_file=str(ipc356),
        bom_report_file=str(bom),
    )

    assert result["overall"]["all_well_formed"] is True
    assert result["overall"]["issues"] == []
    assert result["gerber"][0]["layer"] == "ETCH/TOP"
    assert result["ipc2581"]["well_formed"] is True
    assert result["ipc356"]["well_formed"] is True
    assert result["bom_refdes_count"] == 2


@pytest.mark.asyncio
async def test_missing_and_malformed_files_are_flagged(tmp_path):
    fake_gerber = tmp_path / "not_gerber.art"
    fake_gerber.write_text("this is not a real gerber file\n", encoding="utf-8")
    malformed_xml = tmp_path / "bad.xml"
    malformed_xml.write_text("<not><closed", encoding="utf-8")

    result = await analyze_manufacturing_package(
        gerber_files=[str(fake_gerber), str(tmp_path / "missing.art")],
        ipc2581_file=str(malformed_xml),
    )

    assert result["overall"]["all_well_formed"] is False
    assert result["gerber"][0]["well_formed"] is False
    assert result["gerber"][1]["exists"] is False
    assert result["ipc2581"]["well_formed"] is False
    assert len(result["overall"]["issues"]) == 3


@pytest.mark.asyncio
async def test_empty_call_returns_no_issues_but_nothing_checked():
    result = await analyze_manufacturing_package()
    assert result["gerber"] == []
    assert result["ipc2581"] is None
    assert result["ipc356"] is None
    assert result["overall"]["all_well_formed"] is True
