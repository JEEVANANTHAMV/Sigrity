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

from sigrity_mcp.domains.cad.apd_package_tools import (
    run_allegro_apr,
    run_allegro_zrouter,
    run_apd_batch_script,
)


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
    result = await run_allegro_zrouter("board.brd", "control.txt", output_file="out.brd", x_grid=10.0)
    cmd = result["command"]
    assert "-s" in cmd
    assert "-nograph" in cmd
    assert cmd[-1] == "board.brd"


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
    result = await run_allegro_zrouter(
        "board.brd", "control.txt", x_grid=10.0, y_grid=10.0, min_space=5.0
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
