# abcd `file_path` Must Be a Space-Free Directory (Path Quoting/Resolution Failure)

**Slug**: `abcd-file-path-spaces`
**Tool(s) affected**: `run_touchstone_deembed` (`abcd.exe`, logical tool `abcd`) — the trailing-separator / path-resolution handling of `-filepath`
**Status category**: `precondition_error`
**Pipeline stage**: extraction (utility solvers / Touchstone cascade & de-embed)

## Symptom

`abcd.exe` only resolves its `-tsfile` / `-lefttsfile` / `-righttsfile` / `-duttsfile` arguments against the value of `-filepath` **under two simultaneous preconditions**:
1. `-filepath`'s value ends in a **trailing path separator** (`\` or `/`), and
2. the path is handled as a single, well-formed unit — a `file_path` containing **spaces** is the precondition that makes this fragile.

When the `file_path` precondition is unmet, abcd **parses the command line and silently does nothing** — rc 0, no output, no error, `run.log` shows only "Program started." From the outside this looks identical to a license or missing-input problem; it is neither. A `file_path` with spaces (e.g. `C:\Users\aicoe\Desktop\Sigrity` is fine, but `C:\My Files\abcd`) is the specific precondition trigger: without the wrapper's normalization and without a space-free path, the `-filepath <path>` + relative-token combination does not resolve to a valid base directory and abcd no-ops.

## Root Cause

A **board/file/content precondition**, not a wrapper bug: `abcd.exe`'s path-resolution rule (resolve the file tokens against `-filepath`'s value **only when it ends in a trailing separator**) was empirically confirmed as a real defect in the tool itself — "not a flag-name or quoting issue." The suite encodes the **trailing-separator** half defensively in `run_touchstone_deembed` (it appends `os.sep` automatically). But a **space-free input directory** remains a caller-side precondition: a path containing spaces is unsafe territory for this tool's token-against-base-directory resolution, and the documented mitigation is to stage the inputs under a **space-free directory** and pass that as `file_path`.

The two halves are distinct:
- **Trailing separator** → already normalized in-suite (caller need not remember).
- **Space-free directory** → caller precondition (caller MUST ensure the `file_path` directory has no spaces).

## Evidence

- `sigrity_mcp/domains/extraction/utility_solvers.py:60-65` (`run_touchstone_deembed`) — "abcd.exe resolves -tsfile/-lefttsfile/-righttsfile/-duttsfile against -filepath's value ONLY when that value ends in a trailing path separator; without one it silently does nothing (rc 0, no output, no error) -- a real, confirmed defect in the tool itself, not a flag-name or quoting issue. Normalize here so every caller gets a working invocation with no need to remember this." and `filepath_arg = file_path if file_path.endswith(("\\", "/")) else file_path + os.sep`.
- `sigrity_mcp/domains/extraction/utility_solvers.py:17-21` (module docstring) — "(1) `-filepath`'s value MUST end in a trailing path separator. Without one, abcd parses the command line and silently does nothing -- no output file, no error, rc 0, log shows only 'Program started.' This looks identical to a license or input-file problem from the outside; it is neither."
- `sigrity_mcp/core/tool_status.py:776-783` (`abcd` note) — same trailing-separator root cause: "`abcd.exe` only resolves its file arguments against `-filepath`'s value when that value ends in a trailing path separator -- `run_touchstone_deembed` now normalizes this automatically, so no caller needs to remember it."
- `SCENARIOS.md:116` (manifest) — "73 | abcd-file-path-spaces | file_path must be space-free dir | precondition_error | YES (space-free dir)".
- `.forjinn/skills/sigrity-extraction/SKILL.md:251-256` (Task 5) — the confirmed-live call uses `file_path="C:\Users\aicoe\Desktop\Sigrity\runs\t5_abcd"` — a **space-free** directory — with bare filenames (`cap.s2p`, `dut.s2p`), consistent with the space-free precondition.

## Pipeline Impact

A caller that stages its Touchstone inputs under a directory whose path contains spaces and passes that as `file_path` will hit the **silent no-op** (rc 0, no output, "Program started." only) and misread it as a license/input failure — the same downstream harm as `abcd-silent-no-op-no-output`, but with a preventable, deterministic trigger. Because the failure is silent and rc 0, a pipeline that only checks `state`/`returncode` will propagate a missing/stale `.s2p` downstream. The precondition is cheap to enforce (use a space-free path) and, together with the automatic trailing-separator normalization, removes this whole class of silent no-op for abcd.
