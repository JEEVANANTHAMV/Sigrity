# Workarounds: `lmstat` Unreachable Diagnostic Gap

## Verified Workaround (in-suite)

**Judge license/entitlement per-tool and per-feature, never as a single `lmstat` on/off.** Concretely, the suite uses **three complementary signals instead of one blanket `lmstat`**:

1. **Per-tool hand-curated status** — `core/tool_status.py`'s `TOOL_STATUS` registry (`confirmed_live` / `built_untested` / `known_blocked`), maintained by hand as tools are actually tested (tool_status.py:1-15 docstring: "this module is a single source of truth for what has actually been exercised, updated by hand"). This is the primary predictor of "will this tool run," and it deliberately does *not* derive from `lmutil`.
2. **Per-feature `lmutil` diagnostics when a specific feature is suspect** — `get_license_feature_status` (`lmstat -f <feature>`) and especially `diagnose_license_feature` (`lmdiag -c <spec> <feature>`) answer "can *this* feature be checked out now?", which is the real gate for a specific tool (license_tools.py:28-46).
3. **Per-job log evidence** — `JobManager` sets `license_issue_suspected` by scanning the job's log tail for license markers (`no license`, `flexlm`, `flexnet`, `unable to checkout`, `license denied`; jobs.py:28-35, 268-271). This is the *per-run* signal that a given job actually failed on a license.

Manifest row 108 marks this `verified_workaround: NO (per-tool judgment; curated tool_status)` — i.e. there is no single "fix," the workaround *is* the discipline: **curated `TOOL_STATUS` + per-feature `lmutil` diagnostics + per-job log markers**, and treating `lmstat -a` (server health) as unreliable for predicting tool availability.

## What works / what does not

- **Works**: running the tool directly — the launch-time FlexNet feature check-out is the real test, and it succeeds for the confirmed-live tools (README:667-674). The long `confirmed_live` list in `tool_status.py:38-71` is exactly the set of tools whose check-out demonstrably works despite the `lmstat` "unreachable" read.
- **Does not work (avoid)**: pre-gating a pipeline on `get_license_server_status` reading "reachable." It will report unreachable and **wrongly block tools that run fine**.
- **Does not work (avoid)**: an automated "launch-and-see" per-tool license probe. Explicitly dangerous — a single `allegro.exe -product help` probe "blocked indefinitely on an interactive product-chooser dialog" (tool_status.py:1-15).

## Why there is no "real" fix

The gap is inherent to the machine's FlexNet setup: `lmstat -a` reads the server file as unreachable while per-feature check-out succeeds. No in-suite code can change the FlexLM server state. The suite's answer is to **route around the unreliable single signal** (per-tool/per-feature/per-job evidence) — a judgment discipline, not a fix. A "real" fix would be getting the FlexNet server file properly visible to `lmstat` (an environment/licensing grant issue, out of suite scope).

## Workarounds tried (with outcomes)

| # | Approach | Outcome | Evidence |
|---|----------|---------|----------|
| 1 | Gate the pipeline on `get_license_server_status` reading reachable | **false license-block** — blocks tools that actually run | tool_status.py:1-15; README:667-674 |
| 2 | Curated per-tool `TOOL_STATUS` (hand-maintained) | **works** — accurate predictor of "will this tool run," decoupled from the unreliable `lmstat` read | tool_status.py:1-15, 38-71 |
| 3 | Per-feature `lmstat -f` / `lmdiag` via `diagnose_license_feature` | **works** as a *diagnostic* for a specific feature's check-out | license_tools.py:28-46 |
| 4 | Per-job log license-marker scan (`license_issue_suspected`) | **works** as the *per-run* license signal | jobs.py:28-35, 268-271 |
| 5 | Automated launch-and-see per-tool license probe | **unsafe / rejected** — can hang on an interactive product-chooser dialog | tool_status.py:1-15 |

## Prevention

1. **Never use `lmstat -a` as a global pre-flight gate** for "can I run X" on this machine. Consult the curated `TOOL_STATUS` first.
2. **When a specific tool is failing, use `diagnose_license_feature` / `get_license_feature_status`** for that tool's exact FlexNet feature, and read the job's `tail_job_log` + `license_issue_suspected` — treat license status as per-tool/per-feature (README:667-674).
3. **Do not automate live per-tool license "launch-and-see" probes** (GUI-capable tools can hang on a modal product-chooser dialog).
4. **When adding a tool's status, record the *real* per-feature behavior** (does its FlexNet check-out succeed?) in `TOOL_STATUS`, and note the distinct specific cause for any genuinely-blocked tool (e.g. `con2xml`/`cap2xml`/`dml2con`/`apd2con`'s `No Product License selected` — tool_status.py:636-667) rather than attributing it to the blanket `lmstat` read.

## Remaining Gaps

`lmstat`'s "unreachable" read is a **persistent, environment-level** condition that no in-suite code changes; the diagnostic gap is worked around, not closed. The reliable signals (curated `TOOL_STATUS`, per-feature `lmutil`, per-job log markers) are all *judgment* paths that must be maintained: `TOOL_STATUS` is hand-updated, per-feature diagnostics must be pointed at the right feature, and log markers are heuristic. A blanket "no license" conclusion from `lmstat` remains the documented anti-pattern (README:673-674: "a blanket 'no license' read of `lmstat` would have wrongly written off all of them").