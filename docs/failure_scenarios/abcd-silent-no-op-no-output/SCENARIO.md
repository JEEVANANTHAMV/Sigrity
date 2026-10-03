# abcd Reports rc 0 But Produces No Output (Silent No-Op)

**Slug**: `abcd-silent-no-op-no-output`
**Tool(s) affected**: `run_touchstone_deembed` (`abcd.exe`, logical tool `abcd`)
**Status category**: `known_blocked`
**Pipeline stage**: extraction (utility solvers / Touchstone cascade & de-embed)

## Symptom

`abcd.exe` exits with `returncode 0` while producing **no output file, no result, and no error**. `run.log` shows only "Program started." — identical in appearance to a license or missing-input failure, but it is neither. The de-embed/cascade simply did not run, yet the job reports `succeeded`.

Historically this was the **default** behavior on every attempt and was misdiagnosed as "abcd is effectively broken / no input class works." That verdict was **wrong** — the mechanism was root-caused (see Root Cause), so the specific trailing-separator trigger is now fixed in the wrapper. However, rc 0 with no output **still occurs** whenever the invocation is malformed or inputs are missing/mismatched, and rc 0 **alone is never proof the de-embed actually ran**.

## Root Cause

Two distinct, both-critical properties of `abcd.exe`:

1. **Path resolution requires a trailing separator.** `abcd.exe` resolves its `-tsfile` / `-lefttsfile` / `-righttsfile` / `-duttsfile` arguments against the value of `-filepath` **only when that value ends in a trailing path separator** (`\` or `/`). Without one, it parses the command line and **silently does nothing** — rc 0, no output, no error, log shows only "Program started." `run_touchstone_deembed` now normalizes this automatically (appends `os.sep` if the path doesn't already end in a separator), so this specific trigger no longer needs a manual workaround.
   - See `sigrity_mcp/domains/extraction/utility_solvers.py:60-65` — "abcd.exe resolves -tsfile/-lefttsfile/-righttsfile/-duttsfile against -filepath's value ONLY when that value ends in a trailing path separator; without one it silently does nothing (rc 0, no output, no error) -- a real, confirmed defect in the tool itself, not a flag-name or quoting issue. Normalize here so every caller gets a working invocation with no need to remember this." and line 65: `filepath_arg = file_path if file_path.endswith(("\\", "/")) else file_path + os.sep`.

2. **rc 0 is emitted on a no-op too.** Because abcd exits 0 even when it did nothing, a `succeeded` job with `returncode: 0` is **not by itself proof the de-embed ran**. This is the durable, still-open half of the scenario: correct invocation is necessary but not sufficient — the output file must be independently verified.

Additional precondition (from `abcd.exe -help`, `utility_solvers.py:10-12`): input port count must equal output port count on every file, all files need matching frequency points and reference impedance. Violating these is another route to a silent no-op rather than a hard error.

## Evidence

- `sigrity_mcp/core/tool_status.py:776-790` (`abcd` note) — "Confirmed live for 2-port cascade and de-embed. The apparent silent no-op seen on every earlier attempt (rc 0, no output, no error, zero diagnostic output) was root-caused, not a broken binary: `abcd.exe` only resolves its file arguments against `-filepath`'s value when that value ends in a trailing path separator -- `run_touchstone_deembed` now normalizes this automatically… With a correct invocation, a real de-embed run produces a well-formed Touchstone output file whose values genuinely differ from the input (verified by reading the produced file, not just the exit code -- abcd exits 0 even on the no-op, so rc alone is never proof it ran)."
- `sigrity_mcp/domains/extraction/utility_solvers.py:16-24` (module docstring) — "(1) `-filepath`'s value MUST end in a trailing path separator. Without one, abcd parses the command line and silently does nothing -- no output file, no error, rc 0, log shows only 'Program started.'… (2) abcd exits 0 even on the silent no-op above, so rc 0 is never proof the de-embedding actually ran -- always verify with list_job_files/read_job_output_file that `dut_touchstone_file` exists and is non-empty."
- `.forjinn/skills/sigrity-extraction/SKILL.md:241-250` (Task 5) — "The earlier 'effectively broken, no input class works' verdict for this tool was wrong — root-caused and fixed. `abcd.exe` only resolves its `-tsfile`/`-lefttsfile`/`-righttsfile`/`-duttsfile` arguments against `-filepath`'s value when that value ends in a trailing path separator; without one it silently does nothing (rc 0, no output, no error, `run.log` stays 0 bytes). `run_touchstone_deembed` now normalizes this automatically…"
- `.forjinn/skills/sigrity-extraction/SKILL.md:263-265` — "**Still verify the output file, don't trust rc 0 alone**: abcd exits 0 even on a no-op, so a 'succeeded' job with `returncode: 0` is not by itself proof the de-embed ran — always confirm `dut_touchstone_file` exists and is non-empty."
- `sigrity_mcp/core/tool_status.py:72` — `"abcd": "confirmed_live"` (2-port RI path confirmed; the no-op property still applies to malformed/missing-input invocations).

## Pipeline Impact

Any caller that treats `state: succeeded` + `returncode: 0` from `run_touchstone_deembed` as success will silently propagate **no de-embedded / cascaded Touchstone** into downstream stages whenever the call is malformed (missing/extra separator, mismatched ports, mismatched frequency points or reference impedance, or missing input files). Because the failure is silent and indistinguishable from "did nothing because of a license problem" at the rc/log level, a pipeline can burn a full downstream stage operating on a stale or absent `.s2p` before noticing. This is the core "trust the artifact, not the return code" invariant of the extraction domain.
