# generate-schematic-from-spec-capture-inherited-block

`generate_schematic_from_spec` (sigrity_mcp/domains/cad/schematic_generation_tools.py) inherits OrCAD Capture's `known_blocked` batch-invocation defect: composing more `capture_*` calls into a single script does not fix the underlying reliability issue — it only removes the *sequencing* burden from the caller. status_category: `known_blocked` (inherited).

## What went wrong

The whole point of `generate_schematic_from_spec` is one call from a structured circuit spec (parts/wires/pins lists, already decided by the client's own document-intelligence system — explicitly out of scope for this suite) to a real, saved OrCAD Capture schematic. Before it, that meant composing 6-9 individual `capture_*` tool calls by hand, each needing the same `session_id` threaded through correctly. `generate_schematic_from_spec` collapses that: `start_capture_session` → `capture_select_page` → `capture_place_part` x N → `capture_place_wire` x N → `capture_place_pin` x N → (optionally) `capture_annotate`/`capture_create_netlist` → `capture_save` → `capture_run_session`.

But `capture_run_session` — the final step that actually launches `Capture.exe` against the composed script — is the exact call documented `known_blocked`/genuinely non-deterministic in `core/tool_status.py`'s `capture` note and in `capture_tools.py`'s own module docstring: one clean 3.2s run, then the next identical attempt hanging the full timeout with an empty log (repeatedly), and additionally a fast-exit "succeeded with empty log" mode (see capture-succeeded-but-empty-log-fast-exit). Composing more `capture_*` calls into one macro does not fix that underlying reliability issue — the Open `<project>` step is the first line of the macro, and that's the code path that hangs/fails.

## HONEST LIMITATION (verbatim discipline, from the module itself)

`schematic_generation_tools.py` docstring (lines 18-34): "this composes `capture_tools.py`'s existing primitives, and that module's own docstring documents OrCAD Capture's batch invocation as `known_blocked` — genuinely non-deterministic on this machine even after the stale-lock root-cause fix... Composing more capture_* calls into one script does not fix that underlying reliability issue — it only removes the *sequencing* burden from the caller. Treat a `succeeded` result from this tool the same way `capture_run_session` itself warns to: check the job's actual log content (via `tail_job_log`/`list_job_files`), not just the returncode, before trusting that the parts/wires described below actually landed in the saved design."

A second, separate honest limitation in the same docstring: per-part property assignment (e.g. setting a specific REFDES on a specific placed part) is **deliberately NOT attempted** — Capture's own `SetProperty` Tcl command operates on "the currently selected object(s)", and there is no confirmed way to select a specific just-placed part by name from a batch script; attempting to fake that would silently set the wrong part's property. Instead it queues `capture_annotate` (auto-reference-designation) rather than hand-assigned REFDES.

## Evidence

- `sigrity_mcp/domains/cad/schematic_generation_tools.py` — full module docstring (lines 1-35), and the function body (lines 96-179): resolves `design`/`schematic_folder`/`page` from the `.opj`'s project model when not explicitly given (falls back to the project stem + `PAGE_1`), composes the whole macro, calls `capture_run_session`, and then calls `auto_dismiss_recovery_dialog_if_stuck(run_result["job_id"])` as a defensive guard against the separate "Capture Custom Launch" crash-recovery dialog (see capture-custom-launch-recovery-dialog).
- `README.md` lines 486-500 (built_untested/honest-limitation section): "`generate_schematic_from_spec` ... inherits `capture_tools.py`'s own documented `known_blocked` status verbatim: OrCAD Capture's batch invocation is genuinely non-deterministic on this machine (one clean 3.2s run, then the next identical attempt hanging the full timeout with an empty log)... Composing more calls into one script does not fix that underlying reliability issue, it only removes the sequencing burden from the caller — treat a `succeeded` result the same skeptical way `capture_run_session` itself already warns to (check real log/file content, not just the returncode) until Capture's batch reliability itself is root-caused on whatever machine actually runs this in production."
- `core/tool_status.py` `capture` note — the underlying, project-agnostic, machine-level `Open <project>` defect this inherits (also documented in capture-batch-open-hang).

## Affected code

- `sigrity_mcp/domains/cad/schematic_generation_tools.py` — `generate_schematic_from_spec`.
- Inherits from: `sigrity_mcp/domains/cad/capture_tools.py` — every primitive it composes, especially `capture_run_session`.
