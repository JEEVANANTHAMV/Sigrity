"""Unit tests for the CONFIRMED-LIVE headless APD / Z-Router / APR tools
(`sigrity_mcp.domains.cad.apd_package_tools`).

These mirror the live command construction verified on this machine (see that module's
docstring for the evidence): the `apd -product <tier> -nograph -s <script> <design.mcm>`
base for APD batch + APR, and the `allegro -s <script> -nograph <board> <board>` launcher
for Z-Router. The live proofs (journal files, saved-design re-reads, via diffs) are
documented in the module docstring and in core.tool_status — these tests lock in the argv
and generated .scr content so a future refactor can't silently break the confirmed spellings.
"""

import pytest

from sigrity_mcp.domains.cad import apd_package_tools
from sigrity_mcp.domains.cad.apd_package_tools import (
    _find_zrouter_log,
    _fmt_grid_value,
    _parse_zrouter_log,
    _zrouter_result_note,
    run_allegro_apr,
    run_allegro_zrouter,
    run_apd_batch_script,
)


def _mk_inputs(tmp_path):
    """Create the board + control files run_allegro_zrouter pre-flight validates for.

    fake_exe chdirs to tmp_path, so the relative "board.brd"/"control.txt" the other
    tests pass by name must exist on disk here to reach the launch step at all.
    """
    board = tmp_path / "board.brd"
    board.write_bytes(b"\x00\x01board")
    ctrl = tmp_path / "control.txt"
    ctrl.write_text("U1 * BOTTOM 1\n", encoding="ascii")
    return board, ctrl


@pytest.mark.asyncio
async def test_run_apd_batch_script_argv(fake_exe):
    result = await run_apd_batch_script("design.mcm", skill_line="printf('x')", output_file="out.mcm")
    cmd = result["command"]
    # apd batch base: -product <tier> -nograph -s <script> <design>
    assert cmd[1] == "-product"
    assert cmd[2] == "Allegro_Adv_Packaging_Plus"
    assert "-nograph" in cmd
    assert cmd[-3] == "-s"
    assert cmd[-2].endswith("apd_batch.scr")
    assert cmd[-1] == "design.mcm"


@pytest.mark.asyncio
async def test_run_apd_batch_script_default_product_override(fake_exe):
    result = await run_apd_batch_script("design.mcm", product="Allegro_Packaging_Designer_XL_II")
    cmd = result["command"]
    assert cmd[2] == "Allegro_Packaging_Designer_XL_II"
    assert "-nograph" in cmd


@pytest.mark.asyncio
async def test_run_allegro_apr_argv_has_option_and_nograph(fake_exe):
    result = await run_allegro_apr("design.mcm", output_file="out.mcm")
    cmd = result["command"]
    # APR must select the product tier AND the APR option, and run -nograph.
    assert cmd[1] == "-product"
    assert cmd[2] == "Allegro_Adv_Packaging_Plus"
    assert "-option" in cmd
    # The APR option name is the display label from the Product Choices dialog
    # (doc/aprTut/chap1.html): "Advanced Package Router".
    opt_idx = cmd.index("-option")
    assert cmd[opt_idx + 1] == "Advanced Package Router"
    assert "-nograph" in cmd
    assert cmd[-1] == "design.mcm"


@pytest.mark.asyncio
async def test_run_allegro_zrouter_argv(fake_exe):
    import os
    from pathlib import Path

    board, ctrl = _mk_inputs(Path(os.getcwd()))
    result = await run_allegro_zrouter(
        str(board), str(ctrl), output_file="out.brd", x_grid=10.0,
        wait_for_completion=False,
    )
    cmd = result["command"]
    assert "-s" in cmd
    assert "-nograph" in cmd
    assert cmd[-1].replace("\\", "/").endswith("board.brd")


# ---------------------------------------------------------------------------
# Generated-script content checks: read the .scr the tool just wrote into the
# fake job dir and assert the confirmed-live FORM-replay lines are present with
# the CORRECT (internal, lowercase) field names.
# ---------------------------------------------------------------------------


