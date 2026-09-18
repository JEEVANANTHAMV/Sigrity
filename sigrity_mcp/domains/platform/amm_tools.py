"""Analysis Model Manager (AMM) tools — the confirmed cross-tool technology/model
library layer in Sigrity X (research: identical AMM UI/library format regardless of
which Sigrity tool launches it — PowerDC, PowerSI, PowerTree, and XtractIM all read/
write the same .amm/.ammx libraries).

`AmLibGen.exe`'s exact flags below are transcribed verbatim from
doc/anmodmgr/chap1a_re_Save_Models_in_the_AMM_Format_using_the_Command-Line_Interface.html
(confirmed present at tools/bin/AmLibGen.exe), not guessed.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.process import run_quick
from sigrity_mcp.mcp_app import mcp


@mcp.tool
async def generate_amm_library_from_spreadsheet(
    source_file: str,
    destination_library: Optional[str] = None,
    worksheet: Optional[str] = None,
    header_row: Optional[int] = None,
    component_type: Optional[Literal["Inductor", "Resistor"]] = None,
    resistance_unit: Optional[Literal["Ohm", "mOhm", "uOhm", "nOhm"]] = None,
    inductance_unit: Optional[Literal["H", "mH", "nH", "uH"]] = None,
    max_current_unit: Optional[Literal["A", "mA", "nA", "uA"]] = None,
    on_duplicate_part_number: Optional[Literal["KeepTheFirst", "ReplaceWithNew"]] = None,
    column_mapping_file: Optional[str] = None,
    external_node_assignment: Optional[Literal["Series", "Shunt"]] = None,
) -> dict:
    """Build/populate an AMM (.amm) component library from a spreadsheet of R/L/S-parameter model data.

    Wraps `AmLibGen.exe -b`, Sigrity's real batch tool for converting an Excel-based
    parts library into the Analysis Model Manager format that PowerDC, PowerSI,
    PowerTree, and XtractIM all share. Use this to onboard a vendor/component
    spreadsheet (decap, inductor, resistor, or S-parameter models) into a reusable
    AMM library once, instead of re-entering the same models per-tool.

    `source_file` must be an absolute path to the .xls/.xlsx spreadsheet.
    `destination_library` must end in `.amm` (the CLI does not support writing `.ammx`);
    if omitted, AmLibGen writes alongside the source file using its default naming.
    `on_duplicate_part_number` defaults to `KeepTheFirst` (existing library entries win)
    if not specified — pass `ReplaceWithNew` to overwrite matching part numbers instead.
    """
    args = ["-b", "-SourceFile", source_file]
    if worksheet:
        args += ["-WorkSheet", worksheet]
    if header_row is not None:
        args += ["-HeaderRow", str(header_row)]
    if component_type:
        args += ["-ComponentType", component_type]
    if resistance_unit:
        args += ["-Runit", resistance_unit]
    if inductance_unit:
        args += ["-Lunit", inductance_unit]
    if max_current_unit:
        args += ["-MaxCurrentUnit", max_current_unit]
    if on_duplicate_part_number:
        args += ["-OptionFromDupPartNumber", on_duplicate_part_number]
    if column_mapping_file:
        args += ["-ColumnMapping", column_mapping_file]
    if external_node_assignment:
        args += ["-ExternalNodeAssignment", external_node_assignment]
    if destination_library:
        args += ["-DestinationLibrary", destination_library]

    result = await run_quick("amlibgen", args, timeout=120.0)
    result["destination_library"] = destination_library
    return result
