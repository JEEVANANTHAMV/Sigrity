"""Automated engineering documentation generation tools for PCB & Hardware designs.

Aligned with FORJINN Discovery Form Priorities 7, 8, 9 & Deliverable 2:
- Priority 7: Auto-generate Hardware Design Documents (HDD) with system architecture,
  power tree, interfaces, clocking/reset, and stackup details.
- Priority 8: Auto-generate Validation & Bring-up Test Plans covering power sequencing,
  clock measurements, JTAG/SWD, high-speed interface eye diagrams, and smoke tests.
- Priority 9: Auto-generate Board User Guides with setup instructions, connector pinouts,
  jumper settings, LED indicators, test point maps, and troubleshooting guides.
- Deliverable 2: Auto-generate Requirement-to-Schematic Traceability Matrix linking
  PRD/HRS requirements to schematic sheets, nets, refdes, and verification tests.
"""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime
from typing import Any, Optional

from sigrity_mcp.mcp_app import mcp


def _as_dict(value: Any, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Coerce a tool argument into a dict, tolerating the JSON-string-as-dict quirk.

    Some calling models serialize a dict-typed argument as a JSON string
    (e.g. `'{"rails": [...]}'`) and FastMCP's pydantic validation passes a
    scalar through as-is, so the tool body would otherwise crash on
    `.get()` (e.g. `'str' object has no attribute 'get'`). This normalizes
    that: a dict is returned unchanged, a JSON/Python-literal string that
    parses to a dict is parsed, and anything else becomes `default or {}`.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, RecursionError):
            pass
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError, RecursionError, TypeError, MemoryError):
            pass
    return dict(default) if default else {}


