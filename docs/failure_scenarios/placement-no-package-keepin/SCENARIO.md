# Allegro Auto-Placement: 'No Package Keepin was found'

**Slug**: `placement-no-package-keepin`
**Tool(s) affected**: `run_allegro_placement` (`sigrity_mcp/domains/cad/allegro_placement_tools.py`, the `run_allegro_placement` tool)
**Status category**: `precondition_error`
**Pipeline stage**: placement / design

## Symptom

`run_allegro_placement` (the standalone auto-place engine, `placement.exe <board> <out>`) launches the genuine Allegro auto-place engine — the log shows a real algorithm trace with real weight/rotation parameters — but then fails on this specific sample board with:

```
Error: No Package Keepin was found
```

The job's failure is **not** a wrapper bug, not a licensing problem, and not a tool defect: the auto-place engine requires a defined placement keep-in (keep-out/keep-in) area on the board as a precondition, and the sample board did not have one. The tool and the engine were confirmed live to run (real algorithm log), they simply cannot produce a placement without the keepin region.

## Root Cause

A board-authoring precondition is unmet. Allegro's auto-placement algorithm confines component placement to a defined *package keepin* area (the region within which packages are allowed to be placed). When that region is absent from the board, the engine aborts with `Error: No Package Keepin was found` after it has already begun its calculation (hence the real weight/rotation algorithm log is emitted before the error). The wrapper correctly invokes `placement.exe` with the documented flags; the failure is entirely in the board content, not the invocation.

## Evidence

- `sigrity_mcp/core/tool_status.py:566-572` — `allegro_placement` note: "Confirmed live against a real .brd sample: `placement.exe <board> <out>` ran the genuine Allegro auto-place engine (real algorithm log with real weight/rotation parameters), but this specific sample board failed with 'Error: No Package Keepin was found' — a board-authoring precondition (the board needs a defined placement keep-in area), not a wrapper or licensing problem. Retry against a board that already has a Package Keepin defined."
- `sigrity_mcp/core/tool_status.py:51` — `"allegro_placement": "confirmed_live"` (the *execution path* is confirmed live even though this particular board's *result* is a precondition error).
- `sigrity_mcp/domains/cad/allegro_placement_tools.py:3-10` — module docstring: "Confirmed live on this machine: `allegro_batch.exe placement -help` prints a full usage banner headed 'Allegro auto-place program' — `placement [options] <input_design> [<output_design>]` with `-a` (iterate while improving), `-w` (weight edges), `-p` (print the connection matrix)." And: "`placement.exe` also exists as its own standalone executable in `tools/bin` ... so this tool calls it directly."
- `sigrity_mcp/domains/cad/allegro_placement_tools.py:71-92` — `run_allegro_placement` builds the real `-a`/`-w`/`-p` flags then passes `board_file` (and optional `output_file`) positionally, matching the documented `placement [options] <input_design> [<output_design>]` syntax.
- `sigrity_mcp/domains/cad/__init__.py:33-37` — "`allegro_placement_tools.py` — real auto-placement (`placement.exe`, confirmed via `allegro_batch placement -help`'s 'Allegro auto-place program' banner)."

## Pipeline Impact

Auto-placement is blocked for any board that has **no** package keepin defined. Since the failure occurs after the algorithm has already started (real log output) and is a board-content precondition, a pipeline step `run_allegro_placement` → (placement result) will fail for such boards with no in-tool recourse. Downstream steps that depend on an *auto-placed* board (e.g. SPECCTRA export + autoroute of the placed design, the full `placement_routing_assistance_tools.py` flow) inherit this: you cannot get an auto-placement on a keepin-less board, so the auto-place branch of any placement→route pipeline is unusable until the board has a keepin defined. The NC-drill-route step (`ncroute.exe`) and the rest of the pipeline are unaffected — only the auto-placement requirement itself is the precondition.
