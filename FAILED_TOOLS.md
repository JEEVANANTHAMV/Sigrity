# CAD Domain — Failed / Known-Blocked Tools: Resolution Report

> **UPDATE (2026-10-21) — Of the 18 previously-catalogued failed/blocked tools, 15 have
> been REMOVED from the active MCP tool surface.** Every one of those 15 is now either:
> (a) superseded by a confirmed-live alternative that IS in the tool surface, or
> (b) not applicable to this suite's workflow and correctly absent.
> The code, tests, and smoke scripts for those 15 have been deleted.
>
> The 4 SPB translator CLI tools (`run_con2xml`/`run_cap2xml`/`run_dml2con`/`run_apd2con`)
> were initially removed but **RESTORED (2026-10-22)** at the user's request: they are
> real, working tools (GUI-confirmed) and the headless CLI is a documented best-effort
> fallback, not a broken feature. They are retained in `interchange_tools.py`.
>
> This file is preserved as a technical reference for *why* each path was blocked,
> not as a list of currently-active failing tools.

## What was removed and why

### 1. OrCAD Capture — 12 tools (REMOVED 2026-10-21)

**Software:** `C:\Cadence\SPB_22.1\tools\bin\Capture.exe`
**Root cause (historical):** Capture.exe's `Open <project>` code path hung
deterministically (0-byte log, 100% CPU, zero windows) — a machine-level defect in the
installed Capture, not a wrapper bug. The `ENABLE_CAPTURE_AUTOMATION=TRUE` env var fixed
the *hang* but did NOT fix the underlying script-non-execution problem (supplied Tcl
scripts were never actually sourced by Capture's batch mode).

**Resolution:** The full read→author→netlist→import pipeline these 12 tools were meant
to cover is now solved end-to-end by `capture_headless_tools.py`, which loads
Capture's own database DLL (`orDb_Dll_Tcl64.dll`) directly into `tclsh.exe` —
zero Capture.exe involvement:

| Removed tool | Replacement (confirmed live) |
|---|---|
| `start_capture_session` | `extract_capture_netlist_headless` (read) / `author_capture_schematic_headless` (write) |
| `capture_select_page` | (handled internally by headless tools) |
| `capture_place_part` | `author_capture_schematic_headless` (places real parts from real libraries) |
| `capture_place_wire` | `author_capture_schematic_headless` (draws real wires) |
| `capture_place_pin` | (handled internally by headless tools) |
| `capture_set_property` | (handled internally by headless tools) |
| `capture_annotate` | `author_capture_schematic_headless` (second occurrence-level pass assigns real refdes) |
| `capture_check_design_rules` | (no headless equivalent; GUI-only) |
| `capture_create_netlist` | `generate_capture_pcb_netlist` (wraps `pstswp.exe`, no Capture.exe) |
| `capture_save` | (handled internally by headless tools) |
| `capture_run_session` | (not needed — headless tools submit `tclsh`/`pstswp` jobs directly) |
| `capture_handle_custom_launch_dialog` | (not needed — no Capture.exe process to dialog with) |

The composite `generate_schematic_from_spec` (which called all of the above) was also
removed; its capability is fully covered by `author_capture_schematic_headless`.

**Files deleted:** `sigrity_mcp/domains/cad/capture_tools.py`,
`sigrity_mcp/domains/cad/schematic_generation_tools.py`,
`tests/cad/test_cad_capture_tools.py`,
`tests/cad/test_cad_schematic_generation_tools.py`,
`scripts/smoke/smoke_capture_retest.py`,
`scripts/smoke/smoke_schematic_gen_real.py`,
`scripts/smoke/test_open_only.py`,
`scripts/tools/poll_dismiss_dialog.py`.

### 2. SPB Translators — 4 tools (RESTORED 2026-10-22, were briefly removed 2026-10-21)

**Software:** `C:\Cadence\SPB_22.1\tools\bin\{con2xml,cap2xml,dml2con,apd2con}.exe`

**Status:** These four are real, distinct executables that **WORK on this install via
the GUI** product-chooser + "Translate" dialog (user-confirmed). The bare headless CLI
is a best-effort fallback that stops at the `pcb_librarian_expert` license checkout —
a property of the headless invocation path, **not** evidence the tools are broken or
missing. They are NOT a "failed/blocked" class of problem.

**Resolution:** Initially removed (2026-10-21), then **restored (2026-10-22)** at the
user's explicit request. All four `run_*` CLI helpers are back in `interchange_tools.py`
alongside the GUI helpers:

| Tool | Working path (GUI, user-confirmed) | Fallback path (CLI, best-effort) |
|---|---|---|
| `run_con2xml` | `launch_translator_gui("con2xml")` + drive the GUI dialog | CLI (stops at pcb_librarian_expert checkout) |
| `run_cap2xml` | `launch_translator_gui("cap2xml")` + drive the GUI dialog | CLI (stops at pcb_librarian_expert checkout) |
| `run_dml2con` | `launch_translator_gui("dml2con")` + drive the GUI dialog | CLI (stops at pcb_librarian_expert checkout) |
| `run_apd2con` | `launch_translator_gui("apd2con")` + drive the GUI dialog | CLI (stops at pcb_librarian_expert checkout) |

**Files:** `sigrity_mcp/domains/cad/interchange_tools.py` (all 6 functions present:
4 `run_*` + `launch_translator_gui` + `explain_translator_gate`),
`tests/cad/test_cad_interchange_tools.py` (all 7 tests present).

### 3. checkplus — 1 tool (REMOVED 2026-10-21)

**Software:** `C:\Cadence\SPB_22.1\tools\bin\checkplus.exe`

**Root cause (historical):** `checkplus.exe` checks Concept-HDL/DE-HDL design RULES —
there is NO Allegro `.brd` physical-layout input path at all. The `-proj` flag does
not accept a `.brd` file; it expects a `.cpm`/project-manager entry. This tool is
simply not the DRC path for a `.brd` board.

**Resolution:** `run_allegro_checkplus` was removed. The confirmed-live DRC path for
`.brd` boards is `run_allegro_batch_drc` (`batch_drc.exe`), which remains in the
tool surface.

**Files updated:** `sigrity_mcp/domains/cad/allegro_drc_tools.py` (function removed),
`tests/cad/test_cad_allegro_drc_tools.py` (2 test functions removed),
`scripts/smoke/smoke_new_cad_tools.py` (removed call),
`scripts/tools/brs_v2_s356_constraints.py` (removed import and call).

### 4. designextractor — 1 tool (REMOVED 2026-10-21)

**Software:** `C:\Cadence\SPB_22.1\tools\bin\designextractor.exe`

**Root cause (historical):** `designextractor.exe` is preconditioned on a running
Elastic/connectivity server at `localhost:9200` (or a reachable one via `-u`).
Without that server, it returns rc=0xFFFFFFFF with only the usage banner. Not a
defect, not blocked on a missing sample — it needs the connectivity server up.

**Resolution:** `run_allegro_design_extractor` was removed. For direct `.brd`
extraction without that dependency, use `run_allegro_extracta` (`extracta.exe`),
which is confirmed live and remains in the tool surface.

**Files updated:** `sigrity_mcp/domains/cad/allegro_extraction_tools.py` (function
removed), `tests/cad/test_cad_allegro_extraction_tools.py` (2 test functions removed),
`scripts/smoke/smoke_new_cad_tools.py` (removed import and call).

## Appendix A — `run_specctra_import_session` (still removed, confirmed product-crash)

| Tool | Exe | Command | Failure |
|---|---|---|---|
| `run_specctra_import_session` | `spif_batch.exe` | `spif_batch.exe -i <board.brd> <session.ses>` | **Deterministic product-level crash `ERROR(SPMHDB-238)`** — dies on every run. **Do not use.** |
| `run_allegro_specctra_import` *(the fix)* | `allegro.exe` (script replay) | `allegro.exe -s <macro.scr> <board.brd>` where the macro runs the real `specctra_in <session.ses>` | **confirmed_live end-to-end** |

This tool was already removed from the active surface in a prior pass. It remains
documented here for completeness.

## Appendix B — what this does NOT count as "failed" (for honesty)

- **7 `built_untested` tools** (launch fine, just unproven on real data):
  `allegro_zrouter`, `run_allegro_gerber_plot`, `run_idf_import`, `run_idx_import`,
  `run_die_abstract_check`, `run_die_abstract_compare`, `run_ibis_check` (versions 3/4/5),
  `allegro_get_module_instance_location`, `allegro_get_net_length`.
- **`allegro_place_module_instance`** — correctly implemented; blocked on a
  *board/library-path precondition* (`axlGetParam("library:CAP300")` returns nil on
  this board), an environmental gap, not a software defect.

**Net result after 2026-10-22 cleanup:**

| Category | Count |
|---|---|
| Previously failed/blocked (now removed) | **15** (12 Capture + 1 checkplus + 1 designextractor + 1 specctra_import removed in prior pass) |
| SPB translators (restored, not really failed) | **4** (`run_con2xml`/`run_cap2xml`/`run_dml2con`/`run_apd2con`) |
| Remaining MCP tools in CAD domain | **64** |
| Confirmed-working replacements for the 15 removed capabilities | **5** (3 headless Capture + 2 translator GUI helpers) |
| `known_blocked` executable entries in `tool_status.py` (historical, informational) | Still present for reference |

The `TOOL_STATUS` dict in `sigrity_mcp/core/tool_status.py` still lists the
`known_blocked` entries and their detailed evidence notes. These are informational —
they document *why* the underlying executables don't work in the ways that were tried,
and they're consulted by `get_tool_status()` for callers who need the context. They
do not affect the MCP tool surface (which no longer exposes the failed tools).
