# PowerSI `license_issue_suspected` Flag Is Unreliable/Useless on This Install

**Slug**: `powersi-license-issue-suspected-useless`
**Tool(s) affected**: the job-result `license_issue_suspected` boolean surfaced on PowerSI (and other) jobs
**Status category**: `known_blocked`
**Manifest**: #67

## What went wrong

The `license_issue_suspected` flag on the job result **cannot be trusted** as a license diagnostic on this install. Two concrete problems are both documented live:

1. **It can be `false` on a perfectly healthy, artifact-producing run.** Verified live: `lmstat -c 5280@localhost` returns "Cannot connect to license server (Connection refused)", **yet** every job reported `license_issue_suspected: false` AND PowerSI still produced a genuine 70 MB 68-port `.sNp` in the same session. So the flag says "no license problem" even while the license server is demonstrably unreachable — it is not measuring what its name implies.

2. **It gives zero information when the log is empty.** The flag only reflects whether a license keyword string appears in the **last 1 MB of the log**. A healthy PowerSI run prints no such string (and, per the silent-success fingerprint, often writes a 0-byte `run.log` at all). So on those runs you get `false` with zero information — it neither confirms nor rules out a license issue.

Net effect: the flag is useless for diagnosis — it is `false` both when PowerSI is clearly working and when the license server is clearly down, and it carries no signal for the common empty-log case.

## Evidence

- `.forjinn/skills/sigrity-si/SKILL.md` (PowerSI gotchas #5, lines 196–202): "license_issue_suspected is USELESS on this install — do not trust it. Verified live: lmstat -c 5280@localhost returns 'Cannot connect to license server (Connection refused)' yet every job reported license_issue_suspected: false AND PowerSI still produced a genuine 70 MB 68-port .sNp in the same session. The flag only reflects whether a license keyword string appears in the last 1 MB of the log; a healthy run prints no such string. When a job writes an empty log (see next item) you get false with zero information. Judge by artifact, never by the flag."
- Related platform scenario: manifest #108 `lmstat-unreachable-diagnostic-gap` ("lmstat unreachable but tools work — no confirmed workaround; per-tool judgment, curated tool_status") corroborates that license-server reachability (lmstat) and actual tool success are decoupled on this machine.

## Symptoms a caller observes

- `lmstat -c 5280@localhost` → "Cannot connect to license server (Connection refused)"
- Same/other job → `license_issue_suspected: false` **and** a real 70 MB 68-port `.sNp` produced
- On empty-log runs: `license_issue_suspected: false` with no log keyword → zero diagnostic information
