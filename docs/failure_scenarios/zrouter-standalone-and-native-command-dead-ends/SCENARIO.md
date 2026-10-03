# ZRouter: Standalone & Native-Command Dead Ends — Only FORM Script Replay Works

**Slug**: `zrouter-standalone-and-native-command-dead-ends`
**Tool(s) affected**: `run_allegro_zrouter` (`sigrity_mcp/domains/cad/allegro_placement_tools.py`); the raw `zrouter.exe` process (not directly wrapped)
**Status category**: `gui_only_no_batch`
**Pipeline stage**: routing (via/pin-escape fanout)

## Symptom

Three direct automation paths against the raw `zrouter.exe` process (for via/pin-escape fanout routing driven by a Connections Control File) were **all tried and confirmed to be dead ends**, not merely untested:

1. **Bare standalone `zrouter.exe`** (no session/args): opens its own modal GUI form and has **no `-help` usage text at all** — it hung and had to be killed.
2. **The native `zrouter <control_file>` Command:-prompt command** inside a batch Allegro session (the same mechanism `auto_route` uses): does **not** hang — it returns cleanly (`returncode 0`) — but it also **does nothing**: no `Zrouter.log` is written, no via is created, and no change is saved to the board. This is a *dangerous false-positive*: a clean exit that looks like success but produced no routing.
3. **The documented 5-step GUI workflow** (`doc/zcoms/zchap.html` "Running zrouter" section): this is why paths 1–2 fail — zrouter is strictly a 5-step GUI workflow (open the dialog via menu or by typing `zrouter`, which only *opens* the dialog; then manually type the Connections file name, grid spacing, and via-clearance values into dialog fields; then click Run). There is **no** command-line flag syntax and **no** SKILL function anywhere in the ~840-file SKILL function reference for any of this. `Zrouter.log` is only ever written **after** a real Run click.

A **fourth** path succeeds where those three don't: the same Allegro **script-form-replay** technique that drives Aurora's Workflow Manager also drives the Z-Router dialog — `FORM zrouter filename ...` / `FORM zrouter grid ...` / `FORM zrouter execute` inside a `-s script.scr` batch run populates and clicks the dialog the way a human would. `run_allegro_zrouter` uses this.

## Root Cause

ZRouter is a GUI-driven tool whose batch/CLI surface is deliberately non-existent (or, worse, silently ineffective). The native `zrouter` command in a batch session "succeeds" (rc 0) but performs no work because the real routing only happens after the interactive dialog is populated and Run is clicked — a step with no CLI/SKILL equivalent. The standalone `zrouter.exe` is an even worse dead end (modal GUI, no usage text). The only headless path that produces actual vias is to **replay the dialog interaction** via `FORM zrouter ...` script lines that fill the dialog fields and trigger its Run, which is what the tool does.

## Evidence

- `sigrity_mcp/domains/cad/allegro_placement_tools.py:25-46` — module docstring, the canonical statement: "ZROUTER — three direct automation paths were tried against the raw `zrouter.exe` process, and all three are confirmed dead ends, not merely untested: 1. Bare standalone `zrouter.exe` (no session/args): opens its own modal GUI form with no `-help` usage text at all — confirmed live, had to be killed after it hung. 2. The native `zrouter <control_file>` Command:-prompt command inside a batch Allegro session (the same mechanism `auto_route` uses): confirmed live to NOT hang — it returns cleanly (returncode 0) — but also confirmed to do NOTHING: no `Zrouter.log` was written, no via was created, no change was saved to the board. This is a dangerous false-positive, not a working path. 3. `doc/zcoms/zchap.html`'s own 'Running zrouter' section (`Filename:tk_Running_zrouter`) resolves why: it documents zrouter as a strictly 5-step GUI workflow ... There is no command-line flag syntax and no SKILL function anywhere in the ~840-file function reference for any of this — `Zrouter.log` is only ever written after a real Run click. A FOURTH path succeeds where those three don't: the same Allegro script-form-replay technique that drives Aurora's Workflow Manager ... also drives the Z-Router dialog — `FORM zrouter filename ...` / `FORM zrouter execute` ... `run_allegro_zrouter` below uses this."
- `sigrity_mcp/core/tool_status.py:575-579` — `allegro_zrouter` note: "Automated via Allegro batch script (.scr) form replay — `run_allegro_zrouter` generates script commands to open the ZRouter dialog (`zrouter`), populate the Connections Control File (`FORM zrouter filename <path>`), optionally set grid spacing (`FORM zrouter grid <val>`), and execute fanout routing (`FORM zrouter execute`), saving the resulting board cleanly."
- `sigrity_mcp/core/tool_status.py:65` — `"allegro_zrouter": "built_untested"` (the tool is implemented and self-documenting via the FORM-replay script, but per its registry status is not yet confirmed against a real board run beyond the script mechanics).
- `sigrity_mcp/domains/cad/allegro_placement_tools.py:116-153` — `run_allegro_zrouter` emits the FORM replay: `setwindow pcb` → `zrouter` (opens dialog) → `setwindow form.zrouter` → `FORM zrouter filename "<ctrl>"` → optional `FORM zrouter grid <val>` → `FORM zrouter execute` → `FORM zrouter done` → `setwindow pcb` → `axlSaveDesign ?mode "nocheck"` → `quit`.
- `sigrity_mcp/domains/cad/allegro_placement_tools.py:48-58` — the real Connections Control File grammar (doc-transcribed, not from a shipped sample): lines of `<I/O refdes> <net> <extend_layer> <min#vias> [<max#vias>]` or `* <net> <shape_layer> <extend_layer> <percentage_shape_coverage>`; "No shipped example control file exists anywhere under `C:\Cadence\SPB_22.1\share` to validate against — this grammar is transcribed directly from the doc, not copied from a working sample."

## Pipeline Impact

ZRouter **cannot** be driven via the standalone `zrouter.exe` or the native `zrouter <control_file>` command in any headless pipeline — the standalone path hangs (modal GUI) and the native path is a silent false-positive (rc 0, no vias). The **only** working path is `run_allegro_zrouter`'s FORM script replay, which requires a running Allegro SKILL session (it goes through `core.tclsession.run_session`, inherits the standard Allegro session mechanics, including the automatic `DismissWatcher` and stale `.lck` clearing). Consequences:

- Any fanout-routing pipeline step that assumes zrouter can be invoked as a bare CLI or a one-line native command will either hang or silently produce nothing.
- Because the native command's rc-0 false-positive writes no `Zrouter.log` and creates no vias, a pipeline that judges zrouter success by exit code will be **wrongly told it worked** — success must be confirmed by a downstream read (batch DRC / report / `Zrouter.log` presence), not by return code.
- The control-file grammar is doc-transcribed with no shipped example to validate against (`shared/` has no example control file), so even the working FORM-replay path is `built_untested` end-to-end for a real routed board.