def _read_written_script(result, fname: str) -> str:
    """Locate the .scr the tool wrote under the job dir (result["job_dir"])."""
    from pathlib import Path

    job_dir = Path(result["job_dir"])
    script = job_dir / fname
    assert script.is_file(), f"expected script {fname} under {job_dir}"
    return script.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_allegro_zrouter_script_uses_real_field_names_and_cancel(fake_exe):
    import os
    from pathlib import Path

    board, ctrl = _mk_inputs(Path(os.getcwd()))
    result = await run_allegro_zrouter(
        str(board), str(ctrl), x_grid=10.0, y_grid=10.0, min_space=5.0,
        wait_for_completion=False,
    )
    script = _read_written_script(result, "zrouter_run.scr")
    lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
    # The dialog is opened with the bare command, then driven by the form's INTERNAL
    # field names (filename/xgrid/ygrid/minspace) — NOT the old `grid` token and NOT the
    # display labels.
    assert "zrouter" in lines
    assert "setwindow form.zrouter" in lines
    assert any(ln.startswith("FORM zrouter filename") for ln in lines)
    assert "FORM zrouter xgrid 10.0" in lines or "FORM zrouter xgrid 10" in lines
    assert "FORM zrouter ygrid 10.0" in lines or "FORM zrouter ygrid 10" in lines
    assert "FORM zrouter minspace 5.0" in lines or "FORM zrouter minspace 5" in lines
    # The Run button is the MENUBUTTON field `execute` (display "Run") — `FORM zrouter Run`
    # is the broken spelling that fails in -nograph.
    assert "FORM zrouter execute" in lines
    # The close button is `cancel` (display "Close") and MUST precede the save so the
    # modeless dialog doesn't block axlSaveDesign with "Finish current command first".
    assert "FORM zrouter cancel" in lines
    cancel_i = lines.index("FORM zrouter cancel")
    save_i = next(i for i, ln in enumerate(lines) if "axlSaveDesign" in ln)
    assert cancel_i < save_i
    assert "quit" in lines


# ---------------------------------------------------------------------------
# THE GRID-REQUIRED / SILENT-NO-OP FIX (2026-10-20)
#
# Root cause (confirmed live): `FORM zrouter execute` silently no-ops — writes no
# zrouter.log, adds 0 vias, no error anywhere, job still reports succeeded — whenever
# the REALFILLIN fields (xgrid/ygrid/xoffset/yoffset/minspace) are not explicitly set
# before `execute`. A minimal `run_allegro_zrouter(board, control)` call (no grid args)
# reproduced the user's exact silent 0-via failure on pre_fanout.brd. These tests lock
# in: (1) the five REALFILLIN lines are ALWAYS emitted, even with no optional args;
# (2) inputs are validated and loudly rejected before a doomed launch; (3) the zrouter.log
# is found in the board's directory and parsed; (4) a missing/empty log is surfaced as
# an explicit silent_no_op, never a bare 'succeeded'.
# ---------------------------------------------------------------------------


def _read_lines(result, fname: str) -> list[str]:
    return [ln.strip() for ln in _read_written_script(result, fname).splitlines() if ln.strip()]


