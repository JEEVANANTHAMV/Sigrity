"""Domain 3 — Interconnect Extraction & Modeling.

Covers two distinct kinds of tool:

1. **Translators** (`translators.py`): pure format-conversion CLI utilities that turn a
   layout in some third-party EDA tool's native format into Sigrity's `.spd` — Gds2Spd,
   Oasis2Spd, Ndd2Spd, Pads2Spd, Rif2Spd, Dsn2Spd, plus the broader-format SPDLinks. None
   of these have a Tcl API (confirmed: zero Tcl hits in Translators_UG) — they're driven
   entirely by CLI switches, so they're submitted as plain background jobs the same way
   SPDSIM/BroadbandSPICE are in Domain 2.

2. **Solvers** (`clarity3d_tools.py`, `xtractim_tools.py`): the actual extraction engines.
   Clarity3D is full-wave 3D FEM extraction, driven through a `sigrity::`-namespaced Tcl
   session exactly like PowerSI in Domain 2 (compose a macro across several tool calls,
   then run it once). XtractIM (2.5D/3D package/PCB parasitic extraction) supports both a
   pre-built-workspace CLI mode and a `sigrity::`-Tcl session mode; both are exposed here.

3. **T2B** (`t2b_tools.py`): SPICE-to-IBIS behavioral model conversion. Unrelated to the
   translators despite shipping in the same `tools/bin` folder — CLI-only, no Tcl.

Deliberately NOT exposed as tools: Clarity3DHPCLauncher.exe, Clarity3DAgent.exe,
solver_engine.exe, c3d_engine/c3d_prepare, l3d_engine/l3d_prepare,
wave3d_engine/wave3d_prepare, AFSmodule.exe, HexMesh.exe, MeshRefiner.exe,
SigmaMesh.exe. These are internal worker processes that Clarity3D/XtractIM auto-dispatch
during a run (mesh generation, adaptive frequency sampling, distributed/HPC dispatch) —
none of them are documented anywhere in the shipped doc tree for direct, standalone CLI
invocation, so wrapping them as tools would just offer a way to misuse internals the
product itself drives automatically.
"""

from sigrity_mcp.domains.extraction import (  # noqa: F401
    clarity3d_tools,
    t2b_tools,
    translators,
    xtractim_tools,
)
