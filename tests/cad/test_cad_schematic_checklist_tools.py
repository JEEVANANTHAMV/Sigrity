import pytest

from sigrity_mcp.domains.cad.schematic_checklist_tools import (
    parse_bom_report,
    parse_net_report,
    run_schematic_checklist,
)

NET_REPORT = """Allegro Report
C:/board.brd
Fri Sep 18 22:59:22 2026

Net Name,Net Pins
+5V,U1.1 R1.2 C1.1
GND,C1.2 R1.1 U1.2 SW1.2
RESET,C2.1 R2.2 SW1.1 U1.3
CLK,U1.4
"""

BOM_REPORT = """Bill of Material Report
C:/board.brd
Fri Sep 18 23:37:17 2026

SYM_NAME,COMP_DEVICE_TYPE,COMP_VALUE,COMP_TOL,COMP_CLASS,REFDES
CAP300,C_CAP300_C,C,,IC,C1
CAP300,C_CAP300_C,C,,IC,C2
RES400,R_RES400_R,R,,IC,R1
RES400,R_RES400_R,R,,IC,R2
UNIT_BODY,SW_SW,SW,,IC,SW1
DIP,U_IC,U,,IC,U1
"""


def test_parse_net_report():
    nets = parse_net_report(NET_REPORT)
    assert nets["GND"] == ["C1.2", "R1.1", "U1.2", "SW1.2"]
    assert nets["RESET"] == ["C2.1", "R2.2", "SW1.1", "U1.3"]
    assert nets["+5V"] == ["U1.1", "R1.2", "C1.1"]


def test_parse_bom_report():
    rows = parse_bom_report(BOM_REPORT)
    refdes = [r["REFDES"] for r in rows]
    assert refdes == ["C1", "C2", "R1", "R2", "SW1", "U1"]


@pytest.mark.asyncio
async def test_checklist_flags_power_net_without_decoupling_cap(tmp_path):
    net_file = tmp_path / "net.rpt"
    net_file.write_text(NET_REPORT.replace("CLK,U1.4", "CLK,U1.4\n+3V3,U1.5"), encoding="utf-8")
    result = await run_schematic_checklist(str(net_file), rules=["decoupling"])
    flagged_nets = {f["net"] for f in result["findings"]}
    assert "+3V3" in flagged_nets  # no cap anywhere touches it
    assert "+5V" not in flagged_nets  # C1.1 is on +5V, so it has a decoupling cap


@pytest.mark.asyncio
async def test_checklist_reset_net_with_rc_present_is_clean(tmp_path):
    net_file = tmp_path / "net.rpt"
    net_file.write_text(NET_REPORT, encoding="utf-8")
    result = await run_schematic_checklist(str(net_file), rules=["resets"])
    assert result["findings"] == []  # RESET touches C2 and R2


@pytest.mark.asyncio
async def test_checklist_reset_net_without_rc_is_flagged(tmp_path):
    bad_net_report = NET_REPORT.replace("RESET,C2.1 R2.2 SW1.1 U1.3", "RESET,SW1.1 U1.3")
    net_file = tmp_path / "net.rpt"
    net_file.write_text(bad_net_report, encoding="utf-8")
    result = await run_schematic_checklist(str(net_file), rules=["resets"])
    assert len(result["findings"]) == 1
    assert result["findings"][0]["net"] == "RESET"


@pytest.mark.asyncio
async def test_checklist_flags_floating_clock_net(tmp_path):
    net_file = tmp_path / "net.rpt"
    net_file.write_text(NET_REPORT, encoding="utf-8")
    result = await run_schematic_checklist(str(net_file), rules=["clocks"])
    assert len(result["findings"]) == 1
    assert result["findings"][0]["net"] == "CLK"


@pytest.mark.asyncio
async def test_checklist_test_points_requires_bom_and_flags_when_none_found(tmp_path):
    net_file = tmp_path / "net.rpt"
    net_file.write_text(NET_REPORT, encoding="utf-8")
    bom_file = tmp_path / "bom.rpt"
    bom_file.write_text(BOM_REPORT, encoding="utf-8")

    result = await run_schematic_checklist(str(net_file), bom_report_file=str(bom_file), rules=["test_points"])
    assert len(result["findings"]) == 1
    assert result["findings"][0]["rule"] == "test_points"

    skipped = await run_schematic_checklist(str(net_file), rules=["test_points"])
    assert skipped["findings"][0]["severity"] == "skipped"


@pytest.mark.asyncio
async def test_unknown_rule_returns_error(tmp_path):
    net_file = tmp_path / "net.rpt"
    net_file.write_text(NET_REPORT, encoding="utf-8")
    result = await run_schematic_checklist(str(net_file), rules=["not_a_real_rule"])
    assert "error" in result
