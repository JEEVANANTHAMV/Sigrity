"""Tests for the new headless Cadence Allegro package/keepin tools:
- allegro_create_package_keepin (ROUTE KEEPIN/ALL filled shape)
- allegro_create_keepout         (ROUTE KEEPOUT/ALL unfilled shape)
- allegro_list_packages          (SKILL .il name-discovery via add_il)
- allegro_import_package         (PSMPATH/PADPATH/DEVPATH merge + N placements)

These verify the SKILL *emission* (the queued .scr lines / .il body), not a live
Allegro launch — the session mechanics are the same confirmed-live path the rest of
allegro_tools.py uses, and the new functions only ADD lines to it.
"""

import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad import allegro_geometry_tools as g
from sigrity_mcp.domains.cad.allegro_tools import _CONFIGURE_OPS, allegro_configure


def _new_session() -> str:
    return tcl_sessions.create("allegro").session_id


def _lines(session_id: str) -> list[str]:
    return list(tcl_sessions.get(session_id).script._lines)


@pytest.mark.asyncio
async def test_ops_registered_in_configure():
    for op in ("create_package_keepin", "create_keepout", "list_packages", "import_package"):
        assert op in _CONFIGURE_OPS, f"{op} not registered in _CONFIGURE_OPS"


@pytest.mark.asyncio
async def test_create_package_keepin_emits_filled_keepin_shape():
    sid = _new_session()
    # 2-point rect diagonal -> auto-expanded to 4 corners, auto-closed (5 points).
    await allegro_configure(sid, operations=[{"op": "create_package_keepin", "points": [[0, 0], [1000, 1500]]}])
    lines = _lines(sid)
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("skill ")
    # Filled keepin: l_r_fill must be `t`, layer `ROUTE KEEPIN/ALL`, net `nil`.
    assert 't "ROUTE KEEPIN/ALL" nil' in line
    assert "axlDBCreateShape" in line
    # 2-point input expanded to rectangle corners (0,0)(1000,0)(1000,1500)(0,1500) then closed.
    assert "(list 0 0)" in line
    assert "(list 1000 0)" in line
    assert "(list 1000 1500)" in line
    assert "(list 0 1500)" in line


@pytest.mark.asyncio
async def test_create_keepout_emits_filled_keepout_shape():
    # Regression guard: an UNFILLED "ROUTE KEEPOUT/ALL" shape is rejected live by this
    # Allegro 22.1 build with ERROR(SPMHDB-184): "Unfilled SHAPE may not exist on layer
    # 'ROUTE KEEPOUT/ALL'" -- axlDBCreateShape silently returns nil, no keepout is ever
    # created, and nothing shows up in a DRC/axlDBGetShapes readback either (confirmed
    # live 2026-10-20). Fixed to l_r_fill=t, matching allegro_create_package_keepin's
    # already-correct filled ROUTE KEEPIN/ALL. Independently re-confirmed live: a trace
    # crossing a filled keepout now raises a real "Line to Route Keepout Spacing" DRC
    # violation; one routed around it does not.
    sid = _new_session()
    await allegro_configure(sid, operations=[{"op": "create_keepout", "points": [[50, 50], [200, 200]]}])
    line = _lines(sid)[0]
    assert 't "ROUTE KEEPOUT/ALL" nil' in line
    assert "axlDBCreateShape" in line


@pytest.mark.asyncio
async def test_keepin_rejects_degenerate_input():
    sid = _new_session()
    with pytest.raises(ValueError):
        await allegro_configure(sid, operations=[{"op": "create_package_keepin", "points": [[5, 5]]}])
    with pytest.raises(ValueError):
        await allegro_configure(
            sid, operations=[{"op": "create_keepout", "points": [[5, 5], [5, 5], [5, 5]]}]
        )


@pytest.mark.asyncio
async def test_import_package_emits_path_merges_and_placement_calls():
    sid = _new_session()
    await allegro_configure(
        sid,
        operations=[
            {
                "op": "import_package",
                "package_dir": "C:/x/pkg",
                "placements": [
                    {"name": "U1", "module_def_name": "bga548c50p29x29", "x": 100, "y": 100, "rotation": 90},
                    {"name": "U2", "module_def_name": "bga548c50p29x29", "x": 300, "y": 100, "mirror": True},
                ],
            }
        ],
    )
    lines = _lines(sid)
    # 3 path merges (PSMPATH, PADPATH, DEVPATH) + 2 placement calls.
    assert len(lines) == 5
    assert "axlSetVariable 'PSMPATH" in lines[0]
    assert "axlSetVariable 'PADPATH" in lines[1]
    assert "axlSetVariable 'DEVPATH" in lines[2]
    assert 'axlDBCreateModuleInstance "U1" "bga548c50p29x29" (list 100 100) 90.0 0 nil nil' in lines[3]
    assert 'axlDBCreateModuleInstance "U2" "bga548c50p29x29" (list 300 100) 0.0 0 nil t' in lines[4]


@pytest.mark.asyncio
async def test_import_package_rejects_empty_and_bad_placement():
    sid = _new_session()
    with pytest.raises(ValueError):
        await allegro_configure(sid, operations=[{"op": "import_package", "package_dir": "C:/x", "placements": []}])
    sid2 = _new_session()
    with pytest.raises(ValueError):
        await allegro_configure(
            sid2,
            operations=[
                {"op": "import_package", "package_dir": "C:/x", "placements": [{"name": "U1", "x": 1, "y": 2}]}
            ],
        )


@pytest.mark.asyncio
async def test_list_packages_registers_il_defun():
    sid = _new_session()
    await g.allegro_list_packages(sid, "C:/x/pkg")
    sess = tcl_sessions.get(sid)
    assert "pkglist_report" in sess.il_func_names
    assert len(sess.il_lines) == 1
    body = sess.il_lines[0]
    # The .il must define the single-token function and emit the per-package report line
    # with the resolves/pins/bBox fields, writing to the absolute workdir .txt path.
    assert body.startswith("(defun pkglist_report ()")
    assert 'axlGetParam (strcat "library:" nm)' in body
    assert "resolve=" in body.replace("resolves=", "resolve=")
    assert "axlDBGetPackageDefinition nm nil" in body
    # The package dir is embedded (forward-slashed) as the axlDBGetPackageNames argument.
    assert 'axlDBGetPackageNames "C:/x/pkg"' in body
    # A PSMPATH append-if-needed line must also have been queued to the script
    # (axlSetVariable here uses the lowercase 'psmpath symbol form, matching the
    # axlGetVariableList 'psmpath read in the same expression).
    assert any("axlSetVariable 'psmpath" in ln for ln in _lines(sid))
