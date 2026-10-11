import os
import pytest

from sigrity_mcp.domains.cad.document_generation_tools import (
    generate_board_user_guide,
    generate_hardware_design_document,
    generate_traceability_matrix,
    generate_validation_test_plan,
)


@pytest.mark.asyncio
async def test_generate_hardware_design_document(tmp_path):
    out_file = str(tmp_path / "FRDM_IMX91_HDD.md")
    result = await generate_hardware_design_document(
        project_name="FORJINN_POC",
        board_name="FRDM_IMX91",
        author="Lead Hardware Engineer",
        version="1.0",
        system_overview="NXP i.MX91 based industrial evaluation platform.",
        power_architecture={
            "input_voltage": "5V USB-C / 12V DC",
            "total_power_budget": "15W",
            "rails": [
                {"name": "VDD_SOC_CORE", "voltage": 0.85, "max_current": 3.0, "regulator_type": "Buck", "source": "VIN", "sequence_order": 1},
                {"name": "VDD_DDR_1V1", "voltage": 1.1, "max_current": 1.5, "regulator_type": "Buck", "source": "VIN", "sequence_order": 2},
                {"name": "VDD_3V3", "voltage": 3.3, "max_current": 2.0, "regulator_type": "LDO", "source": "VIN", "sequence_order": 3},
            ],
        },
        subsystems_and_interfaces=[
            {
                "name": "LPDDR4 Interface",
                "type": "Memory Bus",
                "description": "32-bit LPDDR4 bus running at 2400 MT/s.",
                "signals": [
                    {"name": "DDR_CLK_P/N", "type": "Diff", "net": "DDR_CLK", "impedance": "80Ω Diff", "length_match_tol": "±2 mils"},
                ],
            }
        ],
        layer_stackup_summary={
            "layer_count": 18,
            "technology": "Rigid-Flex Multilayer",
            "dimensions": "150mm x 100mm",
            "layers": [
                {"number": 1, "name": "TOP", "type": "Signal", "copper_oz": "1.0", "thickness_mil": "1.4", "material": "Copper"},
                {"number": 2, "name": "GND1", "type": "Plane", "copper_oz": "1.0", "thickness_mil": "1.4", "material": "Copper"},
            ],
        },
        output_markdown_path=out_file,
    )
    assert result["status"] == "success"
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Hardware Design Document (HDD): FORJINN_POC - FRDM_IMX91" in content
    assert "VDD_SOC_CORE" in content
    assert "LPDDR4 Interface" in content


@pytest.mark.asyncio
async def test_generate_validation_test_plan(tmp_path):
    out_file = str(tmp_path / "Validation_Plan.md")
    result = await generate_validation_test_plan(
        project_name="FORJINN_POC",
        board_name="FRDM_IMX91",
        revision="A0",
        author="Validation Lead",
        power_rails=[
            {"name": "VDD_CORE", "voltage": 0.85, "test_point": "TP1", "sequence_step": 1},
            {"name": "VDD_3V3", "voltage": 3.3, "test_point": "TP2", "sequence_step": 2},
        ],
        clocks_and_resets=[
            {"name": "OSC_24M", "frequency": "24.000 MHz", "test_point": "TP_CLK1"},
        ],
        high_speed_interfaces=[
            {"name": "PCIe Gen4 x2", "lanes": "2x", "test_procedure": "Eye diagram compliance", "acceptance_threshold": "Open eye mask"},
        ],
        output_markdown_path=out_file,
    )
    assert result["status"] == "success"
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Hardware Bring-Up & Validation Test Plan" in content
    assert "TP-PWR-01" in content


@pytest.mark.asyncio
async def test_generate_board_user_guide(tmp_path):
    out_file = str(tmp_path / "User_Guide.md")
    result = await generate_board_user_guide(
        project_name="FORJINN_POC",
        board_name="FRDM_IMX91",
        revision="A0",
        author="Applications Team",
        board_description="User reference guide for the evaluation kit.",
        power_supply_specifications={"input_voltage_range": "5V DC", "power_connector_refdes": "J1"},
        connector_pinouts=[
            {
                "refdes": "J2",
                "name": "Debug Header",
                "pins": [{"pin": "1", "signal": "SWDIO", "voltage": "3.3V"}],
            }
        ],
        jumper_configuration_tables=[
            {"refdes": "J3", "function": "Boot Mode", "default": "1-2: QSPI Boot", "alternatives": "2-3: SD Boot"}
        ],
        output_markdown_path=out_file,
    )
    assert result["status"] == "success"
    assert os.path.exists(out_file)


@pytest.mark.asyncio
async def test_generate_traceability_matrix(tmp_path):
    out_file = str(tmp_path / "Traceability.md")
    result = await generate_traceability_matrix(
        project_name="FORJINN_POC",
        board_name="FRDM_IMX91",
        requirements=[
            {"req_id": "REQ-001", "description": "Support 18-layer Rigid-Flex", "schematic_sheets": "Sheet 1", "test_id": "TP-001", "compliance_status": "Compliant"},
        ],
        output_markdown_path=out_file,
    )
    assert result["status"] == "success"
    assert os.path.exists(out_file)
    assert result["total_requirements_tracked"] == 1

@pytest.mark.asyncio
async def test_hdd_tolerates_json_string_structured_args(tmp_path):
    # Regression: a calling model serialized dict/list args as JSON strings;
    # the tool must not crash with "'str' object has no attribute 'get'".
    out_file = str(tmp_path / "STR_HDD.md")
    result = await generate_hardware_design_document(
        project_name="P", board_name="B", author="a", version="1",
        system_overview="ov",
        power_architecture='{"input_voltage": "48V PoE", "rails": [{"name": "VDD_ARM", "voltage": "0.85"}]}',
        subsystems_and_interfaces='[{"name": "SoC", "type": "MSoC", "description": "d", "signals": []}]',
        output_markdown_path=out_file,
    )
    assert result["status"] == "success"
    assert os.path.exists(result["document_path"])


@pytest.mark.asyncio
async def test_user_guide_without_jumpers_or_scalar_rows(tmp_path):
    # Regression 1: jumper_configuration_tables was required; a board with no
    # jumpers is a valid guide. Regression 2: connector 'pins' was a prose
    # string and status/test/trouble rows were flat dicts with alt keys.
    out_file = str(tmp_path / "NOJMP_UG.md")
    result = await generate_board_user_guide(
        project_name="NXP", board_name="IPC", revision="A", author="a",
        board_description="d",
        power_supply_specifications={"input": "PoE 48V"},
        connector_pinouts=[
            {"connector": "30-pin shielded FPC", "pins": "MIPI CSI-2 D0-D3, sensor power, GND"},
            {"connector": "RJ45 magnetics", "pins": "GbE, 1kV isolation"},
        ],
        status_leds_and_switches=[{"function": "power + link", "led": "PWR_LED"}],
        test_points_index=[{"net": "VDD_ARM", "tp": "TP_PVDD"}],
        troubleshooting_matrix=[{"check": "PoE handshake", "symptom": "No power"}],
        # jumper_configuration_tables omitted on purpose
        output_markdown_path=out_file,
    )
    assert result["status"] == "success"
    assert result["total_connectors"] == 2
    text = open(result["user_guide_path"], encoding="utf-8").read()
    assert "30-pin shielded FPC" in text
    assert "PWR_LED" in text
    assert "No jumpers" in text
