# Pipeline / Tool Argument-Name Traps → Silent ~20-Minute Hang

**Slug**: `pipeline-argument-name-traps-silent-hang`
**Tool(s) affected**: any tool where the caller passes a **plausible-but-wrong argument name**; surfaced most dangerously inside `run_tool_pipeline` (where the failure is recorded as a raised step / hang rather than failing fast). Specific verified traps: file tools `copy_file/move_file/delete_file`, PowerSI edge-port tools, frequency-sweep setters, Celsius/Clarity3D `*_run_session`.
**Status category**: `known_blocked` (per manifest row 99)
**Pipeline stage**: platform (all tools; the silent-hang consequence is most severe inside a pipeline because nothing else is driving the flow)

## Symptom

Passing an argument under the **wrong name** (e.g. `source` instead of `source_file`, `positive_net` instead of `positive_node`, `"1MHz"` instead of `"1e6"`) does **not** uniformly fail fast. There are two behaviors, and the worse one is: a **~20-minute silent hang with no clean error**. The pipeline (or the single call) appears to run, the launched Cadence process reaches an interactive prompt waiting for input that will never come (or the wrong arg causes the process to wait), and **nothing is reported** except that the job never finishes.

Two sub-behaviors, both real and documented in the SKILL.md "Argument-name traps" section:

1. **Fast failure** — the tool call **raises `missing_argument`** (a raised step in a pipeline; recorded with `error` and no `result`). This is the "clean" failure; you see it immediately.
2. **Silent hang (~20 min)** — a *plausibly-named but wrong* argument is not caught as missing, the session/macro is written with the wrong line, the batch process launches and **blocks on an interactive prompt** (or a dialog with no console output), and the job never terminates. In a pipeline, the containing `run_tool_pipeline` call then blocks until the MCP client's own timeout — or hangs the whole orchestration.

The reason this is a **trap** rather than a typo: the *correct* names are non-obvious and inconsistent across tools (file tools use `source_file`/`destination_file`, PowerSI edge ports use `positive_node`/`negative_node`, frequency takes plain-Hz strings). Guessing the "obvious" name is the failure mode.

## Root Cause

Two things combine:

1. **Strict but non-self-descriptive arg names.** Tools validate required args strictly, so a missing required arg raises `missing_argument` — but when the caller supplies the *wrong-named* optional/derived arg, the required ones are satisfied and the *wrong* arg is silently ignored (or passed through to the generated Tcl/SKILL line where it becomes a no-op / malformed command). The tool does not echo "did you mean X?" for plausible names.
2. **Batch processes block on interactive input with zero console output** when the generated script is malformed or incomplete (the same "dialog with no console output" class the suite documents elsewhere — e.g. the stale `.lck` override dialog, README:724-734). A wrong arg that leaves a step's command underspecified can land the process in exactly that state: running, not progressing, no log bytes — which the stall watchdog only kills after the long default timeout, hence "~20 min".

## Evidence

- `.forjinn/skills/sigrity/SKILL.md:97-104` (the "Argument-name traps" section, verbatim): "All tool args are strict; passing a plausible-but-wrong name either raises `missing_argument` or, worse, hangs ~20 min. The traps verified live: file tools are `source_file`/`destination_file` (and `file_path` for delete) — NOT `source`/`destination`; PowerSI edge port is `positive_node`/`negative_node` (NOT `positive_net`); frequency sweeps take `start`/`end` as PLAIN Hz strings (`'1e6'`, NOT `'1MHz'`); Celsius/Clarity3D `*_run_session` require the project/design path AGAIN as a second arg."
- `sigrity_mcp/domains/platform/file_tools.py:22,37,54` — the *correct* file-tool arg names: `copy_file(source_file, destination_file, overwrite)`, `move_file(source_file, destination_file, overwrite)`, `delete_file(file_path)`. The "traps" (`source`/`destination`) are simply not these; passing them leaves the real required arg missing (`missing_argument`) or, for an optional-shaped arg, silently ignored.
- `sigrity_mcp/domains/platform/pipeline_tools.py:66-75` — inside a pipeline, a raised step (e.g. `missing_argument`) is recorded with `error` only; combined with `stop_on_error=True` it HALTS. The *silent-hang* variant instead blocks the `client.call_tool` (line 67) until the MCP client round-trip cap, with no step-level signal.
- `.forjinn/skills/sigrity/SKILL.md:33-40` (rule 1, second paragraph) — the companion "MCP client's flat 30-second cap" that fires even when the *tool* is still legitimately working; the silent ~20-min hang is what makes that cap the only thing that eventually surfaces it.
- `.forjinn/skills/sigrity/SKILL.md:102-104` — the "FIXED — list/dict arguments sent as JSON strings now work" note immediately following the traps, confirming the traps section is the canonical verified record of the *string/arg-name* class.

## Pipeline Impact

A single wrong arg name in a `run_tool_pipeline` step can turn a 6-step flow into a **multi-minute to ~20-minute silent stall** with no per-step error (the hang path), or into a hard halt at the raised step (the `missing_argument` path). Because the pipeline is meant to be "fire the whole known sequence in one call" (SKILL.md:94), a silent hang here burns the entire budget of the call and the MCP client's timeout before any signal arrives. This is the #1 reason the SKILL.md playbook says to **source the exact arg names from the SKILL.md / tool docstring, not by guessing**.