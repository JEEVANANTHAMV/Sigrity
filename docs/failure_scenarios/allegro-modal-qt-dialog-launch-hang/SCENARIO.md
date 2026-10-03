# Unlabeled Modal Qt Dialog Blocks Allegro Launch

**Slug**: `allegro-modal-qt-dialog-launch-hang`
**Tool(s) affected**: `allegro_run_session`, `run_allegro_specctra_import`, `run_allegro_zrouter` — any tool that launches `allegro.exe` via `core.tclsession.run_session`
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

A few seconds into an `allegro_run_session` launch (before the board even finishes loading), an unlabeled modal Qt dialog appears on screen. The dialog:
- Has the class `Qt5QWindowIcon`
- Has a title identical to the application's own name (e.g., "Allegro" or "PCB Editor")
- Causes the main shell window's `enabled` bit to flip to 0 while it is up
- Is content-independent (no readable text identifying its purpose)
- Blocks the Allegro command dispatch loop indefinitely — the process hangs with the board never loading

In a headless context there is no one to click it. The process hangs forever with no console output, no error in `run.log`, and no further log growth.

This was reproduced **4-for-4** in a round of stackup-authoring testing, versus the historical ~1-in-4 rate for general Allegro launch flakiness — making it a near-certainty for certain workflows (specifically stackup authoring via `generate_multilayer_stackup`).

## Root Cause

Allegro's GUI initialization (even in batch/script-replay mode via `allegro.exe -s script.scr <board>`) can raise a modal Qt dialog during startup. The dialog is unlabeled and content-independent — it is most likely the same general Allegro launch flakiness as the Product Choices / license dialogs, but manifesting as a different Qt window shape. It is NOT the Product Choices dialog (that is a one-time config step) and NOT the .lck stale-lock dialog (that is a per-design-path condition). It is a third, distinct dialog that appears with higher frequency in certain session types.

The exact trigger is not documented in this codebase. The dialog is content-independent (also hit in a bare 2-layer isolation test), so it is not caused by any specific SKILL command or board content.

## Evidence

- `sigrity_mcp/core/tool_status.py:203-209` — "FOUND (separately from the ~1-in-4 general flakiness above): every one of these 4 stackup-authoring runs raised a modal Qt dialog a couple seconds into the run, requiring `core.win32gui_helper.auto_dismiss_dialogs(pid)` running concurrently to avoid an indefinite hang -- appeared content-independent (also hit a bare 2-layer isolation test) so likely the same launch flakiness, but reproduced 4-for-4 across these runs versus the historical ~1-in-4, so treat it as a near-certainty for this workflow specifically until disproven."
- `.forjinn/skills/sigrity-cad/SKILL.md:232-249` — "a stackup-authoring `allegro_run_session` launch can raise an unlabeled modal Qt dialog a couple seconds in (before the board even finishes loading) — content-independent... a `Qt5QWindowIcon`-classed popup whose title is identical to the app's own name, with the main shell window's `enabled` bit genuinely flipped to 0 for as long as it's up... a production job hung 2.5+ hours on exactly this with no agent-side way to recover."
- `.forjinn/skills/sigrity-cad/SKILL.md:243-248` — "As of this fix, every `tool="allegro"` session job... automatically starts a background `win32gui_helper.DismissWatcher` for the job's whole lifetime and stops it when the job ends — there is nothing for the calling agent to do."
- `sigrity_mcp/core/tclsession.py:140-152` — `run_session` always launches with `dismiss_dialogs=True` for `tool in ("allegro", "capture")`.

## Pipeline Impact

Blocks the **design** stage. Any Allegro session job (stackup authoring, copper shape creation, SPECCTRA import, zrouter runs, net/component creation) that triggers this dialog will hang indefinitely without the DismissWatcher. The 2.5+ hour production hang documented in SKILL.md demonstrates the severity: a single unhandled dialog can block a pipeline for hours if no one is watching. With the DismissWatcher fix in place, this is no longer a blocker, but it remains a latent risk if the watcher is not running (e.g., for hand-run sessions).
