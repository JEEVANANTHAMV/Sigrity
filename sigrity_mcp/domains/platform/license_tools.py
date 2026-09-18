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


@mcp.tool
async def get_license_server_status(license_file: str | None = None) -> dict:
    """Query overall FlexNet license server health and every feature's checkout counts.

    Equivalent to `lmutil lmstat -a -c <license_file>`. If the server is down or
    unreachable you'll get a clear connection-refused message in `output` rather than a
    tool error — that alone is a useful answer ("no Sigrity tool can run right now").
    `license_file` defaults to this machine's configured server (SIGRITY_LICENSE_FILE
    setting, itself defaulted from the CDS_LIC_FILE convention, e.g. '5280@localhost').
    """
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmstat", "-a", "-c", spec], timeout=30.0)
    result["license_file"] = spec
    return result


@mcp.tool
async def get_license_feature_status(feature_name: str, license_file: str | None = None) -> dict:
    """Check checkout status of one specific FlexNet feature (equivalent to `lmutil lmstat -f <feature>`).

    Feature names correspond to licensed Sigrity capabilities (e.g. a PowerSI or
    Clarity3D solver feature) as defined in the license file's INCREMENT lines — use
    get_license_server_status first if you don't already know the exact feature name,
    since this server has no hardcoded license file to read them from statically.
    """
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmstat", "-f", feature_name, "-c", spec], timeout=30.0)
    result["license_file"] = spec
    result["feature_name"] = feature_name
    return result


@mcp.tool
async def diagnose_license_feature(feature_name: str, license_file: str | None = None) -> dict:
    """Diagnose why checking out a specific FlexNet feature would succeed or fail right now.

    Equivalent to `lmutil lmdiag -c <license_file> <feature_name>`. Use this when a
    run_* tool's job fails with `license_issue_suspected=True` to get FlexNet's own
    explanation (feature not found, all seats in use, server unreachable, version
    mismatch, ...).
    """
    spec = license_file or settings.license_file
    result = await run_quick("lmutil", ["lmdiag", "-c", spec, feature_name], timeout=30.0)
    result["license_file"] = spec
    result["feature_name"] = feature_name
    return result


@mcp.tool
async def get_license_host_id() -> dict:
    """Get this machine's FlexNet host ID (`lmutil lmhostid`), needed when requesting or renewing a license file."""
    return await run_quick("lmutil", ["lmhostid"], timeout=15.0)
