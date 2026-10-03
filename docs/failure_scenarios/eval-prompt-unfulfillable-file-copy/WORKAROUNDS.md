# Workarounds: Eval Prompt Required a File Copy That Had No Tool

## Verified Fix (in-suite — `tool_bug_fixed`)

Two coordinated fixes, both landed:

1. **Add the missing file tool.** `copy_file(source_file, destination_file, overwrite=...)` (+ `move_file`, `delete_file`) now exist in `sigrity_mcp/domains/platform/file_tools.py` (lines 22-60), plain `shutil`-based, synchronous (fast, so not tracked as a background job). This makes a "copy the file first" step *actually callable* when a task genuinely needs fresh staging.
2. **Rewrite the prompts to be directly satisfiable.** Per the lesson logged in README:889-891, **every new task prompt points at an already-staged real file under `runs/` rather than asking the model to copy one first.** The current `TASKS` (eval_e2e.py:184-248) all use pre-staged paths (`runs/cad_smoke/board.brd`, `runs/celsius3d_smoke/case.3dth`, the shipped `.brd` sample "directly"). This removes the unfulfillable instruction at the source.

Manifest row 106 marks this `verified_workaround: YES (pre-staged inputs; direct paths)`.

Between these two, the scenario is fully resolved: the model either has a real `copy_file` (when it needs to stage) or is given an already-staged path (when it doesn't).

## What this does / doesn't fix

- **Fixes**: the unfulfillable instruction (run-one 4/6 → 6/6, and 12/12 this pass, README:881, 892-894) and the absence of any in-suite copy/move/delete primitive.
- **Doesn't change**: the broader discipline that shipped samples are **read-only and must not be modified in place** (SKILL.md:128-129). Even now, a task that *does* need in-place-safe staging should use `copy_file` (now available) or a pre-staged path — the "never overwrite a shipped sample in place" rule stands.

## Workarounds / mitigations (with outcomes)

| # | Approach | Outcome | Evidence |
|---|----------|---------|----------|
| 1 | (run one) prompt says "copy the file first", no copy tool exists | **unfulfillable** — model can't perform the step; contributes to run-one 4/6 | file_tools.py:1-11 (docstring); README:873-877 |
| 2 | Add `copy_file`/`move_file`/`delete_file` to the platform domain | **makes the step callable** when fresh staging is genuinely needed | file_tools.py:22-60 |
| 3 | Pre-stage inputs under `runs/` and point prompts at direct paths | **removes the need to copy at all** — the current, adopted pattern for all new tasks | README:889-891; eval_e2e.py:184-248 |
| 4 | Tighten the system prompt (don't fabricate success; cite tool returns) | **reinforces honest behavior** so a missing-ops doesn't turn into a false "done" | eval_e2e.py:175-176 (system prompt tail) |

## Prevention

1. **Before adding an eval task, check that every operation the prompt implies has a registered tool.** If the prompt says "copy/stage," confirm `copy_file` exists (it does now) or pre-stage the input instead.
2. **Prefer pre-staged, direct-path inputs for read-only samples** (the current `TASKS` pattern) — fewer moving parts, no staging step for the model to get wrong, and no in-place mutation of shipped samples.
3. **When a task does require staging, use `copy_file(source_file=..., destination_file=..., overwrite=true)`** (now available) and write to `runs/`, never in place (SKILL.md:128-129).
4. **Keep the system prompt directing honest, cite-the-return answers** so an unfulfillable or partially-fulfillable prompt surfaces as a faithful "couldn't stage" rather than a fabricated success.

## Remaining Gaps

Resolved for the eval: no current task prompt requires a copy that has no tool, and the file tools exist when real staging is needed. The one standing discipline to keep enforcing: **ship samples are read-only** — staging must go to `runs/` (or a job scratch dir), and the `copy_file`/pre-stage pattern is the sanctioned way. There is no gap in the *tool surface* any more; the only residual risk is a *future* prompt re-introducing an unsatisfied operation, so the "every implied op has a tool" check should remain part of adding a new task.