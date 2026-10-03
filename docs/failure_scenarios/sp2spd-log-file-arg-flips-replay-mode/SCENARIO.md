# `*2Spd` Translators: Passing `log_file` Silently Flips the Tool into Log-Replay Mode

**Slug**: `sp2spd-log-file-arg-flips-replay-mode`
**Tool(s) affected**: `translate_gds_to_spd`, `translate_oasis_to_spd`, `translate_ndd_to_spd`, `translate_pads_to_spd`, `translate_rif_to_spd`, `translate_dsn_to_spd`, `translate_to_spd_via_spdlinks` (`sigrity_mcp/domains/extraction/translators.py`); canonical example is `translate_dsn_to_spd` ("sp2spd")
**Status category**: `known_blocked`
**Manifest**: #79

## What went wrong

Passing `log_file` to a `*2Spd` translator **does not redirect output** — it **silently flips the tool into log-replay mode**. In replay mode the tool drops your explicit format/map/tech arguments (e.g. `-gds`/`-oasis`/`-map`/`-tech`) and instead replays a **previously recorded run's stored settings**, which **silently override** any explicit format/map/tech arguments given alongside on the same command line.

So the common intent "point the output elsewhere / name the log" is the **opposite** of what happens: the log's own stored settings win over your explicit args. The tool still runs and can still "succeed", using the recorded settings and (typically) the original recorded I/O, not the conversion you actually intended.

Each wrapper in `translators.py` encodes this as a **branch**: when `log_file` is given it builds `-b -log <log_file> [input_file] [output_file]` (explicit-flags form dropped); otherwise it builds the normal explicit-flag command. The `input_file`/`output_file` are still appended (some tools require them positionally) but are only "override attempts" the log's stored settings will likely win over — not a reliable way to redirect a replayed run's I/O.

## Evidence

- `sigrity_mcp/domains/extraction/translators.py` (module docstring, lines 21–29): "Documented gotcha that applies to every tool below: passing `-log <log_file>` replays a previously recorded run's stored settings, and those stored values **silently override** any explicit format/map/tech arguments given alongside it ... So each tool here treats `log_file` as switching to an entirely different mode: when given, the explicit-flags form (map/tech file, format-specific switches) is dropped and the command becomes `-b -log <log_file> [input_file] [output_file]` instead ... treated as override *attempts* the log's own stored settings will likely win over."
- `sigrity_mcp/domains/extraction/translators.py` (per-tool branches), e.g. `translate_dsn_to_spd` (lines 123–130): `if log_file: args = ["-b", "-log", log_file, dsn_file, spd_file] else: args = ["-b", dsn_file, spd_file]` — the explicit-flag command vanishes in the replay branch. (Same `if log_file:` branch in gds2spd/oasis2spd/ndd2spd/pads2spd/rif2spd/spdlinks.)
- `.forjinn/skills/sigrity-extraction/SKILL.md` (Task 2, lines 96–97): "`Dsn2Spd.exe -b <dsn> <spd>` is what runs. **Do NOT pass `log_file`** — it silently flips the tool into log-replay mode, dropping explicit args and replaying a prior run's stored settings."
- `.forjinn/skills/sigrity-extraction/SKILL.md` (Task 2, "Mistake #1 for translators", lines 107–108): "passing `log_file` thinking it 'redirects output'. It overrides your explicit input/output, not appends. Never pass it for a fresh conversion."

## Symptoms a caller observes

- Caller invokes e.g. `translate_dsn_to_spd(dsn_file=..., spd_file=..., log_file="some.log")` intending a fresh conversion with output routing.
- The generated command is `Dsn2Spd -b -log some.log <dsn> <spd>` — the `-dsn`/etc. explicit flags are gone.
- The tool replays `some.log`'s recorded settings; output reflects the **prior** recorded run rather than the requested conversion. No error is raised.
