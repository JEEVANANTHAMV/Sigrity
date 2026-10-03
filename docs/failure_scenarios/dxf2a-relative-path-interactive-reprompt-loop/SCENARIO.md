# dxf2a-relative-path-interactive-reprompt-loop

- **tool**: `dxf2a` / `a2dxf` (`dxf2a.exe`, `a2dxf.exe`; wrapped as `allegro_import_dxf` / `allegro_export_dxf` in `sigrity_mcp/domains/cad/allegro_import_tools.py`)
- **status_category**: `tool_bug_fixed` (a real failure mode found while building this module, now fixed in the wrappers)
- **verified_workaround**: YES — the wrappers resolve every path argument to an absolute path (relative to the MCP server's own cwd, via `core/paths.py` `resolve_path`) before building argv

## What went wrong

`dxf2a.exe`/`a2dxf.exe` run with the job's own per-run scratch directory as their working directory (like every `submit_job`-based tool). A caller-supplied **relative** `cnv_file`/`dxf_file`/`board_file` path that does not resolve from THAT directory does not fail cleanly: instead the tool falls back to its own interactive prompt (`Conversion File (*.cnv): `), re-prompts in a tight loop reading from a stdin that is never connected, and generates output fast enough to hit this suite's 200 MB job-log watchdog (`max_log_bytes`) **within seconds**.

This watchdog itself was added after an earlier real incident of the same "bad path -> unbounded output loop" class in `report.exe`/`step_out.exe`/`ipc356_out.exe` — so the failure mode class predates this module.

## Evidence

- `allegro_import_tools.py` module docstring (lines 65–79), "REAL FAILURE MODE FOUND WHILE BUILDING THIS MODULE, now fixed": full description including "live reproduced twice while testing this module (two ~205-209MB `run.log` files)" and the fix: "Both tools below now resolve `cnv_file`/`dxf_file`/`board_file` to absolute paths (relative to the MCP server's own working directory, not the job's) before building argv."
- `allegro_import_tools.py:124` (`_resolve(cnv_file), _resolve(dxf_file), _resolve(board_file)`) and `:150` (same for a2dxf) — the fix in the actual argv construction.
- `allegro_manufacturing_tools.py` module docstring (lines 53–57): the same absolute-resolution is applied to all seven newer manufacturing tools specifically "after a demonstrated real failure mode in this same executable family (dxf2a/a2dxf ...)."
- `README.md` (dxf bridge section): "a caller-supplied relative path that doesn't resolve from the job's own per-run scratch directory sends dxf2a/a2dxf into an interactive re-prompt loop instead of failing cleanly, generating output fast enough to hit this suite's 200MB job-log watchdog within seconds (reproduced twice, ~205-209MB logs ...) — both tools now resolve every path argument to absolute before launching."
- Residual caveat (module docstring lines 77–79): "A genuinely wrong/nonexistent absolute path will still trigger the same loop — if a job runs long past dxf2a/a2dxf's normal few-second completion time, suspect this before assuming a hang."

## Symptoms a caller observes

- Job runs long past the normal few-second dxf2a/a2dxf completion time with no `dxf2a complete.`/`a2dxf complete.` line
- Repeated prompt lines (e.g. `Conversion File (*.cnv): `) filling `run.log`
- Job eventually killed by the 200 MB runaway-log watchdog (`max_log_bytes`)
