# Eval Prompt Asked the Model to "Copy the File First" — No Copy Tool Existed

**Slug**: `eval-prompt-unfulfillable-file-copy`
**Tool(s) affected**: the evaluation task *prompts* in `scripts/eval_e2e.py` (run one) and the suite's (then-absent) file-copy capability; **fixed** by adding `copy_file`/`move_file`/`delete_file` (`sigrity_mcp/domains/platform/file_tools.py`) and rewriting the prompts to use pre-staged paths
**Status category**: `tool_bug_fixed` (per manifest row 106) — a harness/prompt gap, fixed
**Pipeline stage**: eval task design (and the platform file-tool surface it exposed)

## Symptom

In the **first** end-to-end evaluation, **two task prompts told the model to "copy the file first"** into a scratch location before running a tool. But the suite had **no file-copy tool at all**, so that instruction was **unfulfillable** — the model had no `copy_file` to call. The model either (a) burned turns looking for / failing to perform a copy, or (b) proceeded without staging, producing spurious tool errors and muddling the "did the model do the right thing" signal. The net effect in run one contributed to the **4 of 6** task+endpoint combinations that failed to reach a final answer.

This was a **prompt/surface mismatch, not a model or Sigrity-tool bug**: the task asked for an operation the tool surface did not provide.

## Root Cause

- The tasks assumed a "stage the read-only sample into a scratch dir first" step (a reasonable, idiomatic Sigrity workflow — the SKILL.md assets section: "Copy read-only sources into the job scratch ... `copy_file(src,dst,overwrite)` to stage", SKILL.md:128-129).
- At the time of the first run, **no such tool was registered** on the server, so the model's `client.call_tool` had no copy tool to invoke. (The SKILL.md guidance referenced `copy_file`, but the tool did not yet exist in the suite — that is the gap the first run exposed.)
- The fix that both closes the gap and the prompt problem is in **`sigrity_mcp/domains/platform/file_tools.py`**: `copy_file(source_file, destination_file, overwrite)` (+ `move_file`, `delete_file`), whose module docstring states the motivation verbatim.

## Evidence

- `sigrity_mcp/domains/platform/file_tools.py:1-11` (module docstring, verbatim): "Generic filesystem utility tools — copy/move/delete a file. **Added after the multi-model end-to-end evaluation (`scripts/eval_e2e.py`) repeatedly hit the same wall**: several realistic task prompts needed to stage a read-only source file (a shipped Cadence sample, an existing design) into a scratch working directory before running a tool against it, and **this suite had no way to do that** — see the README's 'What this caught' notes on task prompts that asked the model to 'copy the file first.' These three tools are plain, synchronous `shutil`-based filesystem operations (not background jobs...)."
- `sigrity_mcp/domains/platform/file_tools.py:22-33` — the now-exists `copy_file(source_file, destination_file, overwrite=...)` (shutil.copy2-based), i.e. the tool the first-run prompt needed.
- `README.md:873-881` — "Both root causes were in the eval harness/task prompts, not the tools: the harness's own 90s per-call timeout... and **two task prompts asked the model to 'copy the file first' into a scratch location — but this suite has no file-copy tool, so that instruction was unfulfillable.** After raising the timeout, making timeout errors self-identifying, **fixing the prompts**, and tightening the system prompt: 6/6 succeeded."
- `README.md:889-891` — the fix adopted for the new task set: "**Learning from the prior pass's 'no file-copy tool' pitfall, every new task prompt points directly at an already-staged real file under `runs/` rather than asking the model to copy one first.**"
- `scripts/eval_e2e.py:184-248` (current `TASKS`) — confirmation the current prompts use **pre-staged** paths: e.g. `cad_drc_and_placement` uses "a real, already-staged Allegro board file at `C:/Users/aicoe/Desktop/Sigrity/runs/cad_smoke/board.brd`" and `thermal_celsius3d_signoff` uses "an already-staged Celsius3D thermal project at `C:/Users/aicoe/Desktop/Sigrity/runs/celsius3d_smoke/case.3dth`". No prompt asks the model to copy first.

## Pipeline Impact

While the prompt asked for an unfulfillable copy step (and no copy tool existed), the model could not complete the intended staging, which (a) consumed turns, (b) produced spurious tool-call errors, and (c) corrupted the eval's "did the model do the right thing" metric — part of why run one was 4/6. It was a **task-design defect** that made a valid workflow impossible. The dual fix (add `copy_file` *and* pre-stage inputs so the prompt doesn't require a copy at all) removes the unfulfillable instruction and restores a faithful signal.