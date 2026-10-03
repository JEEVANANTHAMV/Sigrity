# Workarounds: `axlSaveDesign ?noCheck` Invalid Keyword Causes Silent Save Failure

## Verified Workaround

Replace every occurrence of:

```
(axlSaveDesign ?noCheck t)
```

with the correct string-option form:

```
(axlSaveDesign ?mode "nocheck")
```

or, when an explicit output path is needed:

```
(axlSaveDesign ?design "<path>" ?mode "nocheck")
```

All three known affected call sites are already fixed in the current source of this repo (spif_specctra_tools.py:110-112, allegro_placement_tools.py's zrouter save, aurora/scope_tools.py's workflow save) — callers of those tools do not need to do anything.

Evidence: `sigrity_mcp/core/tool_status.py:236-244` (root cause + fix, including the vendored-doc citation for the correct `?mode "nocheck"` form) and `:244-256` (live end-to-end verification: real output `.brd` genuinely different in size/sha1 from the source, read back correctly by independent `report.exe`).

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Use `(axlSaveDesign ?mode "nocheck")` (string option) instead of `(axlSaveDesign ?noCheck t)` | worked — save executes, real output file written, live-verified end-to-end with independent `report.exe` read-back | `sigrity_mcp/core/tool_status.py:236-256`; spif_specctra_tools.py:110-112 |
| 2 | Keep `(axlSaveDesign ?noCheck t)` and rely on the job's `state:"succeeded"`/rc 0 | didnt_work — save silently fails every time; only detectable via `.jrl` journal or independent file read-back | `sigrity_mcp/core/tool_status.py:236-243` |
| 3 | Drop the no-check option entirely and call `(axlSaveDesign)` with no extra args | not_tested_live — not part of the confirmed fix; the investigated and verified fix specifically is the `?mode "nocheck"` string form. Do not assume dropping the option is equivalent without verifying the save still behaves (skipping the db check may change save behavior/performance in ways not tested here) | — (no evidence found in the sources read) |

## Prevention

1. Grep any hand-written SKILL script or this repo for the literal string `?noCheck` — there is no valid `?noCheck` keyword in `axlSaveDesign`'s real signature (see the vendored `axlSaveDesign.txt`); if you find one, it is always a bug, not a valid alternative spelling.
2. Whenever an Allegro SKILL session reports `succeeded`/rc 0, independently verify the expected output file actually changed (size/sha1) via a read-back path that bypasses the SKILL session itself (`report.exe`, in this tool's case) — `state` is not a reliable save-completion signal for this class of failure.
3. If a save appears to have silently failed, check Allegro's **own** `.jrl` journal file (not `run.log`) for the exact string `*Error* axlSaveDesign: unrecognized keyword` — that specific line is the tell for this failure class.

## Remaining Gaps

- Nothing is automatically surfaced about `.jrl`-journal-only SKILL errors — no tool in this suite reads Allegro's `.jrl` journal and folds its contents into `run.log`, the job dir, or `get_job_status`. Detection of any `.jrl`-only failure (this one, or the sibling `spif-in-form-not-closed-silent-noop`) still requires a human/agent to know specifically to look there. No additional gap for this specific bug: all three known call sites are fixed in code and live-verified.