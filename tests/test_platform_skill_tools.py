import asyncio
import os

from sigrity_mcp.core.config import settings
from sigrity_mcp.domains.platform import skill_tools


def _run(coro):
    return asyncio.run(coro)


def test_resolve_skills_dir_independent_of_cwd(tmp_path, monkeypatch):
    # Regression test for a real bug found via a live forji-desk run: the sigrity MCP
    # server was spawned with its CWD left at the *launching* app's own directory
    # (no `cwd` set in the launcher config), and skills_dir being CWD-relative meant
    # list_skills()/load_skill() silently found nothing on that machine.
    monkeypatch.chdir(tmp_path)
    assert os.getcwd() == str(tmp_path)
    resolved = settings.resolve_skills_dir()
    assert resolved.is_dir()
    assert (resolved / "sigrity" / "SKILL.md").is_file()


def test_list_skills_works_from_unrelated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run(skill_tools.list_skills())
    assert "error" not in result
    names = {s["name"] for s in result["skills"]}
    assert "sigrity" in names
    assert "sigrity-cad" in names


def test_load_skill_works_from_unrelated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run(skill_tools.load_skill("sigrity-cad"))
    assert "error" not in result
    assert "content" in result and len(result["content"]) > 0
