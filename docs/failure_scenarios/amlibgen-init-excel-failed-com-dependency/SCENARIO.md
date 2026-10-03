# amlibgen-init-excel-failed-com-dependency

`generate_amm_library_from_spreadsheet` (AmLibGen.exe) fails with `[ERROR] Init excel failed` on this machine. ROOT CAUSE CONFIRMED and it is **NOT** a license problem and **NOT** a CLI flag error: AmLibGen opens the source spreadsheet through the **Microsoft Excel COM automation** path (`Excel.Application`), which is not registered / not working for legacy `.xls` files on this machine.

## What went wrong

AmLibGen.exe writes its own log file (`AMLibGen.log`, in its process's **launch** directory — the tool goes through `core.process.run_quick`, not `submit_job`, so it inherits this MCP server's own cwd rather than a per-job scratch dir). That log shows, verbatim:

1. it receives the **exact** command line correctly;
2. it **begins processing** the source spreadsheet;
3. it then fails with `[ERROR] Init excel failed`.

This sequence proves: the flags in `generate_amm_library_from_spreadsheet` are correct (the tool parsed and acted on them), and the failure is downstream, at the COM-initialization step that reads the legacy `.xls`.

## Evidence

- `core/tool_status.py` — `amlibgen` note: root cause confirmed, NOT a license issue; "consistent with a broken/missing Microsoft Excel COM automation dependency on this machine for reading legacy .xls files... Needs Excel installed/repaired on this machine (or a native .xlsx source, if AmLibGen supports one, to bypass what legacy .xls COM path is failing) to fully confirm end-to-end."
- `core/tool_status.py` status: `built_untested` / `known_blocked` — end-to-end never confirmed; blocked on the COM dependency, not on a license grant.
- `amm_tools.py` module docstring and `_LIBREOFFICE_CANDIDATES` / `_excel_com_available` / `_convert_xls_to_xlsx` exist specifically to detect/avoid this — the wrapper pre-checks for Excel COM and attempts LibreOffice/`xlrd`+`openpyxl` conversion of `.xls` → `.xlsx` when COM is unavailable.

## Affected code

- `sigrity_mcp/domains/platform/amm_tools.py:152-193` — `generate_amm_library_from_spreadsheet` (calls `run_quick("amlibgen", ...)`).
- `sigrity_mcp/domains/platform/amm_tools.py:46-57` — `_excel_com_available()` (the COM probe).
- `sigrity_mcp/domains/platform/amm_tools.py:125-149` — `_ensure_xlsx_readable` (the conversion / guard).
