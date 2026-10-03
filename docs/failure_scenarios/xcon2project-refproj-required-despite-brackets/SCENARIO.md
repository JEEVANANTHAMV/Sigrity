# xcon2project-refproj-required-despite-brackets

`xcon2project.exe`'s own usage banner displays `-refproj` in **brackets** (the conventional notation for an optional argument) but immediately appends the text "(-refproj must be specified)" — a direct, self-contradictory signal in the tool's own help output. It is required. status_category: `precondition_error` (the tool's own documented usage is internally inconsistent; treating `-refproj` as optional based on the brackets alone is the error).

## What went wrong

`core/tool_status.py`'s `xcon2project` note (lines 875-881) documents the confirmed-live invocation as:

> `xcon2project.exe -xcon <path.xcon> -root <name> -lib <libname> -refproj <ref.cpm> [-refcdslib <cds.lib>] [-output <dir>]` (note: **the tool's own usage banner appends "(-refproj must be specified)" despite showing it in brackets** -- treat it as required)

The confusion this creates is real and specific: a caller (or an LLM researcher) reading the brackets alone, following standard CLI convention, would reasonably treat `-refproj` as optional and omit it — and that invocation would be wrong, per the tool's own (later-appended) text.

## Evidence

- `core/tool_status.py` `xcon2project` note, lines 875-881 (quoted above), confirmed live against a real populated project (`share/pcb/translators/altium_proj_template/`, which has a genuine non-template `.cpm`/`cds.lib`/`.xcon`): produced a real new project `.cpm` + `cds.lib`, log showing real "Packaging design '<root>'" status.
- `sigrity_mcp/domains/cad/allegro_project_tools.py` module docstring (lines 32-34): "Its own usage banner shows `-refproj` in brackets but appends '(-refproj must be specified)' — **treated as required here** despite the bracket notation."
- `sigrity_mcp/domains/cad/allegro_project_tools.py` — `allegro_package_xcon_project` (lines 91-113): the wrapper makes this concrete in code — `reference_project_file` is a **required** positional parameter (no default), and `args` unconditionally includes `["-refproj", _resolve(reference_project_file)]` (lines 102-107), *before* the optional `-refcdslib`/`-output` branches. There is no code path in this wrapper that omits `-refproj`; a caller cannot accidentally omit it through this tool the way they could against the raw `xcon2project.exe` CLI.

## Affected code

- `sigrity_mcp/domains/cad/allegro_project_tools.py` — `allegro_package_xcon_project` (already encodes the correct, required-`-refproj` behavior; this scenario is recorded so the raw-CLI convention of "brackets = optional" isn't reused as a shortcut elsewhere, e.g. if someone later calls `xcon2project.exe` directly for a new flag combination not covered by this wrapper).
