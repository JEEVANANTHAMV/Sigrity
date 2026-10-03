# artwork-exe-exits-rc1-on-success — Workarounds

## What works (confirmed)

- **Judge by the `.art` files, not rc/state**: `list_job_files(job_id)` and check for the expected `TOP.art`/`BOTTOM.art` (or `<film>.art` for each requested film), then read one to confirm real RS274X content (`G04 File Format: Gerber RS274X`). SKILL.md's prescribed completion evidence.
- **Read `photoplot.log`** for the per-film `SUMMARY: <film> created ...` lines — "created with warnings" is the expected successful signature.
- **Pre-suppress the warnings (optional)**: supply an `art_param.txt` parameter file and a real outline rectangle so the two default-fallback warnings don't occur; without them the rc 1 is the normal signature. No in-suite flag on `run_allegro_generate_artwork` takes a param-file argument (its args are `board_file`, `film_names`, `list_only`), so this is a job-cwd/input concern, not a wrapper change.
- `list_only=True` (`artwork.exe -l <board>`) is a cheap pre-flight to list the film records the board actually has before generating.

## What was tried / ruled out

- There is no in-suite flag that forces rc 0; the rc 1-on-success behavior is inherent to `artwork.exe` when the harmless warnings fire, so the workaround is purely in the caller's completion test.

## Notes

- Same family as dxf2a rc 1, dbdoctor rc 1, specctra rc 4 (manifest #96): tool-specific completion evidence, never a blanket rc check.
