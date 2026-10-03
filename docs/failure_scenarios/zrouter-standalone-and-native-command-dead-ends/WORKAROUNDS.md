# Workarounds: ZRouter Standalone & Native-Command Dead Ends

## Verified Workaround

Drive ZRouter by **Allegro script-form (FORM) replay** — the only path confirmed to produce real fanout routing. `run_allegro_zrouter` does exactly this inside a real `-s script.scr` batch Allegro session: it opens the ZRouter dialog (`zrouter`), switches to it (`setwindow form.zrouter`), populates the Connections Control File (`FORM zrouter filename "<path>"`), optionally sets grid spacing (`FORM zrouter grid <val>`), executes the fanout (`FORM zrouter execute`), closes the dialog (`FORM zrouter done`), then saves the board with `axlSaveDesign ?mode "nocheck"` and `quit`.

Evidence: `sigrity_mcp/core/tool_status.py:575-579` — "Automated via Allegro batch script (.scr) form replay — `run_allegro_zrouter` generates script commands to open the ZRouter dialog (`zrouter`), populate the Connections Control File (`FORM zrouter filename <path>`), optionally set grid spacing (`FORM zrouter grid <val>`), and execute fanout routing (`FORM zrouter execute`), saving the resulting board cleanly." And `sigrity_mcp/domains/cad/allegro_placement_tools.py:41-46` — "A FOURTH path succeeds where those three don't: the same Allegro script-form-replay technique that drives Aurora's Workflow Manager ... also drives the Z-Router dialog."

This requires a running Allegro SKILL session (the FORM replay goes through `core.tclsession.run_session`), so it inherits the standard Allegro session mechanics — automatic `DismissWatcher` and stale `.lck` clearing on launch.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | FORM script replay (`FORM zrouter filename ...` / `grid` / `execute` inside `-s script.scr`) | only working path (implemented as `run_allegro_zrouter`) | `sigrity_mcp/domains/cad/allegro_placement_tools.py:116-153`; `sigrity_mcp/core/tool_status.py:575-579` |
| 2 | Bare standalone `zrouter.exe` (no session/args) | didnt_work — opens modal GUI form, no `-help` usage at all, hangs, must be killed | `sigrity_mcp/domains/cad/allegro_placement_tools.py:27-28` |
| 3 | Native `zrouter <control_file>` Command:-prompt command in a batch session | didnt_work (dangerous false-positive) — returns rc 0 but does nothing: no `Zrouter.log`, no via, no board change | `sigrity_mcp/domains/cad/allegro_placement_tools.py:30-33` |
| 4 | Use a CLI flag syntax or SKILL function to drive zrouter | didnt_work — no such flag syntax or SKILL function exists anywhere in the ~840-file SKILL reference; it's a 5-step GUI workflow | `sigrity_mcp/domains/cad/allegro_placement_tools.py:34-40` |

## How to Succeed

1. Use `run_allegro_zrouter` (do **not** invoke raw `zrouter.exe`, and do **not** rely on a bare native `zrouter <file>` command line).
2. Provide a valid **Connections Control File** (`control_file`). The real grammar (doc-transcribed): plain text, `#`-prefixed comments/blank lines ignored, top-to-bottom; line form (1) `<I/O refdes> <net> <extend_layer> <min#vias> [<max#vias>]` (net may be `*`) and form (2) a line starting with `*`: `* <net> <shape_layer> <extend_layer> <percentage_shape_coverage>`. Example (from the doc against this suite's sample board — connect every GND pin on U1 to ETCH/BOTTOM with at least one via): `U1 GND ETCH/BOTTOM 1`.
3. Pass `grid_spacing` only if you want to override the default grid (maps to `FORM zrouter grid <val>`).
4. **Verify success by artifact, not exit code** (the native false-positive proves rc 0 means nothing): after the job, independently confirm vias were created — e.g. a downstream `run_allegro_batch_drc` / `run_allegro_report` re-read, and/or the presence of `Zrouter.log` (only written after a real Run click).

## Prevention

1. Never trust a zrouter run's return code: the native command path returns rc 0 while doing nothing, so rc 0 is **not** evidence of routing. Confirm via a real read-back.
2. Do not attempt to drive zrouter as a bare CLI tool or a one-line native command — it is GUI-only; the FORM replay is the only headless surface.
3. Treat `run_allegro_zrouter` as going through the standard Allegro session lifecycle (stale `.lck` cleared before launch, DismissWatcher auto-started) — there is nothing extra for the caller to do for dialog handling.
4. Before trusting the result, check whether `Zrouter.log` exists / the board actually gained vias; its absence means the Run step did not actually fire (a sign the FORM replay or dialog interaction did not complete).

## Remaining Gaps

- `allegro_zrouter` is `"built_untested"` in the status registry: the FORM-replay script construction is real and self-documenting, but the doc does not record a confirmed end-to-end live run that produced real vias on a real board (unlike, e.g., the SPECCTRA autoroute path). Treat a zrouter result as needing its own artifact verification until a live vias-produced run is captured.
- No shipped example Connections Control File exists under `C:\Cadence\SPB_22.1\share` — the grammar is transcribed from `doc/zcoms/zchap.html`, not validated against a working sample. So even the working path's input format is doc-derived until a real control file is exercised.
- The three dead ends are confirmed dead, but there is no evidence of *why* the native command is wired to be a no-op (Allegro product behavior); it is only characterized as a documented 5-step GUI workflow with no CLI/SKILL surface.