def _as_list(value: Any) -> list[Any]:
    """Coerce a tool argument into a list, tolerating a JSON/Python-literal string.

    A list is returned unchanged; a string that parses to a list is parsed; a
    single dict (a one-item table sent without the wrapping list) is wrapped;
    anything else becomes `[]`.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(value)
            except (ValueError, RecursionError, SyntaxError, TypeError, MemoryError):
                continue
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
    return []


def _row(row: Any) -> dict[str, Any]:
    """Coerce one table row into a dict: a dict passes through, a raw string is
    wrapped as {'_text': <s>} (so a scalar row still renders instead of crashing),
    and anything else becomes an empty dict."""
    if isinstance(row, dict):
        return row
    if isinstance(row, str):
        return {"_text": row}
    return {}


def _cell(row: dict[str, Any], key: str, default: Any = "N/A") -> Any:
    """Read a cell from a row dict, tolerating a scalar/_text row and a missing key.

    Returning `default` (instead of raising or None) keeps the Markdown tables
    from crashing on the observed model-shaped inputs: a dict row with a missing
    key, or a row that was a plain string (e.g. a pins list whose entries are
    bare strings rather than pin objects).
    """
    if "_text" in row and key not in row:
        return row["_text"]
    return row.get(key, default)


@mcp.tool
async def generate_hardware_design_document(
    project_name: str,
    board_name: str,
    author: str,
    version: str,
    system_overview: str,
    power_architecture: dict[str, Any],
    subsystems_and_interfaces: list[dict[str, Any]],
    layer_stackup_summary: Optional[dict[str, Any]] = None,
    clock_and_reset_architecture: Optional[dict[str, Any]] = None,
    bom_summary: Optional[dict[str, Any]] = None,
    thermal_and_power_budget: Optional[dict[str, Any]] = None,
    output_markdown_path: Optional[str] = None,
) -> dict[str, Any]:
    """Auto-generate a comprehensive Hardware Design Document (HDD) in Markdown.

    `power_architecture`: Dict specifying input rails, PMIC/DC-DC/LDO stages, voltages, max currents,
                          and sequencing (e.g. {"input_voltage": "12V", "rails": [...]}).
    `subsystems_and_interfaces`: List of subsystem specifications (e.g. MCU/SoC, DDR4/5, PCIe, USB, Ethernet, MIPI).
    `layer_stackup_summary`: Optional layer count (e.g. 18-layer Rigid-Flex), dielectric types, copper weights, impedance targets.
    `clock_and_reset_architecture`: Optional crystal/oscillator frequencies, reset generators, watchdog circuits.
    `bom_summary`: Optional total component count, SMT vs THT, critical active parts.
    `thermal_and_power_budget`: Optional thermal dissipation, cooling requirements, power budgets per rail.
    `output_markdown_path`: Target path to save the generated document (defaults to <board_name>_HDD.md).
    """
    # Normalize string-encoded / scalar-typed structured args (FastMCP surfaces a few of
    # these as-is; see _as_dict/_as_list at the top of this module).
    power_architecture = _as_dict(power_architecture)
    subsystems_and_interfaces = _as_list(subsystems_and_interfaces)
    layer_stackup_summary = _as_dict(layer_stackup_summary)
    clock_and_reset_architecture = _as_dict(clock_and_reset_architecture)
    bom_summary = _as_dict(bom_summary)
    thermal_and_power_budget = _as_dict(thermal_and_power_budget)

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_markdown_path or f"{board_name.replace(' ', '_')}_HDD_v{version}.md"

    doc_lines: list[str] = [
        f"# Hardware Design Document (HDD): {project_name} - {board_name}",
        f"**Document Version:** {version}  ",
        f"**Date:** {date_str}  ",
        f"**Author / Generated By:** {author} (FORJINN AI Agent)  ",
        f"**Classification:** LTSCT Confidential  ",
        "\n---\n",
        "## 1. Executive Summary & System Overview",
        f"{system_overview.strip()}",
        "\n---\n",
        "## 2. System Architecture Block Diagram",
        "```mermaid",
        "graph TD",
        "    PWR[Main Power Supply] --> PMIC[Power Management IC / Regulators]",
        "    PMIC --> VDD_CORE[Core Logic Rails]",
        "    PMIC --> VDD_IO[IO & Peripheral Rails]",
        "    SOC[Primary SoC / FPGA / MCU] --- DDR[DDR Memory Interface]",
        "    SOC --- PCIE[PCIe / High Speed Bus]",
        "    SOC --- PERIPH[Peripherals & Sensors]",
        "    SOC --- CONN[External Connectors & IO]",
        "```",
        "\n---\n",
        "## 3. Power Architecture & Power Tree",
    ]

    # Power architecture section
    if "input_voltage" in power_architecture:
        doc_lines.append(f"**Primary Input Voltage:** {power_architecture.get('input_voltage')}")
    if "total_power_budget" in power_architecture:
        doc_lines.append(f"**Estimated Peak Power:** {power_architecture.get('total_power_budget')}")

    rails = power_architecture.get("rails", [])
    if rails:
        doc_lines.append("\n### Power Rails & Regulators Table\n")
        doc_lines.append("| Rail Name | Voltage (V) | Max Current (A) | Regulator Type | Source Rail | Sequencing Step |")
        doc_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for r in rails:
            name = r.get("name", "N/A")
            volts = r.get("voltage", "N/A")
            curr = r.get("max_current", "N/A")
            reg = r.get("regulator_type", "N/A")
            src = r.get("source", "VIN")
            seq = r.get("sequence_order", "1")
            doc_lines.append(f"| {name} | {volts} | {curr} | {reg} | {src} | Step {seq} |")

    # Subsystems & Interfaces
    doc_lines.append("\n---\n## 4. Subsystems & High-Speed Interfaces")
    for sub in subsystems_and_interfaces:
        sub_name = sub.get("name", "Subsystem")
        sub_type = sub.get("type", "General")
        desc = sub.get("description", "")
        doc_lines.append(f"\n### 4.{len(doc_lines)} {sub_name} ({sub_type})")
        if desc:
            doc_lines.append(f"{desc}\n")
        signals = sub.get("signals", [])
        if signals:
            doc_lines.append("| Signal / Bus Name | Type | Target Net / IC | Impedance Rule | Length Matching Tol |")
            doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for sig in signals:
                s_name = sig.get("name", "N/A")
                s_type = sig.get("type", "Differential / Single-ended")
                s_net = sig.get("net", "N/A")
                s_imp = sig.get("impedance", "N/A")
                s_len = sig.get("length_match_tol", "N/A")
                doc_lines.append(f"| {s_name} | {s_type} | {s_net} | {s_imp} | {s_len} |")

    # Clock & Reset
    if clock_and_reset_architecture:
        doc_lines.append("\n---\n## 5. Clocking and Reset Architecture")
        clocks = clock_and_reset_architecture.get("clocks", [])
        if clocks:
            doc_lines.append("\n### Clock Generators & Crystals")
            doc_lines.append("| Clock Name | Frequency | Source / IC | Target Pin | Tolerance |")
            doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for clk in clocks:
                doc_lines.append(f"| {clk.get('name')} | {clk.get('frequency')} | {clk.get('source')} | {clk.get('target')} | {clk.get('tolerance', '±20 ppm')} |")
        resets = clock_and_reset_architecture.get("resets", [])
        if resets:
            doc_lines.append("\n### Reset Lines & Supervisory Circuits")
            doc_lines.append("| Reset Signal | Assert Condition | Threshold Voltage | Hold Time (ms) |")
            doc_lines.append("| :--- | :--- | :--- | :--- |")
            for rst in resets:
                doc_lines.append(f"| {rst.get('signal')} | {rst.get('assert_condition')} | {rst.get('threshold', 'N/A')} | {rst.get('hold_time_ms', 'N/A')} |")

    # Stackup Summary
    if layer_stackup_summary:
        doc_lines.append("\n---\n## 6. PCB Stackup & Fabrication Rules")
        doc_lines.append(f"**Layer Count:** {layer_stackup_summary.get('layer_count', '18 Layers')}  ")
        doc_lines.append(f"**Technology:** {layer_stackup_summary.get('technology', 'Rigid-Flex Multilayer')}  ")
        doc_lines.append(f"**Board Dimensions:** {layer_stackup_summary.get('dimensions', '450 mm x 450 mm Max')}  ")
        layers = layer_stackup_summary.get("layers", [])
        if layers:
            doc_lines.append("\n| Layer # | Layer Name | Layer Type | Copper Weight (oz) | Thickness (mil) | Material |")
            doc_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for l in layers:
                doc_lines.append(f"| {l.get('number')} | {l.get('name')} | {l.get('type')} | {l.get('copper_oz', '0.5/1.0')} | {l.get('thickness_mil', 'N/A')} | {l.get('material', 'FR4/Polyimide')} |")

    # Thermal & Power Budget
    if thermal_and_power_budget:
        doc_lines.append("\n---\n## 7. Thermal & Environmental Budget")
        doc_lines.append(f"**Operating Temp Range:** {thermal_and_power_budget.get('operating_temp', '-40°C to +85°C Industrial')}  ")
        doc_lines.append(f"**Total Thermal Dissipation:** {thermal_and_power_budget.get('total_dissipation_watts', 'N/A')} W  ")
        doc_lines.append(f"**Cooling Strategy:** {thermal_and_power_budget.get('cooling_strategy', 'Conduction via Copper Ground Planes & Heat Spreader')}  ")

    # BOM Summary
    if bom_summary:
        doc_lines.append("\n---\n## 8. Bill of Materials (BOM) Statistics")
        doc_lines.append(f"**Total Part Count:** {bom_summary.get('total_components', 'N/A')}  ")
        doc_lines.append(f"**Unique Line Items:** {bom_summary.get('unique_parts', 'N/A')}  ")
        doc_lines.append(f"**SMT / THT Ratio:** {bom_summary.get('smt_tht_ratio', '95% SMT / 5% THT')}  ")

    doc_lines.append("\n---\n*Generated automatically by FORJINN AI Agent for L&T Semiconductor Technologies.*")

    content = "\n".join(doc_lines)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "document_path": os.path.abspath(out_path),
        "total_sections": 8,
        "document_title": f"Hardware Design Document: {project_name} - {board_name}",
        "version": version,
    }


@mcp.tool
async def generate_validation_test_plan(
    project_name: str,
    board_name: str,
    revision: str,
    author: str,
    power_rails: list[dict[str, Any]],
    clocks_and_resets: list[dict[str, Any]],
    high_speed_interfaces: list[dict[str, Any]],
    peripheral_smoke_tests: Optional[list[dict[str, Any]]] = None,
    output_markdown_path: Optional[str] = None,
) -> dict[str, Any]:
    """Auto-generate a Bring-up & Validation Test Plan for Hardware Design Teams.

    Covers Power Rail Sequencing, Voltage Margins, Clock Frequencies, JTAG/SWD Bringup,
    High-Speed Bus Signal Integrity (Eye-diagrams, BER), and Peripheral Functional Tests.
    Every table parameter may be a native list OR a JSON string (both are accepted).
    """
    power_rails = _as_list(power_rails)
    clocks_and_resets = _as_list(clocks_and_resets)
    high_speed_interfaces = _as_list(high_speed_interfaces)
    peripheral_smoke_tests = _as_list(peripheral_smoke_tests)

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_markdown_path or f"{board_name.replace(' ', '_')}_Validation_Test_Plan_Rev{revision}.md"

    doc_lines: list[str] = [
        f"# Hardware Bring-Up & Validation Test Plan: {project_name} - {board_name}",
        f"**Revision:** {revision}  ",
        f"**Date Issued:** {date_str}  ",
        f"**Author / Lead:** {author}  ",
        f"**Classification:** LTSCT Confidential  ",
        "\n---\n",
        "## 1. Scope & Bring-Up Prerequisites",
        "- Verify benchtop lab power supply current limits before initial power-on (set to 20% above quiescent budget).",
        "- Perform unpowered impedance / short-circuit check between all power rails and GND using a DMM.",
        "- ESD protection precautions and wrist straps mandatory during board handling.",
        "\n---\n",
        "## 2. Stage 1: Unpowered Cold-Board Continuity & Resistance Check",
        "| Test ID | Test Description | Measurement Point | Expected Nominal | Pass Criteria | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    idx = 1
    for pwr in power_rails:
        rail_name = pwr.get("name", f"RAIL_{idx}")
        tp = pwr.get("test_point", f"TP_{rail_name}")
        min_res = pwr.get("min_resistance_to_gnd", "> 100 Ω")
        doc_lines.append(f"| TP-COLD-{idx:02d} | Resistance to GND: {rail_name} | {tp} to GND | {min_res} | No short circuit (>= {min_res}) | [ ] Pass / [ ] Fail |")
        idx += 1

    doc_lines.append("\n---\n## 3. Stage 2: Power-On Sequencing & Voltage Rail Margin Checks")
    doc_lines.append("| Test ID | Power Rail | Test Point | Nominal (V) | Min Tol (-5%) | Max Tol (+5%) | Sequence Order | Rise Time (ms) | Pass / Fail |")
    doc_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    idx = 1
    for pwr in power_rails:
        name = pwr.get("name", f"RAIL_{idx}")
        tp = pwr.get("test_point", f"TP_{name}")
        nom = float(pwr.get("voltage", 3.3))
        v_min = round(nom * 0.95, 3)
        v_max = round(nom * 1.05, 3)
        seq = pwr.get("sequence_step", idx)
        rise = pwr.get("rise_time_ms", "< 10 ms")
        doc_lines.append(f"| TP-PWR-{idx:02d} | {name} | {tp} | {nom:.3f} V | {v_min:.3f} V | {v_max:.3f} V | Step {seq} | {rise} | [ ] Pass / [ ] Fail |")
        idx += 1

    doc_lines.append("\n---\n## 4. Stage 3: Clock Signals & Reset Release Verification")
    doc_lines.append("| Test ID | Signal Name | Test Point | Nominal Frequency | Amplitude (Vpp) | Jitter / Tolerance | Pass / Fail |")
    doc_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    idx = 1
    for clk in clocks_and_resets:
        sig = clk.get("name", f"CLK_{idx}")
        tp = clk.get("test_point", f"TP_{sig}")
        freq = clk.get("frequency", "N/A")
        vpp = clk.get("vpp", "3.3 V")
        tol = clk.get("tolerance", "±50 ppm")
        doc_lines.append(f"| TP-CLK-{idx:02d} | {sig} | {tp} | {freq} | {vpp} | {tol} | [ ] Pass / [ ] Fail |")
        idx += 1

    doc_lines.append("\n---\n## 5. Stage 4: High-Speed Interface Compliance & Signal Integrity")
    doc_lines.append("| Test ID | Interface | Signals / Lanes | Test Procedure | Acceptance Threshold | Pass / Fail |")
    doc_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

    idx = 1
    for hs in high_speed_interfaces:
        name = hs.get("name", "High-Speed Bus")
        lanes = hs.get("lanes", "1x")
        proc = hs.get("test_procedure", "Scope Eye-Diagram & PRBS / Packet Loopback")
        thresh = hs.get("acceptance_threshold", "Zero bit-errors across 10^12 bits, Eye mask open")
        doc_lines.append(f"| TP-HS-{idx:02d} | {name} | {lanes} | {proc} | {thresh} | [ ] Pass / [ ] Fail |")
        idx += 1

    if peripheral_smoke_tests:
        doc_lines.append("\n---\n## 6. Stage 5: Peripheral & Functional Smoke Tests")
        doc_lines.append("| Test ID | Subsystem | Test Description | Expected Functional Behavior | Result |")
        doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
        idx = 1
        for periph in peripheral_smoke_tests:
            sub = periph.get("subsystem", "Peripheral")
            desc = periph.get("description", "Functional verification")
            exp = periph.get("expected", "Operational")
            doc_lines.append(f"| TP-PER-{idx:02d} | {sub} | {desc} | {exp} | [ ] Pass / [ ] Fail |")
            idx += 1

    doc_lines.append("\n---\n## 7. Sign-off & Execution Approvals")
    doc_lines.append("| Role | Name | Signature | Date | Final Verdict |")
    doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
    doc_lines.append("| Test / Bring-Up Engineer | __________________ | __________________ | __________ | [ ] GO / [ ] NO-GO |")
    doc_lines.append("| Hardware Lead Engineer | __________________ | __________________ | __________ | [ ] APPROVED |")

    content = "\n".join(doc_lines)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "test_plan_path": os.path.abspath(out_path),
        "total_test_sections": 7,
        "version": revision,
    }


@mcp.tool
async def generate_board_user_guide(
    project_name: str,
    board_name: str,
    revision: str,
    author: str,
    board_description: str,
    power_supply_specifications: dict[str, Any],
    connector_pinouts: list[dict[str, Any]],
    jumper_configuration_tables: Optional[list[dict[str, Any]]] = None,
    status_leds_and_switches: Optional[list[dict[str, Any]]] = None,
    test_points_index: Optional[list[dict[str, Any]]] = None,
    troubleshooting_matrix: Optional[list[dict[str, Any]]] = None,
    output_markdown_path: Optional[str] = None,
) -> dict[str, Any]:
    """Auto-generate a Board User Guide for engineers, bring-up teams, and customers.

    `connector_pinouts` / `jumper_configuration_tables` may be passed as a native list
    OR as a JSON string (a quirk observed from some calling models); both are accepted.
    Any of the table parameters may be empty or omitted (a board with no jumpers /
    LEDs / test points / troubleshooting rows is still a valid guide).
    """
    power_supply_specifications = _as_dict(power_supply_specifications)
    connector_pinouts = _as_list(connector_pinouts)
    jumper_configuration_tables = _as_list(jumper_configuration_tables)
    status_leds_and_switches = _as_list(status_leds_and_switches)
    test_points_index = _as_list(test_points_index)
    troubleshooting_matrix = _as_list(troubleshooting_matrix)

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_markdown_path or f"{board_name.replace(' ', '_')}_User_Guide_Rev{revision}.md"

    doc_lines: list[str] = [
        f"# Hardware User Guide: {project_name} - {board_name}",
        f"**Hardware Revision:** {revision}  ",
        f"**Date:** {date_str}  ",
        f"**Prepared By:** {author}  ",
        f"**Classification:** LTSCT Confidential  ",
        "\n---\n",
        "## 1. Board Overview",
        f"{board_description.strip()}",
        "\n---\n",
        "## 2. Power Supply & Operating Requirements",
        f"- **Input Voltage Range:** {power_supply_specifications.get('input_voltage_range', '12V DC ± 5%')}",
        f"- **Recommended Supply Current:** {power_supply_specifications.get('recommended_current', '3.0 A')}",
        f"- **Power Connector:** {power_supply_specifications.get('power_connector_refdes', 'J1 (DC Barrel / USB-C PD)')}",
        f"- **Operating Temperature:** {power_supply_specifications.get('operating_temp', '0°C to +70°C Commercial / -40°C to +85°C Industrial')}",
        "\n---\n",
        "## 3. Connector Pinouts & Interfaces",
    ]

    for conn in connector_pinouts:
        c = _row(conn)
        refdes = _cell(c, "refdes", "J_CONN")
        name = _cell(c, "name", "")
        # Some callers label the connector with a 'connector'/'label' key instead of
        # a separate refdes/name pair — fall back to the first non-empty of those.
        labelish = next((c[k] for k in ("connector", "label") if c.get(k)), None)
        if not name:
            if refdes and refdes != "J_CONN":
                name = labelish or refdes
            else:
                name = labelish or "Header / Interface"
        desc = _cell(c, "description", "")
        doc_lines.append(f"\n### {refdes}: {name}")
        if desc:
            doc_lines.append(f"{desc}\n")
        # `pins` may be a list of dicts ({"pin","signal",...}), a list of bare
        # strings, or a single string describing the pins in prose.
        pins_raw = c.get("pins", [])
        pins = _as_list(pins_raw)
        if pins and not isinstance(pins, str):
            doc_lines.append("| Pin # | Signal Name | Type | Voltage | Description |")
            doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for pi, p in enumerate(_as_list(pins), start=1):
                pr = _row(p)
                doc_lines.append(f"| {_cell(pr, 'pin', pi)} | {_cell(pr, 'signal', _cell(c, 'name', ''))} | {_cell(pr, 'type', 'IO')} | {_cell(pr, 'voltage', '3.3V')} | {_cell(pr, 'description', '')} |")
        elif isinstance(pins_raw, str) and pins_raw.strip():
            doc_lines.append(f"Pins: {pins_raw.strip()}")

    doc_lines.append("\n---\n## 4. Jumper & DIP Switch Configuration")
    doc_lines.append("| Jumper RefDes | Function | Default Setting | Alternative Positions & Mode |")
    doc_lines.append("| :--- | :--- | :--- | :--- |")
    if jumper_configuration_tables:
        for jmp in jumper_configuration_tables:
            j = _row(jmp)
            doc_lines.append(f"| {_cell(j, 'refdes')} | {_cell(j, 'function')} | {_cell(j, 'default')} | {_cell(j, 'alternatives', 'N/A')} |")
    else:
        doc_lines.append("| (none) | No jumpers / DIP switches on this board | N/A | N/A |")

    if status_leds_and_switches:
        doc_lines.append("\n---\n## 5. Status LEDs, Push Buttons & Indicators")
        doc_lines.append("| RefDes | Type | Color / Label | Normal State | Function / Indicator Meaning |")
        doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for ind in status_leds_and_switches:
            i = _row(ind)
            refdes = _cell(i, "refdes", "N/A")
            if refdes == "N/A":
                refdes = _cell(i, "led", _cell(i, "switch", "N/A"))
            ind_type = _cell(i, "type", "LED")
            if "switch" in i:
                ind_type = "Switch"
            doc_lines.append(f"| {refdes} | {ind_type} | {_cell(i, 'color', 'Green')} | {_cell(i, 'normal_state', 'ON')} | {_cell(i, 'function')} |")

    if test_points_index:
        doc_lines.append("\n---\n## 6. Test Points Quick Reference")
        doc_lines.append("| Test Point | Net Name | Expected Signal / Voltage | Pad Type | Location / Layer |")
        doc_lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for tp in test_points_index:
            t = _row(tp)
            doc_lines.append(f"| {_cell(t, 'refdes', _cell(t, 'tp'))} | {_cell(t, 'net_name', _cell(t, 'net'))} | {_cell(t, 'expected_value')} | {_cell(t, 'pad_type', 'SMD Pad')} | {_cell(t, 'location', 'Top')} |")

    if troubleshooting_matrix:
        doc_lines.append("\n---\n## 7. Troubleshooting & Common Issues")
        doc_lines.append("| Symptom / Failure | Likely Cause | Recommended Diagnostic / Action |")
        doc_lines.append("| :--- | :--- | :--- |")
        for tr in troubleshooting_matrix:
            t = _row(tr)
            doc_lines.append(f"| {_cell(t, 'symptom', _cell(t, 'check'))} | {_cell(t, 'cause', 'N/A')} | {_cell(t, 'action', _cell(t, 'check'))} |")

    content = "\n".join(doc_lines)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "user_guide_path": os.path.abspath(out_path),
        "total_connectors": len(connector_pinouts),
        "version": revision,
    }


@mcp.tool
async def generate_traceability_matrix(
    project_name: str,
    board_name: str,
    requirements: list[dict[str, Any]],
    output_markdown_path: Optional[str] = None,
) -> dict[str, Any]:
    """Auto-generate a Requirement-to-Schematic Traceability Matrix.

    Maps PRD/HRS requirement IDs to schematic sheets, net names, component refdes,
    constraint rules, and verification test cases. `requirements` may be a native list
    OR a JSON string (both accepted).
    """
    requirements = _as_list(requirements)

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = output_markdown_path or f"{board_name.replace(' ', '_')}_Traceability_Matrix.md"

    doc_lines: list[str] = [
        f"# Requirement-to-Design Traceability Matrix: {project_name} - {board_name}",
        f"**Date:** {date_str}  ",
        f"**Classification:** LTSCT Confidential  ",
        "\n---\n",
        "## Bi-Directional Traceability Table\n",
        "| Req ID | Requirement Description | Schematic Sheet(s) | Impacted Component(s) | Net(s) / Interface | Verification Test ID | Compliance Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for req in requirements:
        req_id = req.get("req_id", "REQ-000")
        desc = req.get("description", "N/A")
        sheets = req.get("schematic_sheets", "Sheet 1")
        comps = req.get("components", "N/A")
        nets = req.get("nets", "N/A")
        test_id = req.get("test_id", "TP-001")
        status = req.get("compliance_status", "Compliant")
        doc_lines.append(f"| {req_id} | {desc} | {sheets} | {comps} | {nets} | {test_id} | {status} |")

    doc_lines.append("\n---\n*Generated automatically by FORJINN AI Agent.*")
    content = "\n".join(doc_lines)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "matrix_path": os.path.abspath(out_path),
        "total_requirements_tracked": len(requirements),
    }
