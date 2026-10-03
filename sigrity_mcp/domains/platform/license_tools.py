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
    "lmstat-based server-health readings are known-unreliable on this machine as a "
    "predictor of per-tool usability (see core.tool_status's module docstring): "
    "PowerSI/PowerDC/Celsius/Allegro etc. fetch real licenses and run successfully "
    "despite this reading the server as unreachable. Do NOT use this as a global "
    "pre-flight gate -- for 'will tool X run', consult the per-tool TOOL_STATUS "
    "registry instead."
)


@mcp.tool
async def get_license_server_status(license_file: str | None = None) -> dict:
    """Query overall FlexNet license server health and every feature's checkout counts.
CAVEAT: on this machine this reading has been proven UNRELIABLE as a predictor of whether
a specific tool can actually run -- see the returned reliability_note.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmstat", "-a", "-c", spec], timeout=30.0)
    result["license_file"] = spec
    result["reliability_note"] = _RELIABILITY_NOTE
    return result


@mcp.tool
async def get_license_feature_status(feature_name: str, license_file: str | None = None) -> dict:
    """Check checkout status of one specific FlexNet feature (equivalent to `lmutil lmstat -f <feature>`).
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmstat", "-f", feature_name, "-c", spec], timeout=30.0)
    result["license_file"] = spec
    result["feature_name"] = feature_name
    result["reliability_note"] = _RELIABILITY_NOTE
    return result


@mcp.tool
async def diagnose_license_feature(feature_name: str, license_file: str | None = None) -> dict:
    """Diagnose why checking out a specific FlexNet feature would succeed or fail right now.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmdiag", "-c", spec, feature_name], timeout=30.0)
    result["license_file"] = spec
    result["feature_name"] = feature_name
    return result


@mcp.tool
async def get_license_host_id() -> dict:
    """Get this machine's FlexNet host ID (`lmutil lmhostid`), needed when requesting or renewing a license file.
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    return await run_quick("lmutil", ["lmhostid"], timeout=15.0)
