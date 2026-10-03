# eagle2cp-no-batch-mode — Workarounds

## What works (confirmed in-suite paths, not Eagle2Cp itself)

- **No in-suite, non-interactive Eagle import exists.** For schematic/netlist → project flows the suite's real, headless mechanisms are the project translators/wrappers already confirmed live (e.g. `allegro_copy_project`/`copyproject.exe`, `xcon2project`) rather than the Eagle bridge.
- If the Eagle data must first be converted, the practical path is to do the Eagle → (intermediate the suite *can* read headlessly) conversion **outside** this MCP (manually, once, in the GUI) and then feed the result to a wrapped tool — the suite itself does not automate the Eagle step.

## What was tried / ruled out

- Non-interactive / flag-driven invocation: not found — the exe halts specifically on `waiting for forcelabel parameter (yes or no)`. No flag to answer or bypass that prompt was located, so it is not wrapped.

## Evidence gap (honest)

- This is a documented dead end, not a bug in any wrapper: the only confirmation is the observed prompt behavior; no alternate invocation was discovered, and there is no confirmed in-suite workaround at all.

## Notes

- If a future pass discovers the flag/piping form that answers the `forcelabel` prompt, a `submit_job`-style wrapper (with the standard absolute-path convention) would be the natural shape — but that is future work, not current capability.
