"""Analysis Model Manager (AMM) tools — the confirmed cross-tool technology/model
library layer in Sigrity X (research: identical AMM UI/library format regardless of
which Sigrity tool launches it — PowerDC, PowerSI, PowerTree, and XtractIM all read/
write the same .amm/.ammx libraries).

`AmLibGen.exe`'s exact flags below are transcribed verbatim from
doc/anmodmgr/chap1a_re_Save_Models_in_the_AMM_Format_using_the_Command-Line_Interface.html
(confirmed present at tools/bin/AmLibGen.exe), not guessed.
"""

from __future__ import annotations

import os
import subprocess
from typing import Literal, Optional

from sigrity_mcp.core.process import run_quick
from sigrity_mcp.mcp_app import mcp

# AmLibGen.exe opens the source spreadsheet through Excel COM (Excel.Application), so on
# a machine without Excel installed it dies with "[ERROR] Init excel failed" before it
# even touches a .xls. .xlsx sources are likewise opened via COM (workbooks, sheets), so
# the same COM dependency applies. Both paths therefore need Excel — the only way to run
# AmLibGen without Excel is to pre-convert the workbook with a non-COM reader and pass
# AmLibGen a .xlsx, which still fails on .xls-style COM-less installs; the robust fix is
# to convert to .xlsx when we can, and surface a clear error when we cannot.
_LIBREOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


def _find_soffice() -> Optional[str]:
    """Locate a soffice.exe (LibreOffice headless converter) if installed."""
    for candidate in _LIBREOFFICE_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    path_var = os.environ.get("PATH", "")
    for entry in path_var.split(os.pathsep):
        candidate = os.path.join(entry, "soffice.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


def _excel_com_available() -> bool:
    """True if an Excel.Application COM object can be created (pywin32)."""
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        app = win32com.client.DispatchEx("Excel.Application")
        app.Quit()
        return True
    except Exception:  # noqa: BLE001 - any COM failure means Excel is unavailable
        return False


def _convert_xls_to_xlsx(source: str, target: str) -> Optional[str]:
    """Convert `source` .xls to a sibling/`target` .xlsx without using Excel COM.

    Strategy (most-capable first):
      1. LibreOffice headless (`soffice --headless --convert-to xlsx`).
      2. Pure-Python: `xlrd` (legacy BIFF reader) + `openpyxl` writer. Works for the
         flat header-row / column layouts AmLibGen consumes (numeric + text cells).
         Requires `xlrd<2.0` (2.x dropped BIFF support) and `openpyxl`.
    Returns `target` on success, None if no converter could read the file.
    """
    soffice = _find_soffice()
    if soffice:
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    "xlsx",
                    "--outdir",
                    os.path.dirname(target) or ".",
                    source,
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            out_name = os.path.splitext(os.path.basename(source))[0] + ".xlsx"
            out_path = os.path.join(os.path.dirname(target) or ".", out_name)
            if out_path != target and os.path.isfile(out_path):
                os.replace(out_path, target)
            if os.path.isfile(target):
                print(f"[amm] converted {source} -> {target} via LibreOffice")
                return target
        except Exception as exc:  # noqa: BLE001
            print(f"[amm] LibreOffice conversion failed ({exc}); trying pure-Python")

    try:
        import xlrd  # type: ignore  # noqa: F401
        import openpyxl
    except Exception as exc:  # noqa: BLE001
        print(f"[amm] pure-Python conversion unavailable ({exc})")
        return None

    try:
        book = xlrd.open_workbook(source)
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for sheet in book.sheets():
            ws = wb.create_sheet(title=sheet.name[:31])
            for r in range(sheet.nrows):
                for c in range(sheet.ncols):
                    cell = sheet.cell(r, c)
                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        continue
                    ws.cell(row=r + 1, column=c + 1, value=cell.value)
        wb.save(target)
        print(f"[amm] converted {source} -> {target} via xlrd+openpyxl")
        return target
    except Exception as exc:  # noqa: BLE001
        print(f"[amm] pure-Python conversion failed: {exc}")
        return None


def _ensure_xlsx_readable(source_file: str) -> str:
    """Return a spreadsheet path AmLibGen can open, converting .xls to .xlsx first when
    Excel COM is unavailable. Passes .xlsx (and already-convertible .xls) through as-is.
    Raises LookupError with an actionable message when conversion is impossible."""
    lower = source_file.lower()
    if lower.endswith(".xlsx"):
        return source_file
    if not lower.endswith(".xls"):
        return source_file
    if os.path.splitext(source_file)[1].lower() == ".xls" and _excel_com_available():
        # Excel itself is present, so AmLibGen can read the .xls directly.
        return source_file
    target = os.path.splitext(source_file)[0] + ".xlsx"
    if os.path.isfile(target):
        return target
    converted = _convert_xls_to_xlsx(source_file, target)
    if converted:
        return converted
    raise LookupError(
        f"Cannot process '{source_file}' without Microsoft Excel. AmLibGen reads "
        "spreadsheets through the Excel.Application COM object, which is not "
        "registered on this machine. Install LibreOffice (for headless .xls -> .xlsx "
        "conversion) and install `xlrd<2.0` + `openpyxl` in the Python environment, or "
        "install Microsoft Excel."
    )


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
See `.forjinn/skills/sigrity/SKILL.md` for the full verified playbook, pitfalls, and a live example."""
    source_file = _ensure_xlsx_readable(source_file)
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
