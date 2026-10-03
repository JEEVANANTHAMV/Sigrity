# SPDIF Translator: IPC-2581 (.xml) Path Unconfirmed (Still Parsing at 90s)

**Slug**: `spdif-translator-ipc2581-unconfirmed`
**Tool(s) affected**: the built-in **SPDIF Translator** reached via `start_powersi_session` + `powersi_save_document` (no dedicated exe) — specifically the `sigrity::open document` IPC-2581 (`.xml`) path
**Status category**: `built_untested`
**Pipeline stage**: extraction (layout → `.spd` translation, IPC-2581 import)

## Symptom

Sigrity's built-in **SPDIF Translator** (inside every Layout Workbench tool — PowerSI, PowerDC, etc., *not* a separate exe) is confirmed to translate several formats to `.spd` (Altium `.pcbdoc`, DXF `.dxf`, ODB++ archives, Allegro `.brd`/`.mcm`), but its **IPC-2581 (`.xml`) path was never confirmed to complete.** When tested against a real **229 MB IPC-2581 sample**, the process was **still genuinely parsing** (holding ~1.6 GB RAM — i.e., actively working, not stalled on a dialog) when the test was **cut off at 90 s** rather than left to run unbounded.

So the IPC-2581 branch of the SPDIF translator is **plausible but unconfirmed**: no completed, verified `.spd` was produced from an IPC-2581 input on this machine. It is *not* demonstrated broken — just never observed to finish.

## Root Cause

Not blocked — **incompletely exercised.** The IPC-2581 translation of a large (229 MB / ~1.6 GB working set) design is slow, and the verification run was interrupted at the 90 s point instead of being allowed to run to completion. The translation mechanism itself (the `start_powersi_session` → `sigrity::open document` → `powersi_save_document` bridge that is already confirmed for DXF/Altium) is the same code path for IPC-2581; the format just was never given enough wall time to produce and verify an output `.spd`.

This is the built-in translator distinct from the six dedicated `*2Spd.exe` standalone CLI translators in `translators.py` (Gds2Spd/Oasis2Spd/Ndd2Spd/Pads2Spd/Rif2Spd/Dsn2Spd + SPDLinks). The built-in SPDIF Translator additionally covers Altium, **IPC-2581 (.xml)**, DXF, ODB++, and Allegro formats via `sigrity::open document` inside a PowerSI/PowerDC session.

## Evidence

- `README.md:334-346` (Domain 3, Audit) — "Sigrity's built-in 'SPDIF Translator' (inside every Layout Workbench tool, not a separate exe …) covers Altium (`.pcbdoc`), **IPC-2581 (`.xml`)**, DXF (`.dxf`), ODB++ archives, and Allegro formats … It's already reachable today through the existing `start_powersi_session`/`powersi_save_document` tool pair … **CONFIRMED LIVE against two formats this pass: a real 130KB DXF sample produced a genuine 640KB `.spd`; a real 55MB Altium `.PcbDoc` sample produced a genuine ~19MB `.spd`. IPC-2581 (tried against a real 229MB sample) is plausible but unconfirmed — the process was still genuinely parsing (1.6GB RAM, not a stalled dialog) when the test was cut off at 90s rather than left to run unbounded.**"
- `sigrity_mcp/domains/extraction/translators.py:9-19` (module docstring) — "Sigrity ships a built-in 'SPDIF Translator' inside every Layout Workbench tool (PowerSI, PowerDC, ...), not a separate exe … that additionally covers Altium (`.pcbdoc`), **IPC-2581 (`.xml`)**, DXF (`.dxf`), ODB++ archives, and Allegro `.brd`/`.mcm`/etc. Reached via `sigrity::open document` inside a PowerSI/PowerDC session … see that module's docstring for full live-test evidence: **confirmed against real DXF and Altium samples, producing valid multi-KB/multi-MB `.spd` files**."
- `sigrity_mcp/core/tool_status.py` (PowerSI/PowerDC are `confirmed_live`, lines 39-40) — the bridge's DXF/Altium path is what's confirmed; the IPC-2581 branch has no separate `confirmed_live` evidence.

## Pipeline Impact

A pipeline that needs to import an **IPC-2581 design into `.spd** via the SPDIF translator cannot currently rely on a *confirmed* result: the path has never been verified to complete for a large (229 MB) sample. On the confirmed paths (DXF, Altium) the same `start_powersi_session`/`powersi_save_document` bridge is known-good. For IPC-2581, a caller must (a) allow more than 90 s of wall time for a large design, (b) verify a real, correctly-sized `.spd` actually lands, and (c) distinguish "still parsing (1.6 GB RAM, alive)" from "stalled dialog (the 30 s MCP round-trip cap or a hung `wait_for_job`)". Treating the 90 s interruption as a failure would be wrong; treating it as success without a completed `.spd` would also be wrong.
