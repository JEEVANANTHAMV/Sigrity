# pspice-gui-entrypoints-hang-on-help

`pspice.exe` and `pspiceaa.exe`, probed with `-help`, both hang with no output — the symptom of a GUI launch, not a CLI. This led this project's own earlier research to (incorrectly) classify PSpice as GUI-only. status_category: `gui_only_no_batch` for these two specific entrypoints.

## What went wrong

`pspice_tools.py`'s module docstring records the correction explicitly: "`pspice.exe`/`pspiceaa.exe` were probed directly and both hung with no output (consistent with a GUI launch), leading to a 'GUI-only' classification. `psp_cmd.exe` — a separate, dedicated batch-simulation executable also shipped in the same `tools/bin` — was **not** probed in that pass."

So the failure is a misclassification of the *suite's investigation*, not a bug in a wrapper: the two obvious-sounding entrypoints for "run PSpice from the command line" turn out to be GUI applications, and the actually-working headless binary lives under a completely non-obvious name (`psp_cmd.exe`) in the same directory. A caller (or an LLM, or a docs-only researcher) who tries `pspice.exe -help` or `pspiceaa.exe -help` expecting a usage banner will just hang the probe indefinitely with zero output — exactly the same trap this suite itself walked into before finding `psp_cmd.exe`.

## Evidence

- `sigrity_mcp/domains/cad/pspice_tools.py` module docstring (lines 1-17): the full "CORRECTION to this project's own earlier research" write-up, verbatim.
- `core/tool_status.py` `psp_cmd` note (lines 686-693): "MAJOR CORRECTION to earlier research, which classified PSpice as GUI-only after `pspice.exe`/`pspiceaa.exe` both hung on `-help`. `psp_cmd.exe` is a separate, dedicated batch-simulation executable in the same tools/bin, confirmed live: a bare invocation prints 'Missing circuit file argument' and exits immediately (no hang), and running it against a real shipped OrCAD PSpice sample genuinely loaded and attempted simulation..."
- `core/tool_status.py` `TOOL_STATUS` line 82: `"psp_cmd": "confirmed_live"` — the actual working binary, as opposed to the (unregistered-in-TOOL_STATUS, GUI-only) `pspice`/`pspiceaa`.
- `README.md` Domain 6 corrections section (via `sigrity_mcp/domains/cad/__init__.py`, lines 76-80): "`pspice_tools.py` — a genuine headless PSpice batch simulator (`psp_cmd.exe`, distinct from the GUI-only `pspice.exe`/`pspiceaa.exe`) were both found the same way."

## Affected code

- None, in the *current* code — `pspice_tools.py` already wraps the correct binary (`psp_cmd`) via `submit_job(tool="psp_cmd", ...)`. The scenario is a historical misclassification of `pspice.exe`/`pspiceaa.exe` as viable CLI entrypoints, corrected in `pspice_tools.py`'s docstring and `core/tool_status.py`.
