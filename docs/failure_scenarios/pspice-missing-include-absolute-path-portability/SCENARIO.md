# pspice-missing-include-absolute-path-portability

Running `psp_cmd.exe` against a real shipped OrCAD PSpice sample fails because the sample's SPICE netlist references a `.include`d model file by an **absolute path from the original authoring machine** — a path that doesn't exist on this machine. status_category: `precondition_error` (the tool is correct; a board/file-content precondition — a self-contained netlist — is unmet).

## What went wrong

`core/tool_status.py`'s `psp_cmd` note records that running `psp_cmd.exe <circuit>.cir` against a real shipped OrCAD PSpice example (`share/orcad/examples/PSpice/TI/DRV8837/.../trans.cir`) genuinely loaded and **attempted** the simulation — this is genuine, real, working behavior, not a fake — but failed with a specific, readable diagnostic:

> `ERROR(ORPSIM-15347): Cannot open input file ...`

The cause, established from the sample's own content: a `.include`d model file referenced an absolute path from the original authoring machine that doesn't exist on this install. This is a property of that particular shipped sample (a portability defect in the sample itself — it was authored on a machine with a different directory layout and carries hardcoded absolute paths), not a defect in `psp_cmd.exe`, this suite's wrapper, or licensing.

## The fix is a property of the input, not the tool

`pspice_tools.py`'s module docstring states it directly: "A **self-contained** `.cir` file (no missing `.include`s) should simulate cleanly with this same invocation." — i.e. the workaround is to supply a netlist whose `.include` directives (if any) resolve to files that actually exist in this environment, rather than to change anything about how `psp_cmd` is invoked.

## Evidence

- `core/tool_status.py` `psp_cmd` note (lines 686-693): "running it against a real shipped OrCAD PSpice sample genuinely loaded and attempted simulation, failing only on that sample's own portability issue (a missing .include file from the original authoring machine) with a specific, readable diagnostic."
- `sigrity_mcp/domains/cad/pspice_tools.py` module docstring (lines 10-16): the same finding, plus the explicit self-contained-netlist guidance quoted above, verbatim.
- `sigrity_mcp/domains/cad/pspice_tools.py` `run_pspice_simulation` (lines 26-30): a plain `submit_job(tool="psp_cmd", build_args=[circuit_file])` — nothing in the invocation path itself is at fault for a bad `.include` target.

## Affected code

- `sigrity_mcp/domains/cad/pspice_tools.py` — `run_pspice_simulation` (the tool itself is fine; the input file's content is the precondition that isn't met).
- The offending artifact is the **sample input file** (`share/orcad/examples/PSpice/TI/DRV8837/.../trans.cir`), not any file in this repo.
