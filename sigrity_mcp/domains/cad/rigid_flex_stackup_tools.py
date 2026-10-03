"""18-Layer Rigid-Flex Stackup and High-Speed Interface Constraint Presets.

Aligned with FORJINN Discovery Form Section 1.2 & Section 4.2:
- 18-Layer Multilayer Rigid, Flex, and Rigid-Flex Stackup Generator.
- High-Speed Bus Constraint Presets:
  * DDR4 / DDR5 (single-ended 40/50Ω, diff 80/100Ω, skew < 5ps / 0.75mm)
  * PCIe Gen4 / Gen5 (diff 85Ω, length match < 0.127mm, max uncoupled < 2.5mm)
  * USB4 / USB 3.2 Gen 2 (diff 90Ω, intra-pair skew < 0.15mm)
  * MIPI D-PHY / C-PHY (diff 100Ω, clock-to-data skew < 1.0mm)
  * 1000BASE-T Ethernet (diff 100Ω, pair-to-pair match < 10mm)
"""

from __future__ import annotations

import os
from typing import Any, Literal, Optional

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.allegro_tools import _make_axlxsection, _skill_line, _xsection_position_arg
from sigrity_mcp.mcp_app import mcp


HIGH_SPEED_INTERFACE_PRESETS: dict[str, dict[str, Any]] = {
    "DDR4": {
        "single_ended_impedance_ohms": 50.0,
        "diff_impedance_ohms": 100.0,
        "impedance_tolerance_percent": 10.0,
        "intra_pair_length_match_mils": 5.0,
        "data_to_dqs_length_match_mils": 10.0,
        "addr_ctrl_to_clk_length_match_mils": 25.0,
        "min_spacing_mils": 6.0,
        "diff_spacing_mils": 6.0,
        "diff_trace_width_mils": 4.5,
    },
    "DDR5": {
        "single_ended_impedance_ohms": 40.0,
        "diff_impedance_ohms": 80.0,
        "impedance_tolerance_percent": 8.0,
        "intra_pair_length_match_mils": 2.0,
        "data_to_dqs_length_match_mils": 5.0,
        "addr_ctrl_to_clk_length_match_mils": 15.0,
        "min_spacing_mils": 5.0,
        "diff_spacing_mils": 5.0,
        "diff_trace_width_mils": 4.0,
    },
    "PCIE_GEN4": {
        "diff_impedance_ohms": 85.0,
        "impedance_tolerance_percent": 10.0,
        "intra_pair_length_match_mils": 5.0,
        "inter_pair_length_match_mils": 500.0,
        "max_uncoupled_length_mils": 100.0,
        "diff_trace_width_mils": 5.0,
        "diff_spacing_mils": 7.0,
        "min_isolation_spacing_mils": 20.0,
    },
    "PCIE_GEN5": {
        "diff_impedance_ohms": 85.0,
        "impedance_tolerance_percent": 8.0,
        "intra_pair_length_match_mils": 2.0,
        "inter_pair_length_match_mils": 250.0,
        "max_uncoupled_length_mils": 60.0,
        "diff_trace_width_mils": 5.0,
        "diff_spacing_mils": 7.0,
        "min_isolation_spacing_mils": 25.0,
    },
    "USB4": {
        "diff_impedance_ohms": 90.0,
        "impedance_tolerance_percent": 10.0,
        "intra_pair_length_match_mils": 4.0,
        "diff_trace_width_mils": 4.5,
        "diff_spacing_mils": 6.0,
        "min_isolation_spacing_mils": 15.0,
    },
    "MIPI_DPHY": {
        "diff_impedance_ohms": 100.0,
        "impedance_tolerance_percent": 10.0,
        "intra_pair_length_match_mils": 5.0,
        "clock_to_data_length_match_mils": 25.0,
        "diff_trace_width_mils": 4.0,
        "diff_spacing_mils": 5.5,
        "min_isolation_spacing_mils": 12.0,
    },
    "ETHERNET_1G": {
        "diff_impedance_ohms": 100.0,
        "impedance_tolerance_percent": 10.0,
        "intra_pair_length_match_mils": 10.0,
        "pair_to_pair_length_match_mils": 200.0,
        "diff_trace_width_mils": 5.0,
        "diff_spacing_mils": 6.5,
        "min_isolation_spacing_mils": 15.0,
    },
}


