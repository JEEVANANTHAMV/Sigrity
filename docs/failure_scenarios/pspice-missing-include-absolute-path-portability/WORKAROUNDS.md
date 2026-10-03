# Workarounds — pspice-missing-include-absolute-path-portability

## Confirmed workaround: supply a self-contained `.cir` file

`pspice_tools.py`'s module docstring, verbatim: "A **self-contained `.cir` file (no missing `.include`s) should simulate cleanly with this same invocation." That's the entire workaround — it's a property of the input netlist, not of `psp_cmd`'s invocation.

Concrete options, in order of preference:

1. **Use a `.cir` with no `.include` directives at all** (all model content inlined) — this is what "self-contained" means and is the cleanest form to hand to `run_pspice_simulation`.
2. **If the netlist genuinely needs `.include`** (e.g. a shared model library), rewrite each `.include` line to point at an **absolute path that exists on this machine** (or a relative path resolvable from the job's own working directory, if that's more convenient and you can't/aren't supposed to edit the original sample), rather than the original authoring machine's layout.
3. **Don't reuse the specific shipped sample as-is** for a clean end-to-end smoke test: `share/orcad/examples/PSpice/TI/DRV8837/.../trans.cir` is the one file confirmed to carry this defect. A different, self-contained netlist is the right test input for confirming `psp_cmd` simulates cleanly (which, per `core/tool_status.py`, it does — it "genuinely loaded and attempted simulation" before hitting only this file-specific portability error).

## What is NOT the problem here (don't waste time on)

- `psp_cmd`'s own launch/CLI mechanics — confirmed working, no hang, real headless binary (see pspice-gui-entrypoints-hang-on-help).
- Licensing — the tool's own diagnostic (`ERROR(ORPSIM-15347): Cannot open input file`) is a plain file-not-opened error, not a license message.
- This suite's `run_pspice_simulation` wrapper — it's a one-argument, one-flag pass-through (`submit_job(tool="psp_cmd", build_args=[circuit_file])`); nothing in the invocation path can fix or is causing a bad `.include` path.
