"""Domain 2 — Signal Integrity (SI) & Power-Aware Analysis.

PowerSI is automated through a Tcl session (see core.tclsession) — the same
compose-then-run pattern used by every `sigrity::`-scripted tool in this suite.
SPDSIM and BroadbandSPICE have no Tcl API at all (confirmed by grepping their doc
trees for zero hits); they're driven by CLI switches only, submitted as plain jobs.
"""

from sigrity_mcp.domains.si import broadbandspice_tools, powersi_tools, spdsim_tools  # noqa: F401