def build_18layer_rigid_flex_stackup_definition() -> list[dict[str, Any]]:
    """Build a standard symmetrical 18-layer Rigid-Flex PCB stackup structure."""
    return [
        {"layer": 1, "name": "TOP", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": "L2_GND"},
        {"layer": 2, "name": "L2_GND", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 3, "name": "L3_SIG1", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7, "zone": "RIGID", "ref_plane": "L2_GND"},
        {"layer": 4, "name": "L4_PWR1", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 5, "name": "L5_SIG2", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7, "zone": "RIGID", "ref_plane": "L4_PWR1"},
        {"layer": 6, "name": "L6_GND2", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 7, "name": "L7_SIG3", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7, "zone": "RIGID", "ref_plane": "L6_GND2"},
        {"layer": 8, "name": "L8_PWR2", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        # Flex Core (Layers 9-10 Polyimide Flex Substrate)
        {"layer": 9, "name": "L9_FLEX_SIG1", "type": "CONDUCTOR", "material": "RA_COPPER", "thickness_mil": 0.7, "zone": "FLEX", "ref_plane": "L10_FLEX_GND", "hatched_plane": True},
        {"layer": 10, "name": "L10_FLEX_GND", "type": "PLANE", "material": "RA_COPPER", "thickness_mil": 0.7, "zone": "FLEX", "ref_plane": None, "hatched_plane": True},
        # Rigid Lower Section
        {"layer": 11, "name": "L11_PWR3", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 12, "name": "L12_SIG4", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7, "zone": "RIGID", "ref_plane": "L11_PWR3"},
        {"layer": 13, "name": "L13_GND3", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 14, "name": "L14_SIG5", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7, "zone": "RIGID", "ref_plane": "L13_GND3"},
        {"layer": 15, "name": "L15_PWR4", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 16, "name": "L16_SIG6", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 0.7, "zone": "RIGID", "ref_plane": "L15_PWR4"},
        {"layer": 17, "name": "L17_GND4", "type": "PLANE", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": None},
        {"layer": 18, "name": "BOTTOM", "type": "CONDUCTOR", "material": "COPPER", "thickness_mil": 1.4, "zone": "RIGID", "ref_plane": "L17_GND4"},
    ]


@mcp.tool
async def generate_18layer_rigid_flex_stackup(
    board_thickness_mil: float = 62.0,
    flex_core_thickness_mil: float = 4.0,
    output_script_path: Optional[str] = None,
) -> dict[str, Any]:
    """Return the standard 18-layer Rigid-Flex layer definition (JSON) and write a HUMAN-READABLE
    preview `.scr` (comment lines only — NOT executable SKILL) — this tool does NOT touch a real
    board. To actually author this stackup (or any other layer list) in a real Allegro design,
    call `start_allegro_session()`, then `generate_multilayer_stackup(session_id, layers=...)`
    with this tool's `layers` return value, then `allegro_save_design(session_id)` +
    `allegro_run_session(session_id, board_file)` — that is the real, SKILL-executing path.
    (Previously this tool's name/docstring implied it wrote real Allegro commands; it never did —
    corrected here rather than silently left misleading. See `generate_multilayer_stackup`'s
    docstring for the real authoring flow and its honest limitations.)
    """
    stackup = build_18layer_rigid_flex_stackup_definition()
    out_path = output_script_path or "setup_18layer_rigid_flex.scr"

    script_lines = [
        "# PREVIEW ONLY -- not executable SKILL/Allegro commands.",
        "# To actually author this stackup on a real board, use generate_multilayer_stackup()",
        "# (session_id, layers=...) inside a start_allegro_session()/allegro_run_session() flow.",
        "# Cadence Allegro 18-Layer Rigid-Flex Stackup Configuration Script",
        "setwindow pcb",
        "generaledit",
        "cmgr",
    ]

    for layer in stackup:
        script_lines.append(f"# Layer {layer['layer']}: {layer['name']} ({layer['type']}, {layer['zone']})")

    content = "\n".join(script_lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "layer_count": 18,
        "technology": "Rigid-Flex Multilayer",
        "total_thickness_mil": board_thickness_mil,
        "flex_layers": ["L9_FLEX_SIG1", "L10_FLEX_GND"],
        "layers": stackup,
        "script_path": os.path.abspath(out_path),
        "note": "script_path is a human-readable PREVIEW ONLY (comment lines), not executable "
        "SKILL. Pass this result's 'layers' to generate_multilayer_stackup(session_id, layers=...) "
        "for a real, session-composed axlXSectionCreate sequence against a live board.",
    }


@mcp.tool
async def generate_multilayer_stackup(session_id: str, layers: list[dict[str, Any]]) -> dict[str, Any]:
    """Queue a REAL top-to-bottom sequence of Allegro cross-section layers (one real
    `axlXSectionCreate` SKILL call per layer), within the current Allegro SKILL session.

    This is the real fix for the gap `generate_18layer_rigid_flex_stackup` left open: that
    tool only ever wrote `#`-comment lines describing a stackup — this tool actually composes
    executable SKILL against a live `start_allegro_session()`, the same "Model B" session
    mechanics as `allegro_create_stackup` (`sigrity_mcp/domains/cad/allegro_tools.py`), whose
    single-layer primitive this tool calls once per entry in `layers`.

    `layers`: list of dicts in TOP-TO-BOTTOM physical order (index 0 = physical top), each:
      - name (str, required) — xsection/etch layer name, e.g. "L2_GND"
      - layer_type (str, required; alias "type" accepted) — "CONDUCTOR"/"PLANE"/"DIELECTRIC"/
        "MASK"/... (see `axlXSectionLayerTypes()`)
      - thickness_mil (float, optional) — REAL, SKILL-settable xsection attribute
      - material (str, optional) — REAL, SKILL-settable xsection attribute (e.g. "COPPER")
      - zone (str, optional) — INFORMATIONAL ONLY (e.g. "RIGID"/"FLEX"), see LIMITATIONS
      - ref_plane (str, optional) — INFORMATIONAL ONLY, see LIMITATIONS
      - hatched_plane (bool, optional) — INFORMATIONAL ONLY, see LIMITATIONS

    Unlike the single-purpose `_create_*`/`_set_*` tools elsewhere in this suite (which queue
    exactly one script line per call), this bulk tool queues `len(layers)` lines in ONE call —
    composing an 18-layer stackup one MCP round-trip per layer doesn't scale. It is still
    "Model B": nothing executes until you follow with `allegro_save_design(session_id)` and
    `allegro_run_session(session_id, board_file)`.

    ORDERING (verified LIVE 2026-09-30 against a real board copy on this machine, TWICE —
    see `.forjinn/skills/sigrity-cad/SKILL.md` for the exact run and raw `x-section` report
    output): each layer is queued via `axlXSectionCreate(nil 'bottom <defstruct>)` IN THE
    SAME order as the input `layers` list (top physical layer queued first). `'top'`/
    `'afterBottom` are documented as restricted to unnamed dielectric/MASK layers for PCB
    designs, so `'bottom'` is the only endpoint usable for a full named CONDUCTOR/PLANE
    stackup.
    CORRECTION to a literal reading of Cadence's own vendored doc tip (`axlXSectionCreate.txt`
    PROGRAMMING TIPS: "If populating multiple internal layers, use the 'bottom option and
    build the stackup from bottom to top", which reads as "queue bottom-most layer first"):
    an initial implementation did exactly that (reverse-queued, bottom-most layer first) and
    a live `run_allegro_report(..., report_code="x-section")` read-back showed the OPPOSITE of
    the intended order — the first-queued (bottom-most, intended) landed closest to the
    board's physical TOP of the inserted group, and the last-queued (top-most, intended)
    landed closest to physical BOTTOM. Empirically, EACH successive `'bottom` insert lands
    directly adjacent to the true outer BOTTOM layer, pushing every earlier `'bottom` insert
    one position further up — i.e. queuing order chronologically becomes physical order
    top-to-bottom of the inserted block. So NOT reversing (queuing in the caller's own
    top-to-bottom order, as this tool does) is what actually produces correct top-to-bottom
    placement. RE-VERIFIED after the fix on a second fresh board copy: a 3-layer queue
    (TOPTEST, PLANETEST, BOTTOMTEST, queued in that order) landed as
    TOP / TOPTEST / PLANETEST / BOTTOMTEST / BOTTOM — correct — with real name/type/material/
    thickness values matching the input exactly.

    VERIFY, don't trust this tool's return value: SKILL return values never surface here (see
    parent SKILL.md) — after `allegro_run_session`, call `run_allegro_report(board_file,
    report_code="x-section", output_file=...)` and read the real report for the actual
    resulting layer order/names/types/thicknesses.

    FULL-SCALE LIVE TEST (2026-09-30): the actual production
    `build_18layer_rigid_flex_stackup_definition()` list (18 layers, reusing "TOP"/"BOTTOM" as
    layer 1/18's names, matching the board's own default outer layer names) was queued and run
    against a fresh real board copy. Result via `run_allegro_report(..., report_code=
    "x-section")`: all 16 INTERNAL layers (L2_GND through L17_GND4, including the RA_COPPER
    flex pair L9/L10) landed with correct name/type/material/thickness in the exact
    top-to-bottom order given. The 2 layers named "TOP"/"BOTTOM" did NOT change anything — the
    board's pre-existing default TOP/BOTTOM entries kept their original attributes (thickness
    stayed 1.44 mil, not the input's 1.4) — no duplicate layer, no error surfaced, no effect.
    This matches Cadence's own documented restriction ("Allegro PCB does not allow name layers
    above top or below bottom") extended to same-named internal create attempts: creating a
    layer whose name collides with an existing outer TOP/BOTTOM entry is a silent no-op here,
    not a duplicate and not an update. PRACTICAL IMPLICATION: if you want the real board's
    outer TOP/BOTTOM layers customized too (not just the internal stack), do NOT rely on this
    tool for those two entries — either omit "TOP"/"BOTTOM"-named entries from `layers` (the
    physical outer layers already exist by default; only the internal ones need creating), or
    separately fetch+modify them via `axlXSectionGet(nil "TOP")` +
    `axlXSectionModify(?thickness ... ?material ...)` + `axlXSectionSet(...)` — NOT wrapped by
    any tool in this suite yet.

    OPERATIONAL CAVEAT (observed live, 4-for-4 test runs on this machine, including this
    full-scale one): the `allegro.exe` process launched by `allegro_run_session` reproducibly
    raised an unlabeled modal Qt dialog a couple seconds into every stackup-authoring run in
    this session (before the script even finishes loading the board) — NOT obviously
    content-dependent (it also appeared in a 2-layer isolation test), so likely the same
    general Allegro launch flakiness already documented in `core/tool_status.py`'s "allegro"
    note (product-chooser/license dialogs, ~1-in-4 launches historically) rather than
    something this tool's SKILL calls specifically cause — but it showed up EVERY time in this
    round of testing, not 1-in-4, so treat stackup authoring as a higher-risk case for this
    until proven otherwise. Without something to dismiss it, the job hangs past its normal
    ~15-20s load time with an empty `run.log` (the same non-terminal "state lies" pattern
    documented in the parent SKILL.md). What worked live:
    `sigrity_mcp.core.win32gui_helper.auto_dismiss_dialogs(pid, timeout=...)`, run concurrently
    (poll for the job's `pid` via `get_job_status`/`job_manager.get`, then call this once the
    process exists) — it posts Enter/Space to the dialog's default button, which let all 3
    successful full-run tests above (two small + the full 18-layer one) complete with
    `state:"succeeded"`, `returncode:0`, and correct on-disk layers confirmed by
    `run_allegro_report`. Dismissal had no observed effect on correctness — every run's
    `x-section` read-back matched its input exactly (modulo the TOP/BOTTOM name-collision
    finding above).

    UPDATE: this manual poll-and-dismiss step is no longer necessary to do by hand —
    `core.jobs.JobManager.submit` now auto-starts a `core.win32gui_helper.DismissWatcher`
    for the job's whole lifetime whenever `run_session` launches `tool="allegro"` (which
    `allegro_run_session` always does), closing the hang this section describes at the
    source. See `win32gui_helper.DismissWatcher`'s docstring for the live repro evidence.

    LIMITATIONS (honest, checked against this install's vendored SKILL docs): only
    name/layerType/material/thickness are real, SKILL-settable xsection attributes —
    confirmed against `axlXSectionGet.txt`'s own attribute table (`Modify: Yes` column) and the
    real example `share/pcb/examples/skill/dbcreate/xsection.il` on this machine. There is NO
    SKILL attribute anywhere in that attribute table, nor in any `axlCNS*`/`axlCns*`
    Constraint-Manager function (the full `DOC/FUNCS/axlCNS*.txt`/`axlCns*.txt` listing on this
    install was checked), for an explicit "reference plane" assignment on a layer — Allegro's
    impedance calculator infers a signal layer's reference plane from stackup ADJACENCY to a
    PLANE layer, not from any settable field. So `ref_plane`/`zone`/`hatched_plane` inputs are
    echoed back in this tool's return value for bookkeeping/documentation only — they do NOT
    correspond to any SKILL call made against the board. Order your `layers` list so the
    intended reference plane is physically adjacent to its signal layer; that adjacency alone
    is what Allegro's calculator uses.
See `.forjinn/skills/sigrity-cad/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    if not layers:
        raise ValueError("layers must be a non-empty list, in top-to-bottom physical order.")

    queued: list[dict[str, Any]] = []
    for layer in layers:
        name = layer.get("name")
        if not name:
            raise ValueError(f"Each layer dict needs a 'name': {layer!r}")
        layer_type = layer.get("layer_type", layer.get("type"))
        material = layer.get("material")
        thickness_mil = layer.get("thickness_mil")

        defstruct = _make_axlxsection(name, layer_type, material, thickness_mil)
        expr = f"(axlXSectionCreate nil {_xsection_position_arg('bottom')} {defstruct})"
        tcl_sessions.add_line(session_id, _skill_line(expr))

        queued.append(
            {
                "name": name,
                "layer_type": layer_type,
                "material": material,
                "thickness_mil": thickness_mil,
                "zone": layer.get("zone"),
                "ref_plane": layer.get("ref_plane"),
                "hatched_plane": layer.get("hatched_plane"),
            }
        )

    result = {
        "session_id": session_id,
        "layer_count": len(layers),
        "queued_layers": queued,
        "ordering_method": "queued IN THE GIVEN top-to-bottom order, each via "
        "axlXSectionCreate(nil 'bottom <defstruct>) -- see this tool's docstring for the "
        "live-verified reasoning (this is the OPPOSITE of a literal reading of Cadence's own "
        "'build bottom-to-top' doc tip; empirical behavior on this machine wins).",
        "verify_with": "run_allegro_report(board_file, report_code='x-section', output_file=...) "
        "AFTER allegro_save_design + allegro_run_session -- do not trust this return value alone.",
        "limitation": "name/layerType/material/thickness are real SKILL-authored attributes; "
        "zone/ref_plane/hatched_plane are informational metadata only, not settable via any "
        "SKILL API found on this install -- see this tool's docstring for what was checked.",
    }
    collision_names = [
        layer.get("name") for layer in layers
        if str(layer.get("name", "")).upper() in ("TOP", "BOTTOM")
    ]
    if collision_names:
        result["warning"] = (
            f"Layer(s) named {collision_names} will be SILENTLY SKIPPED by Allegro "
            "(name collision with the board's pre-existing outer TOP/BOTTOM layers) -- "
            "no duplicate is created and the existing entry's attributes are NOT "
            "modified. Drop these entries from `layers` if you want only internal "
            "layers created, or separately drive axlXSectionGet/axlXSectionModify/"
            "axlXSectionSet to change the outer layers' attributes."
        )
    return result


@mcp.tool
async def get_high_speed_constraint_preset(
    interface_type: Literal["DDR4", "DDR5", "PCIE_GEN4", "PCIE_GEN5", "USB4", "MIPI_DPHY", "ETHERNET_1G"],
    net_class_name: Optional[str] = None,
) -> dict[str, Any]:
    """Retrieve high-speed bus layout and routing constraint rules for Allegro Constraint Manager.

    Returns differential impedance targets, intra-pair skew limits, max uncoupled lengths,
    trace widths, and physical spacing values for high-speed routing.
    """
    preset = HIGH_SPEED_INTERFACE_PRESETS.get(interface_type)
    if not preset:
        raise ValueError(f"Unknown interface_type '{interface_type}'. Supported: {list(HIGH_SPEED_INTERFACE_PRESETS.keys())}")

    return {
        "status": "success",
        "interface": interface_type,
        "net_class": net_class_name or f"CLASS_{interface_type}",
        "constraints": preset,
    }
