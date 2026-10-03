# ibischk345-untested

- **tools**: `ibischk3` / `ibischk4` / `ibischk5` (`ibischk3.exe`, `ibischk4.exe`, `ibischk5.exe`, all reached via `run_ibis_check` in `sigrity_mcp/domains/cad/allegro_library_tools.py`)
- **status_category**: `built_untested` (implemented and self-documenting; only `ibischk6` has a confirmed-live run)
- **verified_workaround**: NO (no per-version independent live test; `ibischk6` is the only confirmed-live member of the family)

## What went wrong (the gap)

The IBIS-model checker is one binary per IBIS spec generation: `ibischk{3,4,5,6}.exe`, exposed through a single wrapper `run_ibis_check(model_file, ibis_version="6")`. Only **`ibischk6` is confirmed_live**; **`ibischk3`/`4`/`5` were never independently run** against a model of their matching spec version, so their exact runtime behavior is unverified.

## Evidence

- `core/tool_status.py` (`ibischk6` note): "Confirmed live: `ibischk6.exe <real .ibs sample>` ran and correctly found real syntax errors/warnings in the sample model, exiting with its own 'File Failed' verdict — that's the checker doing its job on a model with genuine issues, not a tool failure. **ibischk3/4/5 share the same binary family/CLI shape but were not independently run.**"
- `sigrity_mcp/core/tool_status.py` TOOL_STATUS (lines 56–59): `ibischk3: "built_untested"`, `ibischk4: "built_untested"`, `ibischk5: "built_untested"`, `ibischk6: "confirmed_live"`.
- `allegro_library_tools.py` module docstring (lines 4–8): "ibischk3.exe/ibischk4.exe/ibischk5.exe/ibischk6.exe each print a version banner and try to open an argument as an IBIS filename (e.g. running one bare attempted to open a literal -help.ibs) — real invocation is `ibischkN <model.ibs>`, one binary per IBIS spec generation (3.2, 4.x, 5.x, 6.x). No dedicated doc page was found, but the live behavior is unambiguous and there is no GUI."
- `allegro_library_tools.py:43-49`: `run_ibis_check` builds `tool_name = f"ibischk{ibis_version}"` and submits `[model_file]` — identical argv shape for all four versions, which is what makes treating 6 as representative of 3/4/5 *plausible but unconfirmed*.
- `README.md`: "ibischk3/4/5/6.exe, one binary per IBIS spec generation; `ibischk6` confirmed live against a real shipped `.ibs` sample — it correctly found real syntax errors/warnings in that model, which is the checker doing its job, not a tool failure."

## Symptoms a caller should expect (unconfirmed for 3/4/5)

- A version banner, then the binary attempting to open its argument as an `.ibs` file. A bare/`-help`-ish invocation tries to open a literal `-help.ibs`.
- On a model with genuine issues, a non-clean verdict such as `File Failed` (confirmed for v6 only) — that outcome is the checker working, not a tool failure.
