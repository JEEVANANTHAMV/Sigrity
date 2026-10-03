import pytest

from sigrity_mcp.domains.platform.license_tools import (
    get_license_feature_status,
    get_license_server_status,
)

# Regression coverage for a real gap: lmstat-based readings are confirmed unreliable
# as a predictor of per-tool usability on this machine (PowerSI etc. fetch real
# licenses and run despite lmstat reporting the server unreachable), but nothing in
# the tool's own return value said so -- a caller gating on "reachable" got exactly
# the false license-block the finding describes, with no self-contained warning.


@pytest.mark.asyncio
async def test_get_license_server_status_always_carries_reliability_note(fake_exe):
    result = await get_license_server_status()
    assert "known-unreliable" in result["reliability_note"]


@pytest.mark.asyncio
async def test_get_license_feature_status_always_carries_reliability_note(fake_exe):
    result = await get_license_feature_status("PowerSI")
    assert "known-unreliable" in result["reliability_note"]
