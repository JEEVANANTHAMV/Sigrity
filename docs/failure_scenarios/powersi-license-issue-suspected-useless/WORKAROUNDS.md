# powersi-license-issue-suspected-useless — Workarounds

## What works (confirmed)

- **Judge license/health by artifact, never by the flag.** The standing rule (SKILL gotcha #5): "Judge by artifact, never by the flag." For PowerSI that means a non-empty `<name>_S.<N>p` / `.spd` appearing in `runs/` (see `powersi-silent-success-runs-dir`). The live evidence is that a real 70 MB 68-port `.sNp` was produced even while `lmstat` reported "Connection refused" and the flag read `false` — i.e. the artifact, not the flag, reflects truth.
- **Do not treat `lmstat` reachability as the gate either.** `lmstat -c 5280@localhost` is unreachable on this install while PowerSI still works (corroborated by manifest #108 `lmstat-unreach-able-diagnostic-gap`). Use per-tool artifact judgment, not a central license-server check.

## What was tried / ruled out

- Relying on `license_issue_suspected` to detect a license problem: ruled out — it is `false` both on healthy artifact-producing runs and when the license server is demonstrably down.
- Relying on the last-1MB-of-log keyword heuristic behind the flag: ruled out — on the common empty/0-byte PowerSI log the flag returns `false` with zero information.

## Notes

- This is a `known_blocked` diagnostic gap (manifest #67): the in-suite flag cannot be fixed by a caller, and there is no confirmed better in-suite license signal. The only confirmed practice is to bypass it entirely and verify the artifact (and, where a separate negative rc + no output occurs, consult manifest #110 `negative-rc-silent-license-abort-note` for per-tool log/artifact inspection).
