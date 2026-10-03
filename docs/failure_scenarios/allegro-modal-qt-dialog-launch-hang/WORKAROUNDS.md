# Workarounds: Unlabeled Modal Qt Dialog Blocks Allegro Launch

## Verified Workaround

**Automatic `DismissWatcher`** — every `tool="allegro"` session job now automatically starts a background `win32gui_helper.DismissWatcher` for the job's whole lifetime (`sigrity_mcp/core/tclsession.py:194` — `dismiss_dialogs=(tool in ("allegro", "capture"))`). The watcher polls for modal Qt dialog windows and dismisses them (clicks OK/Close) automatically. This is confirmed live: every run's `x-section` read-back matched its input exactly once dismissed. Dismissal has zero observed effect on correctness.

For hand-run Allegro sessions (outside the MCP suite), the operator must manually dismiss the dialog if it appears, or use `core.win32gui_helper.auto_dismiss_dialogs(pid, timeout=...)` from a separate script.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Automatic `DismissWatcher` in `run_session` for all Allegro jobs | worked | `sigrity_mcp/core/tclsession.py:194`; `.forjinn/skills/sigrity-cad/SKILL.md:243-248` |
| 2 | Agent calls `auto_dismiss_dialogs(pid)` concurrently (pre-fix manual approach) | worked (but required agent-side action) | `sigrity_mcp/core/tool_status.py:206-207` |
| 3 | Do nothing, wait for dialog to self-dismiss | didnt_work — the dialog never self-dismisses; production job hung 2.5+ hours | `.forjinn/skills/sigrity-cad/SKILL.md:242-243` |

## Prevention

1. **Always use the MCP suite's `allegro_run_session`** (or any tool that goes through `core.tclsession.run_session`) rather than hand-running `allegro.exe` from a terminal — the DismissWatcher is wired in automatically.
2. If building a custom pipeline that launches `allegro.exe` directly, replicate the DismissWatcher pattern: start a background thread that polls for `Qt5QWindowIcon`-classed modal windows and dismisses them.
3. Monitor `run.log` for the 3-line startup banner with no further growth — if a job is still `running` after 30+ seconds with no log growth, suspect a modal dialog and check for open Qt windows on the machine.

## Remaining Gaps

The DismissWatcher handles the **symptom** (clicking the dialog away) but does not address the **cause** (why Allegro's GUI initialization raises this dialog in the first place). The dialog is:
- Unlabeled (no text identifying its purpose)
- Content-independent (appears regardless of board content or SKILL script)
- More frequent in certain workflow types (4-for-4 for stackup authoring vs ~1-in-4 generally)

This suggests a deeper Allegro GUI initialization issue that this codebase does not diagnose further. A 25-year senior designer would consider the DismissWatcher an **acceptable mitigation** for production use — it is reliable, has zero correctness impact, and fully automates the dialog handling. However, it is not a root fix: if Allegro's dialog behavior changes (different window class, different button layout), the watcher may need updating. This is a maintained-mitigation, not a solved problem. Full automation is not blocked, but the pipeline carries a small risk of a future Allegro update breaking the watcher's window-matching logic.
