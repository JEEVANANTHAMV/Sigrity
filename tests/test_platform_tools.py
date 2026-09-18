"""Exercises the platform-domain tools against the real local Sigrity/FlexNet install.

These skip cleanly (rather than fail) if run on a machine without that install, but on
this project's target machine they are genuine end-to-end checks, not mocks.
"""

import pytest

from sigrity_mcp.core import executables
from sigrity_mcp.domains.platform.install_tools import (
    check_name_server,
    get_cds_environment_info,
    get_install_info,
    list_sigrity_tools,
)
from sigrity_mcp.domains.platform.license_tools import get_license_host_id, get_license_server_status

requires_sigrity = pytest.mark.skipif(
    not executables.available_tools().get("cdsinfo", False),
    reason="Sigrity Suite not installed on this machine",
)
requires_flexnet = pytest.mark.skipif(
    not executables.available_tools().get("lmutil", False),
    reason="FlexNet lmutil.exe not installed on this machine",
)


@requires_sigrity
async def test_get_install_info_reads_real_manifest():
    info = await get_install_info()
    assert "error" not in info
    assert info["release_version"]
    assert info["product_path"]
    assert isinstance(info["licensed_product_bundles"], list)
    assert len(info["licensed_product_bundles"]) > 0


@requires_sigrity
async def test_list_sigrity_tools_reports_every_registered_name():
    report = await list_sigrity_tools()
    expected = set(executables.EXECUTABLES) | set(executables.LICENSE_EXECUTABLES)
    assert set(report["tools"].keys()) == expected
    assert report["total_count"] == len(expected)


@requires_sigrity
async def test_check_name_server_returns_bool_flag():
    result = await check_name_server()
    assert isinstance(result["name_server_running"], bool)
    assert result["returncode"] in (0, 1)


@requires_sigrity
async def test_get_cds_environment_info_show_runs():
    result = await get_cds_environment_info()
    assert result["tool"] == "cdsinfo"
    assert "-show" in result["command"]


@requires_flexnet
async def test_get_license_host_id_matches_flexnet_format():
    result = await get_license_host_id()
    assert result["returncode"] == 0
    assert "FlexNet host ID" in result["output"]


@requires_flexnet
async def test_get_license_server_status_never_raises_even_when_down():
    # Whether or not a license server happens to be up right now, the tool must return a
    # structured result rather than throwing — an unreachable server is a normal, expected
    # answer for callers to act on (e.g. "no Sigrity tool can run right now").
    result = await get_license_server_status()
    assert "output" in result
    assert result["license_file"]
