# Workarounds: Extracta 'Illegal view name'

## Verified Workaround

Use `run_allegro_extracta` with the **fixed** `EXTRACTION_TEMPLATES` (the version currently in `sigrity_mcp/domains/cad/allegro_extraction_tools.py`). The built-in templates now emit real, Cadence-documented view/field keywords sourced from `share/pcb/text/views/*.txt`: `bom`→`COMPONENT`, `nets`→`LOGICAL_PIN`, `components`→`COMPONENT`, `pins`→`COMPONENT_PIN`, `testpoints`→`COMPOSITE_PAD`, `drc`→`DRC_ERROR`. Confirmed live end-to-end against the real sample board (`fd.brd`) for all 5 built-in view types: every one returns `state=succeeded`, `returncode=0`, with real non-empty extracted data (e.g. the `drc` view correctly listed real Package-to-Package and Line-to-Line spacing DRC violations on the sample board).

Evidence: `sigrity_mcp/core/tool_status.py:619-624` — "LIVE-VERIFIED end-to-end against the real sample board (fd.brd) for all 5 built-in view types (bom/nets/components/pins/drc): every one now returns state=succeeded, returncode=0, with real non-empty extracted data (e.g. drc view correctly listed real Package-to-Package and Line-to-Line spacing DRC violations on the sample board)."

Do NOT call this tool with an unpatched/older copy of `allegro_extraction_tools.py` — that reproduces the 100% `returncode=2` / `Illegal view name` failure. If for any reason you must regenerate a command file, copy a real file from `share/pcb/text/views/` rather than inventing keywords (extracta's command-file syntax is not self-explanatory, and wrong keywords fail silently at the job-result level).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Replace `EXTRACTION_TEMPLATES` keywords with real ones from `share/pcb/text/views/*.txt` | worked | `sigrity_mcp/core/tool_status.py:615-628` |
| 2 | Read the real `extract.log` from the job's own `job_dir` (not beside board/output file) to see the true error | worked (diagnosis only — the tool still failed until templates fixed) | `sigrity_mcp/core/tool_status.py:610-614`; `.forjinn/skills/sigrity-cad/SKILL.md:409-415` (Task 8: "`list_job_files(job_id)` + `read_job_output_file(job_id, relative_path="extract.log")` ... is the only way to see why") |
| 3 | Trust `run.log`/`returncode` alone | didnt_work — run.log only says "Extract ended ... see extract.log for errors" with no path; `returncode=2` with no detail | `sigrity_mcp/core/tool_status.py:609-613` |
| 4 | Keep the original invented view/field keywords (`NETS`, `COMPONENTS`, ...) | didnt_work — `ERROR(SPMHDX-10): Illegal view name.` for every view_type, 100% | `sigrity_mcp/domains/cad/allegro_extraction_tools.py:52-67`; `sigrity_mcp/core/tool_status.py:600-608` |

## Diagnosis Rule (the real fix for "why can't I see the error")

On **any** `allegro_extracta` failure, locate the real error via:

1. `list_job_files(job_id)` — confirm `extract.log` exists in the job dir.
2. `read_job_output_file(job_id, relative_path="extract.log")` — read the actual `ERROR(SPMHDX-*)` line.

Do **not** look beside `board_file`/`output_file`, and do **not** rely on `run.log` (it only points at `extract.log` without a path). `extract.log` is written to the submitted job's own `job_dir` (its process cwd), which is why this failure went undiagnosed across many calls.

## Prevention

1. Source all extracta view/field keywords from Cadence's own shipped command files in `share/pcb/text/views/` — never invent them. The suite now does this in `EXTRACTION_TEMPLATES`.
2. If a caller needs a view this tool does not cover (a `view_type` not in `{bom,nets,components,pins,testpoints,drc}`), prefer copying another real file from `share/pcb/text/views/` over guessing — per the tool note, "extracta.exe's own error reporting for bad keywords is silent at the job-result level (run.log/returncode alone never show it)."
3. Always check the job's own `job_dir/extract.log` (never a guessed path) when `run_allegro_extracta` fails.
4. Downstream helpers that wrap this tool (e.g. `allegro_get_board_extent_points`, which calls `view_type="pins"`) inherit this failure, so a failure in the helper means the inner extraction job failed — check `extract.log` there.

## Remaining Gaps

None outstanding for the wrapped views. The fix is live-verified for all 5 built-in view types plus `pins` (used by `allegro_get_board_extent_points`). The only residual caution: any **custom** command content (`custom_command_content` / `custom_command_file`) still depends on the caller using real extracta vocabulary, and the tool will not surface keyword errors at the job-result level — the caller must inspect `extract.log`.
