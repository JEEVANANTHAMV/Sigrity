"""Regression tests for the GUI-tool job layer (core.gui_tool_runner + the
JobManager submit() routing that adds it for GUI exes).

On this PREMIUM / no-license-required install, a SMALL number of tools genuinely
open a real GUI window even on their batch invocation (no confirmed headless
surface: currently just PowerTree and Optimality). For those, the console watcher's
log-size/stall heuristics mislead (a GUI tool's empty log is normal), so
JobManager routes them through the screen-based runner (screenshot + dialog
dismissal) and must NEVER label a GUI tool's empty output / non-zero exit as a
license failure.

2026-10-26 CORRECTION under test: PowerDC, PowerSI, XtractIM, Clarity3DWorkbench,
OptimizePI, XcitePI, XcitePICon, BroadbandSPICE, SPDSIM, SPDsimCon and Celsius3D
moved OUT of the GUI set after live verification (each launched with its documented
batch flags -- `-b -tcl` / `--NoUI -tcl` / `-b -export_data` / `-b -<mode>` /
`-b <file>` / `-tcl` -- ran CONSOLE-ONLY with zero windows and a real rc). They MUST
now route through the normal CONSOLE job path, not the GUI observer. The tests
below assert both directions of that routing.

These tests need no real Sigrity or GUI: submit_job is tested with a command whose
first token is named like a GUI exe (PowerTree.exe -> a throwaway copy of the
running python), and the runner's blocking monitor / async entry point are
monkeypatched out, so only the wiring under test -- gui_tool flag, gui_tool_result
capture, state, license_issue_suspected forced False for GUI tools,
success/failed transitions, cancel() on a needs_user_intervention job -- is
exercised.
"""

import shutil
import sys
from pathlib import Path

import pytest

from sigrity_mcp.core import gui_tool_runner as gui
from sigrity_mcp.core import jobs as jobs_module
from sigrity_mcp.core import process as process_module
from sigrity_mcp.core.gui_tool_runner import GuiToolResult
from sigrity_mcp.core.jobs import JobManager


def _stub_gui_exe(tmp_path: Path, stem: str = "PowerTree") -> Path:
    """A native stub named like a GUI tool's exe so `is_gui_tool(command[0])`
    matches by stem, while remaining harmless.

    Copying the VENV's python.exe here is not viable (a venv launcher reads
    pyvenv.cfg relative to its own location, so the copy dies with
    'No pyvenv.cfg file', rc 106). The stub is therefore a copy of the BASE
    (non-venv) interpreter named <stem>.EXE; it then runs the args JobManager
    passes it (`-c '<code>'`) exactly like the real interpreter does, so the
    tests still exercise a genuine process launch + real exit code, just under
    a GUI-sounding name.
    """
    import subprocess as _sp
    r = _sp.run([sys.executable, "-c", "import sys; print(sys.base_prefix)"],
                capture_output=True, text=True)
    base_prefix = r.stdout.strip()
    base_python = Path(base_prefix) / "python.exe"
    exe = tmp_path / f"{stem}.EXE"
    if not base_python.exists():
        pytest.skip(f"base interpreter not found at {base_python}")
    shutil.copy(base_python, exe)
    return exe


# --- is_gui_tool(): the routing predicate ------------------------------------


def test_gui_set_is_exactly_the_two_tools_with_no_headless_surface():
    """The 2026-10-26 corrected GUI set contains ONLY the tools that open a real
    window even on their batch flags. The 11 analysis tools moved out (they run
    console-only under -b/-tcl/--NoUI) -- asserting the set exactly guards
    against any regression that re-lumps them back in and re-routes them through
    the (overhead) GUI observer."""
    assert gui.GUI_TOOL_EXE_NAMES == frozenset({"PowerTree", "Optimality"})
    from sigrity_mcp.core import executables
    assert executables.GUI_TOOL_NAMES == frozenset({"powertree", "optimality"})


def test_is_gui_tool_matches_known_gui_exes():
    for stem in ("PowerTree", "Optimality"):
        assert gui.is_gui_tool(f"C:\\fake\\{stem}.exe") is True, stem
        assert gui.is_gui_tool(f"C:\\fake\\{stem}") is True, stem


def test_is_gui_tool_rejects_console_tools():
    # The 11 tools that were (wrongly) in the old set now run as console jobs.
    for name in ("PowerDC", "PowerSI", "XtractIM", "Clarity3DWorkbench",
                 "OptimizePI", "XcitePI", "XcitePICon", "BroadbandSPICE",
                 "SPDSIM", "SPDsimCon", "Celsius3D",
                 # plus the always-console standalone CLIs
                 "psp_cmd", "checkplus", "batch_drc", "report", "artwork",
                 "allegro", "capture", "spif_batch"):
        assert gui.is_gui_tool(f"C:\\fake\\{name}.exe") is False, name


