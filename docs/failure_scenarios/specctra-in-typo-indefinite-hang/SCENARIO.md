# `specctra in` Two-Word Typo Causes Indefinite Hang

**Slug**: `specctra-in-typo-indefinite-hang`
**Tool(s) affected**: `run_allegro_specctra_import` (spif_specctra_tools.py)
**Status category**: `tool_bug_fixed`
**Pipeline stage**: specctra routing import

## Symptom

`run_allegro_specctra_import` previously emitted the script-replay line `specctra in "<path>"` — **two words, a space** — which is not a real Allegro command. This put Allegro's command dispatcher into a permanently stuck state: an **indefinite hang** at exactly 0% CPU, with **zero** new dialog windows and `run.log` frozen at the 3-line startup banner forever, no further output of any kind. Reproduced 3-for-3.

## Root Cause

The real, documented Allegro command is `specctra_in` (one word, underscore) — confirmed against `doc/scoms/schap.html`'s own command reference, which names it consistently throughout. The typo'd two-word form is not a recognized command at all, so the dispatcher never reaches a command-boundary it can recover from: no error is raised, no dialog is shown, nothing is logged beyond the initial banner, and the process just sits at 0% CPU indefinitely. This was a real bug in this suite's emitted-script line, not a product limitation.

## Evidence

- `sigrity_mcp/core/tool_status.py:215-228` (the `allegro` entry's specctra-import note) — "ROOT-CAUSED AND FIXED a real, reproducible (3-for-3) indefinite hang in `run_allegro_specctra_import` … Root cause: the script-replay line the tool emitted was literally `specctra in \"<path>\"` (two words, a space) -- not a real Allegro command. The real, documented command is `specctra_in` (one word, underscore; confirmed against `doc/scoms/schap.html`'s own command reference). Typing the wrong two-word form puts Allegro's command dispatcher into a permanently stuck state with no dialog and no further output."
- `sigrity_mcp/core/tool_status.py:226-228` — "confirmed live via an isolated repro (scratch board/session copies under `runs/specctra_import_investigation/`): the exact same hang shape reproduced identically, then switching only `in ` -> `_in` in the emitted script line made the process exit cleanly in under 2 seconds instead of hanging."
- `sigrity_mcp/domains/cad/spif_specctra_tools.py:95` — the fixed line: `tcl_sessions.add_line(session.session_id, f'specctra_in \"{clean_ses}\"')` (one word).
- `.forjinn/skills/sigrity-cad/SKILL.md:106-114` (Task 3, `run_allegro_specctra_import` note) — "Do NOT call this tool with an unpatched/older copy of `spif_specctra_tools.py` — doing so reproduces a real, 3-for-3 indefinite hang (0% CPU, no window, `run.log` stuck forever at the 3-line startup banner) caused by a literal typo in the emitted script line (`specctra in \"<path>\"`, two words — not a real command; the real one is `specctra_in`, one word)."

## Pipeline Impact

Any pipeline stage that calls `run_allegro_specctra_import` (directly, or via `run_placement_and_routing_assistance`'s `specctra_import` stage) against an unpatched copy of the file hangs indefinitely with **no** dialog to dismiss, **no** error in `run.log`, **no** nonzero return code, and **no** log line ever written past the banner. Because the hang signature (0% CPU, no window, banner-only log) is visually distinct from the modal-dialog hang's signature (a visible `Qt5QWindowIcon` popup), `DismissWatcher` — which only handles real dialog windows — will **not** detect or resolve it; the job simply never reaches a terminal state. The fix is purely in the emitted script text; there is no runtime workaround against the unpatched form.
