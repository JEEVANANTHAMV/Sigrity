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


# --- Distinguishing "skills dir missing" from "skills dir exists but wrong layout" --
#
# Regression coverage for a real gap: an explicitly-set-but-wrong SIGRITY_SKILLS_DIR
# used to produce the same generic empty-list error regardless of WHY it was empty,
# making the actual misconfiguration easy to miss.


def test_list_skills_reports_missing_directory_distinctly(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(settings, "skills_dir", missing)
    result = _run(skill_tools.list_skills())
    assert result["skills"] == []
    assert "does not exist" in result["error"]
    assert str(missing) in result["error"]


def test_list_skills_reports_wrong_layout_distinctly(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_skills_dir"
    empty_dir.mkdir()
    monkeypatch.setattr(settings, "skills_dir", empty_dir)
    result = _run(skill_tools.list_skills())
    assert result["skills"] == []
    assert "no skill subdirectories" in result["error"]


def test_load_skill_unknown_name_reports_missing_directory_distinctly(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(settings, "skills_dir", missing)
    result = _run(skill_tools.load_skill("sigrity-cad"))
    assert result["available_skills"] == []
    assert "does not exist" in result["error"]
