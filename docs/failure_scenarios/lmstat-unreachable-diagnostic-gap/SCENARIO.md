# `lmstat` Reports the License Server Unreachable, but Tools Fetch Licenses and Run Fine

**Slug**: `lmstat-unreachable-diagnostic-gap`
**Tool(s) affected**: the *diagnostic* path — `get_license_server_status`, `get_license_feature_status`, `diagnose_license_feature`, `get_license_host_id` (all wrapping `lmutil`) — as a predictor of real tool usability; vs the *actual* Sigrity tools (PowerSI, PowerDC, XcitePI, OptimizePI, XtractIM, Dsn2Spd, Celsius3D/CFD/2D, Allegro session+mutation, CAD batch CLIs) which all fetch real licenses and run.
**Status category**: `known_blocked` (per manifest row 108)
**Pipeline stage**: platform (license introspection vs real license check-out)

## Symptom

`lmutil lmstat` reports this machine's FlexNet license server (`5280@localhost`) as **unreachable** — a blanket "server down / no license" signal. Yet **the same machine fetches real licenses and runs tools successfully, repeatedly** for PowerSI, PowerDC, XcitePI, OptimizePI, XtractIM, Dsn2Spd, Celsius3D/CFD/2D, Allegro session+mutation, and the CAD batch CLIs. A caller that reads `lmstat` as the single source of truth for "can I run a simulation right now" would **wrongly conclude everything is license-blocked**, when in fact the tools work.

So there is a **diagnostic gap**: the license *status* tools (`lmstat`-backed) report unreachable, while the license *check-out* that each tool does on launch actually succeeds. `lmstat`'s answer is **unreliable as a predictor of real tool usability**, so the suite deliberately does not build an automated "ping the license server per tool" feature on top of it.

## Root Cause

`lmstat -a`/`-c` (what `get_license_server_status` runs) probes the *license server's file/demon state*, which on this machine reads as unreachable (`5280@localhost`). But each Sigrity tool checks out its specific **FlexNet feature** at launch via the real FlexNet client, and that per-feature check-out **succeeds** even though the server-file probe reads unreachable. The two are different signals:

1. **`lmstat` server-file health** → "unreachable" (the diagnosed, unreliable signal).
2. **Per-tool FlexNet feature check-out at launch** → succeeds (what actually determines whether a run works), confirmed live for the long list of working tools (README:670-674).

The docstring of `core/tool_status.py` is explicit about the *second-order* danger of relying on the unreliable signal, including that an automated launch-and-see probe is *actively risky*: a single `allegro.exe -product help` probe (documented as print-and-exit) "instead blocked indefinitely on an interactive product-chooser dialog" — so the suite could not even safely automate a live per-tool license probe.

Hence: `core/tool_status.py` is **hand-curated** (a per-tool `confirmed_live`/`built_untested`/`known_blocked` registry, updated by hand as tools are tested), *deliberately not* derived from `lmutil`; and `lmstat`-backed license tools are kept (they are the real, honest `lmutil` wrappers) but treated as **per-tool/per-feature diagnostics**, not a global on/off.

## Evidence

- `sigrity_mcp/core/tool_status.py:1-15` (module docstring, verbatim): "`lmutil lmstat` has already been proven unreliable as a predictor of real tool usability on this machine — PowerSI and PowerDC both fetch licenses and run successfully, repeatedly, despite `lmstat` reporting the configured license server **unreachable**. Building an automated 'ping the license server per tool' status feature on top of that already-unreliable signal would mislead callers, not help them. Worse, an automated *launch-and-see* probe is actively risky for GUI-capable tools: a single `allegro.exe -product help` probe ... instead blocked indefinitely on an interactive product-chooser dialog."
- `README.md:667-674` (live validation, verbatim): "`lmutil lmstat` reports this machine's FlexNet server (`5280@localhost`) as unreachable — but treat license status as per-tool/per-feature, not a single on/off switch (see `get_license_server_status`/`diagnose_license_feature`): this pass alone found PowerSI/PowerDC/XcitePI/OptimizePI/XtractIM/Dsn2Spd/Celsius3D/CelsiusCFD/Celsius2D/Allegro's session+mutation mechanics/every new batch-CLI CAD tool all fetches real licenses and running successfully, while a genuinely separate handful of tools are blocked on distinct, specific causes below — **a blanket 'no license' read of `lmstat` would have wrongly written off all of them**."
- `sigrity_mcp/domains/platform/license_tools.py:17-46` — the real `lmutil` wrappers (`lmstat -a -c`, `lmstat -f`, `lmdiag`) exist and are the *honest* per-feature diagnostic; they answer "can I check this feature out now?", **not** "will tool X run."
- `sigrity_mcp/domains/platform/license_tools.py:1-8` (docstring) — confirms these wrap the real FlexLM/FlexNet client (`lmutil.exe`), confirmed via `lmutil.exe -h`/`lmstat -h`.
- `sigrity_mcp/core/tool_status.py:38-71` — the hand-curated per-tool status (a long list of `confirmed_live` tools that *do* fetch licenses), maintained by hand rather than from `lmutil`, per the module docstring's "So instead of a live query, this module is a single source of truth for what has actually been exercised, updated by hand."
- Distinct, genuinely-blocked tools are **not** `lmstat` artifacts but have their own specific causes (e.g. the interchange tools' `No Product License selected` / FlexNet server down on this machine; see tool_status.py:639-663; README:757-759) — reinforcing that license blockage here is *per-tool/per-feature*, never a blanket `lmstat` statement.

## Pipeline Impact

A pipeline or operator that **gates** a long simulation on `get_license_server_status` reading "reachable"/OK will **refuse to run tools that work fine** (false license-block), wasting hours. Conversely, a pipeline that gates on *nothing* and just runs the tool is actually correct here — the launch-time FlexNet check-out is the real test. The correct use of the license tools is **diagnostic/per-feature** ("why would *this* feature fail?"), fed by `diagnose_license_feature`/`get_license_feature_status`, combined with the hand-curated `TOOL_STATUS` — not a global pre-flight gate. This is why the suite treats `license_issue_suspected` (the per-job log-marker check in jobs.py:269-271) as the *per-job* license signal rather than `lmstat`.