# gerber-no-films-silent-noop — Workarounds

## What works (confirmed — the real pipeline)

```
start_allegro_session()                                              -> {session_id}
allegro_create_film(session_id, film_name="TOP",    layers=["ETCH/TOP"])
allegro_create_film(session_id, film_name="BOTTOM", layers=["ETCH/BOTTOM"])
allegro_save_design(session_id)                                      # REQUIRED — nothing persists without it
allegro_run_session(session_id, board_file="…\\fd.brd")              # board_file REQUIRED; appends bare `quit`
wait_for_job(job_id, 240)                                            # ~17 s (allegro.exe loads board 15–20 s)
run_allegro_generate_artwork(board_file="…\\fd.brd")                 # all films, or film_names=[…] for a subset
wait_for_job(job_id, 180)
```

- `allegro_create_film` (SKILL `axlFilmCreate`) writes the film records **into the board**; `allegro_save_design` is required or the films don't persist; the session must run against the **same board copy** the artwork step will read.
- The confirmed-live result of this sequence: real `TOP.art` (12,209 B) and `BOTTOM.art` (6,036 B), RS274X, in the artwork job dir, with `photoplot.log` `SUMMARY` lines.
- `list_only=True` (`artwork.exe -l <board>`) lists the film records currently on a board — use it to verify the precondition before generating.
- `film_names` on `run_allegro_generate_artwork` selects a subset of existing films (`-f <film>` each); it does not create films.

## What was tried / ruled out

- Running `artwork.exe` on a board with no films: ruled out as a path — it is the documented silent no-op. There is no artwork.exe flag that synthesizes default films; the records must exist on the board.

## Notes

- A stale `<brd>.lck` (e.g. from a killed prior `allegro.exe` job on the same path) makes the film-authoring session hang on a modal "design locked" dialog; the tool clears the stale sibling `.lck` before launch, but if you hand-ran `allegro.exe`, delete `<brd>.lck` first (SKILL.md Task 4 error note).
