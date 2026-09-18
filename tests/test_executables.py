import pytest

from sigrity_mcp.core import executables
from sigrity_mcp.core.errors import ExecutableNotFoundError


def test_unknown_tool_raises():
    executables.resolve.cache_clear()
    with pytest.raises(ExecutableNotFoundError):
        executables.resolve("not_a_real_tool")


def test_all_registered_names_have_exe_suffix():
    for name, exe in executables.EXECUTABLES.items():
        assert exe.lower().endswith(".exe"), f"{name} -> {exe} missing .exe"


def test_available_tools_matches_registry_keys():
    report = executables.available_tools()
    expected = set(executables.EXECUTABLES) | set(executables.LICENSE_EXECUTABLES)
    assert set(report.keys()) == expected
