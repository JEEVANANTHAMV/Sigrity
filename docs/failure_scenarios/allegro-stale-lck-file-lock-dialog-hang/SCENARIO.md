# Orphaned .lck File Causes Modal "Design Locked" Dialog on Next Launch

**Slug**: `allegro-stale-lck-file-lock-dialog-hang`
**Tool(s) affected**: `allegro_run_session`, `capture_run_session`, any tool that launches Allegro or Capture against a design path
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

After a prior batch job against a design was killed (rather than exiting cleanly — routine in headless automation where hung jobs get cancelled or test scripts get interrupted), the NEXT batch launch against that same design path blocks forever on a modal "this design appears to be open/locked, override?" dialog. There is zero console output from the process — it looks identical to a license-fetch hang or a generic timeout. The only way to recover without the fix was for a human to click through the dialog.

Specifically: a `.lck` file (e.g., `myboard.brd.lck`) is left in the design's directory. When `allegro.exe` or `Capture.exe` next opens that design path, it detects the lock file, concludes the design is still open elsewhere, and presents an interactive override dialog. In a headless context, no one can click it, so the process hangs indefinitely.

## Root Cause

Allegro and Capture both write a `<design_path>.lck` sibling file while a design is open. When the process that created the lock is killed (a hung batch job cancelled via `cancel_job`, a forcibly-terminated session, a test script interrupted) rather than exiting cleanly, the `.lck` file is orphaned — it remains on disk while no live process actually holds the design. The next launch interprets the stale `.lck` as a genuine concurrent-open indicator and pops the interactive "override?" dialog.

This was previously misdiagnosed multiple times in the project README as a license-fetch delay or a generic timeout, because the symptom (no console output, indefinite hang) is indistinguishable from those without knowing to check for a `.lck` file.

## Evidence

- `sigrity_mcp/core/tclsession.py:35-57` — `clear_stale_design_lock` function: full root-cause explanation in docstring, "Allegro/Capture both write a `.lck` file next to a design while it's open; if the process that created it is killed... that `.lck` file is orphaned. The NEXT batch launch against that same design path then hits a real modal 'this design appears to be open/locked, override?' dialog — which blocks forever with no console output at all."
- `sigrity_mcp/domains/cad/allegro_tools.py:194` — `clear_stale_design_lock(board_file)` called automatically in `allegro_run_session` before launch.
- `README.md:252-268` — "A suite-wide reliability root cause, found from a live user report of a real modal dialog... Fixed via `clear_stale_design_lock()` (`core/tclsession.py`), now called automatically by `allegro_run_session` and `start_capture_session` before every launch."
- `README.md:266-268` — "Proven live: a fake stale lock was planted next to a fresh board copy, and the real production `allegro_run_session` tool cleared it and completed in 5.3s instead of hanging."
- `sigrity_mcp/core/tool_status.py:458-468` — Capture note documenting the same root cause and the fix being "proven live for Allegro: a planted fake stale lock was auto-cleared and the job completed in 5.3s instead of hanging."
- `.forjinn/skills/sigrity-cad/SKILL.md:142-144` — "if a prior allegro job against the same board path was killed, a stale `<brd>.lck` makes the next `allegro.exe` hang on a modal 'design locked' dialog — the tool clears a stale sibling `.lck` before launch, but if you hand-ran allegro, delete `<brd>.lck` first."

## Pipeline Impact

Blocks the **design** stage. Any Allegro or Capture session against a design whose `.lck` file was orphaned by a prior killed process will hang indefinitely. This affects the entire design→analysis→production pipeline because it prevents any subsequent board authoring, DRC, or report operations on the affected board. The failure is silent (no error, no log output), making it particularly dangerous in automated pipelines where an operator might assume the job is simply slow.
