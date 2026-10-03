# dxf2a-nonzero-exit-on-success

- **tool**: `dxf2a` (`dxf2a.exe`, wrapped as `allegro_import_dxf` in `sigrity_mcp/domains/cad/allegro_import_tools.py`)
- **status_category**: `unreliable_intermittent` (member of the "nonzero exit on successful work" family, scenario #96 in the manifest)
- **verified_workaround**: YES — judge success by the job log line `dxf2a complete.` + the produced `.brd`, not the exit code

## What went wrong

`dxf2a.exe` exits with **returncode 1 even on a fully successful run**. The suite's job tracker therefore reports `state: "failed"` for a job that actually completed and wrote a valid board. A caller that trusts `wait_for_job`/`get_job_status` state (or return code) alone will conclude the import failed and either retry needlessly or give up on a valid artifact.

This is the same real pattern as `allegro_dbdoctor` (rc 1 on a clean check-only pass), `artwork.exe` (rc 1 with "had warnings"), and `specctra` (rc 4) — but it is dxf2a-specific in its exit value.

## Evidence

- `core/tool_status.py` (`dxf2a` note): "Two confirmed quirks: (1) exits with returncode 1 even on this fully successful run (log ends 'dxf2a complete.') — same nonzero-on-success pattern as allegro_dbdoctor/artwork.exe/specctra elsewhere in this suite, don't trust job state alone."
- `allegro_import_tools.py` module docstring (lines 22–27): "dxf2a.exe exits with returncode 1 even on this fully successful run (the job log's final line reads 'dxf2a complete.') ... Do not treat this tool's job `state == "failed"` as proof of failure; read the job log for 'dxf2a complete.' first."
- `README.md` (dxf bridge section): "dxf2a.exe exits with returncode 1 even on a fully successful run (same 'nonzero exit on real success' pattern already documented for allegro_dbdoctor/artwork.exe/specctra)."
- The live run that established this: `dxf2a.exe -u MILS -a 2 flag_l.cnv flag.dxf out.brd` (Cadence's own shipped tutorial sample, `doc/wb_tut/examples/Module_1/`) produced a real 203,456-byte `.brd`, independently re-read by `report.exe` (2 routing layers, drawing extents matching the DXF outline, `DRC State: UP TO DATE`), with the job log ending `dxf2a complete.` and rc 1.

## Symptoms a caller observes

- `wait_for_job(job_id)` → `state: "failed"`, `returncode: 1`
- Job log final line: `dxf2a complete.`
- Output `.brd` present at the requested path, valid (verified via `report.exe`).
