# Scenario: list-skills-empty-when-sql-dirs-wrong

**Manifest entry:** #102 — "list_skills empty if SIGRITY_SKILLS_DIR wrong"
**Status category:** `known_blocked`
**Verified workaround:** YES — fix `SIGRITY_SKILLS_DIR` (or the server's working directory)
to point at the real skills directory

## What goes wrong

`list_skills` / `load_skill` / the `skill://{name}` resource template
(`domains/platform/skill_tools.py`) exist so that an MCP client with NO filesystem access to
this machine (e.g. a remote `deepagents`/LangChain agent over `http`/`sse`, per
`skill_tools.py`'s own module docstring) can still discover and read the domain playbooks.
They resolve "where do the skills live" via ONE setting:

```python
def _skills_root() -> Path:
    return settings.resolve_skills_dir()     # core/config.py:145-154
```

```python
def resolve_skills_dir(self) -> Path:
    """...
    Resolved against this repo's own root, not the launching process's CWD — skills ship
    with this repo, so they must be found regardless of what directory spawned the server
    (a real bug: a client launching this server with no explicit `cwd` resolved this to
    its own working directory and found nothing)."""
    return self.skills_dir if self.skills_dir.is_absolute() else _PROJECT_ROOT / self.skills_dir
```

with `skills_dir: Path = Path(".forjinn/skills")` as the default (`core/config.py:107`), and
`_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent` (the repo root, computed
independently of CWD, `core/config.py:18`).

The failure shape, when `SIGRITY_SKILLS_DIR` (env var, prefix `SIGRITY_` + `skills_dir` field
name, `core/config.py:22`) is set to a WRONG path — or, per the documented real bug, when the
server was historically launched from a CWD the (pre-fix) code didn't anchor against the repo
root — `_iter_skill_files()` does this:

```python
def _iter_skill_files():
    root = _skills_root()
    if not root.is_dir():
        return          # <-- silently yields NOTHING
    for entry in sorted(root.iterdir()):
        candidate = entry / "SKILL.md"
        if candidate.is_file():
            yield candidate
```

i.e. **if the resolved directory doesn't exist, `list_skills` returns an EMPTY list with no
error** — `_skills_root()` failing to be a directory is not treated as an error condition at
iteration time. `list_skills` itself does branch on "if not files:" and returns an
`error` message IN THE PAYLOAD, but only in that case
(`skill_tools.py:82-88`):

```python
files = list(_iter_skill_files())
if not files:
    return {
        "skills": [],
        "error": f"No skill files found under {_skills_root()} — check the "
        "SIGRITY_SKILLS_DIR setting / server working directory.",
    }
```

So the caller-facing symptom of a wrong `SIGRITY_SKILLS_DIR` (or the historical pre-fix CWD
bug) is `{"skills": [], "error": "No skill files found under <wrong-path> — check the
SIGRITY_SKILLS_DIR setting / server working directory."}` — an "empty but with an explanation"
result, NOT a raised exception. A caller that only checks
"did I get a nonempty `skills` list?" and ignores the sibling `error` key (a perfectly natural
way to read this response shape, since the field is `error` inside an otherwise-successful-
looking dict, the same "error payload not raised" pattern as sibling scenario
`stale-session-id-error-payload-vs-real-error`) will conclude "there are simply no skills to
list here" rather than "the directory I was told to look in doesn't exist / isn't the real
skills directory."

`load_skill` is a bit more informative in the wrong-case: it resolves the specific named path
and, if not found, returns `{"error": f"No skill named '{name}'.", "available_skills": [...]}`
where `available_skills` is itself built from `_iter_skill_files()` — so under the same wrong-
`SIGRITY_SKILLS_DIR` condition, `available_skills` will ALSO just be `[]`, and the message
genuinely is "no skill named X" (correctly, given the (empty) set of skills the (wrong) root
actually contains) — the error text does NOT itself say "the root directory is missing/
wrong," so a caller reading `load_skill`'s error (rather than `list_skills`'s, which IS more
diagnostic) gets no stronger hint than `list_skills`'s generic message at all.

The "a real bug" comment in `resolve_skills_dir`'s docstring confirms this is not a
hypothetical: at some point the code resolved `skills_dir` against the *launching process's*
CWD rather than anchoring to the repo root, and "a client launching this server with no
explicit `cwd` resolved this to its own working directory and found nothing" — i.e. this exact
empty-list failure was hit live, and the fix was the `_PROJECT_ROOT` anchoring now visible in
the code. The env-var override (`SIGRITY_SKILLS_DIR`, or a `.env` file, `core/config.py:22-23`)
is the remaining, undiagnosed-at-call-time way to still end up pointing at the wrong directory
(e.g. a stale/typo'd absolute path baked into an environment or `.env`), which is why this
scenario stays `known_blocked` (no in-suite mechanism auto-corrects or even warns-with-a-
stronger-than-current signal if an *explicitly-set-but-wrong* `SIGRITY_SKILLS_DIR` is used —
the code takes the given path at face value, and the only diagnostic is the
`list_skills` "check the SIGRITY_SKILLS_DIR setting / server working directory" string, which
names the likely cause but is easy to overlook if a caller only inspects the `skills` array).

## Evidence

- `core/config.py:18` — `_PROJECT_ROOT = Path(__file__).resolve().parent.parent.
  parent`: the repo-root anchor, computed off the *source file's location*, not CWD.
- `core/config.py:107-112` — `skills_dir: Path = Path(".forjinn/skills")` default, plus its
  docstring ("Claude Code reads these off disk directly; `list_skills`/`load_skill` ... serve
  the same files over the MCP protocol itself for clients with no filesystem access to this
  machine").
- `core/config.py:145-154` — `resolve_skills_dir()` full source, including the verbatim "a
  real bug: a client launching this server with no explicit `cwd` resolved this to its own
  working directory and found nothing" comment, and the "Unlike `resolve_workdir`, never
  creates the directory — skills are version-controlled content ... a missing dir is a
  deployment error `skill_tools` surfaces explicitly rather than papering over" comment —
  i.e. the code deliberately does NOT auto-create a missing skills dir (contrast with
  `resolve_workdir()`, `core/config.py:140-143`, which does `mkdir(parents=True, exist_ok=True)`)
  — so a wrong path is a real, surfaceable deployment error, not something silently fixed by
  making the directory.
- `domains/platform/skill_tools.py:38-39,60-67` — `_skills_root()` (1-line delegate to
  `settings.resolve_skills_dir()`) and `_iter_skill_files()`'s `if not root.is_dir(): return`
  silent-yields-nothing branch.
- `domains/platform/skill_tools.py:78-89` — `list_skills`'s `if not files: return
  {"skills": [], "error": "No skill files found under ... check the SIGRITY_SKILLS_DIR
  setting / server working directory."}` branch — the exact shape/symptom documented in this
  scenario, including the literal "SIGRITY_SKILLS_DIR" naming in the caller-visible error
  string.
- `domains/platform/skill_tools.py:93-101` — `load_skill`'s `{"error": f"No skill named
  '{name}'.", "available_skills": available}` branch, where `available` comes from the same
  (possibly empty) `_iter_skill_files()` — confirming the weaker diagnostic shape for the
  `load_skill` path specifically.
- `.forjinn/skills/sigrity/SKILL.md`'s module-level "Domain index" and the tool-description
  pattern in every tool ("See `.forjinn/skills/sigrity/SKILL.md`..." — e.g.
  `domains/platform/job_tools.py:67,77,90,...`) — confirms the skills dir is a load-bearing,
  referenced-by-name dependency for the whole suite's self-documentation model, not an
  optional extra, which is exactly why a wrong path degrades the entire "which tool do I call
  and how" discovery mechanism for a non-filesystem-connected client.
