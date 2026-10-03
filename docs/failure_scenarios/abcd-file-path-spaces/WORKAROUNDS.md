# Workarounds: abcd `file_path` Must Be a Space-Free Directory

## Verified Workaround

**Use a space-free directory for `file_path`.** Stage all Touchstone inputs (and the DUT output) under a directory whose full path contains **no spaces**, and pass that directory as `file_path` to `run_touchstone_deembed`. The confirmed-live Task 5 call does exactly this: `file_path="C:\Users\aicoe\Desktop\Sigrity\runs\t5_abcd"` with bare filenames (`cap.s2p`, `dut.s2p`), producing a well-formed de-embedded `.s2p` whose values genuinely differ from the input.

The **trailing-separator** half of abcd's path-resolution rule is **already handled in-suite** — `run_touchstone_deembed` appends `os.sep` when the path doesn't end in a separator (`utility_solvers.py:65`), so the caller does not need to remember that. What the caller **must** still guarantee is the **space-free path** precondition; the wrapper does not rewrite/sanitize a path containing spaces.

Also, as with every abcd call, **verify the output `.s2p` exists and is non-empty** (rc 0 does not prove the de-embed ran — see `abcd-silent-no-op-no-output`).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Pass a **space-free** `file_path` directory with bare file names | **worked.** Real 2-port Murata `.s2p` cascade/de-embed confirmed live; produced well-formed Touchstone output differing from input. | `SKILL.md:251-260` (Task 5, `runs/t5_abcd`); `tool_status.py:776-783` |
| 2 | Let the wrapper normalize the trailing separator (automatic) | **worked / adopted.** Removes the "missing separator" variant of the silent no-op without caller effort. | `utility_solvers.py:60-65` |
| 3 | Pass a `file_path` containing spaces | **precondition violation → silent no-op risk** (rc 0, no output, "Program started." only). This is the failure the workaround exists to avoid. | `utility_solvers.py:17-21`, `:60-64`; `SCENARIOS.md:116` |

## Prevention

1. **Always stage abcd inputs under a space-free directory** (e.g. under `runs/<job>` with an ASCII, unspaced leaf name) before calling `run_touchstone_deembed`. If the source design lives under a space-containing path, `copy_file` the `.s2p` inputs (and choose the output name) into a space-free scratch dir first.
2. **Pass `file_path` as a directory and file names as bare tokens** (`cap.s2p`, `dut.s2p`), matching the confirmed-live shape — abcd resolves the tokens against the `-filepath` value.
3. **Don't rely on the wrapper to fix spaces** — it normalizes the trailing separator only. A space in the path is a caller precondition.
4. **Verify the output file** (exists + non-empty) after `wait_for_job`, never trust rc 0 alone.

## Remaining Gaps

The trailing-separator cause is fully handled in-suite; the **space-free-path** cause is a **caller precondition with no in-suite enforcement** — `run_touchstone_deembed` does not validate or rewrite a space-containing `file_path`, so a caller that ignores it still gets the silent no-op. An in-suite guard (e.g. asserting `file_path` is space-free, or auto-relocating inputs to a sanitized scratch dir) would close this completely. Until then, treat "space-free directory" as a hard, documented precondition for every abcd call, and pair it with the output-file verification so the two silent-failure siblings (`file-path-spaces` and `silent-no-op-no-output`) are both guarded.
