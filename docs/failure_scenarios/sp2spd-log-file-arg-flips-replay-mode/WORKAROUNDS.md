# sp2spd-log-file-arg-flips-replay-mode — Workarounds

## What works (confirmed)

- **Omit `log_file` for any fresh conversion.** For each `translate_*_to_spd` call, leave `log_file` as `None` so the wrapper builds the normal explicit-flag command (e.g. `Dsn2Spd -b <dsn> <spd>`; Gds2Spd as `-b -gds <gds> [-map …] [-tech …] -spd <spd>`; etc.). This is the verified, working path.
- **Use explicit args to control I/O.** To choose the output `.spd` (and any map/tech file), pass the real `spd_file` / `map_file` / `tech_file` in a fresh (no-`log_file`) call — that's the reliable way to redirect output.
- **Check the generated `command` list in the run return** to confirm the explicit-flag form was used, not the replay form. (SKILL Tip: "check the generated `command` list in the run return — it's the literal argv that was executed.")

## What was tried / ruled out

- Passing `log_file` to "redirect output" or "name the log": ruled out — it does the opposite. It flips the tool into replay mode and the recorded settings override your explicit args.
- Treating the positionally-appended `input_file`/`output_file` in a replay command as a reliable override of a replayed run's I/O: ruled out — they are "override attempts the log's own stored settings will likely win over."

## Notes

- This applies to **every** tool in `translators.py` (gds2spd, oasis2spd, ndd2spd, pads2spd, rif2spd, dsn2spd, spdlinks) — the `log_file` branch is the same. The fix is at the call site (just don't pass `log_file` for a fresh conversion); `translators.py` already branches correctly, no source change needed.
