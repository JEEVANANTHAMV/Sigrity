"""Domain 5 — Unified Framework (Sigrity X Platform).

Scope, deliberately honest about what's confirmed on this machine (see project docs/
research notes): FlexNet license status (via lmutil, the real Cadence license client),
install/environment introspection (cdsinfo, mpsinfo), the cross-tool job-control surface
shared by every other domain, and Analysis Model Manager (AMM) — the actually-confirmed
cross-tool technology/model-library layer. We deliberately do NOT wrap SigritySuite.exe /
SigritySuiteManager.exe / SigSuiteReg.exe: their command-line contracts are undocumented
and untested (SigritySuiteCon.exe turned out to be a Chromium-embedded GUI shell, not a
scripting console), so building tools around them would be fabricating capability.
"""

from sigrity_mcp.domains.platform import job_tools, license_tools, install_tools  # noqa: F401
