# capture-batch-open-hang

The OrCAD Capture batch invocation `Capture.exe -product=<name> script.tcl` hangs on the very first `Open <project>` step: 100% CPU spin, a 0-byte `run.log`, zero windows of any kind, forever. status_category: `unreliable_intermittent` (with a project-agnostic, machine-level `Open`-step hang component).

## What went wrong

A minimal Tcl macro (Open + Save + Close + Exit — no placement at all) submitted through `capture_run_session` (`sigrity_mcp/domains/cad/capture_tools.py`) does not reliably run. `core/tool_status.py`'s `capture` note (lines 458-523) records the observed failure modes across repeated attempts:

- One run hung the full 90s wait with an empty log and had to be killed.
- Against the real shipped sample `tools/capture/samples/PCB-Layout/Fault-Detector/Fault-Detector.opj`: the process launched with the confirmed-correct argv but was **still running with an empty log after 60s** and had to be force-killed. This rules out licensing as the cause.
- With a full 5-minute wait, results are inconsistent across repeated attempts: one run completed cleanly in **~3.2s** (open+save+close+exit, returncode 0), but the next fresh attempt hung with an empty log for the full 5 minutes and had to be killed.
- The hang reproduces with a *different*, simpler shipped sample (`FullAdder.opj`, pure schematic, no PCB data) using only the minimal Open+Close+Exit script: identical 0-byte log, **no `.lck` file ever written into the project directory** (i.e. the `Open <project>` step itself never completes, before any Part/Wire/Pin command has a chance to run), 100% CPU spin, and **zero windows** the entire hang — checked live via EnumWindows, so it is not hidden behind a modal dialog of any kind.
- Meanwhile `Capture.exe -version` alone returns cleanly in ~0.1s, and a bare `Capture.exe` launch (no args) now opens cleanly after the Product Choices default was set once — so `Capture.exe` is not fully broken; it is specifically the project-opening code path (the first thing any real automation script does) that hangs deterministically, with no CLI flag or documented workaround found in the local doc tree.

Repeated earlier attempts also inconsistently opened Capture's own default/tutorial project instead of running the given script, or exited immediately with no output.

## Evidence

- `core/tool_status.py` `capture` note, lines 468-523: the 3.2s clean run vs. full-5-minute hang on consecutive fresh attempts (fresh project-directory copy per run, to rule out lock confusion); FullAdder.opj repro with no `.lck` ever written and zero windows (live EnumWindows check).
- `README.md` lines 137-143: Capture re-tested after the licensing fix against `Fault-Detector.opj` with a minimal Open+Save+Close+Exit macro — running with an empty log after 60s, force-killed; "This rules out licensing as the cause definitively — the batch-invocation unreliability documented before is a separate, still-unresolved issue."
- `sigrity_mcp/domains/cad/capture_tools.py` module docstring (lines 21-35): the `known_blocked` status further root-caused to a specific, **project-agnostic, machine-level defect** in this install's own `Open <project>` code path — not a wrapper-layer bug; "nothing in this module's Python code is a workaround for that."
- `core/tool_status.py` `TOOL_STATUS` line 43: `"capture": "known_blocked"`.

## Affected code

- `sigrity_mcp/domains/cad/capture_tools.py` — `start_capture_session` (emits `Open <project>` as the first macro line; calls `clear_stale_design_lock` first, which does not resolve this), `capture_run_session` (launches `Capture.exe -product=<name> macro.tcl`).
- `core/tclsession.py` `run_session` (shared launcher; not itself at fault).
