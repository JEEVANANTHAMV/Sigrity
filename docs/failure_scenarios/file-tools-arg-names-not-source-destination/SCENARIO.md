# Scenario: file-tools-arg-names-not-source-destination

**Manifest entry:** #101 — "file tools: source_file/destination_file/file_path"
**Status category:** `precondition_error`
**Verified workaround:** YES — use the exact argument names

## What goes wrong

`copy_file`, `move_file`, and `delete_file` (`domains/platform/file_tools.py`) are plain,
synchronous `shutil`-based operations — the one file-related concern they raise, by design, is
**strict, exact-matching argument names**, and getting a name wrong is a live-observed,
recurring, high-cost failure rather than a typo that "obviously" fails:

```python
@mcp.tool
async def copy_file(source_file: str, destination_file: str, overwrite: bool = False) -> dict: ...

@mcp.tool
async def move_file(source_file: str, destination_file: str, overwrite: bool = False) -> dict: ...

@mcp.tool
async def delete_file(file_path: str) -> dict: ...
```

Note the deliberate, non-obvious asymmetry: `copy_file`/`move_file` take `source_file` /
`destination_file`, but `delete_file` takes **`file_path`** — not `source_file`, not
`destination_file`, a third, different name for what is conceptually "the file you're pointing
at." SKILL.md calls these out by name in its "Argument-name traps" section, verbatim:

> "file tools are `source_file`/`destination_file` (and `file_path` for delete) — NOT
> `source`/`destination`"

The traps this protects against are plausible-sounding, "obviously-correct" alternatives an LLM
caller is very likely to generate from general knowledge of what copy/delete operations are
usually called (`source`, `destination`, `path`, `filename`, `src`, `dst`...) — none of which
match the actual registered parameter names.

## Why this is worse than a normal "missing argument" error

SKILL.md's "Argument-name traps" intro, verbatim: "All tool args are strict; passing a
plausible-but-wrong name either raises `missing_argument` or, **worse, hangs ~20 min**." This is
what makes this a `precondition_error`-category, real, documented, high-severity failure rather
than a harmless docstring mismatch: depending on exactly WHERE in the calling flow the
wrong-named argument lands, the observed consequence is not always a fast, clear
"missing_argument" error — in at least one confirmed, live-observed case (the SKILL.md text
doesn't scope this to the file tools specifically — it's stated as a general property of
"all tool args" in this suite), a wrong-but-plausible argument name resulted in a ~20-minute
SILENT hang, with no clean error ever surfacing, before anyone noticed anything was wrong.
The file tools are the canonical, named example of the trap class; the ~20-min silent hang is
documented as a possible (not the only possible) consequence for argument-name traps generally
in this suite.

This repo's own end-to-end evaluation history adds a related, concrete data point about how
easily file-related tooling gaps/quirks bite real task flows at scale — `README.md`'s
multi-model evaluation write-up (the "first run" paragraph) notes that "two task prompts asked
the model to 'copy the file first' into a scratch location — but this suite has no file-copy
tool, so that instruction was unfulfillable" → one of the two root causes of that first
evaluation pass's 4-of-6 failures, BEFORE `copy_file`/`move_file`/`delete_file` were added in
`file_tools.py`'s own module docstring ("Added after the multi-model end-to-end evaluation ...
repeatedly hit the same wall"). The existence of the tools themselves is the "fix"; the
argument-name strictness of the tools that were added is the *remaining*, live-documented trap
documented under this exact scenario slug.

There is no fuzzy-matching, alias, or "did you mean ..." layer on ANY tool in this suite
(including these) — the parameter names are exactly as registered above, full stop. The only
"recovery" is for the caller to use the correct name on the next attempt.

## Evidence

- `domains/platform/file_tools.py:21-33, 36-50, 53-63` — the three tools' actual, exact
  registered signatures: `copy_file(source_file, destination_file, overwrite=False)`,
  `move_file(source_file, destination_file, overwrite=False)`, `delete_file(file_path)` — the
  `file_path` vs. `source_file`/`destination_file` asymmetry is right there in the code, with no
  aliases, no `*args`/`**kwargs`, no normalization layer before them (the functions themselves
  take the parameters and use them directly, e.g. `src = Path(source_file)` /
  `dst = Path(destination_file)` — a wrong name fails at tool-argument-binding time, before any
  of this code runs).
- `.forjinn/skills/sigrity/SKILL.md`, "Argument-name traps (wrong names → SILENT hang, no
  clean error)" — the exact, verbatim named examples: "file tools are
  `source_file`/`destination_file` (and `file_path` for delete) — NOT `source`/`destination`";
  and the general severity statement: "passing a plausible-but-wrong name either raises
  `missing_argument` or, worse, hangs ~20 min."
- `domains/platform/file_tools.py:1-11` (module docstring) — the tools' own documented origin:
  added specifically because the multi-model evaluation "repeatedly hit the same wall" of
  needing to stage a file before running a tool — i.e. these three tools are on a real, high-
  traffic code path (any task that stages an input file), which is exactly why their argument-
  name strictness is documented as a live, recurring failure mode rather than a theoretical one.
- `README.md` (multi-model evaluation, "first run" paragraph) — the 4-of-6-first-pass failures
  caused in part by the PRE-EXISTENCE gap ("no file-copy tool"), the documented reason these
  tools were added at all; `copy_file`'s existence since then is what makes the argument-name
  trap (rather than the outright absence of a copy tool) the correct, current, live failure
  shape for this scenario.
