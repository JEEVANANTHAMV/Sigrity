# Workarounds — amlibgen-init-excel-failed-com-dependency

## verified_workaround: None (no confirmed in-suite end-to-end fix)

The blocker is a missing/broken third-party dependency (Microsoft Excel COM automation), not a Sigrity license and not a CLI flag. No license grant fixes it.

## In-suite guard + fallback (present in code, not end-to-end confirmed)

`_ensure_xlsx_readable` (amm_tools.py:125) already handles the common case:

1. If the source is `.xlsx` → pass through.
2. If the source is `.xls` **and** Excel COM is available (`_excel_com_available()` via pywin32 `Excel.Application`) → pass the `.xls` straight to AmLibGen (Excel will read it).
3. If the source is `.xls` **and** Excel COM is NOT available → try to convert `.xls` → `.xlsx` WITHOUT Excel COM, in order of capability:
   - **LibreOffice headless** `soffice.exe --headless --convert-to xlsx` (looked up in `_LIBREOFFICE_CANDIDATES` + PATH);
   - then pure-Python **`xlrd<2.0` + `openpyxl`** reader/writer (works for the flat header-row/column layouts AmLibGen consumes).
4. If no converter can read the file → `raise LookupError` with an actionable message (install LibreOffice + `xlrd<2.0` + `openpyxl`, or install Microsoft Excel).

So if you do have LibreOffice or the Python readers, a `.xls` source gets converted to `.xlsx` and fed to AmLibGen. **Caveat:** even the `.xlsx` path is opened via COM (workbooks/sheets) per the module docstring, so on a truly Excel-less box the converted `.xlsx` may still hit the same COM wall — the robust fix is a working Excel (or a genuine non-COM AmLibGen path, which has not been confirmed to exist).

## What to actually do

- **To unblock on this machine:** install/repair Microsoft Excel (COM automation must register), OR install LibreOffice + `xlrd<2.0` + `openpyxl` in the Python environment so the conversion guard can at least produce a valid `.xlsx`.
- **Do not** treat `[ERROR] Init excel failed` as a license error — the AmLibGen.log shows the license/CLI stage passed; it is the COM init that died.
- **Watch the log location:** `AMLibGen.log` is written to the server's own cwd (run_quick), not the job dir — read it there, not via `list_job_files`.
