# Workarounds — copyproject-cpm-extension-not-appended

## Confirmed workaround (caller-side, documented in-suite): include `.cpm` in `new_project_name` yourself

There is no code fix and no flag to change this — `copyproject.exe` simply uses the `-newprojname` value as-is. Both authoritative in-suite sources (core/tool_status.py's `copyproject` note, and `allegro_project_tools.py`'s own module docstring) state the same, explicit workaround:

> "include the extension in `new_project_name` yourself if you want one" (`core/tool_status.py`)
>
> "pass one yourself (`new_project_name='myproj.cpm'`) if you want it." (`allegro_project_tools.py` docstring)

So when calling `allegro_copy_project(..., new_project_name=...)`, pass e.g. `"myproj.cpm"`, not `"myproj"`, if you want the resulting project file to carry a `.cpm` extension. This is a one-line caller discipline, already baked into the tool's own documentation — no further in-suite mechanism is needed or provided to enforce it.

## What to verify after a run

The copy operation itself (everything except the top-level file name) is confirmed working: a freshly-timestamped real CPM file (plain text, correct `design_name`/`design_library` fields) plus a full `worklib/<newdesign>/{sch_1,packaged,physical,cfg_package}` tree, ending in "SUCCESS(COPYPROJ-67): Copy Project Success." If a later stage of a pipeline fails to find/open the newly created project file, confirm the name on disk **exactly** matches what was passed as `new_project_name` (extension included) — that mismatch, not a failed copy, is the expected cause of this scenario.

## Note on `xcon2project` (its sibling tool)

The same module's `allegro_package_xcon_project` (`xcon2project.exe`) has a *separate*, documented precondition quirk that is easy to confuse with this one: its own usage banner shows `-refproj` in brackets but appends "(-refproj must be specified)" — see xcon2project-refproj-required-despite-brackets. The module's docstring documents both tools together, but the two quirks are independent: this one is about extension handling on `copyproject`'s output file name; the other is about a required-but-bracketed argument on `xcon2project`.
