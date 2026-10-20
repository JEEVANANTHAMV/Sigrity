"""Tests for allegro_constraint_tools.py's .il-routed Constraint Manager automation.

Every compose function here queues a multi-arg axlCNS* call via `tcl_sessions.add_il`
(BUG #2 fix: Allegro 22.1's `-s` command-replay parser corrupts any `skill <expr>` line
with more than one top-level token, so these calls can no longer be asserted as a raw
line in `preview_tcl_session`/`tcl_sessions.preview` -- that only renders `session.script`,
which stays empty until `allegro_run_session` emits the `skill (load ...)` +
`skill (<func>)` pair). So these tests inspect `tcl_sessions.get(sid).il_lines`/
`il_func_names` directly for the composed defun source, and a dedicated end-to-end group
verifies `allegro_run_session` actually writes `auto_il.il` and the correct load+call
sequence into the real `.scr` file on disk.
"""

from pathlib import Path

import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.allegro_constraint_tools import (
    allegro_create_ecset,
    allegro_delete_ecset,
    allegro_design_value_set,
    allegro_get_electrical_constraint,
    allegro_get_net_constraint,
    allegro_list_ecsets,
    allegro_set_electrical_check_mode,
    allegro_set_electrical_constraint,
    allegro_set_physical_constraint,
    allegro_set_spacing_constraint,
)
from sigrity_mcp.domains.cad.allegro_tools import allegro_run_session, start_allegro_session
from sigrity_mcp.domains.platform.session_tools import close_tcl_session


def _last_il_call(session_id: str) -> str:
    """Return the most recently queued `.il` defun source for this session."""
    return tcl_sessions.get(session_id).il_lines[-1]


