import pytest

from sigrity_mcp.domains.cad.allegro_library_tools import (
    run_die_abstract_check,
    run_die_abstract_compare,
    run_ibis_check,
)


@pytest.mark.asyncio
async def test_run_ibis_check_default_version(fake_exe):
    result = await run_ibis_check("model.ibs")
    assert result["command"][1:] == ["model.ibs"]


@pytest.mark.asyncio
async def test_run_ibis_check_explicit_version(fake_exe):
    result = await run_ibis_check("model.ibs", ibis_version="4")
    # fake_exe resolves every logical tool name to the same fake exe, so we can only
    # assert the argv shape here, not which ibischkN binary was actually picked.
    assert result["command"][1:] == ["model.ibs"]


@pytest.mark.asyncio
async def test_run_die_abstract_check_minimal(fake_exe):
    result = await run_die_abstract_check("die.dia")
    assert result["command"][1:] == ["die.dia"]


@pytest.mark.asyncio
async def test_run_die_abstract_check_with_flags(fake_exe):
    result = await run_die_abstract_check(
        "die.dia", output_file="out.txt", skip_net_names=True, skip_connectivity=True, skip_layer_info=True
    )
    assert result["command"][1:] == ["die.dia", "out.txt", "-nn", "-nc", "-nl"]


@pytest.mark.asyncio
async def test_run_die_abstract_compare(fake_exe):
    result = await run_die_abstract_compare("golden.dia", "eco.dia", output_file="diff.txt")
    assert result["command"][1:] == ["golden.dia", "eco.dia", "diff.txt"]
