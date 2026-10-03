# powersi-silent-success-runs-dir — Workarounds

## What works (confirmed)

- **Glob `runs/` for the artifact, not the job dir.** Right after the job ends, check `C:\Users\aicoe\Desktop\Sigrity\runs\` for a non-empty `*_S.*p` (and companions `_S.ckt`, `_Options.xml`, `_PowerSI.err`) with a timestamp newer than the job start. Prescribed literally in the SKILL: `Get-ChildItem C:\Users\aicoe\Desktop\Sigrity\runs -Filter *_S.*p` (and `_S.ckt`, `_Options.xml`, `_PowerSI.err`). A non-empty `*.sNp` newer than the job start = success.
- **Use the `<basename>_S.<N>p` naming to recover the exact filename.** The basename is the `.spd` name from `powersi_save_document` (NOT the `.brd`). Glob `C:\Users\aicoe\Desktop\Sigrity\runs\<basename>_S.*p` — `list_job_files` will never show it.
- **Invert the success check**: "PowerSI wrote real output iff a new `*_S.sNp` appeared in `runs/` with non-zero size." Do not require a non-zero log or a job-dir listing to contain the sNp.

## What was tried / ruled out

- `list_job_files(job_id)` as the success check: ruled out — it is a dead end for PowerSI output ("#1 mistake: concluding failure because list_job_files lacks an .sNp").
- Reading `run.log` / job `state` alone: ruled out — a perfect run and a missing-save failure produce the same 0-byte log and rc 0; neither discriminates.

## Notes

- This is the same "output next to / instead of the job dir" family as BroadbandSPICE (which writes next to its CWD, see `broadbandspice-output-next-to-cwd-not-jobdir`) and XtractIM (artifacts next to the `.ximx`). The general rule: verify against the *input file's* directory / configured workdir, never the MCP job dir.
