# celsius2d-invalid-cfd-reference-domain-error

- **tool**: `celsius2d` (`Celsius2D.exe`, wrapped as `run_celsius2d_workspace` in `sigrity_mcp/domains/thermal/celsius2d_tools.py`)
- **status_category**: `precondition_error` (the tool and its invocation are correct; a specific input workspace's *content* is invalid — it references a CFD file that does not exist/is not valid for that workspace)
- **verified_workaround**: YES — use a valid, self-contained workspace (e.g. the Cadence `demo_sim.pdcx` sample) and confirm the "Simulation succeed" line + artifacts

## What went wrong

Running the **`chip.pdcx`** sample workspace fails with a **domain-content error**:
"The CFD File Specified in the Use Defined CFD File is invalid." This is NOT a
launch failure, a license failure, or a CLI/syntax problem. The CLI invocation is
identical to the one that succeeds for `demo_sim.pdcx`; both use
`Celsius2D.exe -b -XIMSAVE -r <workspace>.pdcx`. The difference is purely the
workspace's internal content — `chip.pdcx` references a CFD file that is invalid
for that workspace (missing, mismatched, or not present where the workspace expects
it).

The good news this error surfaces: it is a real, readable diagnostic in the job log,
not a silent failure — which confirms the CLI wrapper itself is sound and that
Celsius2D reports content problems explicitly.

## Root cause

A Celsius2D `.pdcx` workspace is a pre-built, self-contained description of a 2D
board thermal/stress problem: geometry, materials, sources, boundary conditions,
and (for coupled cases) a referenced CFD definition. When the "Use Defined CFD File"
setting points at a file that does not exist or is not a valid CFD file, the solver
rejects the workspace at load — before doing any simulation work. `chip.pdcx`
shipped in that state (or its companion CFD file was not shipped alongside it), so
any run of that specific sample fails on that precondition. This is a
**board/file/content precondition**, not a defect in the suite or in Sigrity's CLI.

## Evidence

- `core/tool_status.py:554-559` (the `celsius2d` note): "Confirmed live against a
  real Cadence sample workspace (share/PostInstallationCheck/celsius2d/demo_sim.pdcx):
  `Celsius2D.exe -b -XIMSAVE -r demo_sim.pdcx` exited 0 with 'Simulation succeed' and
  full thermal+stress engine logs. **A second sample (chip.pdcx) failed with a real
  domain-content error (an invalid referenced CFD file), not a launch/license/syntax
  failure** — confirming errors surface as readable diagnostics rather than silently."
- `domains/thermal/celsius2d_tools.py` module docstring (lines 12-15): "A second
  sample (`chip.pdcx`) failed with a domain-content error ('The CFD File Specified in
  the Use Defined CFD File is invalid') rather than a launch/license/syntax failure —
  confirming the CLI invocation itself is solid and errors surface as real, readable
  diagnostics in the job log, not silent failure."
- `.forjinn/skills/sigrity-celsius/SKILL.md` Task 1 (Caveats): "A *different* sample
  (`chip.pdcx`) fails with a domain-content error ('The CFD File Specified in the Use
  Defined CFD File is invalid') — that's an input problem, not a launch/license
  failure." (Contrast: `demo_sim.pdcx` → succeeded, rc=0, ~14 s.)

## Positive control (the same invocation works on valid input)

- `demo_sim.pdcx` with the identical `Celsius2D.exe -b -XIMSAVE -r …` invocation:
  exited 0, "Simulation succeed", full thermal+stress engine logs, real artifacts
  written next to the `.pdcx` (`demo_sim.results` 1.36 MB, `demo_sim_ThermalResult.tem`
  12 MB, `demo_sim_ThermalEngine.log` with a real MUMPS in-core solve). Success line
  (engine log, exact): `[2026/09/26-19:26:52]--Simulation succeed` and
  `demo_sim_ResourceProfile.log`: `[Total Simulation Time] 10.899124 s`.

## Symptoms a caller observes (for the invalid reference)

- `run_celsius2d_workspace(pdcx_file="…chip.pdcx")` submits normally (no error at
  submit time); the job runs.
- `wait_for_job` → the job **fails** with a readable diagnostic in the log: "The CFD
  File Specified in the Use Defined CFD File is invalid."
- No result artifacts are produced next to `chip.pdcx`.
- No license error, no syntax error, no launch error in the log — it is specifically
  a referenced-file/CFD-content diagnostic.

## Pipeline Impact

A pipeline that assumed any shipped `.pdcx` would run will stall/fail specifically
on `chip.pdcx` (or any workspace with a dangling/invalid CFD reference). Because the
error is a clear, readable log line, the right response is to treat it as an
**input-precondition failure** — swap in a valid self-contained workspace or fix the
referenced CFD file — rather than retrying blindly or concluding the tool is broken.
