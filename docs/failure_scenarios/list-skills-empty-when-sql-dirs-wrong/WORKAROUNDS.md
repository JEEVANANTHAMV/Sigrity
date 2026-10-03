# Workarounds: list-skills-empty-when-sql-dirs-wrong

**Verified workaround: YES** — fix `SIGRITY_SKILLS_DIR` (env var or `.env`) to point at the real
skills directory (default: the repo's own `.forjinn/skills`, resolved relative to the repo root
by `resolve_skills_dir()`, `core/config.py:145-154`), or unset it and make sure the server
process's launch doesn't depend on a CWD the (older) code would have mis-resolved against.

## What works (verified)

1. **Unset `SIGRITY_SKILLS_DIR` / `.env`'s `skills_dir` and let the code use its built-in
   default + repo-root anchor.** `core/config.py:154`: `return self.skills_dir if
   self.skills_dir.is_absolute() else _PROJECT_ROOT / self.skills_dir` — with the default
   `skills_dir = Path(".forjinn/skills")` (relative), this ALWAYS resolves to
   `<repo_root>/.forjinn/skills` regardless of CWD, because `_PROJECT_ROOT`
   (`core/config.py:18`) is derived from the source file's own on-disk location, not from
   `Path.cwd()`. This is the code's own, in-code-stated fix for the documented historical bug
   (the exact "resolved this to its own working directory and found nothing" failure, per
   `resolve_skills_dir`'s docstring) — the safest "just make it stop being wrong" move is to
   stop overriding it at all.
2. **If you DO need a non-default skills location** (skills checked out/staged elsewhere), set
   `SIGRITY_SKILLS_DIR` (env var) or `skills_dir` in a `.env` file to an **absolute** path to a
   directory that genuinely contains `<name>/SKILL.md` subdirs (the exact shape
   `_iter_skill_files()` requires: `skill_tools.py:64-67` — it does NOT recurse; it looks for
   exactly one level of `<root>/<entry>/SKILL.md`). Verify the path is real and correctly
   shaped *before* restarting/relaunching the server, since `resolve_skills_dir()` deliberately
   does not create the directory (`core/config.py:145-149`) and `list_skills` will just return
   the empty-list-with-error payload (this scenario's core symptom) if it's wrong.
3. **Treat `list_skills`'s return as a PAIR, not just the `skills` array.** The correct
   caller-side check, when you're trying to confirm the skills dir is actually wired right, is:
   if `skills` is empty, CHECK the sibling `error` key before drawing any other conclusion —
   `skill_tools.py:82-88`'s `{"skills": [], "error": "No skill files found under <path> — check
   the SIGRITY_SKILLS_DIR setting / server working directory."}` is the suite's ONLY
   diagnostic for this failure, and it names both likely causes (the env var AND the working
   directory) verbatim. The same "inspect `result['error']` / sibling error payload before
   concluding the primary field is authoritative" discipline applies here as in sibling scenario
   `stale-session-id-error-payload-vs-real-error`.
4. **If you're the one launching the server (not a remote client), the local, always-available
   alternative is to skip `list_skills`/`load_skill` entirely and read
   `.forjinn/skills/<domain>/SKILL.md` directly off disk** — the parent SKILL.md and
   `skill_tools.py`'s module docstring both state this is the whole reason the MCP-served
   copies exist at all (for clients with no filesystem access); a same-machine launcher (e.g.
   Claude Code per the docstring) never needs `list_skills` in the first place and is immune
   to this failure entirely.

## What does NOT work / is out of scope

- No in-suite auto-repair: if `SIGRITY_SKILLS_DIR`/`skills_dir` points at a nonexistent or wrong
  directory, nothing in `core/config.py` or `domains/platform/skill_tools.py` falls back to the
  repo-root default, guesses a correction, or raises a hard error — the "surfaces explicitly"
  language in `resolve_skills_dir`'s docstring (`core/config.py:145-149`) is realized only as
  the `list_skills` empty-list + `error`-string payload described above, which is easy to
  overlook if a caller only inspects the `skills` array (hence why the manifest keeps this
  `known_blocked` rather than listing it as purely fixed — the repo-root-anchoring bug itself
  IS fixed, but the "explicitly-set-wrong-`SIGRITY_SKILLS_DIR`" case is still only diagnosed by
  a string the caller has to actually read, not by any fail-closed mechanism).
- Setting `SIGRITY_SKILLS_DIR` to a path that exists but does NOT follow the exact
  `<root>/<name>/SKILL.md` subdirectory shape (e.g. pointing it directly at a flat list of
  `SKILL.md` files, or one level too deep/too shallow) will ALSO produce an empty
  `_iter_skill_files()` yield (the `candidate = entry / "SKILL.md"; if candidate.is_file()`
  check, `skill_tools.py:64-67`, finds nothing) and the same empty-list symptom — "the
  directory exists" is not by itself sufficient; the exact subdirectory-per-skill layout is what
  the code requires.