@pytest.mark.asyncio
async def test_zrouter_always_emits_grid_minspace_even_with_no_optional_args(fake_exe):
    """The minimal call — the user's exact failing scenario — MUST now emit all five
    REALFILLIN FORM lines with the documented defaults. Omitting them is what made
    `execute` silently no-op (0 vias, no zrouter.log)."""
    import os
    from pathlib import Path

    board, ctrl = _mk_inputs(Path(os.getcwd()))
    result = await run_allegro_zrouter(str(board), str(ctrl), wait_for_completion=False)
    lines = _read_lines(result, "zrouter_run.scr")
    # All five REALFILLIN fields must be present (never conditionally omitted):
    assert any(ln.startswith("FORM zrouter xgrid") for ln in lines), "xgrid missing"
    assert any(ln.startswith("FORM zrouter ygrid") for ln in lines), "ygrid missing"
    assert any(ln.startswith("FORM zrouter xoffset") for ln in lines), "xoffset missing"
    assert any(ln.startswith("FORM zrouter yoffset") for ln in lines), "yoffset missing"
    assert any(ln.startswith("FORM zrouter minspace") for ln in lines), "minspace missing"
    # Defaults applied (10/10/0/0 and minspace 3.0):
    assert "FORM zrouter xgrid 10" in lines
    assert "FORM zrouter ygrid 10" in lines
    assert "FORM zrouter xoffset 0" in lines
    assert "FORM zrouter yoffset 0" in lines
    assert "FORM zrouter minspace 3" in lines
    # Ordering: every field is set BEFORE the `execute` button is fired.
    exec_i = lines.index("FORM zrouter execute")
    for field in ("xgrid", "ygrid", "xoffset", "yoffset", "minspace", "filename"):
        field_line = next(ln for ln in lines if ln.startswith(f"FORM zrouter {field}"))
        assert lines.index(field_line) < exec_i, f"{field} must be set before execute"


@pytest.mark.asyncio
async def test_zrouter_minimal_call_no_silent_noop_default(fake_exe):
    """With no optional args, the run must still produce a zrouter.log-driven result
    (the fake Python 'allegro' won't really route, so the log is absent -> the tool must
    surface silent_no_op=True + an explanatory note, NOT a bare succeeded with vias None
    and no explanation)."""
    import os
    from pathlib import Path

    board, ctrl = _mk_inputs(Path(os.getcwd()))
    result = await run_allegro_zrouter(str(board), str(ctrl))
    assert result["state"] in ("succeeded", "failed", "cancelled", "timeout")
    assert "zrouter_result" in result
    rz = result["zrouter_result"]
    # No real Allegro -> no zrouter.log -> silent_no_op True AND log_found False.
    assert rz["log_found"] is False
    assert rz["silent_no_op"] is True
    assert "DID NOT actually run" in result["note"]


@pytest.mark.asyncio
async def test_zrouter_rejects_zero_grid_before_launch(fake_exe):
    """x_grid/y_grid <= 0 is rejected by the form (MESSAGE nogrid) — the tool must fail
    fast with a clear error instead of launching a doomed 5s no-op."""
    import os
    from pathlib import Path

    board, ctrl = _mk_inputs(Path(os.getcwd()))
    result = await run_allegro_zrouter(str(board), str(ctrl), x_grid=0.0, wait_for_completion=False)
    assert "not_launched" == result["state"]
    assert "error" in result
    assert "grid" in result["error"].lower()


@pytest.mark.asyncio
async def test_zrouter_rejects_missing_control_file(fake_exe):
    import os
    from pathlib import Path

    board, _ = _mk_inputs(Path(os.getcwd()))
    result = await run_allegro_zrouter(str(board), "does_not_exist.txt", wait_for_completion=False)
    assert "not_launched" == result["state"]
    assert "control_file not found" in result["error"]


@pytest.mark.asyncio
async def test_zrouter_rejects_missing_board(fake_exe):
    from pathlib import Path

    result = await run_allegro_zrouter(
        "no_such_board.brd", "control.txt", wait_for_completion=False
    )
    assert "not_launched" == result["state"]
    assert "board_file not found" in result["error"]


