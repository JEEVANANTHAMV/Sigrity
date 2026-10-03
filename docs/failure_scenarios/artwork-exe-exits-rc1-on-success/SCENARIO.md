# artwork-exe-exits-rc1-on-success

- **tool**: `allegro_artwork` (`artwork.exe`, wrapped as `run_allegro_generate_artwork` in `sigrity_mcp/domains/cad/allegro_manufacturing_tools.py`)
- **status_category**: `unreliable_intermittent` (member of the "nonzero exit on successful work" family, manifest #96)
- **verified_workaround**: YES — judge by the produced `.art` files + `photoplot.log`, not the exit code

## What went wrong

`artwork.exe` exits with **rc 1 — "ARTWORK had warnings" — even on a fully successful Gerber generation run**. The suite's job tracker reports `state: "failed"` for a job that correctly produced real RS274X Gerber films. Treating rc 1 (or `state: "failed"`) as failure leads to needless retries or abandoning valid artwork output.

The rc 1 comes from genuinely non-fatal warnings the tool logs while falling back to sane defaults:
- `Can't open parameter file ... using default values` (no `art_param.txt` present)
- `Photoplot outline rectangle not found; using drawing extents`

Those warnings are default-fallbacks, not errors, yet they force the "had warnings" exit code.

## Evidence

- `core/tool_status.py` (`allegro_artwork` note): "NOTE: artwork.exe exits 1 ('ARTWORK had warnings') even on this fully successful run — the warnings ('Can't open parameter file ... using default values', 'Photoplot outline rectangle not found; using drawing extents') are the tool falling back to sane defaults, not errors — read photoplot.log/check for the actual .art files before treating a nonzero exit as failure."
- `.forjinn/skills/sigrity-cad/SKILL.md` (Task 4): "wait_for_job(job_id, 180) -> state:\"FAILED\", returncode:1  #  <-- SEE GOTCHA" and "GOTCHA: artwork.exe exits rc 1 ('had warnings') even on full success (missing art_param.txt / outline rect warnings). state:\"failed\" rc 1 here is normal. Judge by the .art files + photoplot.log."
- `allegro_manufacturing_tools.py` module docstring (lines 16–19): the same non-fatal warnings documented as "`artwork.exe` falling back to sane defaults ... — not errors."

## Verified-good artifacts (from the live runs — for what "success" looks like)

- `TOP.art` (12,209 B) and `BOTTOM.art` (6,036 B) in the job dir, real RS274X Gerber: `G04 File Format: Gerber RS274X`, `G04 Layer: ETCH/TOP`, `%FSLAX25Y25*MOIN*%`, real `G04`/`G01 ... D01*` plot data.
- `photoplot.log` → `SUMMARY: TOP created with warnings / BOTTOM created with warnings`.

## Symptoms a caller observes

- `wait_for_job(job_id)` → `state: "failed"`, `returncode: 1`
- `photoplot.log` shows films "created with warnings"
- `.art` files present and valid at the job dir
