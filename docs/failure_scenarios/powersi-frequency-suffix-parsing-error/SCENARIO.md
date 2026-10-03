# PowerSI Frequency Suffix ("1MHz"/"1GHz") Parses Wrong → "ending frequency < starting"

**Slug**: `powersi-frequency-suffix-parsing-error`
**Tool(s) affected**: `powersi_set_frequency_sweep` (`sigrity_mcp/domains/si/powersi_tools.py`)
**Status category**: `precondition_error`
**Manifest**: #66

## What went wrong

Passing a **unit-suffixed** frequency string to `powersi_set_frequency_sweep` — e.g. `start="1MHz"`, `end="1GHz"` — is **mis-parsed** by PowerSI. The tool reports an error of the form **"The ending frequency should not be smaller than the starting frequency"** (i.e. it treats the suffix-bearing values as numbers and ends up with ending < starting), so the run fails even though the human intent (1 MHz → 1 GHz) was valid.

The correct form is **plain Hz, no unit suffix**: `start="1e6"`, `end="1e9"` (or `"0"`, `"1e3"`, etc.). This is a content precondition on the argument values, not a bug in the wrapper — `tcl_str()` interpolates the string verbatim into:

```
sigrity::update freq -start {1e6} -end {1e9} -AFS {!}
```

## Evidence

- `.forjinn/skills/sigrity-si/SKILL.md` (Task 2, line 36): `powersi_set_frequency_sweep(session_id, start="1e6", end="1e9")   # PLAIN Hz strings, NOT "1MHz"/"1GHz"`.
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 2, "#1 mistake", line 59–60): "Also: do not pass `"1MHz"` — PowerSI mis-parses the suffix and errors 'ending frequency smaller than starting'; always `"1e6"`/`"1e9"`."
- `.forjinn/skills/sigrity-si/SKILL.md` (PowerSI gotchas #1, lines 177–181): "Frequency flags = plain Hz, no unit suffix. start='1e6', end='1e9' (or '0', '1e3'). '1MHz'/'1GHz' is parsed wrong → 'The ending frequency should not be smaller than the starting frequency.' Also the Tcl line is `sigrity::update freq -start {1e6} -end {1e9} -AFS {!}` — the space between each flag and its brace-quoted value is required; `-start{1e6}` (no space) is rejected as one unrecognized token."
- `sigrity_mcp/domains/si/powersi_tools.py:84-98` — `powersi_set_frequency_sweep` builds the line as `sigrity::update freq -start {start} -end {end}{afs} {!}` using `tcl_str()`, confirming the value is passed through verbatim (no unit conversion is performed by the wrapper).

## Symptoms a caller observes

- `powersi_set_frequency_sweep(session_id, start="1MHz", end="1GHz")`
- Run errors out with: "The ending frequency should not be smaller than the starting frequency."
- No actual extraction produced; the sweep never runs as intended.