def test_parse_zrouter_log_success_15_vias(tmp_path):
    """A real successful zrouter.log (the 15-via pre_fanout.brd evidence) parses to
    vias_added=15, errors=0, silent_no_op=False."""
    log = tmp_path / "zrouter.log"
    log.write_text(
        "Allegro I/O Pin Router - revision 1.4\n"
        "Pins Connection File: C:/x/connections.txt\n"
        "Minimum Via to I/O Pad Edge Spacing: 3.000000\n"
        "Via Grid: (10.000000, 10.000000)\n"
        "Number of legal I/O Pin Connections found in the file: 1\n"
        "Number of errors found in the file: 0\n"
        "Processing net * on refdes U1\n"
        "number pins on component: 400\n"
        "number pins that match net restriction: 15\n"
        "number pins already connected: 0\n"
        "number pins with vias added: 15\n"
        "Normal program termination\n"
        "Total number of error messages: 0\n"
        "Total number of warning messages: 0\n",
        encoding="ascii",
    )
    rz = _parse_zrouter_log(log)
    assert rz["log_found"] is True
    assert rz["silent_no_op"] is False
    assert rz["vias_added"] == 15
    assert rz["errors"] == 0
    assert rz["warnings"] == 0
    assert rz["legal_connections"] == 1
    assert rz["file_errors"] == 0
    assert "added vias to 15" in _zrouter_result_note(rz)


def test_parse_zrouter_log_zero_via_minspace_too_high(tmp_path):
    """The minspace-too-high failure (0 vias, 15 per-pin 'Unable to connect' errors):
    log_found True, vias_added 0, silent_no_op False (it DID run), per_pin_failures
    captured, and the note tells the caller to lower min_space."""
    log = tmp_path / "zrouter.log"
    log.write_text(
        "Number of legal I/O Pin Connections found in the file: 1\n"
        "Number of errors found in the file: 0\n"
        "Processing net * on refdes U1\n"
        "number pins on component: 400\n"
        "number pins that match net restriction: 15\n"
        "number pins already connected: 0\n"
        "*ERROR: Unable to connect any vias to pin U1.A4\n"
        "*ERROR: Unable to connect any vias to pin U1.A9\n"
        "number pins with vias added: 0\n"
        "Total number of error messages: 15\n"
        "Total number of warning messages: 0\n",
        encoding="ascii",
    )
    rz = _parse_zrouter_log(log)
    assert rz["log_found"] is True
    assert rz["silent_no_op"] is False
    assert rz["vias_added"] == 0
    assert rz["errors"] == 15
    assert len(rz["per_pin_failures"]) == 2
    # The note must steer the caller to lower min_space (the real root cause).
    assert "min_space" in _zrouter_result_note(rz).lower()


def test_parse_zrouter_log_missing_is_silent_noop(tmp_path):
    """No zrouter.log at all (the user's exact reported signature: execute fired, zero
    output, nothing) => log_found False, silent_no_op True, explanatory note."""
    rz = _parse_zrouter_log(_find_zrouter_log(str(tmp_path / "board.brd")))
    assert rz["log_found"] is False
    assert rz["silent_no_op"] is True
    assert "DID NOT actually run" in _zrouter_result_note(rz)


def test_find_zrouter_log_lands_in_board_dir_case_insensitive(tmp_path):
    """_find_zrouter_log must locate Allegro's real (lowercase) zrouter.log in the
    board's directory, matching case-insensitively regardless of the spelling probed."""
    board = tmp_path / "board.brd"
    board.write_bytes(b"x")
    for name, expected in (
        ("zrouter.log", True),
        ("Zrouter.log", True),  # Windows: FS is case-insensitive, both hit the same file
    ):
        log = tmp_path / name
        log.write_text("number pins with vias added: 15\n", encoding="ascii")
        assert _find_zrouter_log(str(board)) is not None, name
        log.unlink()


def test_fmt_grid_value_styles():
    assert _fmt_grid_value(10.0) == "10"
    assert _fmt_grid_value(10) == "10"
    assert _fmt_grid_value(3.0) == "3"
    assert _fmt_grid_value(0.0) == "0"
    assert _fmt_grid_value(0.5) == "0.5"
    assert _fmt_grid_value(3.25) == "3.25"


