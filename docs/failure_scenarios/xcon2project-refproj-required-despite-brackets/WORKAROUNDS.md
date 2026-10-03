# Workarounds — xcon2project-refproj-required-despite-brackets

## Confirmed workaround: always pass `-refproj`, regardless of the brackets

Both in-suite authorities state the same rule:

- `core/tool_status.py` `xcon2project` note: "treat it as required" (regarding `-refproj`).
- `allegro_project_tools.py` module docstring: "treated as required here despite the bracket notation."

## In practice, via this suite's own tool, it's already handled

`allegro_package_xcon_project(xcon_file, root_design_name, library_name, reference_project_file, reference_cdslib_file=None, output_folder=None)` (allegro_project_tools.py lines 91-113) makes `reference_project_file` a **required** parameter and **unconditionally** appends `["-refproj", _resolve(reference_project_file)]` to the argv (lines 102-107) — so any caller going through this wrapper already passes `-refproj` every time, whether or not they consciously remembered to. The `-refcdslib` and `-output` flags remain genuinely optional (lines 108-111).

## If calling `xcon2project.exe` directly (bypassing the wrapper)

Always include `-refproj <path-to-a-real-populated-.cpm>`. The reference project must be a genuine, already-populated project (`.cpm`/`cds.lib`/`.xcon` all present and non-template) — the confirmed-live test used `share/pcb/translators/altium_proj_template/altium_proj_template.cpm`'s sibling real project as the reference. If you don't have an obvious reference project, the in-suite-confirmed source to use is the same `share/pcb/translators/altium_proj_template/` directory that `core/tool_status.py` records as the verified live test input.

## Do NOT confuse with

- **copyproject-cpm-extension-not-appended** — a quirk of `copyproject.exe`'s *output file naming* (no `.cpm` auto-appended), unrelated to `xcon2project`'s argv.
- The generally-optional `-refcdslib`/`-output` flags on `xcon2project` — those genuinely are optional (brackets are correct for those two), unlike `-refproj`.
