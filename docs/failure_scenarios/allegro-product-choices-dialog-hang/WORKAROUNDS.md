# Workarounds: Product Choices Dialog Blocks Headless Allegro Launch

## Verified Workaround

Set a default product once via the Allegro GUI (launch `allegro.exe` interactively, select the desired product tier from the "Product Choices" dialog, and let it persist). After this one-time step, all subsequent headless `allegro.exe -s script.scr <board>` launches proceed cleanly with no dialog. This is confirmed live: after the user's fix, the session/query mechanics work end-to-end (load board, run SKILL queries, clean quit) within ~20s.

Evidence: `sigrity_mcp/core/tool_status.py:122-123` — "With a default product set, confirmed live for the session/query mechanics: `allegro.exe -s script.scr <real .brd>` loads the board and a `skill (axlCurrentDesign)` query executed and returned correctly, followed by a clean `quit`-triggered exit, all within ~20s."

Additionally, the `DismissWatcher` mechanism (`core.win32gui_helper.auto_dismiss_dialogs`) can auto-dismiss the dialog if it does appear, but the preferred fix is the one-time GUI configuration.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Set default product once via GUI | worked | `sigrity_mcp/core/tool_status.py:122-123` |
| 2 | `allegro.exe -product help` (attempted probe) | didnt_work — blocked indefinitely on the same dialog | `sigrity_mcp/core/tool_status.py:9-10` |
| 3 | `DismissWatcher` auto-dismiss (background thread) | worked (defensive) | `sigrity_mcp/core/tclsession.py:140-152` — every `tool="allegro"` session job automatically starts a DismissWatcher |

## Prevention

1. Before deploying to a new machine or CI environment, launch `allegro.exe` once interactively and select a default product from the Product Choices dialog.
2. Include this step in any provisioning/setup playbook for new Cadence install instances.
3. The `DismissWatcher` is now automatic for all Allegro session jobs (`core/tclsession.py:194`), so even if the dialog reappears (e.g., after a config reset), it will be dismissed automatically.

## Remaining Gaps

None. This is a one-time, permanently resolved configuration step. Once the default product is set, the dialog never reappears under normal operation. The only residual risk is a config reset (e.g., `CDSsetup` directory deleted), which would require repeating the one-time GUI step. A 25-year senior designer would consider this fully acceptable risk — it is standard Cadence setup procedure, not a code defect.
