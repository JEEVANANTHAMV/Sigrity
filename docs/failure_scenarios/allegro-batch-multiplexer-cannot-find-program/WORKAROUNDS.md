# Workarounds: allegro_batch Multiplexer 'Cannot find program'

## Verified Workaround

**Call each underlying standalone `.exe` directly instead of routing through the `allegro_batch.exe` multiplexer.** This is the established, confirmed-working pattern across this suite: every batch utility is invoked as its own standalone executable, not as an `allegro_batch <program>` sub-program. Confirmed live end-to-end against real sample board files — e.g. `report.exe -v sum <board> <out>` and `dbdoctor.exe -check_only <board>` both succeed via the standalone exes, whereas `allegro_batch dbdoctor ...` fails with `Cannot find program` (exit 2).

Evidence:
- `sigrity_mcp/core/tool_status.py:529-530` — "Tools call each underlying standalone exe directly (allegro_report, allegro_dbdoctor, ...) instead of routing through this multiplexer."
- `sigrity_mcp/core/tool_status.py:531-533` — `allegro_report` note: "Confirmed genuinely headless, no dialog: `report.exe -v sum <real .brd sample> out.txt` produced a real, correct summary report end-to-end." and `:560-564` — `allegro_dbdoctor` note: "Confirmed genuinely headless, no dialog: `dbdoctor.exe -check_only <real .brd sample>` ran a real orphan-record check end-to-end."
- `sigrity_mcp/domains/cad/allegro_batch_tools.py:8-11` — "So these tools call each standalone exe directly (`report.exe`, `dbdoctor.exe`) instead of going through the multiplexer — confirmed working end-to-end against a real sample board file, not just from documentation."

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Call the standalone exe directly (`dbdoctor.exe`, `report.exe`, `placement.exe`, `ncroute.exe`, ...) | worked (this is the suite-wide pattern; every such tool is `confirmed_live` or stronger) | `sigrity_mcp/core/tool_status.py:529-530`; `sigrity_mcp/domains/cad/allegro_batch_tools.py:8-11` |
| 2 | Route through the multiplexer `allegro_batch <program> <args>` | didnt_work — `ERROR: Cannot find program "<program>"` (exit 2), even with a real `.brd` | `sigrity_mcp/core/tool_status.py:526-528` |
| 3 | Check `allegro_batch -help` / `allegro_batch <program> -help` to confirm the program is supported | misleading — help output is genuine and headless, but does NOT confirm dispatch works (the program can have working help yet still fail to resolve at dispatch) | `sigrity_mcp/core/tool_status.py:524-526` |

## The Suite's Standalone-Exe Mapping (use these, not `allegro_batch <prog>`)

| Sub-program (as `allegro_batch <prog>`) | Standalone exe to call directly | Suite tool |
|---|---|---|
| `report` | `report.exe -v <code> <board> [<out>]` | `run_allegro_report` (`allegro_batch_tools.py:33-51`) |
| `dbdoctor` | `dbdoctor.exe [-check_only\|-drc\|-shapes] ... <board>` | `run_allegro_dbdoctor` (`allegro_batch_tools.py:53-88`) |
| `placement` | `placement.exe [-a][-w][-p] <input> [<output>]` | `run_allegro_placement` (`allegro_placement_tools.py:71-92`) |
| ncroute | `ncroute.exe [-q][-v][-o <out>] <board>` | `run_allegro_ncroute` (`allegro_placement_tools.py:95-113`) |

(The `placement.exe` module explicitly notes it exists as a standalone exe precisely so the (broken) multiplexer dispatch can be bypassed: `allegro_placement_tools.py:7-10`.)

## Prevention

1. Form batch-utility invocations against the **standalone exe**, never against `allegro_batch <program>`, on this machine.
2. Do **not** conclude a sub-program is supported (or dispatchable) solely because `allegro_batch <prog> -help` prints — on this install the help path and the dispatch path are decoupled, and dispatch is broken.
3. If you encounter `ERROR: Cannot find program "<program>"` (exit 2) from any `allegro_batch` invocation, the fix is to switch to the standalone exe — not to retry the multiplexer, and not to treat it as a missing/typo'd flag.
4. Keep the project's "call the standalone exe directly, verify against real `-help`/doc text, never fabricate a flag" discipline (stated in `allegro_batch_tools.py:3-12` and `domains/cad/__init__.py:25-29`) — it is specifically what keeps pipelines out of the multiplexer trap.

## Remaining Gaps

- The root cause of why the multiplexer's dispatch cannot locate sub-programs (while their help works) is not isolated in the source — it is characterized as "unreliable"/broken for at least the `dbdoctor` dispatch on this machine, and treated as a product/environment issue rather than a wrapper bug. It is `known_blocked`, not something the suite has fixed.
- The confirmed failure is specifically `allegro_batch dbdoctor`. Other sub-program dispatches through the multiplexer are not each individually recorded as failing with `Cannot find program` — the suite simply never routes through the multiplexer at all, so the breadth of the dispatch failure across *all* sub-programs is not exhaustively characterized (the pattern and the safest workaround, however, are clear: use the standalone exes).
- There is no in-suite fix for the multiplexer itself; the only "workaround" is the project-wide architectural choice to bypass it.
