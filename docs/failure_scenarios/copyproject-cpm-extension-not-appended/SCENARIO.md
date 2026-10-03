# copyproject-cpm-extension-not-appended

`copyproject.exe` names the created project file **exactly** the `-newprojname` value given — with **no `.cpm` extension appended automatically**. If a caller passes a bare name expecting the tool to add the extension (the common EDA convention), the resulting project file will have no extension and may not be recognized by other tools that expect `.cpm`. status_category: `precondition_error` (the tool/call is correct; a caller-side naming precondition — include the extension yourself — is unmet).

## What went wrong

`core/tool_status.py`'s `copyproject` note (lines 860-874) records this explicitly as "IMPORTANT": "the created project file is named EXACTLY the `-newprojname` value with no `.cpm` extension appended automatically -- **include the extension in `new_project_name` yourself if you want one**."

`sigrity_mcp/domains/cad/allegro_project_tools.py`'s module docstring (lines 26-29) repeats it: "IMPORTANT CONFIRMED QUIRK: the resulting project file is named EXACTLY the `new_project_name` value given, with NO `.cpm` extension appended automatically — pass one yourself (`new_project_name='myproj.cpm'`) if you want it."

The underlying execution itself is confirmed working — the rest of the copy operation (the full `worklib/<newdesign>/{sch_1,packaged,physical,cfg_package}` tree, real schematic pages, the physical `.brd` placeholder, "SUCCESS(COPYPROJ-67): Copy Project Success.") all landed correctly. The quirk is strictly about the *top-level CPM file's name*.

## Evidence

- `core/tool_status.py` `copyproject` note, lines 860-874 (quoted above, plus the full confirmed-live run against `share/pcb/translators/altium_proj_template/altium_proj_template.cpm`, independently verified twice).
- `sigrity_mcp/domains/cad/allegro_project_tools.py` module docstring (lines 18-34) and `allegro_copy_project` (lines 70-88): `new_project_name` is passed through **unresolved/unmodified** — the module's own docstring (lines 55-58) explains this deliberately: "Bare name arguments (`new_project_name`, `new_library_name`, `new_design_name`, `root_design_name`, `library_name`) are passed through unresolved since they aren't paths — `copyproject`/`xcon2project` interpret them relative to `copy_to_path`/`output_folder`, not the server's cwd." There is no code in the wrapper that appends or normalizes an extension — the caller is fully responsible for the exact final name, extension included.
- `README.md` lines 386-394 (`allegro_project_tools.py` write-up) documents the confirmed-live copy result but does not restate the extension quirk in that section — the authority for it is `core/tool_status.py` and `allegro_project_tools.py`'s own docstring.

## Affected code

- `sigrity_mcp/domains/cad/allegro_project_tools.py` — `allegro_copy_project` (pass-through of `new_project_name`; no extension normalization, by design, for the reasons in the module docstring).
