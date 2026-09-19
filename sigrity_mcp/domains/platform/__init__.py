"""Domain 5 — Unified Framework (Sigrity X Platform).

Scope, deliberately honest about what's confirmed on this machine (see project docs/
research notes): FlexNet license status (via lmutil, the real Cadence license client),
install/environment introspection (cdsinfo, mpsinfo), the cross-tool job-control surface
shared by every other domain, and Analysis Model Manager (AMM) — the actually-confirmed
cross-tool technology/model-library layer. We deliberately do NOT wrap SigritySuite.exe /
SigritySuiteManager.exe / SigSuiteReg.exe: their command-line contracts are undocumented
and untested. CORRECTED FINDING: `SigritySuiteCon.exe -h` was re-probed live and is
confirmed to be an internal Google Test (gtest) binary — its "-h" output is literally
gtest's own flag reference (`--gtest_list_tests`, `--gtest_filter`, ...), not a
Chromium-embedded GUI shell as an earlier pass of this research guessed, and not a
scripting console either way — so it remains correctly unwrapped, just for a different,
now-confirmed reason.
"""

from sigrity_mcp.domains.platform import (  # noqa: F401
    amm_tools,
    file_tools,
    install_tools,
    job_tools,
    license_tools,
    pipeline_tools,
    session_tools,
)
