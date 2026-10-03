# PowerSI on a Non-.spd Design Without `powersi_save_document`: rc 0, Empty Options.xml Only

**Slug**: `powersi-missing-save-document-empty-options`
**Tool(s) affected**: `powersi_run_session` after `start_powersi_session` on a non-`.spd` design (e.g. `.brd`) without an intervening `powersi_save_document`
**Status category**: `precondition_error`
**Manifest**: #65

## What went wrong

When `start_powersi_session` opens a **non-`.spd`** design (a `.brd` opened through PowerSI's built-in BRDExtractor/SPDIF Translator) and `powersi_run_session` is called **without** an intervening `powersi_save_document`, the run does **NOT** error out. The process still exits rc 0, but it **silently writes only** an empty `<design>_Options.xml` and `<design>_PowerSI.err`, with **no `.spd` and no `.sNp`**.

The tool docstring documents the rule: "Call powersi_save_document right after opening a non-`.spd` design and before adding any other steps — PowerSI refuses to simulate a design that hasn't been saved to native SPD form first." The failure is *silent*: no exception, no nonzero rc, no error text — this is a genuine precondition gap, and the "failure" is only detectable by its output-fingerprint.

Order matters in the composed macro: `sigrity::save` must be **line 2** of the macro (immediately after `sigrity::open document`), *before* `set_frequency_sweep` / `add_ports_auto`. Calling `powersi_save_document` after those steps is "the order that silently produces no output."

The empty-options-only signature (`_Options.xml` + `_PowerSI.err`, no `.spd`, no `.sNp`) is the fingerprint of the missing save — and because PowerSI's silent-success fingerprint (0-byte `run.log` + rc 0) is identical, the only discriminator is the artifact set in `runs/` (see `powersi-silent-success-runs-dir`).

## Evidence

- `sigrity_mcp/domains/si/powersi_tools.py` (module docstring, lines 15–20): "a real Allegro/OrCAD 22.1 `.brd` file ... opens directly via start_powersi_session, auto-translated by PowerSI's built-in 'BRDExtractor'. Call powersi_save_document right after opening a non-`.spd` design and before adding any other steps — PowerSI refuses to simulate a design that hasn't been saved to native SPD form first."
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 3, "Error hit"): "The omitted negative test (calling powersi_run_session on an opened .brd WITHOUT powersi_save_document) does NOT return a tool error — the process still exits rc 0 but silently writes only an empty task3_board_Options.xml and task3_board_PowerSI.err with no .spd and no .sNp. That empty-options-only signature is the fingerprint of the missing save; fix = re-run with powersi_save_document right after start_powersi_session."
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 3, "#1 mistake"): "Skipping powersi_save_document after opening a non-.spd design. It must be the first composed step (line 2 of the macro, immediately after sigrity::open document) — calling it after set_frequency_sweep/add_ports_auto is the order that silently produces no output."
- `.forjinn/skills/sigrity-si/SKILL.md` (gotcha #2): "Non-.spd input (e.g. a .brd) REQUIRES powersi_save_document first. ... Call it immediately after start_powersi_session and before any other step. Omit it on a design that is already .spd."
- Positive live confirmation (same flow WITH save): produced `task3_board.spd` (237 KB) + `task3_board_<ts>_S.s68p` (~70 MB, 68 ports) + `_S.ckt` (9 KB) + `_Options.xml` (27 KB) — all in `runs/`, job `succeeded` rc 0.

## Symptoms a caller observes

- `wait_for_job(job_id)` → `state: "succeeded"`, returncode 0
- `runs/` contains only an **empty** `<design>_Options.xml` (and `<design>_PowerSI.err`); **no** `.spd`, **no** `.sNp`, **no** `_S.ckt`
- No tool error raised anywhere in the chain
