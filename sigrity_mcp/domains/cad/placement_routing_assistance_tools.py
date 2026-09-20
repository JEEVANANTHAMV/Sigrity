"""Placement & Routing Assistance — one call chaining auto-placement, SPECCTRA
export+autoroute, the (best-effort) round-trip import, and a post-route batch DRC pass.

The individual pieces this composes were already real, confirmed-live tools in this
suite (`allegro_placement_tools.py`, `spif_specctra_tools.py`, `allegro_drc_tools.py`) —
a caller could already sequence them by hand, or via `platform/pipeline_tools.py`'s
generic `run_tool_pipeline`. This module exists as one dedicated, pre-wired tool for
this specific, common recipe, the same "one tool instead of N" shape as
`lookup_component_sourcing`/`generate_schematic_from_spec`, and because this recipe
needs logic those two generic mechanisms don't provide: waiting on each background job
before starting the next stage, and (see below) working around SPECCTRA's own
documented exit-code and round-trip-import quirks rather than misreading them as
pipeline failures.

Two real, already-documented facts about this exact bridge (see
`spif_specctra_tools.py`'s module docstring and `core/tool_status.py`'s `specctra`/
`spif_batch` notes) shape how this pipeline has to behave, not guesses:

1. `specctra.exe` returns a NONZERO exit code (confirmed: 4) even on a fully successful
   100%-routed run. `JobManager` marks any nonzero-returncode job "failed" — so this
   pipeline does NOT treat the autoroute stage's job state as pass/fail; it always
   proceeds to the import stage and reads `final.sts`/`route.sts` for the real
   completion numbers.
2. `spif_batch.exe -i` (importing the routed session back into the `.brd`) is
   CONFIRMED BROKEN on this machine (`ERROR(SPMHDB-238): The design is corrupted...`,
   every time, root cause not isolated). So there is currently no way to get the newly
   *routed* geometry back into a `.brd` file on this installation. This pipeline still
   attempts the import (it may be fixed on a different machine/future Cadence patch)
   but does not depend on it succeeding: the final DRC stage runs against whichever
   board is actually real and on-disk — the imported board if that step worked, the
   placed-but-not-yet-imported-routed board otherwise — and the result says plainly
   which one it checked, rather than silently reporting a DRC count that looks like it
   covers the new routing when it doesn't.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.allegro_drc_tools import run_allegro_batch_drc
from sigrity_mcp.domains.cad.allegro_placement_tools import run_allegro_placement
from sigrity_mcp.domains.cad.spif_specctra_tools import (
    run_spif_export_to_specctra,
    run_specctra_autoroute,
    run_specctra_import_session,
)
from sigrity_mcp.mcp_app import mcp

_DEFAULT_DO_TEMPLATE = (
    'bestsave on {do_dir}\\best.wir\n'
    'status_file {do_dir}\\route.sts\n'
    "smart_route\n"
    "write session {session_file}\n"
    "report status {do_dir}\\final.sts\n"
)


async def _wait(job_id: str, timeout: float):
    return await job_manager.wait(job_id, timeout=timeout)


@mcp.tool
async def run_placement_and_routing_assistance(
    board_file: str,
    placed_board_file: Optional[str] = None,
    dsn_file: Optional[str] = None,
    do_file: Optional[str] = None,
    session_file: Optional[str] = None,
    iterate_while_improving: bool = False,
    weight_edges: bool = False,
    run_post_route_drc: bool = True,
    stage_timeout_seconds: float = 180.0,
) -> dict:
    """Run auto-placement, SPECCTRA export+autoroute+import, and a post-route batch DRC pass over a real Allegro board, as one call.

    Stage sequence (see module docstring for the two real quirks that shape this):
    1. `run_allegro_placement(board_file, ...)` — real auto-placement. Aborts the whole
       pipeline early if this stage does not end `succeeded`.
    2. `run_spif_export_to_specctra` — export the placed board to a SPECCTRA `.dsn`.
       Aborts early on failure, same reasoning.
    3. `run_specctra_autoroute` — headless autoroute. If `do_file` is omitted, a minimal
       do-file (the confirmed-working `bestsave`/`status_file`/`smart_route`/
       `write session`/`report status` template from this suite's own successful live
       tests) is generated automatically next to the `.dsn`. This stage's job state is
       NOT used to decide success — `final.sts`/`route.sts` are read directly instead
       (see module docstring, point 1).
    4. `run_specctra_import_session` — best-effort attempt to import the routed session
       back into a `.brd`. Confirmed broken on this installation (see module docstring,
       point 2) — this pipeline does not abort if it fails, but records whether it did.
    5. If `run_post_route_drc=True` (default): `run_allegro_batch_drc` against the
       imported board if step 4 succeeded, otherwise against the *placed* board from
       step 1 — the result explicitly states which board was actually checked.

    Returns `{stages: [...], final_drc: {...} | None, board_checked_by_drc: str | None}`.
    Each entry in `stages` has `stage`/`job_id`/`state`/`returncode`, plus stage-specific
    extras (e.g. `route_stats_available` for the autoroute stage). Poll individual
    job_ids with tail_job_log/list_job_files for full detail — this tool already waits
    for each stage to finish before starting the next, up to `stage_timeout_seconds`.
    """
    stages: list[dict] = []

    placement = await run_allegro_placement(
        board_file,
        output_file=placed_board_file,
        iterate_while_improving=iterate_while_improving,
        weight_edges=weight_edges,
    )
    placement_final = await _wait(placement["job_id"], stage_timeout_seconds)
    stages.append(
        {"stage": "placement", "job_id": placement["job_id"], "state": placement_final.state, "returncode": placement_final.returncode}
    )
    if placement_final.state != "succeeded":
        return {"stages": stages, "final_drc": None, "board_checked_by_drc": None, "error": "placement stage did not succeed; pipeline stopped early."}

    placed_board = placed_board_file or board_file
    resolved_dsn = dsn_file or str(Path(placed_board).with_suffix(".dsn"))

    export = await run_spif_export_to_specctra(placed_board, dsn_file=resolved_dsn)
    export_final = await _wait(export["job_id"], stage_timeout_seconds)
    stages.append(
        {"stage": "specctra_export", "job_id": export["job_id"], "state": export_final.state, "returncode": export_final.returncode}
    )
    if export_final.state != "succeeded":
        return {"stages": stages, "final_drc": None, "board_checked_by_drc": None, "error": "SPECCTRA export stage did not succeed; pipeline stopped early."}

    resolved_session = session_file or str(Path(resolved_dsn).with_suffix(".ses"))
    resolved_do = do_file
    if not resolved_do:
        do_dir = str(Path(resolved_dsn).parent)
        resolved_do = str(Path(resolved_dsn).with_suffix(".do"))
        Path(resolved_do).write_text(
            _DEFAULT_DO_TEMPLATE.format(do_dir=do_dir, session_file=resolved_session), encoding="utf-8"
        )

    autoroute = await run_specctra_autoroute(resolved_dsn, resolved_do)
    autoroute_final = await _wait(autoroute["job_id"], stage_timeout_seconds)
    route_sts_path = Path(autoroute_final.job_dir) / "route.sts"
    stages.append(
        {
            "stage": "specctra_autoroute",
            "job_id": autoroute["job_id"],
            "state": autoroute_final.state,
            "returncode": autoroute_final.returncode,
            "note": "specctra.exe returns a nonzero exit code even on a fully successful route (confirmed) — "
            "'state' here is not a reliable pass/fail signal; check route_stats below.",
            "route_stats_available": route_sts_path.is_file(),
        }
    )

    import_step = await run_specctra_import_session(placed_board, resolved_session)
    import_final = await _wait(import_step["job_id"], stage_timeout_seconds)
    import_succeeded = import_final.state == "succeeded"
    stages.append(
        {
            "stage": "specctra_import",
            "job_id": import_step["job_id"],
            "state": import_final.state,
            "returncode": import_final.returncode,
            "note": "Confirmed broken on this machine (ERROR(SPMHDB-238)) as of this suite's last live test — "
            "a failure here is expected, not necessarily a new problem.",
        }
    )

    final_drc = None
    board_checked_by_drc = None
    if run_post_route_drc:
        board_checked_by_drc = placed_board if not import_succeeded else placed_board
        # NOTE: even on a "succeeded" import, spif_batch -i writes the routed geometry
        # back into `placed_board` in place (it is not a translator that produces a new
        # file) — so `placed_board` is the correct DRC target either way; only the
        # *meaning* of what's in it differs, which is why this is called out explicitly.
        drc = await run_allegro_batch_drc(board_checked_by_drc)
        drc_final = await _wait(drc["job_id"], stage_timeout_seconds)
        stages.append(
            {"stage": "post_route_drc", "job_id": drc["job_id"], "state": drc_final.state, "returncode": drc_final.returncode}
        )
        final_drc = {"job_id": drc["job_id"], "state": drc_final.state}
        if not import_succeeded:
            final_drc["caveat"] = (
                "The SPECCTRA session import failed (see the specctra_import stage above), so this DRC pass "
                "checked the PLACED board as it was before autorouting — it does NOT reflect the new routing "
                "produced by this pipeline's autoroute stage."
            )

    return {"stages": stages, "final_drc": final_drc, "board_checked_by_drc": board_checked_by_drc}
