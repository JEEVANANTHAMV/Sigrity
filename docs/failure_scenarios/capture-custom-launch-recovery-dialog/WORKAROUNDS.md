# Workarounds — capture-custom-launch-recovery-dialog

## Confirmed fix (in-suite, live-verified)

- **`capture_handle_custom_launch_dialog(button="No")`** — an agent-callable tool that auto-dismisses the "Capture Custom Launch" recovery dialog if it's currently open. It finds the dialog window (title contains "Capture Custom Launch"), locates the matching child button by caption, and clicks it via `SendMessageW`/`BM_CLICK`. Live-verified per `capture_tools.py`'s module docstring ("a real, live-verified fix for that specific, narrower problem"). If no such dialog is open, it returns `found: False` cleanly (no error).
- **`auto_dismiss_recovery_dialog_if_stuck(job_id, check_after_seconds=15.0)`** — the opt-in, job-scoped version: after a `capture_run_session`-style job has been running with an *empty* log past 15s, it checks for this specific modal and dismisses it ("No"), returning an explanatory note on the result. `generate_schematic_from_spec` already calls this automatically after its run step (schematic_generation_tools.py line 170). Any other caller that already blocks on a Capture job can call it the same way without adding an unconditional delay to every capture tool call (it's deliberately kept separate from `capture_run_session`, which must stay a fast fire-and-forget launcher).

## What to do if you see it

1. If a Capture job looks stuck (running, empty `run.log`), call `capture_handle_custom_launch_dialog` (or, if you have the `job_id`, `auto_dismiss_recovery_dialog_if_stuck`).
2. Check the returned `found`/`clicked` fields: `found=True, clicked=True` means it was dismissed and the original `job_id` continues — re-check it with `wait_for_job`/`tail_job_log` rather than relaunching.
3. If `found=True, clicked=False` (buttons present but not clickable), the function's note tells you to use `capture_handle_custom_launch_dialog` for a manual click with a different button caption if needed.
4. Note this fix is scoped to this one dialog. It does **not** fix the main `Open <project>` hang (zero windows — there is nothing to dismiss there). See capture-batch-open-hang.

## Not the same as

- The **`Open <project>` batch hang** (capture-batch-open-hang) — that one has *no* dialog window at all; no button-click workaround can reach it.
- The **"Product Choices" license-tier dialog** (legitimately one-time for both Allegro and Capture, resolved once via the GUI) — different dialog, different cause.
