# bem2d3 Built but Never Run — No Sample File on This Machine

**Slug**: `bem2d3-builtin-untested-no-sample`
**Tool(s) affected**: `run_xhatch_field_solver` (`bem2d3.exe`, logical tool `bem2d3`)
**Status category**: `built_untested`
**Pipeline stage**: extraction (utility solvers / 2D static field solver for rigid-flex)

## Symptom

`run_xhatch_field_solver` / `bem2d3.exe` is a fully implemented, self-documenting standalone 2D static field solver, but it has **never been run against a real geometry input file on this machine**. The CLI spelling, flags, and semantics are a "best transcription" from the tool's own `-help` banner — not a guarantee it produces correct results against a real `.in` geometry file. There is **no sample input file on the machine** to exercise it.

The tool's own banner still calls itself **"BEM2D2"** internally (a legacy name baked into the shipped help text — not a typo in this suite's wrapper).

## Root Cause

Not a defect — a **coverage gap**: no real 2D rigid-flex x-hatch ground geometry input was present in the install or in `runs/` to run against. The wrapper and its flag mapping were built from the confirmed-live `-help` output (real flag names/semantics) but, per this suite's own discipline, were never promoted to `confirmed_live` because they were never executed against a live design/license end-to-end.

The tool's purpose (from the module docstring, `utility_solvers.py:32-38`): a 2D static field solver "complementary to existing BEM2D in order to support rigid-flex design" — it extracts transmission-line impedance / propagation delay over x-hatched ground planes. Invoked as `bem2d3.exe -in <geometry.in> -out <results.out> [-xhatchmode y -xhatchhp <hatch_space_m> -xhatchw <hatch_line_width_m> -xhatchangle <angle_deg>]`.

## Evidence

- `sigrity_mcp/core/tool_status.py:73` — `"bem2d3": "built_untested"`.
- `sigrity_mcp/core/tool_status.py:668-670` (`bem2d3` note) — "Confirmed via `bem2d3.exe -help`'s full self-printed usage banner (real flag names/semantics, tool's own banner still calls itself 'BEM2D2' internally), **but not run against a real geometry input file on this machine**."
- `sigrity_mcp/domains/extraction/utility_solvers.py:78-100` (`run_xhatch_field_solver`) — builds `[ -in <input> -out <output> ( -xhatchmode y ( -xhatchhp <m> ( -xhatchw <m> ( -xhatchangle <deg>) ) ) ), submits via `submit_job(tool="bem2d3", build_args=args)`.
- `README.md:438-450` (Domain 3, utility solvers) — "**`bem2d3.exe`** (a 2D static field solver for transmission-line impedance/delay over x-hatched ground, for rigid-flex designs — `run_xhatch_field_solver`). Both confirmed via their own `-help` output; **neither was run against a real data file (none was on hand) so both are `built_untested`**."
- `.forjinn/skills/sigrity-extraction/SKILL.md:300-301` — "`run_xhatch_field_solver(in, out, -xhatchmode y, …)` → `bem2d3.exe`, standalone 2D solver for rigid-flex x-hatched ground; **not exercised in this report**, same job-pattern."

## Pipeline Impact

No **confirmed** rigid-flex x-hatch impedance/delay result can be produced by the suite on this machine today. A pipeline that relies on `run_xhatch_field_solver` for real values is operating on a tool whose exact CLI/flag behavior is transcription-only — correct flag spellings may have landed, but there is no live evidence that a given `.in` file yields the correct impedance/delay output, nor that the output file is written where expected. Treat any bem2d3 result as **unvalidated** until a real geometry sample is run and the output is independently checked.