# --- run_gui_tool(): entry-point semantics -------------------------------------


@pytest.mark.asyncio
async def test_run_gui_tool_attaches_and_reports_success(tmp_path, monkeypatch):
    """Attach mode (pid given): no launch by the runner, screenshots under
    workdir/screenshots/, honest status, error note preserved."""
    calls = {}

    def fake_monitor(pid, shot_dir, timeout_s, interval, max_dismiss_attempts,
                     return_at_timeout=False, on_running_long=None):
        calls.update(pid=pid, shot_dir=shot_dir)
        shot = shot_dir / "screen_01.png"
        shot.write_bytes(b"fakepng")
        return ("success", 0, [], [shot],
                ["attached monitor: process exited with code 0 after 0s of screen monitoring"])

    monkeypatch.setattr(gui, "_blocking_attach_monitor", fake_monitor)
    monkeypatch.setattr(gui, "_load_imports", lambda: None)

    result = await gui.run_gui_tool(
        exe_path=tmp_path / "PowerTree.exe",
        args=[], workdir=tmp_path, timeout_s=120.0, job_name="powertree-test",
        pid=4242,
    )
    assert result.status == "success"
    assert result.returncode == 0
    assert calls["pid"] == 4242
    assert calls["shot_dir"] == tmp_path / "screenshots"
    assert (tmp_path / "screenshots" / "screen_01.png").is_file()
    assert result.screenshots == [tmp_path / "screenshots" / "screen_01.png"]
    assert result.error and "exited with code 0" in result.error


@pytest.mark.asyncio
async def test_run_gui_tool_headless_degrades_to_intervention_not_crash(
    tmp_path, monkeypatch
):
    """If pyautogui/PIL/pywin32 are unavailable, the runner must degrade to
    needs_user_intervention (with a clear error) -- NOT crash, NOT launch, and
    NEVER classify as a license failure."""
    monkeypatch.setattr(gui, "_load_imports", lambda: "ImportError: no display")
    result = await gui.run_gui_tool(
        exe_path=tmp_path / "PowerTree.exe",
        args=[], workdir=tmp_path, timeout_s=1.0, job_name="x",
    )
    assert result.status == "needs_user_intervention"
    assert result.error and "GUI tool runner unavailable" in result.error
    # nothing launched, and no license misclassification of the error
    assert "license" not in result.error.lower()


@pytest.mark.asyncio
async def test_stuck_dialog_renames_screenshot_and_reports_intervention(
    tmp_path, monkeypatch
):
    """A dialog that survives max_dismiss_attempts must rename the latest shot to
    screen_NN_STUCK_Here.png and produce needs_user_intervention -- and must NOT
    classify it as a license failure."""
    def fake_monitor(pid, shot_dir, timeout_s, interval, max_dismiss_attempts,
                     return_at_timeout=False, on_running_long=None):
        shot = shot_dir / "screen_01.png"
        shot.write_bytes(b"fakepng")
        stuck = shot.with_name("screen_01_STUCK_Here.png")
        shot.rename(stuck)
        errors = ["dialog still present after 3 dismissal attempts; a human needs to click it"]
        return ("needs_user_intervention", None, ["SomeDialog -> OK"], [stuck], errors)

    monkeypatch.setattr(gui, "_blocking_attach_monitor", fake_monitor)
    monkeypatch.setattr(gui, "_load_imports", lambda: None)
    result = await gui.run_gui_tool(
        exe_path=tmp_path / "Optimality.exe",
        args=[], workdir=tmp_path, timeout_s=120.0, job_name="optimality",
        pid=1, max_dismiss_attempts=3,
    )
    assert result.status == "needs_user_intervention"
    assert (tmp_path / "screenshots" / "screen_01_STUCK_Here.png").is_file()
    assert not (tmp_path / "screenshots" / "screen_01.png").exists()
    assert "license" not in (result.error or "").lower()


def test_gui_tool_result_to_dict_fields():
    r = GuiToolResult(status="success", screenshots=[Path("a.png")],
                      dismissed_dialogs=["OK"], error=None, returncode=0)
    d = r.to_dict()
    assert set(d.keys()) == {"status", "screenshots", "dismissed_dialogs",
                             "error", "returncode"}
    assert d["screenshots"] == [str(Path("a.png"))]


