# Workarounds: file-tools-arg-names-not-source-destination

**Verified workaround: YES** — use the exact argument names: `source_file`/`destination_file`
for `copy_file`/`move_file`, `file_path` for `delete_file`, plus `overwrite` (boolean) where
applicable. There is no fuzzy matching or alias to fall back on if you get them wrong — the
only "workaround" is knowing the correct names up front.

## What works (verified)

1. **Use these exact signatures, copied verbatim (`domains/platform/file_tools.py`):**
   - `copy_file(source_file: str, destination_file: str, overwrite: bool = False)`
   - `move_file(source_file: str, destination_file: str, overwrite: bool = False)`
   - `delete_file(file_path: str)`
   - `check_design_lock(design_path: str)` (the other tool in this file — note it uses
     `design_path`, a fourth distinct name, for the same conceptual "which file/design am I
     pointing at" slot; same trap class)
2. **Before calling, if in doubt, call `load_skill("sigrity")` (or read the parent SKILL.md)
   first** — SKILL.md's "Argument-name traps" section exists precisely as the
   pre-consultation reference for exactly this class of error, and names this exact tool set as
   a confirmed live example: "file tools are `source_file`/`destination_file` (and
   `file_path` for delete) — NOT `source`/`destination`."
3. **If a file-tool call does hang / time out / fail in a way that doesn't look like an obvious
   typo you already spotted**, apply the general recovery pattern from sibling scenario
   `mcp-client-30s-roundtrip-cap` (check what actually happened before retrying or assuming it's
   a simple typo) and, specifically for the documented "~20 minute silent hang" failure shape
   (SKILL.md "Argument-name traps" section), do NOT blindly keep retrying variations of guess-
   work argument names — stop, re-read the exact signatures in `file_tools.py` (or SKILL.md)
   once, and use them verbatim on the next attempt.

## What does NOT work / is out of scope

- No alias/fuzzy-matching/typo-correction layer exists in this suite for ANY tool, including
  these three — a wrong name is not quietly "close enough"; it either produces a
  `missing_argument`-style binding error or (per the documented general trap class) the
  worse-observed case of a long, silent hang. There is nothing to "work around" on the
  server side; the fix is purely getting the name right on the calling side.
- `delete_file` is specifically flagged "DESTRUCTIVE — there is no undo" in its own docstring —
  when correcting an argument-name mistake on a `delete_file` call, double-check you're pointing
   at the RIGHT file with `file_path` before re-calling, for the obvious reason a destructive,
  no-undo operation deserves one extra check beyond the usual "use the right name" advice.
