# gerber-no-films-silent-noop

- **tool**: `allegro_artwork` (`artwork.exe`, wrapped as `run_allegro_generate_artwork` in `sigrity_mcp/domains/cad/allegro_manufacturing_tools.py`)
- **status_category**: `precondition_error` (correct tool and invocation, but the board carries no film records)
- **verified_workaround**: YES — author film records in the board first (`allegro_create_film` + `allegro_save_design` in a SKILL session), then run artwork

## What went wrong

`artwork.exe` **emits nothing** when the board it is run against has **no film records defined**. There is no error and no useful log content to explain it — it is a silent no-op. A caller who jumps straight to `run_allegro_generate_artwork` on a board that was never set up for artwork gets a job that completes with no `.art` output and no diagnostic naming the missing films.

The real Gerber pipeline is two steps, not one: (1) define film records **on the board** (Allegro's Artwork Control Form does this interactively; the headless SKILL equivalent is `axlFilmCreate`, wrapped as `allegro_create_film`), then save the design; (2) run `artwork.exe <board>`, which renders whichever films exist. Skipping step 1 means step 2 has nothing to render.

## Evidence

- `.forjinn/skills/sigrity-cad/SKILL.md` (Task 4, header + gotcha): "Films must be authored **in the board** before artwork.exe emits anything. One session composes films + save, then a standalone artwork job renders." and "#1 mistake: running `run_allegro_generate_artwork` on a board that has no film records — it emits nothing. Always `allegro_create_film` + `allegro_save_design` in a SKILL session (on that same board copy) first, then artwork."
- `core/tool_status.py` (`allegro_artwork` note): "The missing piece was authoring those film records at all — Allegro's Artwork Control Form normally does this interactively, but the real documented SKILL equivalent, `axlFilmCreate` (now wrapped as `allegro_create_film` in allegro_geometry_tools.py), does it headlessly." and documents the full confirmed pipeline `allegro_create_film -> allegro_save_design -> allegro_run_session -> run_allegro_generate_artwork`.
- `allegro_manufacturing_tools.py` module docstring (lines 10–19): "The real pipeline has two steps, not one: (1) define film records on the board (there was no wrapper for this at all — now `allegro_create_film` ...) then save the design; (2) run `artwork.exe <board> [-f <film>]...`."
- Confirmed-live happy path (SKILL.md Task 4): `allegro_create_film(session_id, film_name="TOP", layers=["ETCH/TOP"])` + `BOTTOM` + `allegro_save_design` + `allegro_run_session` → `run_allegro_generate_artwork` → real `TOP.art`/`BOTTOM.art` in the job dir. This is the contrast that defines the precondition.

## Symptoms a caller observes

- `run_allegro_generate_artwork` job completing without any `<film>.art` file in the job dir
- No per-layer error in `photoplot.log` naming the omission — an easy silent no-op
- Possible accompanying rc 1 "had warnings" (see sibling scenario) that masks the real cause
