# powersi-frequency-suffix-parsing-error — Workarounds

## What works (confirmed)

- **Pass plain Hz exponents, never a unit suffix.** Use `start="1e6"`, `end="1e9"` (or `"0"` / `"1e3"` etc.) with `powersi_set_frequency_sweep`. The verified Task 2/Task 3 flows use exactly `start="1e6", end="1e9"`.
- **Mind the Tcl spacing when composing a raw macro**: the space between each flag and its brace-quoted value is required — `-start {1e6}` not `-start{1e6}` (the no-space form is rejected as one unrecognized token). The wrapper already emits the spaced form, so going through `powersi_set_frequency_sweep` avoids this.

## What was tried / ruled out

- Unit-suffixed strings (`"1MHz"`, `"1GHz"`): ruled out — PowerSI mis-parses the suffix and produces the spurious "ending < starting" error.
- Relying on the wrapper to convert units: ruled out — `powersi_tools.py` interpolates the string verbatim via `tcl_str()`; no conversion happens, so the caller must supply plain Hz.

## Notes

- Precondition_error: the tool call is well-formed; only the *numeric content* of `start`/`end` is wrong (unit suffix). The fix is at the call site, not in source.
