import pytest

from sigrity_mcp.domains.cad.interchange_tools import (
    explain_translator_gate,
    run_apd2con,
    run_cap2xml,
    run_con2xml,
    run_dml2con,
)


@pytest.mark.asyncio
async def test_run_con2xml_switch_form(fake_exe):
    # con2xml is switch-based per the pdv manual: -cdslib -lib -cell -package -xmldir
    result = await run_con2xml(
        cds_lib="C:/proj/cds.lib", lib="top", cell="top", package="sch_1", xmldir="C:/out"
    )
    assert result["command"][1:] == [
        "-cdslib", "C:/proj/cds.lib", "-lib", "top", "-cell", "top",
        "-package", "sch_1", "-xmldir", "C:/out",
    ]
    assert result["tool"] == "con2xml"
    assert "gate" in result


@pytest.mark.asyncio
async def test_run_con2xml_overwrite_and_product(fake_exe):
    result = await run_con2xml(
        cds_lib="C:/proj/cds.lib", lib="top", cell="top", package="sch_1",
        xmldir="C:/out", overwrite=True, product="pcb_librarian_expert",
    )
    assert "-overwrite" in result["command"]
    assert "-product" in result["command"]
    assert "pcb_librarian_expert" in result["command"]


@pytest.mark.asyncio
async def test_run_cap2xml_switch_form(fake_exe):
    # cap2xml per the pdv manual: -olbpath [-part] -xmldir [-overwrite]
    result = await run_cap2xml(olbpath="C:/proj/PROJ.OLB", xmldir="C:/out")
    assert result["command"][1:] == ["-olbpath", "C:/proj/PROJ.OLB", "-xmldir", "C:/out"]
    # with an explicit part
    result2 = await run_cap2xml(
        olbpath="C:/proj/PROJ.OLB", xmldir="C:/out", part="U1", product="pcb_librarian_expert"
    )
    assert "-part" in result2["command"]
    assert "U1" in result2["command"]


@pytest.mark.asyncio
async def test_run_dml2con_switch_form(fake_exe):
    # dml2con non-ECO per the pdv manual: -proj -cdslib -lib [-cell] -dmlfile -device
    result = await run_dml2con(
        proj="C:/p/proj.cpm", cds_lib="C:/p/cds.lib", lib="dest_lib",
        dmlfile="C:/m/model.dml", device="DEV1",
    )
    assert "-proj" in result["command"]
    assert "-cdslib" in result["command"]
    assert "-lib" in result["command"]
    assert "-dmlfile" in result["command"]
    assert "-device" in result["command"]
    assert result["command"].index("-device") + 1 < len(result["command"])
    assert result["command"][result["command"].index("-device") + 1] == "DEV1"


@pytest.mark.asyncio
async def test_run_apd2con_switch_form(fake_exe):
    # apd2con non-ECO per the pdv manual: -proj -cdslib -apddir -lib [-cell]
    result = await run_apd2con(
        proj="C:/p/proj.cpm", cds_lib="C:/p/cds.lib", apddir="C:/apd", lib="dest_lib",
    )
    assert "-proj" in result["command"]
    assert "-apddir" in result["command"]
    assert "-lib" in result["command"]
    assert result["command"].index("-apddir") + 1 < len(result["command"])
    assert result["command"][result["command"].index("-apddir") + 1] == "C:/apd"


@pytest.mark.asyncio
async def test_explain_translator_gate_no_tool(fake_exe):
    # No tool name -> returns the documented contracts, no process launch.
    result = await explain_translator_gate()
    assert "contracts" in result
    for name in ("con2xml", "cap2xml", "dml2con", "apd2con"):
        assert name in result["contracts"]
    # All four are documented switch-based translators (not bare positional in/out).
    for name in ("con2xml", "cap2xml", "dml2con", "apd2con"):
        assert result["contracts"][name]["positional"] is False
        assert any(s["flag"] == "-product" or s["flag"].startswith("-") for s in result["contracts"][name]["switches"])


@pytest.mark.asyncio
async def test_explain_translator_gate_unknown_tool(fake_exe):
    result = await explain_translator_gate("nope")
    assert result["gate"]["stage"] == "unknown_tool"
