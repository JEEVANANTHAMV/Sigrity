# abcd Segfaults on 4-Port MA/dB S-Parameter Files

**Slug**: `abcd-segfault-ma-format-4port`
**Tool(s) affected**: `run_touchstone_deembed` (`abcd.exe`, logical tool `abcd`)
**Status category**: `crash`
**Pipeline stage**: extraction (utility solvers / Touchstone cascade & de-embed)

## Symptom

A hard segfault was observed when `abcd.exe` was fed a specific **4-port** Touchstone file expressed in **magnitude/angle (MA / dB) data format**. The process dies with no well-formed output file, no useful error text, and no clean return code.

This crash was seen **once**, on a specific 4-port magnitude/angle-format file. It is **not re-confirmed** today: a later attempt to re-test it found the original input files had been removed from this machine, so nothing was re-proven in either direction. The current evidence record is therefore "a real segfault was seen, root cause not isolated, cannot be reproduced because the triggering input is gone."

## Root Cause

Not isolated. Plausible hypothesis (explicitly unverified): `abcd.exe` handles 4-port S-parameter data correctly only for the rectangular-imaginary (RI) format and crashes when handed the polar MA/dB format for a multi-port (>2-port) network. The 2-port RI path is the only fully confirmed-working path; the MA/dB and 4-port axes were never independently validated.

A later re-test attempt exited `rc 0` with **no output** — but that was because the intended 4-port inputs were no longer present (abcd with missing/invalid input silently no-ops, rc 0, see `abcd-silent-no-op-no-output`). That no-op exit is **not** evidence the segfault is fixed or absent.

## Evidence

- `.forjinn/skills/sigrity-extraction/SKILL.md:267-271` — "4-port S-parameter files remain unverified (not confirmed broken, not confirmed working): a real segfault was once seen on a specific 4-port magnitude/angle-format file, but a later attempt to re-test it found the original input files no longer present on this machine, so nothing was actually re-proven either way. If 4-port work is needed, obtain real 4-port files first and test before relying on it."
- `sigrity_mcp/core/tool_status.py:786-791` (`abcd` note) — "4-port S-parameter files remain unverified either way: an earlier real segfault was seen on a specific 4-port magnitude/angle-format file, but a later attempt to re-test it found the original input files no longer present (so that attempt proved nothing about the segfault either way) -- treat 4-port work as untested-pending-real-inputs, not confirmed broken or confirmed working."
- `sigrity_mcp/core/tool_status.py:72` — `"abcd": "confirmed_live"` (2-port only; the 4-port MA/dB path is NOT what "confirmed_live" covers).
- `.forjinn/skills/sigrity-extraction/SKILL.md:286` — sample inventory rows the machine actually holds: RI 4-port `app1_drv.S4P` and `CoupledLines_SplitPlane.s4p` ("unverified with abcd, not a known crash"); MA/dB 4-port `channel.s4p` ("once segfaulted abcd; unverified since").
- `sigrity_mcp/domains/extraction/utility_solvers.py:26-31` (module docstring) — "4-port S-parameter files remain unverified either way: an earlier real segfault was seen on a specific 4-port magnitude/angle-format file, but the original input files were no longer present on a later attempt to re-test it (so that attempt exited 0 with no output for lack of valid input, not because the segfault was fixed or absent). Treat 4-port work as untested-pending-real-inputs… "

## Pipeline Impact

Blocks any Touchstone **cascade/de-embed** pipeline step that must operate on **4-port** or **MA/dB-format** S-parameters. 2-port RI de-embed (e.g. Murata capacitor `.s2p` samples) works and is the only reliable path. A pipeline that silently assumes `run_touchstone_deembed` handles 4-port MA/dB will either segfault (if feeding the offending format) or no-op rc 0 (if the input is missing), both of which a naive "trust rc 0" check would misread as success.
