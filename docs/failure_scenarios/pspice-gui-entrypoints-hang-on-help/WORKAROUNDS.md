# Workarounds — pspice-gui-entrypoints-hang-on-help

## Confirmed workaround (in-suite, live-verified): use `psp_cmd.exe`, not `pspice.exe`/`pspiceaa.exe`

- `core/tool_status.py` `TOOL_STATUS`: `"psp_cmd": "confirmed_live"` — the actual working, headless batch-simulation executable. This is a separate binary from (and lives in the same `tools/bin` directory as) the GUI-only `pspice.exe`/`pspiceaa.exe`.
- `sigrity_mcp/domains/cad/pspice_tools.py` — `run_pspice_simulation(circuit_file)` already submits its job against `tool="psp_cmd"` (line 29), so any caller using this suite's own tool is already on the correct path and does not need to do anything differently.
- Live evidence (`core/tool_status.py` `psp_cmd` note): a bare `psp_cmd.exe` invocation prints `"Missing circuit file argument"` and exits immediately (no GUI, no hang) — real headless CLI; and it genuinely loaded and attempted simulation against a real shipped OrCAD PSpice sample (failing only on that sample's own portability issue — see pspice-missing-include-absolute-path-portability).

## Rule for anyone probing PSpice entrypoints manually

Never probe `pspice.exe -help` or `pspiceaa.exe -help` expecting CLI usage output — they will just hang with no output (confirmed: both were probed this way and hung). If you need to confirm PSpice's batch capability on this machine, probe `psp_cmd.exe` directly (a bare invocation is a safe, fast, no-side-effect probe: it just prints the missing-argument error and exits).

## Not needed for anything in this suite

Since `pspice_tools.py` (the only PSpice-facing tool in this codebase) already uses `psp_cmd`, there is no further code change required. This scenario is recorded so that a future researcher (or an LLM) extending this area doesn't redo the same misclassification walk from scratch.
