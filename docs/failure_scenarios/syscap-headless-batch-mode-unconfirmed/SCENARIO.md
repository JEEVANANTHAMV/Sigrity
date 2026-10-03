# syscap-headless-batch-mode-unconfirmed

`syscap.exe` ("Allegro System Capture" — a distinct, more modern schematic-capture product than the classic `Capture.exe`/OrCAD Capture already wrapped in `capture_tools.py`) has a real, extensively documented Tcl command reference (`doc/scap_tcl_comms/`, ~600 commands, including a from-nothing `newProject` call) — but **no confirmed headless/batch launch mode**. Neither `-help` nor `-tcl <script>` produced usable live evidence either way. status_category: `built_untested` (more precisely: a promising automation surface explicitly *not* wrapped, pending a documented batch-invocation that the current evidence doesn't establish).

## What went wrong (i.e. what remains unconfirmed)

`sigrity_mcp/domains/cad/__init__.py`'s module docstring (lines 121-140) is the authoritative write-up and states the status plainly: "a genuinely-documented, from-nothing 'create a brand new schematic project' call (real worked example given in its own doc page, returns 0 on success)... This would be a much more promising schematic-authoring path than `capture_tools.py`'s already-documented `known_blocked` Tcl batch reliability, IF `syscap.exe` has a working headless/batch launch mode. **That launch mechanism is NOT confirmed**: `syscap.exe -help`/`-tcl <script>` were both tried live this pass and neither produced a usable result — `-help` opened a GUI window with no console output (had to be killed) and `-tcl probe.tcl` exited immediately with no output at all (ambiguous: could mean the flag isn't recognized, or that it ran and produced no visible result for a `puts` call)."

Per the suite's own standing discipline (`__init__.py` line 51-52, and echoed in the README): tools are "deliberately NOT wrapped, to avoid fabricating a capability that doesn't exist." `syscap.exe` hits exactly that bar — the documented Tcl vocabulary is real and attractive, but the invocation surface needed to actually use it headlessly has not been confirmed, so `syscap` has **no entry at all** in `core/tool_status.py`'s `TOOL_STATUS` registry at all (unlike `capture`, which is at least `known_blocked` with a real wrapper).

## Why this matters: it's the documented *future* answer to Capture's block

`capture_tools.py`'s module docstring itself (lines 33-35) points at it: "Actually authoring a real, populated schematic end-to-end on this machine is still blocked... actually authoring schematics end-to-end on this machine would require a Cadence-level patch/reinstall **or a working `syscap.exe` batch mode** (see `domains/cad/__init__.py`'s noted, not-yet-implemented lead)." And `README.md` lines 318-332 (the "promising, not-yet-implemented lead" section) repeats the full write-up, including the exact `newProject <name> <design_name> <project_path> sch composite` signature and the list of other real, documented commands (`createSchematicPage`/`addComponent`/`drawWire`/`saveDesign`/`openProject`), with the identical conclusion that no batch-launch evidence exists yet to justify wrapping it.

## Evidence

- `sigrity_mcp/domains/cad/__init__.py` module docstring, lines 121-140 (full write-up, quoted above).
- `README.md` lines 318-332 (the "not-yet-implemented lead for future work" section — same content, same conclusion).
- `sigrity_mcp/domains/cad/capture_tools.py` module docstring, lines 33-35 (the pointer to this as the named future alternative to the current Capture block).
- `core/tool_status.py` — `syscap` is deliberately **absent** from `TOOL_STATUS`/`TOOL_STATUS_NOTES` entirely (no status assigned, because it isn't even wrapped), in contrast to `capture`, which is present and marked `known_blocked`.

## Affected code

- None, in this suite — `syscap.exe` has no wrapper, no entry in `sigrity_mcp/core/executables.py`'s registries, and no `TOOL_STATUS` entry, by deliberate design. This scenario is recorded purely as the *named, documented-but-unconfirmed* future work item, so it isn't mistaken for an oversight or re-derived from scratch.
