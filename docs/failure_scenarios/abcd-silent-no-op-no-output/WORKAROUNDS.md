# Workarounds: abcd Reports rc 0 But Produces No Output (Silent No-Op)

## Verified Workaround

**Always verify the output artifact, never trust rc 0.** After `run_touchstone_deembed` + `wait_for_job`, call `list_job_files(job_id)` and/or `read_job_output_file(job_id, dut_touchstone_file)` and **confirm `dut_touchstone_file` exists and is non-empty** before treating the de-embed as done. This is the documented, live-confirmed guard: the confirmed-live 2-port run (SKILL.md Task 5) was verified by *reading the produced file*, whose well-formed Touchstone content ("! Cadence S Parameter Output From ABCD Version 1.0") and values genuinely differ from the input — not by the exit code.

The **trailing-separator** trigger that historically produced this no-op is **already fixed in-suite**: `run_touchstone_deembed` normalizes `file_path` to end in a separator (`utility_solvers.py:65`), so a caller does not need to manually append `\`/`/`. No caller-side workaround for that specific cause is required anymore. What is NOT fixed in-suite is the *other* half: rc 0 on no-op — that is a property of `abcd.exe` itself, so the output-file check is the only guard.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Normalize `file_path` to end in a trailing path separator (in-suite, automatic) | **worked / adopted.** With a correct invocation a real de-embed produces a well-formed Touchstone output whose values differ from the input. This is the root-cause fix, now baked into the wrapper. | `utility_solvers.py:60-65`; `tool_status.py:780-781` ("now normalizes this automatically, so no caller needs to remember it") |
| 2 | Verify the output file exists & is non-empty rather than trusting rc 0 | **worked / required.** Confirmed the 2-port de-embed actually ran by reading the produced file. This is the only durable guard against the still-open no-op property. | `SKILL.md:263-265`, `258-260`; `tool_status.py:782-785` |
| 3 | Ensure matching port counts / frequency points / reference impedance across all files | **precondition, not independently re-demonstrated.** Documented as required by `abcd.exe -help`; violating it is a distinct route to a silent no-op. | `utility_solvers.py:10-12` |

## Prevention

1. **Mandate the artifact check in the pipeline.** Any step consuming `run_touchstone_deembed` output must assert the `.s2p` exists and is non-empty (ideally parse the Touchstone header) before continuing. Do not branch on `state`/`returncode` for this tool.
2. **Use the wrapper, not raw `abcd.exe`.** The trailing-separator normalization only lives in `run_touchstone_deembed`; bypassing it (e.g. hand-rolling `abcd.exe -filepath <dir>` with no trailing separator) reproduces the silent no-op.
3. **Pre-flight the inputs.** Confirm all three files (`-tsfile`/`-lefttsfile`/`-righttsfile` + `-duttsfile`) exist, share the same port count, matching frequency points, and reference impedance before submitting — a mismatch yields the same rc 0 / no-output signature as a missing file.
4. **Treat `run.log == 0 bytes` + rc 0 as failure, not success**, for this tool specifically (same invariant as `abcd`: a successful de-embed writes a real output file and a non-trivial log line).

## Remaining Gaps

The wrapper fix removes the *most common* trigger (missing trailing separator) but does **not** change abcd's fundamental contract of exiting 0 on a no-op. There is no flag, retry, or in-suite mechanism that makes a malformed/missing-input invocation produce a non-zero exit or an error — `abcd.exe` is simply silent. Consequently this scenario is `known_blocked`: the **correct** call is confirmed live (2-port RI), but the **failure detection** responsibility is pushed entirely to the caller via artifact verification. Until Cadence changes abcd to fail loudly, every pipeline must implement its own output-existence check for this tool.
