# allegro_batch Multiplexer: 'Cannot find program'

**Slug**: `allegro-batch-multiplexer-cannot-find-program`
**Tool(s) affected**: `allegro_batch` (the `allegro_batch.exe` multiplexer, `known_blocked` in the status registry); the standalone `dbdoctor.exe` path as the contrast that works
**Status category**: `known_blocked`
**Pipeline stage**: design / DRC / batch utilities (any batch utility Cadence docs list as an `allegro_batch <program>` sub-program)

## Symptom

The `allegro_batch.exe <program> <args>` "central batch utility" multiplexer — which Cadence's own docs describe as the way to invoke batch sub-programs like `report`, `dbdoctor`, `placement`, etc. — **cannot actually find/dispatch its sub-programs**. The concrete, confirmed failure:

```
allegro_batch dbdoctor -check_only <real .brd>
  -> ERROR: Cannot find program "dbdoctor"   (exit 2)
```

while the **identical** operation via the standalone `dbdoctor.exe` succeeded. Tellingly, the multiplexer's own `-help` and `<program> -help` output is genuine and correct (truly headless, no dialog) — so the tool *looks* like it works (it prints help) but fails at the actual dispatch step.

## Root Cause

The multiplexer's help/dispatch is split in two: its help generation works, but its sub-program resolution (locating the executable it should actually run for `<program>`) does not, on this machine. So an invocation that a user would form from `allegro_batch.dbdoctor` help (or from Cadence's docs, which present these tools as `allegro_batch <program>` sub-programs) fails at the "find the program" step with `ERROR: Cannot find program "<program>"` (exit 2), even though the same sub-program runs fine as its own standalone `.exe`. This is a genuine product/environment blocker in the multiplexer's dispatch — not a bug in this suite's wrapper, which deliberately avoids the multiplexer entirely.

The suite's project-level discipline (stated in several module docstrings) is to **call each standalone exe directly** (`report.exe`, `dbdoctor.exe`, `placement.exe`, ...) rather than routing through the multiplexer — which is why the wrapper tools work end-to-end even though the multiplexer itself is broken.

## Evidence

- `sigrity_mcp/core/tool_status.py:524-530` — `allegro_batch` note: "The multiplexer's own -help and '<program> -help' output is fine (genuinely headless, no dialog), but actually dispatching a sub-program through it is unreliable: `allegro_batch dbdoctor -check_only <real .brd>` failed immediately with 'ERROR: Cannot find program \"dbdoctor\"' (exit 2), while the identical operation via the standalone `dbdoctor.exe` succeeded. Tools call each underlying standalone exe directly (allegro_report, allegro_dbdoctor, ...) instead of routing through this multiplexer."
- `sigrity_mcp/core/tool_status.py:44` — `"allegro_batch": "known_blocked"` in the `TOOL_STATUS` registry.
- `sigrity_mcp/domains/cad/allegro_batch_tools.py:3-12` — module docstring: "Cadence's own docs describe these as sub-programs of a 'central batch utility' multiplexer, `allegro_batch.exe <program> <args>`. That multiplexer's own `-help` and `<program> -help` output is genuine and correct, but actually dispatching a sub-program through it is unreliable: routing `dbdoctor` through it failed outright ('ERROR: Cannot find program \"dbdoctor\"', exit 2) on this machine, while calling the identical standalone `dbdoctor.exe` directly succeeded. So these tools call each standalone exe directly (`report.exe`, `dbdoctor.exe`) instead of going through the multiplexer — confirmed working end-to-end against a real sample board file, not just from documentation."
- `sigrity_mcp/domains/cad/allegro_batch_tools.py:33-51` — `run_allegro_report` builds the real `report.exe` argv (`-v <code>`, board, optional output) and submits the standalone tool `allegro_report` directly, never via the multiplexer.
- `sigrity_mcp/domains/cad/allegro_batch_tools.py:53-88` — `run_allegro_dbdoctor` builds the real `dbdoctor.exe` argv and submits the standalone tool `allegro_dbdoctor` directly, never via the multiplexer.

## Pipeline Impact

Any pipeline step that forms its command as `allegro_batch <program> <args>` (matching Cadence's own documentation framing of these as multiplexer sub-programs) will fail at dispatch with `ERROR: Cannot find program "<program>"` (exit 2), even though the help for that exact program prints fine. This is a trap specifically because the tool *appears* to work (help output is genuine and headless) — a caller who only checks `-help` will assume dispatch works. The practical impact: the suite's entire batch-utility pipeline (report, dbdoctor, placement, ncroute, zrouter, etc.) is only viable through the **standalone exes**, not through the multiplexer. Anything outside this suite that still routes through `allegro_batch.exe` on this machine is blocked until it switches to direct standalone-exe invocation.
