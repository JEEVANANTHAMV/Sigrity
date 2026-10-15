"""FlexNet license status tools, wrapping the real Cadence license client (lmutil.exe).

Confirmed by running `lmutil.exe -h` / `lmstat -h` directly on this machine (Copyright
Flexera, standard FlexLM/FlexNet client) — these are the actual documented flags, not
guessed. Every Sigrity tool (PowerSI, PowerDC, Clarity3D, ...) checks out a FlexNet
feature on launch, so these tools are the honest way to answer "can I actually run a
simulation right now" before kicking off a long job.
"""

from __future__ import annotations

from sigrity_mcp.core.config import settings
from sigrity_mcp.core.process import run_quick
from sigrity_mcp.mcp_app import mcp


_RELIABILITY_NOTE = (
    "This is a PREMIUM, no-license-required install: lmstat/server readings are "
    "known-unreliable as a predictor of per-tool usability here (see core.tool_status's "
    "module docstring) -- PowerSI/PowerDC/Celsius/Allegro etc. run successfully "
    "despite lmstat reading the configured server as unreachable. No tool in this suite "
    "is license-gated, so do NOT use this as a gate or 'will tool X run' pre-flight "
    "check at all; consult the per-tool TOOL_STATUS registry instead."
)


@mcp.tool
async def get_license_server_status(license_file: str | None = None) -> dict:
    """Query overall FlexNet license server health and every feature's checkout counts.
CAVEAT: on this PREMIUM no-license-required machine this reading has been proven
UNRELIABLE and is NOT a predictor of whether a specific tool can run (no tool is
license-gated here) -- see the returned reliability_note.
Call load_skill('sigrity') for the full verified playbook, pitfalls, and a live example."""
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmstat", "-a", "-c", spec], timeout=30.0)
    result["license_file"] = spec
    result["reliability_note"] = _RELIABILITY_NOTE
    return result


@mcp.tool
async def get_license_feature_status(feature_name: str, license_file: str | None = None) -> dict:
    """Check checkout status of one specific FlexNet feature (equivalent to `lmutil lmstat -f <feature>`).
Call load_skill('sigrity') for the full verified playbook, pitfalls, and a live example."""
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmstat", "-f", feature_name, "-c", spec], timeout=30.0)
    result["license_file"] = spec
    result["feature_name"] = feature_name
    result["reliability_note"] = _RELIABILITY_NOTE
    return result


@mcp.tool
async def diagnose_license_feature(feature_name: str, license_file: str | None = None) -> dict:
    """Diagnose why checking out a specific FlexNet feature would succeed or fail right now.
Call load_skill('sigrity') for the full verified playbook, pitfalls, and a live example."""
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmdiag", "-c", spec, feature_name], timeout=30.0)
    result["license_file"] = spec
    result["feature_name"] = feature_name
    return result


@mcp.tool
async def get_license_host_id() -> dict:
    """Get this machine's FlexNet host ID (`lmutil lmhostid`), needed when requesting or renewing a license file.
Call load_skill('sigrity') for the full verified playbook, pitfalls, and a live example."""
    return await run_quick("lmutil", ["lmhostid"], timeout=15.0)
