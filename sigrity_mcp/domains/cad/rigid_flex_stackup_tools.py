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
    """Generate an Allegro SKILL / script template for an 18-layer Rigid-Flex PCB stackup."""
    stackup = build_18layer_rigid_flex_stackup_definition()
    out_path = output_script_path or "setup_18layer_rigid_flex.scr"

    script_lines = [
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
    }


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
