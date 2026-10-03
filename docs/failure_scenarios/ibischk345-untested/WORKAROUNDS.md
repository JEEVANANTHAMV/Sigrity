# ibischk345-untested — Workarounds

## What works (confirmed)

- **`ibischk6` is the confirmed-live reference**: `run_ibis_check(model_file=..., ibis_version="6")` (or bare `ibischk6.exe <model.ibs>`) is demonstrated to run and correctly flag real IBIS syntax errors/warnings on a real shipped `.ibs` sample. For IBIS 6.x models, this is the path with live evidence.
- **Pass the model as a bare positional argument**: the confirmed invocation shape is `ibischkN <model.ibs>` (single position arg) — `run_ibis_check` submits exactly `[model_file]`. Don't pass `model_file` to a bare/`-help` invocation, which makes the binary try to open a literal `-help.ibs`.

## What was tried / ruled out

- **No independent live run exists for ibischk3/4/5** — the manifest classifies all three as `built_untested`. The wrappers' CLI shape is shared with the confirmed v6 (same argv, one binary per spec generation), but that is inference, not verification; there is no confirmed in-suite workaround that exercises 3/4/5.

## How to close the gap (requires external input)

- Supply a real IBIS model of the matching generation (3.2 for `ibischk3`, 4.x for `ibischk4`, 5.x for `ibischk5`) and run `run_ibis_check(model_file=..., ibis_version="3"|"4"|"5")`. No dedicated doc page exists for these, so confirm behavior empirically per version once a sample is available.
- Treat exact flag/command behavior for 3/4/5 as "best transcription, not guaranteed correct" per the suite's `built_untested` contract.

## Notes

- A non-clean verdict (`File Failed`) on a genuinely-bad model is the checker doing its job (confirmed for v6) — do not read a nonzero/fail verdict as a tool failure when the input model has real issues.
