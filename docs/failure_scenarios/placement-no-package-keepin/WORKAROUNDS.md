# Workarounds: Allegro Auto-Placement 'No Package Keepin was found'

## Verified Workaround

Retry `run_allegro_placement` against a board that **already has a Package Keepin (keep-in) area defined**. The placement engine works correctly (confirmed live: real algorithm log with real weight/rotation parameters); the failure is purely the missing board-level keepin region. On a board that has a keepin defined, the same `placement.exe <board> <out>` invocation runs the genuine auto-place engine to completion.

Evidence: `sigrity_mcp/core/tool_status.py:571-572` — "a board-authoring precondition (the board needs a defined placement keep-in area), not a wrapper or licensing problem. Retry against a board that already has a Package Keepin defined."

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Retry against a board that has a Package Keepin defined | worked (per the tool note's explicit guidance) | `sigrity_mcp/core/tool_status.py:569-572` |
| 2 | Add flags `-a`/`-w`/`-p` (iterate/weight/print matrix) to satisfy the engine | didnt_work — these are real, valid options but do NOT supply the missing keepin region | `sigrity_mcp/domains/cad/allegro_placement_tools.py:81-90` |
| 3 | Route the call through the `allegro_batch` multiplexer instead of the standalone exe | didnt_work — not relevant here, and the multiplexer is broken for other sub-programs (`dbdoctor`); the standalone `placement.exe` is the correct, working entry point | `sigrity_mcp/domains/cad/allegro_placement_tools.py:7-10` |

## How to Define a Package Keepin (to satisfy the precondition)

The keepin is a board-content object, not a CLI flag — it must be authored into the board before placement runs:

1. In a SKILL/Allegro session, define the placement keep-in region for the board (e.g. via the board's keepin/polygon geometry on the appropriate layer class). The suite's SKILL geometry/shape authoring tools (`allegro_create_copper_shape` in `allegro_geometry_tools.py`, or a hand-written SKILL script drawing the keepin region) are the available automation surfaces for adding board geometry — but note there is **no dedicated `allegro_create_keepin`-style tool** currently wrapping the keepin authoring; a board that ships without a keepin needs that region added by the board owner (GUI or hand-authored SKILL) first.
2. Save the board (`allegro_save_design`) and re-run `run_allegro_placement` against the now-keepin-defined board.
3. Verify via the placement log: a successful run emits the real algorithm/weight/rotation trace **without** the `Error: No Package Keepin was found` line.

## Prevention

1. Before running `run_allegro_placement`, confirm the board has a placement keepin region defined (this is a board-authoring responsibility, not a tool invocation detail).
2. Do **not** treat `Error: No Package Keepin was found` as a wrapper/licensing defect — the engine and wrapper are confirmed live; the board is missing content. Do not retry the same keepin-less board with different flags.
3. In placement→route pipelines (`placement_routing_assistance_tools.py`), gate the auto-placement step on the keepin precondition so the pipeline fails fast with a clear diagnostic rather than after the algorithm has already started.
4. If a board legitimately cannot have a keepin (e.g. you only need NC drill routing), skip the auto-placement step and use `run_allegro_ncroute` directly.

## Remaining Gaps

- No in-suite tool currently wraps "author a package keepin region" headlessly — the precondition must be satisfied on the board before placement, via GUI or a hand-written SKILL script. The suite's generic shape authoring (`allegro_create_copper_shape`) creates etch/boundary copper shapes, not a placement keepin object, so it is **not** a drop-in keepin author.
- The confirmed-live test was against the specific sample board that **lacked** a keepin — the engine ran (real log) but hit the precondition. The positive path (placement completing on a keepin-defined board) is documented in the tool note as the correct remedy but has not been captured as a separate live-success artifact here.
- The multiplexer (`allegro_batch.exe placement`) is known broken for other sub-programs (`dbdoctor` → "Cannot find program") and is deliberately bypassed in favor of the standalone `placement.exe`; do not route placement through the multiplexer expecting a fix.
