# Workarounds — syscap-headless-batch-mode-unconfirmed

## verified_workaround: None — by design, this is a "not yet, and only when" item

There is no in-suite workaround because there is no in-suite *tool* yet: `syscap.exe` has no wrapper, no registry entry, and no `TOOL_STATUS` line. `__init__.py`'s docstring is explicit about why: "Not wrapped here because **that's not enough evidence to claim a working automation surface, per this suite's own discipline**." The workaround, in other words, is the suite's documented *decision not to paper over the gap with an unverified surface* — the same discipline that produced the "deliberately NOT wrapped" classification for `apr.exe`/`placeroute.exe`, `padstack_editor.exe`, and the other genuinely GUI-only tools (`__init__.py` lines 50-57).

## What to do *today* for the same goal (confirmed-live, already available)

The manifest itself points at the intended fallback (SCENARIOS.md line 97, and `__init__.py`'s `allegro_project_tools.py` write-up): **use `copyproject`/`xcon2project`** for actual "create a new schematic project" work on this machine, not `syscap`:

- `allegro_copy_project` (`copyproject.exe`, confirmed live) and `allegro_package_xcon_project` (`xcon2project.exe`, confirmed live) are "genuinely headless/flag-driven — no GUI needed — making them a strictly better automation path than System Capture's Tcl API for 'create/duplicate a schematic project,' at least until a real `syscap.exe` batch invocation is confirmed." (`allegro_project_tools.py` module docstring, lines 36-38.)
- For PSpice simulation independent of any schematic tool, `run_pspice_simulation` (`psp_cmd.exe`, confirmed live) is available directly on a `.cir` netlist.
- For getting an already-existing `.brd` into analysis-ready form, the PowerSI BRD-bridge (`start_powersi_session`/`powersi_save_document`, confirmed live) is the confirmed path — see interchange-translators-license-gated-workaround.

## What would change this scenario (the named future-work trigger, verbatim)

`README.md` lines 330-332: "Not wrapped without stronger evidence of a real batch invocation, per this suite's standing discipline against fabricating automation surfaces — **but the Tcl vocabulary itself is real and worth revisiting if a documented `syscap.exe` CLI/batch flag turns up.**"

`__init__.py` lines 136-140 gives the concrete next step to check for that: "worth revisiting **if a documented `syscap.exe` CLI/batch invocation is found (check for an 'Allegro System Capture' install/admin guide chapter this pass didn't locate)**." Concretely, a future pass should look in `doc/scap_tcl_comms/` (whose real `newProject`/`createSchematicPage`/`addComponent`/`drawWire`/`saveDesign`/`openProject` vocabulary is already confirmed real) and any install/admin guide not yet searched, for an explicitly documented command-line or batch flag for `syscap.exe` — **not** just re-running `-help` (which opens a GUI window) or `-tcl <script>` (which exits with no output — ambiguous, as the current evidence records) and calling that confirmation.

## What does NOT count as closing this scenario

- Rerunning the same ambiguous `-tcl probe.tcl` probe and getting "no output" again — `__init__.py` already classifies that result as explicitly ambiguous ("could mean the flag isn't recognized, or that it ran and produced no visible result for a `puts` call"), not as confirmation.
- Wrapping `syscap.exe` on the strength of `doc/scap_tcl_comms/`'s documented Tcl vocabulary alone — that is exactly the "fabricating an automation surface" anti-pattern the project's own discipline (and `SCENARIOS.md`'s scope note) is set up to prevent.
