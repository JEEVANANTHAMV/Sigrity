# Workarounds: Orphaned .lck File Causes Modal "Design Locked" Dialog

## Verified Workaround

`clear_stale_design_lock(design_path)` (`sigrity_mcp/core/tclsession.py:35-57`) removes the `<design_path>.lck` sibling file before launch. This is now called **automatically** by `allegro_run_session` (`sigrity_mcp/domains/cad/allegro_tools.py:194`) and by `start_capture_session` before every launch. Proven live: a planted fake stale lock was auto-cleared and the job completed in 5.3s instead of hanging.

Additionally, a `check_design_lock` diagnostic tool (`platform/file_tools.py`) lets a caller check this specific condition on a suspiciously-stuck job.

For hand-run Allegro sessions (outside the MCP suite), the operator must manually delete `<brd>.lck` before launching.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | `clear_stale_design_lock()` auto-called before every launch | worked | `sigrity_mcp/domains/cad/allegro_tools.py:194`; `README.md:266-268` |
| 2 | `check_design_lock` diagnostic tool to detect the condition on a stuck job | worked | `README.md:264-265` |
| 3 | Manually delete `<brd>.lck` before hand-running Allegro | worked | `.forjinn/skills/sigrity-cad/SKILL.md:144` |
| 4 | Wait/retry hoping the dialog clears | didnt_work — the dialog is modal and blocks forever with no timeout | `sigrity_mcp/core/tclsession.py:44-45` |

## Prevention

1. Ensure every Allegro/Capture session job that runs through the MCP suite gets the automatic `clear_stale_design_lock` call (this is already wired in for `allegro_run_session` and `start_capture_session`).
2. After any `cancel_job` or forced kill of an Allegro/Capture process, check for and remove any `.lck` file in the design's directory before the next launch.
3. If a job appears to hang with zero log output and the board file path has a `.lck` sibling, use `check_design_lock` to confirm the condition rather than guessing it is a license issue.
4. Design pipelines to use a private, freshly-copied working file per job (the suite already does this), so that a stale lock from one job cannot affect the next.

## Remaining Gaps

The fix is complete for in-suite launches. The only residual gap is for processes launched **outside** the MCP suite (e.g., a human hand-running `allegro.exe` from a terminal, or a third-party script launching Allegro directly) — those bypass `clear_stale_design_lock` entirely and will still hang on a stale lock. A 25-year senior designer would accept this as adequate: the automated pipeline is protected, and the manual case is a one-time `del *.lck` that any Allegro user already knows about.
