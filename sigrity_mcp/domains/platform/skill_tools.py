"""MCP-native skill discovery/loading.

Every tool's one-line description points at a domain "skill" file
(`.forjinn/skills/<name>/SKILL.md`) for the full verified playbook. Claude Code reads
that path directly off its own disk because it runs on the same filesystem as this
repo. A client that isn't Claude Code — a deepagents/LangChain agent connected over
`http`/`sse`, possibly from a different machine entirely — has no such access: the
*only* channel it has into this server is the MCP protocol itself, and a bare file path
in a docstring is meaningless to it.

So every skill is also served two ways over MCP:
  - `list_skills` / `load_skill` — plain tools. Every MCP client that can call tools at
    all (which is all of them) can use these; this is the one to reach for first.
  - `skill://{name}` — an MCP resource template, for clients that read resources
    directly. Note this is a *template* (it takes a parameter), so it will not appear
    in a plain `list_resources()`/`get_resources()` call with no URIs — call
    `list_skills` first to get the concrete names, then read `skill://<name>` (or just
    call `load_skill(name)`, which returns the identical content without needing
    resource support at all).

Recommended flow for a non-Claude-Code client on any transport: call `list_skills()`
once at the start of a task to see what's available, then `load_skill(name)` for the
one or two domains the task actually needs before calling that domain's tools.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sigrity_mcp.core.config import settings
from sigrity_mcp.mcp_app import mcp

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _skills_root() -> Path:
    return settings.resolve_skills_dir()


def _parse_skill_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {"name": path.parent.name, "description": "", "body": text.strip()}
    frontmatter, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return {
        "name": fields.get("name", path.parent.name),
        "description": fields.get("description", ""),
        "body": body.strip(),
    }


def _iter_skill_files():
    root = _skills_root()
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        candidate = entry / "SKILL.md"
        if candidate.is_file():
            yield candidate


def _resolve_skill_path(name: str) -> Optional[Path]:
    # `Path(name).name` strips any directory components so a caller can't escape
    # `_skills_root()` with a `../` style name.
    safe_name = Path(name).name
    path = _skills_root() / safe_name / "SKILL.md"
    return path if path.is_file() else None


@mcp.tool
async def list_skills() -> dict:
    """List every domain skill playbook available (name + one-line description each) — call this first, especially on a non-stdio connection where you cannot read `.forjinn/skills/` off disk directly.
Then call load_skill(name) for the domain(s) your task actually needs before calling its tools."""
    files = list(_iter_skill_files())
    if not files:
        return {
            "skills": [],
            "error": f"No skill files found under {_skills_root()} — check the "
            "SIGRITY_SKILLS_DIR setting / server working directory.",
        }
    return {"skills": [{"name": s["name"], "description": s["description"]} for s in map(_parse_skill_file, files)]}


@mcp.tool
async def load_skill(name: str) -> dict:
    """Fetch the full verified playbook (exact call sequences, pitfalls, real sample file paths, live examples) for one domain skill by name, as returned by list_skills.
Use this in place of reading `.forjinn/skills/<name>/SKILL.md` off disk when you have no filesystem access to this machine."""
    path = _resolve_skill_path(name)
    if path is None:
        available = sorted(p.parent.name for p in _iter_skill_files())
        return {"error": f"No skill named '{name}'.", "available_skills": available}
    parsed = _parse_skill_file(path)
    return {"name": parsed["name"], "description": parsed["description"], "content": parsed["body"]}


@mcp.resource("skill://{name}")
async def skill_resource(name: str) -> str:
    """The full markdown body of one domain skill playbook, addressable by name (see list_skills for the available names)."""
    path = _resolve_skill_path(name)
    if path is None:
        raise FileNotFoundError(f"No skill named '{name}'")
    return _parse_skill_file(path)["body"]