@pytest.mark.asyncio
async def test_set_spacing_constraint_default_cset_and_layer():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_spacing_constraint(sid, "line_line", 5)
    assert "(axlCNSSetSpacing nil nil 'line_line 5)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_spacing_constraint_explicit_cset_and_layer_and_string_value():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_spacing_constraint(sid, "line_shape", "5mil", cset="", layer="TOP")
    assert '(axlCNSSetSpacing "" "TOP" \'line_shape "5mil")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_spacing_constraint_named_cset():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_spacing_constraint(sid, "shape_shape", 12, cset="MY_CSET")
    assert '(axlCNSSetSpacing "MY_CSET" nil \'shape_shape 12)' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_physical_constraint_boolean_true():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_physical_constraint(sid, "allow_etch", True, cset="")
    assert "(axlCNSSetPhysical \"\" nil 'allow_etch t)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_physical_constraint_boolean_false_renders_nil():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_physical_constraint(sid, "allow_etch", False)
    assert "'allow_etch nil)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_physical_constraint_diff_pair_gap():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_physical_constraint(sid, "dp_primary_gap", 4)
    assert "'dp_primary_gap 4)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_physical_constraint_enumerated_symbol_value():
    # allow_ts/allow_padconnect take a SYMBOL value ('PINS_ONLY etc), not a bare string.
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_physical_constraint(sid, "allow_ts", "PINS_ONLY")
    assert "'allow_ts 'PINS_ONLY)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_ecset_minimal():
    sid = (await start_allegro_session())["session_id"]
    await allegro_create_ecset(sid, "USB_DIFFPAIR")
    assert '(axlCNSEcsetCreate "USB_DIFFPAIR")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_create_ecset_copy_from():
    sid = (await start_allegro_session())["session_id"]
    await allegro_create_ecset(sid, "NEW_SET", copy_from="OLD_SET")
    assert '(axlCNSEcsetCreate "NEW_SET" "OLD_SET")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_delete_ecset():
    sid = (await start_allegro_session())["session_id"]
    await allegro_delete_ecset(sid, "OLD_SET")
    assert '(axlCNSEcsetDelete "OLD_SET")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_electrical_constraint_impedance():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_electrical_constraint(sid, "DP_SET", "Impedance", "ALL:ALL:50:1:1500:4.4:0")
    assert '(axlCNSEcsetValueSet "DP_SET" \'Impedance "ALL:ALL:50:1:1500:4.4:0")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_electrical_constraint_diff_pair_impedance():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_electrical_constraint(sid, "DP_SET", "Diff_Pair_Impedance", "ALL:ALL:100:3:1500:4.4:0")
    assert "'Diff_Pair_Impedance \"ALL:ALL:100:3:1500:4.4:0\")" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_electrical_constraint_numeric_value():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_electrical_constraint(sid, "DP_SET", "Maximum_Via_Count", 12)
    assert "'Maximum_Via_Count 12)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_electrical_constraint_single_check():
    sid = (await start_allegro_session())["session_id"]
    await allegro_get_electrical_constraint(sid, "DP_SET", "Impedance")
    assert '(axlCNSEcsetValueGet "DP_SET" \'Impedance)' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_electrical_constraint_all():
    sid = (await start_allegro_session())["session_id"]
    await allegro_get_electrical_constraint(sid, "DP_SET", "all")
    assert '(axlCNSEcsetValueGet "DP_SET" \'all)' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_set_electrical_check_mode():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_electrical_check_mode(sid, "Impedance", "batch")
    assert "(axlCNSEcsetModeSet 'Impedance 'batch)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_net_constraint_property_name_stays_quoted_string():
    sid = (await start_allegro_session())["session_id"]
    await allegro_get_net_constraint(sid, "NET1", "IMPEDANCE_RULE")
    assert '(axlCnsNetFlattened "NET1" "IMPEDANCE_RULE")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_get_net_constraint_drc_check_symbol_renders_as_symbol():
    sid = (await start_allegro_session())["session_id"]
    await allegro_get_net_constraint(sid, "NET1", "Impedance")
    assert "(axlCnsNetFlattened \"NET1\" 'Impedance)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_list_ecsets_default_domain():
    sid = (await start_allegro_session())["session_id"]
    await allegro_list_ecsets(sid)
    assert '(axlCnsList "electrical")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_list_ecsets_explicit_domain():
    sid = (await start_allegro_session())["session_id"]
    await allegro_list_ecsets(sid, domain="spacing")
    assert '(axlCnsList "spacing")' in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_design_value_set():
    sid = (await start_allegro_session())["session_id"]
    await allegro_design_value_set(sid, "Minimum_Bonding_Wire_Length", 2.5)
    assert "(axlCNSDesignValueSet 'Minimum_Bonding_Wire_Length 2.5)" in _last_il_call(sid)
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_each_call_gets_its_own_unique_readback_capture_file():
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_spacing_constraint(sid, "line_line", 5)
    await allegro_set_spacing_constraint(sid, "line_shape", 7)
    session = tcl_sessions.get(sid)
    assert len(session.il_lines) == 2
    assert session.il_func_names[0] != session.il_func_names[1]
    tag0 = session.il_func_names[0].removeprefix("_cns_")
    tag1 = session.il_func_names[1].removeprefix("_cns_")
    assert f'cns_{tag0}.txt' in session.il_lines[0]
    assert f'cns_{tag1}.txt' in session.il_lines[1]
    assert f'cns_{tag0}.txt' not in session.il_lines[1]
    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_writes_auto_il_file_and_load_call_sequence(tmp_path, fake_exe):
    sid = (await start_allegro_session())["session_id"]
    await allegro_set_spacing_constraint(sid, "line_line", 5)
    await allegro_create_ecset(sid, "DP_SET")

    session = tcl_sessions.get(sid)
    expected_bodies = list(session.il_lines)
    expected_func_names = list(session.il_func_names)

    result = await allegro_run_session(sid, board_file="board.brd")

    il_path = tmp_path / "auto_il.il"
    assert il_path.is_file()
    il_content = il_path.read_text(encoding="utf-8")
    for body in expected_bodies:
        assert body in il_content

    scr_content = Path(result["command"][2]).read_text(encoding="utf-8")
    # The .il path in the emitted `load` call is relative to board_file's own directory
    # (the design-dir-relative convention `load`/`outfile` use), not an absolute tmp_path
    # string -- here board_file="board.brd" has no parent component, so it's bare.
    load_line_index = scr_content.find('skill (load "auto_il.il")')
    assert load_line_index != -1, scr_content
    # Each queued defun is called by its own single-token name, in queue order, AFTER
    # the load line -- this is the whole point of the BUG #2 fix (a bare .scr line can
    # only ever carry one top-level token).
    last_index = load_line_index
    for func_name in expected_func_names:
        call_index = scr_content.find(f"skill ({func_name})")
        assert call_index > last_index, f"{func_name} call missing or out of order"
        last_index = call_index

    assert "note" in result
    assert "auto_il.il" in result["note"]
    assert "cns_" in result["note"]


@pytest.mark.asyncio
async def test_run_session_omits_il_machinery_when_no_constraint_calls_queued(tmp_path, fake_exe):
    from sigrity_mcp.domains.cad.allegro_tools import allegro_create_net

    sid = (await start_allegro_session())["session_id"]
    await allegro_create_net(sid, "GND")

    result = await allegro_run_session(sid, board_file="board.brd")

    assert not (tmp_path / "auto_il.il").exists()
    assert "note" not in result


@pytest.mark.asyncio
async def test_configure_dispatcher_routes_all_six_new_ops():
    from sigrity_mcp.domains.cad.allegro_tools import allegro_configure

    sid = (await start_allegro_session())["session_id"]
    await allegro_configure(sid, operations=[
        {"op": "create_ecset", "name": "DP_SET"},
        {"op": "set_electrical_constraint", "ecset": "DP_SET", "check": "Impedance", "value": "ALL:ALL:50:1:1500:4.4:0"},
        {"op": "get_electrical_constraint", "ecset": "DP_SET", "check": "Impedance"},
        {"op": "set_electrical_check_mode", "check": "Impedance", "mode": "on"},
        {"op": "list_ecsets"},
        {"op": "design_value_set", "check": "Minimum_Bonding_Wire_Length", "value": 2.5},
        {"op": "delete_ecset", "name": "DP_SET"},
    ])
    session = tcl_sessions.get(sid)
    assert len(session.il_lines) == 7
    await close_tcl_session(sid)