@pytest.mark.asyncio
async def test_run_allegro_apr_script_fire_route_button(fake_exe):
    result = await run_allegro_apr("design.mcm")
    script = _read_written_script(result, "apr_run.scr")
    lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
    # The APR dialog is opened by its menu callback `pkg_router`, then routing is started
    # by firing the Route MENUBUTTON's internal field name `route` (display "Route").
    assert "pkg_router" in lines
    assert "setwindow form.icp_pkg_router" in lines
    assert "FORM icp_pkg_router route" in lines
    # The modeless dialog is closed with `cancel` before the save.
    cancel_i = next(i for i, ln in enumerate(lines) if ln == "FORM icp_pkg_router cancel")
    save_i = next(i for i, ln in enumerate(lines) if "axlSaveDesign" in ln)
    assert cancel_i < save_i
    assert "quit" in lines
    # The run button fires AFTER all config fields are set.
    route_i = lines.index("FORM icp_pkg_router route")
    for field in ("routing_goal", "routing_priority", "detour_type", "via_method", "net_filter"):
        assert any(ln.startswith(f"FORM icp_pkg_router {field}") for ln in lines), field
        assert lines.index(next(ln for ln in lines if ln.startswith(f"FORM icp_pkg_router {field}"))) < route_i


@pytest.mark.asyncio
async def test_run_apd_batch_script_script_has_skill_and_save(fake_exe):
    result = await run_apd_batch_script("design.mcm", skill_line="printf('ok','X')")
    script = _read_written_script(result, "apd_batch.scr")
    lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
    assert "setwindow pcb" in lines
    assert any(ln.startswith("skill ") for ln in lines)
    assert next(ln for ln in lines if "axlSaveDesign" in ln).endswith("?mode \"nocheck\")") or "axlSaveDesign" in next(ln for ln in lines if "axlSaveDesign" in ln)
    assert "quit" in lines


@pytest.mark.asyncio
async def test_run_allegro_apr_script_enum_uses_display_names(fake_exe):
    """The FORM command for icp_pkg_router enum fields requires the POPUP *display name*
    (first string in the POP line of icp_pkg_router.form), not the token code. The token
    codes (COMPLETE, COMPLETION, RATIO, SPIRAL, ALL) are all rejected in -nograph mode with
    "Value for field is not legal". This test locks in the confirmed display-name spellings."""
    result = await run_allegro_apr(
        "design.mcm",
        routing_goal="COMPLETE",
        routing_priority="COMPLETION",
        detour_type="RATIO",
        via_method="SPIRAL",
        net_filter="ALL",
    )
    script = _read_written_script(result, "apr_run.scr")
    lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
    # Display names (from icp_pkg_router.form POP lines) — NOT token codes.
    assert "FORM icp_pkg_router routing_goal 100% Completion" in lines
    assert "FORM icp_pkg_router routing_priority Maximize for completion" in lines
    assert "FORM icp_pkg_router detour_type Ratio" in lines
    assert "FORM icp_pkg_router via_method Spiral" in lines
    assert "FORM icp_pkg_router net_filter All nets" in lines
    # Token codes must NOT appear as enum values.
    assert not any("FORM icp_pkg_router routing_goal COMPLETE" == ln for ln in lines)
    assert not any("FORM icp_pkg_router via_method SPIRAL" == ln for ln in lines)


@pytest.mark.asyncio
async def test_run_allegro_apr_script_enum_alternate_values(fake_exe):
    """Non-default enum tokens map to their corresponding display names."""
    result = await run_allegro_apr(
        "design.mcm",
        routing_goal="ESTIMATE",
        detour_type="LENGTH",
        via_method="STAGGER",
        net_filter="SIGNALS",
    )
    script = _read_written_script(result, "apr_run.scr")
    lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
    assert "FORM icp_pkg_router routing_goal Estimate Only" in lines
    assert "FORM icp_pkg_router detour_type Length" in lines
    assert "FORM icp_pkg_router via_method Stagger" in lines
    assert "FORM icp_pkg_router net_filter Signal nets" in lines
