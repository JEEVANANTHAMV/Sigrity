# Workarounds — interchange-translators-license-gated-workaround

The license block on `con2xml`/`cap2xml`/`dml2con`/`apd2con` is out of scope to fix (FlexNet/entitlement issue, per the project's scope note and `SCENARIOS.md` lines 24-27). The following are the confirmed-live, in-suite paths that avoid needing these four tools for the practical goals they normally serve.

## 1. "Create/duplicate a new schematic project" → `copyproject`/`xcon2project`, both confirmed live

`interchange_tools.py`'s own neighbors — `allegro_project_tools.py`'s `allegro_copy_project` (`copyproject.exe`) and `allegro_package_xcon_project` (`xcon2project.exe`) — are the suite's actual, confirmed-headless mechanism for turning an existing Capture/Concept-HDL-style project structure into a new project, bypassing any XML round-trip entirely. `core/tool_status.py`'s `copyproject` note calls it, verbatim, "the strongest 'create a new schematic design from scratch' finding in this whole pass -- it's flag-driven and fully headless (no GUI), **unlike Capture.exe's/syscap.exe's unconfirmed batch reliability**."

- Create a project by copying a real template (e.g. the confirmed-live `share/pcb/translators/altium_proj_template/altium_proj_template.cpm`): `allegro_copy_project(source_project_file, copy_to_path, new_project_name, new_library_name, new_design_name)` — produces a complete, freshly-timestamped project tree, ending in "SUCCESS(COPYPROJ-67): Copy Project Success." (Remember: include `.cpm` in `new_project_name` yourself — see copyproject-cpm-extension-not-appended.)
- Package an existing `.xcon` connectivity file into a new project: `allegro_package_xcon_project(xcon_file, root_design_name, library_name, reference_project_file, ...)` — always pass `-refproj` even though the raw CLI's banner brackets it (see xcon2project-refproj-required-despite-brackets).

These are the two paths `SCENARIOS.md`'s scope note itself names as the intended workaround for this exact group of license-blocked translators.

## 2. "Get a real `.brd` into a form Sigrity analysis tools can consume" → PowerSI BRD-bridge, confirmed live

For the downstream goal the translators nominally serve — getting connectivity/netlist data into Sigrity's analysis tools (PowerSI/PowerDC/etc.) — this install has a directly confirmed, better-supported path that does not touch XML at all:

`README.md` lines 144-149, verbatim: "The real, confirmed CAD-to-analysis bridge is PowerSI, not a dedicated translator: `start_powersi_session` accepts a real Allegro `.brd` directly — PowerSI's built-in 'BRDExtractor' translates it automatically on open. Call `powersi_save_document` right after (required — PowerSI refuses to simulate a design that hasn't been saved to native `.spd` form first), then proceed normally. Confirmed live producing a real 237KB `.spd` file and reaching `begin simulation`."

This same BRD-bridge path is reused, confirmed-live, in multiple places in this suite's own investigation notes (e.g. `core/tool_status.py`'s `allegro` note, for independently verifying a real copper-pour board by translating it to `.spd` and reading back the resulting `.Shape`/`PatchSignal` blocks through a completely separate translation engine — SPDIF — as third-party confirmation the geometry was real).

## 3. Related import/export formats that ARE confirmed live, no license gate

While the four Concept-HDL/Capture ⇄ XML/DML translators are blocked, the same "interchange" domain has several **other** confirmed-live, license-free interchange tools worth knowing about, so the workaround scope isn't accidentally assumed to be narrower than it is (`core/tool_status.py`, all `confirmed_live`):

- `ipc2581_in` / `ipc2581_out` — IPC-2581 ⇄ Allegro `.brd` (import and export both confirmed live).
- `brd2dml` — Allegro `.brd` → DML boardmodel format (confirmed live, real 51KB `.dml` with genuine `(Library (BoardModel (PinMap ...)))` content, verified by reading it) — note this is the *export-to-DML* direction, a separate, working tool from the license-blocked *import*-direction `dml2con`.
- `dsn2spd` — SPECCTRA `.dsn` → `.spd` (confirmed live).
- `idf_out`/`idx_out` — mechanical outline/placement export (confirmed live).
- `spif_batch` — Allegro `.brd` → SPECCTRA `.dsn` (confirmed live).

## What does NOT work / is out of scope here

- Retrying `con2xml`/`cap2xml`/`dml2con`/`apd2con` expecting a different result without a license change: `core/tool_status.py` notes each one was run against a real, correct sample input file and still failed identically — this is a genuine entitlement gate on this machine (whether the whole license server is unreachable, or just this specific SPB Translators feature is missing from an otherwise-working SPB 22.1 grant serving `allegro`/`allegro_report` successfully, was "not conclusively distinguished" — see the `con2xml` note, lines 643-648).
- `apd2con` has an additional, independent problem even setting license aside: no `.apd` sample file exists anywhere in the install to even give it a valid input.