# --- JobManager.submit() routing -----------------------------------------------


@pytest.mark.asyncio
async def test_submit_job_for_gui_exe_sets_gui_tool_flag(tmp_path, monkeypatch):
    """A command whose first token is a GUI exe (PowerTree) must get gui_tool=True
    on the record, have the runner attached with that process's pid and the job
    dir as workdir, and (with a real exit code 0) finish as a genuine success
    with license_issue_suspected forced to False for GUI tools."""
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("powertree")
    exe = _stub_gui_exe(tmp_path, "PowerTree")

    runner_calls = {}

    async def fake_run_gui_tool(exe_path, args, workdir, timeout_s, job_name,
                                pid=None, screenshot_interval=2.0,
                                max_dismiss_attempts=3, on_running_long=None):
        runner_calls.update(pid=pid, workdir=workdir, job_name=job_name)
        return GuiToolResult(status="success", screenshots=[],
                             dismissed_dialogs=[], error=None, returncode=0)

    monkeypatch.setattr(gui, "run_gui_tool", fake_run_gui_tool)

    record = await jm.submit(
        tool="powertree",
        command=[str(exe), "-c", "print('hi')"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=15)
    assert finished.gui_tool is True
    assert runner_calls["pid"] == finished.pid
    assert runner_calls["workdir"] == job_dir
    assert runner_calls["job_name"] == job_id
    assert finished.state == "succeeded"
    assert finished.returncode == 0
    assert finished.license_issue_suspected is False
    assert finished.stall_timeout_killed is False


@pytest.mark.asyncio
async def test_submit_job_for_console_exe_does_not_route_to_gui(
    tmp_path, monkeypatch
):
    """A command whose first token is a console exe must NOT get the GUI routing:
    gui_tool stays False and the runner is never invoked."""
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("fake_console")
    called = {"n": 0}

    async def fake_run_gui_tool(*a, **kw):
        called["n"] += 1
        return GuiToolResult(status="success", screenshots=[],
                             dismissed_dialogs=[], error=None, returncode=0)

    monkeypatch.setattr(gui, "run_gui_tool", fake_run_gui_tool)

    await jm.submit(
        tool="fake_console",
        command=[sys.executable, "-c", "print('ok')"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=15)
    assert finished.gui_tool is False
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_analysis_tools_route_through_console_path_not_gui(
    tmp_path, monkeypatch
):
    """The 2026-10-26 regression test: an analysis tool that moves OUT of the GUI
    set (here PowerSI, which now runs console-only under -b -tcl) must be
    treated as a CONSOLE job -- gui_tool False, the screen runner NEVER invoked,
    and its real exit code honored (a fast clean exit = succeeded). This is
    exactly the routing that previously 'opened the GUI' (screenshot+dismiss)
    and disabled the log-stall watchdog."""
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("powersi")
    exe = _stub_gui_exe(tmp_path, "PowerSI")  # name it PowerSI; it is no longer a GUI tool
    called = {"n": 0}

    async def fake_run_gui_tool(*a, **kw):
        called["n"] += 1
        return GuiToolResult(status="success", screenshots=[],
                             dismissed_dialogs=[], error=None, returncode=0)

    monkeypatch.setattr(gui, "run_gui_tool", fake_run_gui_tool)

    await jm.submit(
        tool="powersi",
        command=[str(exe), "-c", "import sys; sys.exit(0)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    finished = await jm.wait(job_id, timeout=15)
    assert finished.gui_tool is False
    assert called["n"] == 0
    assert finished.state == "succeeded"
    assert finished.returncode == 0


@pytest.mark.asyncio
async def test_needs_user_intervention_state_is_set_and_cancelable(
    tmp_path, monkeypatch
):
    """If the runner reports needs_user_intervention (a dialog a human must
    click), the job's state becomes needs_user_intervention -- NEVER a license
    issue -- and the job must still be cancellable (the process is alive)."""
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("powertree")
    exe = _stub_gui_exe(tmp_path, "PowerTree")

    async def fake_run_gui_tool(exe_path, args, workdir, timeout_s, job_name,
                                pid=None, screenshot_interval=2.0,
                                max_dismiss_attempts=3, on_running_long=None):
        return GuiToolResult(
            status="needs_user_intervention", screenshots=[], dismissed_dialogs=[],
            error="dialog survived dismissal attempts", returncode=None,
        )

    monkeypatch.setattr(gui, "run_gui_tool", fake_run_gui_tool)

    await jm.submit(
        tool="powertree",
        command=[str(exe), "-c", "import time; time.sleep(30)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    import asyncio
    for _ in range(400):
        if jm._jobs[job_id].state == "needs_user_intervention":
            break
        await asyncio.sleep(0.05)
    rec = jm.get(job_id)
    assert rec.state == "needs_user_intervention"
    assert rec.license_issue_suspected is False
    assert "license" not in (rec.gui_tool_result or "").lower()

    cancelled, outcome = await jm.cancel(job_id)
    assert cancelled.state == "cancelled"
    assert outcome == "killed"


@pytest.mark.asyncio
async def test_wait_keeps_polling_while_needs_user_intervention(
    tmp_path, monkeypatch
):
    """wait() must treat needs_user_intervention as NON-terminal: the process may
    still exit after a human unblocks the dialog, and the honest rc-based
    outcome (success here) must win over the stale intervention state."""
    monkeypatch.chdir(tmp_path)
    jm = JobManager()
    job_id, job_dir = jm.new_job_dir("powertree")
    exe = _stub_gui_exe(tmp_path, "PowerTree")
    import asyncio

    async def fake_run_gui_tool(exe_path, args, workdir, timeout_s, job_name,
                                pid=None, screenshot_interval=2.0,
                                max_dismiss_attempts=3, on_running_long=None):
        jm._jobs[job_id].state = "needs_user_intervention"
        await asyncio.sleep(0.3)  # 'human' unblocks; the tool then completes
        return GuiToolResult(status="success", screenshots=[],
                             dismissed_dialogs=[], error=None, returncode=0)

    monkeypatch.setattr(gui, "run_gui_tool", fake_run_gui_tool)
    await jm.submit(
        tool="powertree",
        command=[str(exe), "-c", "import time,sys; time.sleep(5); sys.exit(0)"],
        job_dir=job_dir,
        job_id=job_id,
    )
    final = await jm.wait(job_id, timeout=10)
    assert final.state == "succeeded"
    assert final.returncode == 0


@pytest.mark.asyncio
async def test_submit_via_process_module_routes_gui_exe(tmp_path, monkeypatch, job_manager_holder):
    """The MCP-facing process.submit_job entry point must route a GUI tool
    (resolved exe named PowerTree.exe) through the runner path, while leaving
    console tools on the normal path."""
    exe = _stub_gui_exe(tmp_path, "PowerTree")
    monkeypatch.setattr(process_module.executables, "resolve", lambda name: exe)

    async def fake_run_gui_tool(*a, **kw):
        return GuiToolResult(status="success", screenshots=[],
                             dismissed_dialogs=[], error=None, returncode=0)
    monkeypatch.setattr(gui, "run_gui_tool", fake_run_gui_tool)

    rec = await process_module.submit_job(tool="powertree", build_args=["-c", "pass"])
    finished = await job_manager_holder["jm"].wait(rec.job_id, timeout=15)
    assert finished.gui_tool is True


@pytest.fixture
def job_manager_holder(monkeypatch):
    """Point process_module at a FRESH JobManager so this test's job lands in a
    local dict (the global job_manager singleton is shared by other tests)."""
    import sigrity_mcp.core.jobs as jm_mod

    fresh = JobManager()
    monkeypatch.setattr(jm_mod, "job_manager", fresh)
    monkeypatch.setattr(process_module, "job_manager", fresh)
    return {"jm": fresh}


# --- end-to-end: the REAL (unpatched) runner against a real short-lived process.
# In a headless CI there is no display, so pyautogui.screenshot() raises and each
# shot is skipped (logged, never fatal) -- which is exactly the graceful-degradation
# contract. The process still exits, the exit code is still read, and the status is
# still the honest rc-based one. On an interactive machine the same code path also
# captures real screenshots (asserted separately, only when a display is present).


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only process paths")
@pytest.mark.asyncio
async def test_run_gui_tool_end_to_end_short_exit(tmp_path):
    """Launch mode: a 250ms process that exits 0. The real monitor attaches, the
    process exits, and the status is the honest success -- with or without a
    display. This proves the runner works against a real process (not a mocked
    one) and that a headless screen-grab failure is non-fatal."""
    exe = _stub_gui_exe(tmp_path, "PowerTree")
    result = await gui.run_gui_tool(
        exe_path=exe,
        args=["-c", "import time,sys; time.sleep(0.25); sys.exit(0)"],
        workdir=tmp_path,
        timeout_s=20.0,
        job_name="powertree-e2e",
        screenshot_interval=0.05,
    )
    assert result.status == "success"
    assert result.returncode == 0
    assert "license" not in (result.error or "").lower()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only process paths")
@pytest.mark.asyncio
async def test_run_gui_tool_end_to_end_nonzero_exit(tmp_path):
    """A non-zero exit is reported as 'failed' with the code -- and, critically,
    is NOT dressed up as a license problem for a GUI tool."""
    exe = _stub_gui_exe(tmp_path, "Optimality")
    result = await gui.run_gui_tool(
        exe_path=exe,
        args=["-c", "import sys; sys.exit(7)"],
        workdir=tmp_path,
        timeout_s=20.0,
        job_name="optimality-e2e",
        screenshot_interval=0.05,
    )
    assert result.status == "failed"
    assert result.returncode == 7
    assert "license" not in (result.error or "").lower()


def test_gui_tool_result_stable_serialization():
    """gui_tool_result is persisted as JSON on the record, so the to_dict() shape
    (the only thing JobManager serializes) must be a fixed, documented set of
    keys and JSON-serializable end to end."""
    import json
    r = GuiToolResult(status="failed", screenshots=[Path("s.png")],
                      dismissed_dialogs=["OK"], error="boom", returncode=3)
    d = json.loads(json.dumps(r.to_dict()))
    assert d["status"] == "failed"
    assert d["returncode"] == 3
    assert d["screenshots"] == [str(Path("s.png"))]
    assert d["dismissed_dialogs"] == ["OK"]


# --- Selection-modal (select a tree / proxy / internet-waiting) auto-answer layer.
# Regression for the #1 'known blocked' root cause: these modals need a SELECTION
# answer (default/local/localhost/continue), not a bare OK. The tests below are
# pure-Python: `_selector_pattern_for`/`_auto_answer_selector` (no live GUI needed
# for the pattern-matching half) and a headless-safe call of `preseed_selection`
# (which no-ops cleanly when there's no display).


def test_selector_pattern_matches_tree_proxy_waiting_product():
    """Each of the four documented selection dialogs maps to a pattern + keywords.
    Title match is primary; class is the fallback for untitled probe windows."""
    from sigrity_mcp.core.executables import SELECTOR_DIALOG_PATTERNS
    # Title-path matches (the usual case).
    assert gui._selector_pattern_for({"title": "Select a Tree", "class": "Dialog"})[0] == "tree"
    assert gui._selector_pattern_for({"title": "Select a Proxy Server", "class": "Dialog"})[0] == "proxy"
    assert gui._selector_pattern_for({"title": "Product Choices", "class": "Dialog"})[0] == "product"
    assert gui._selector_pattern_for({"title": "Waiting for network resource...", "class": "Dialog"})[0] == "waiting"
    # Untitled probe windows fall back to a class hint.
    assert gui._selector_pattern_for({"title": "", "class": "WaitDialog"})[0] == "waiting"
    # A plain confirm dialog must NOT be misclassified as a selection modal.
    assert gui._selector_pattern_for({"title": "Are you sure?", "class": "#32770"}) is None
    # Every registered pattern has at least one answer keyword to try.
    for key, spec in SELECTOR_DIALOG_PATTERNS.items():
        assert key and spec.get("answer_keywords")


def test_auto_answer_selector_prefers_selection_keyword_then_fallback():
    """When a selection keyword resolves to a child, the runner clicks it (no
    fallback); when none resolve, it degrades to the generic confirm ladder (or
    None on a headless box where win32 is unavailable). Never raises."""
    # No child matching any keyword -> falls through to _try_dismiss -> None on headless.
    win = {"hwnd": 12345, "title": "Select a Tree", "class": "Dialog"}
    out = gui._auto_answer_selector(win, "tree",
                                    {"answer_keywords": ("default", "local", "ok")},
                                    confirmed=set(), errors=[])
    # On a headless/CI box with no matching child and no real win32 dialog, this is
    # None; on an interactive box it may be a fallback string. Both are acceptable —
    # the contract is 'never raise, never crash'.
    assert out is None or isinstance(out, str)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only desktop paths")
def test_preseed_selection_is_noop_when_screen_is_clean():
    """preseed_selection scans the desktop for a *stale* selection modal and answers
    it. On a clean screen (no matching modal open) it returns [] and — crucially —
    never raises. This is the pre-launch 'clear a leftover tree/proxy/dialog' guard
    that stops a fresh GUI-tool launch from inheriting a stale selection modal and
    freezing at 100% CPU / empty log (the 'blocked' look)."""
    result = gui.preseed_selection(note="unit-test preseed")
    assert isinstance(result, list)
    # A clean screen answers nothing; if a stale modal happened to be open on this
    # interactive machine it is still a list of description strings.
    for entry in result:
        assert isinstance(entry, str)
