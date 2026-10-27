"""GUI tool runner: screens as logs, dialogs auto-dismissed, no license involved.

On this PREMIUM / no-license-required Sigrity install, a SMALL number of tools
genuinely open a real GUI window even when launched from the command line (no
batch surface exists that runs them headless -- currently just PowerTree and
Optimality, which have no confirmed `-b`/`-tcl` entry point and block on a
"Product Choices"/welcome dialog). For those, a console-oriented watcher
("bytes in run.log") misreads the run: zero output for a while looks like a
stall, and the old negative-rc / empty-log heuristic labelled that shape a
"license issue" -- impossible on this build, where no license exists to fail.

This module is the GUI-tool replacement for that model. Design:

* Process lifecycle is owned by the caller (core.jobs): `JobManager.submit`
  launches the exe the normal way (so `_procs`/`cancel()`/stale-state
  correction in `get()`/`wait()` all keep working), then starts
  `_gui_observe`, which calls `run_gui_tool` as a screen OBSERVER.
* `run_gui_tool` monitors the SCREEN in two modes: with `pid=<int>` it ATTACHES
  to a process the caller already launched (JobManager mode -- the caller keeps
  proc/_procs/cancel as the lifecycle authority) and screenshots it for its
  whole lifetime; with `pid=None` it LAUNCHES `exe_path *args` itself (one-shot
  convenience). Either way a screenshot every `interval` seconds (pyautogui) is
  saved under `workdir / screenshots/` as screen_01.png, screen_02.png, ...
* Dialogs owned by the process are found via the existing win32 enumeration
  in core.win32gui_helper and dismissed best-effort with the common confirm
  words (OK/Continue/Yes/Close/I Agree/Accept/Skip/Next/Don't show again).
* Outcomes are the fixed GUI-honest statuses below. A GUI tool is NEVER
  classified as a license failure by this module:

    status="success"                   process exited with return code 0
    status="failed"                    process exited non-zero
    status="running_long"              still running after `timeout_s`: a real
                                        long simulator run, not a hang; the
                                        caller is expected to keep the job
                                        'running' and let cancel()/wait manage it
    status="timeout"                   (reserved; the monitor ended abnormally
                                        before a normal observation)
    status="needs_user_intervention"   a dialog survived all dismissal attempts
                                        (latest shot renamed screen_NN_STUCK_Here.png)
                                        OR the runner prerequisites (pyautogui/PIL/
                                        pywin32) are unavailable on this host
                                        (headless / non-Windows dev machine)

WHY THIS SET IS SMALL AND MUST STAY SMALL (2026-10-26 correction):
The earlier version of this set lumped in PowerDC, PowerSI, XtractIM,
Clarity3DWorkbench, OptimizePI, XcitePI, XcitePICon, BroadbandSPICE, SPDSIM,
SPDsimCon and Celsius3D on the (wrong) premise that they "open a window and
block on a dialog even under their batch flags." That premise was disproven
live (2026-10-26): each of those tools, driven with its DOCUMENTED batch
invocation (PowerDC/PowerSI/XtractIM/XcitePI `--NoUI`-free `-b -tcl <script>`,
Clarity3DWorkbench `--NoUI -tcl`, OptimizePI `-b -export_data`, BroadbandSPICE
`-b -<mode>`, SPDSIM/-Con `-b <spd>`, Celsius3D `-tcl`), runs CONSOLE-ONLY with
ZERO windows and a real rc + (for most) real log output. Routing them through
this GUI observer was pure overhead that (a) made them "open the GUI" in the
screenshot/dismiss sense the user sees and (b) disabled the log-stall watchdog
(`stall_disabled=gui_tool` in core.jobs), which is why XcitePI-style runs
appeared to hang indefinitely. They are therefore NOT in GUI_TOOL_EXE_NAMES and
run as ordinary console jobs. Only the two tools with no confirmed headless
surface (PowerTree, Optimality -- both probed: open 1 window, stay alive) remain.
If Cadence ever adds a `-b`/`-tcl` surface to one of the two, move it out here;
if a new tool proves to open a window even on its batch flags, add it.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from sigrity_mcp.core import win32gui_helper
from sigrity_mcp.core.executables import SELECTOR_DIALOG_PATTERNS

GUI_TOOL_EXE_NAMES: frozenset[str] = frozenset({
    # ONLY the tools that open a real window even on their batch invocation and
    # have no confirmed headless surface. See the module docstring's 2026-10-26
    # correction for why the other 11 exes moved OUT of this set: under their
    # documented batch flags they run console-only with zero windows, so routing
    # them through the GUI observer was pure overhead (it "opened the GUI" in
    # screenshot/dismiss terms and disabled the log-stall watchdog).
    "PowerTree",
    "Optimality",
})
"""Exe stems (without .exe) that open a GUI on this install. This set is the
routing source of truth; core.executables.GUI_TOOL_NAMES mirrors it by logical
name for tool-facing messages. KEEP THIS LIST MINIMAL -- every stem here makes
its jobs skip the log-stall watchdog and attach a screen-watching/dialog-dismissing
observer, which is only correct for a tool that genuinely opens a window on its
batch flags."""

CONFIRM_BUTTON_WORDS: tuple[str, ...] = (
    "I Agree",
    "Accept",
    "Don't show again",
    "Continue",
    "Next",
    "Yes",
    "OK",
    "Okay",
    "Close",
    "Skip",
)
"""Button labels tried, in order of preference, when dismissing a dialog."""

DEFAULT_SCREENSHOT_INTERVAL = 2.0
MAX_DISMISS_ATTEMPTS = 3
"""How many dismissal attempts (across re-appearing dialogs) before giving up
and reporting needs_user_intervention with a STUCK_Here screenshot."""


def _normalize_window_text(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def _selector_pattern_for(win: dict) -> Optional[tuple[str, dict]]:
    """Match a dialog window against SELECTOR_DIALOG_PATTERNS; return (key, spec) or None.

    Matches case-insensitively against the dialog TITLE (primary signal) and, for the
    resource-'waiting' / tree / proxy patterns, the window CLASS (those probe windows are
    often untitled). This is what lets the runner tell 'make-a-selection' modals
    (select a tree / proxy / internet waiting) apart from ordinary confirm dialogs so it
    can answer them with a SELECTION (default/local/localhost/continue) instead of a bare
    OK — the reason most of this build's 'known blocked' labels stuck on an unclicked
    selection modal.
    """
    title = _normalize_window_text(win.get("title"))
    cls = _normalize_window_text(win.get("class"))
    for key, spec in SELECTOR_DIALOG_PATTERNS.items():
        if key in title:
            return (key, spec)
    # Untitled probe windows: fall back to class hints for the resource-waiting family.
    # These probe windows are often untitled, so a class substring is the only signal —
    # "wait" (not just "waiting") covers the "WaitDialog"/"WaitFor..." naming variants.
    if not title and cls:
        for key, hints in (
            ("waiting", ("wait", "check", "connect", "contact", "query")),
            ("proxy", ("prox",)),
            ("tree", ("tree", "bom", "model")),
        ):
            if any(h in cls for h in hints):
                return (key, SELECTOR_DIALOG_PATTERNS[key])
    return None


def _auto_answer_selector(win: dict, key: str, spec: dict, confirmed: set, errors: list) -> str:
    """Answer a selection modal by clicking the first matching selection keyword as a
    child button, else falling back to the default confirm-word ladder. Returns a
    description for dismissed_dialogs. Never raises.

    The difference from `_try_dismiss`: it tries the SELECTION keywords from the pattern
    (default/local/localhost/continue — the words that actually advance a tree/proxy/
    waiting modal) BEFORE the generic confirm words, and it targets a selection control
    (a button or the default-list row), not just an OK. If no selection keyword resolves,
    it degrades to `_try_dismiss` so we no longer do worse than before.

    MULTI-STEP SELECTIONS: some real dialogs (e.g. PowerSI/PowerDC's "Choose License
    Suites") are not a single click — they need a SEQUENCE of distinct controls driven,
    in order (e.g. click the "Choose all" checkbox button, then a SEPARATE "Close"
    button to finally dismiss the modal). A bare single-click answer (the original
    behavior, still what happens when `answer_steps` is absent, exactly as before)
    clicks the first matching keyword and stops, leaving the rest of the dialog
    unanswered. `spec["answer_steps"]`, if present, is a list of keywords to click IN
    ORDER, each an independent `_find_child_by_text`+`BN_CLICKED` attempt, with a short
    settle delay between clicks (so a control that only becomes clickable/enabled
    after the prior click's state change has a chance to appear); only if a step finds
    no matching child is it skipped (not treated as a hard failure — the dialog may
    legitimately not have that particular control on some build). If `answer_steps`
    is absent or empty, this function's behavior is byte-identical to the original
    single-keyword implementation above (full backward compatibility for the existing
    product/tree/proxy/waiting selector patterns).
    """
    steps = list(spec.get("answer_steps") or tuple())
    keywords = list(spec.get("answer_keywords", tuple()))
    to_try = steps if steps else keywords
    if win32gui_helper._WIN32:
        import time as _time

        import win32gui

        hwnd = win["hwnd"]
        clicked_any = False
        clicked_which = []
        for kw in to_try:
            child = win32gui_helper._find_child_by_text(hwnd, kw)
            if child:
                try:
                    import win32api
                    import win32con

                    win32api.PostMessage(child, win32con.WM_COMMAND, win32con.BN_CLICKED, 0)
                    clicked_any = True
                    clicked_which.append(kw)
                    if not steps:
                        # Single-keyword mode (original behavior): exactly one click,
                        # then done -- the "first match wins, stop" contract the other
                        # four selector patterns (product/tree/proxy/waiting) already
                        # rely on for plain "pick X, dialog closes" modals.
                        confirmed.add(hwnd)
                        return f"selection:auto-answer[{key}] '{kw}'"
                    _time.sleep(0.25)
                    # Multi-step mode: settle, then re-check the dialog is still there
                    # (some dialogs close themselves on an intermediate click, e.g. if
                    # a "Choose all" also triggers a confirmation) before trying the
                    # next step's control.
                    if not win32gui.IsWindow(hwnd):
                        break
                except Exception as e:
                    errors.append(f"selector {key} '{kw}': {e}")
        if clicked_any and steps:
            confirmed.add(hwnd)
            return f"selection:auto-answer[{key}] " + " then ".join(repr(k) for k in clicked_which)
    # No selection keyword resolved (or all steps found no matching child) — degrade to
    # the generic confirm dismiss ladder.
    fallback = _try_dismiss(win, confirmed, errors)
    if fallback is None:
        return None
    return f"selection:fallback[{key}] {fallback}"


@dataclass
class GuiToolResult:
    status: str
    screenshots: list[Path] = field(default_factory=list)
    dismissed_dialogs: list[str] = field(default_factory=list)
    error: Optional[str] = None
    returncode: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "screenshots": [str(p) for p in self.screenshots],
            "dismissed_dialogs": list(self.dismissed_dialogs),
            "error": self.error,
            "returncode": self.returncode,
        }


def is_gui_tool(exe) -> bool:
    """True if `exe` (a Path or a path string) is one of GUI_TOOL_EXE_NAMES."""
    return Path(str(exe)).stem in GUI_TOOL_EXE_NAMES


def preseed_selection(window_hints: Optional[dict] = None, note: str = "") -> list:
    """Resolve any ALREADY-OPEN selection modal (tree/proxy/waiting/product) on the
    desktop BEFORE a GUI tool is launched, so the new process doesn't inherit a stale
    one and freeze.

    This is phase 1 of the two-phase selection fix (phase 2 is the in-line ladder in
    `_blocking_attach_monitor`). It scans the whole desktop for top-level windows matching
    `SELECTOR_DIALOG_PATTERNS` (no pid — a stale modal from a prior run can be owned by
    any process, including a dead one) and auto-answers each with its default/local/
    localhost/continue selection. Idempotent and best-effort: it never raises, and if
    nothing matches it returns immediately with `[]`.

    Returns a list of descriptions (e.g. `['selector:product "default"']`) of anything it
    answered. Callers (core.jobs) record this on the job so a run doesn't look "blocked"
    just because a leftover selection dialog was waiting on a human.

    `window_hints` / `note` are accepted for forward-compat (the pre-seed today is
    desktop-global; a per-process variant can key off a pid later).
    """
    del window_hints, note
    answered: list = []
    if not win32gui_helper._WIN32:
        return answered
    try:
        import win32gui

        def _enum_callback(hwnd, _):
            try:
                if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                win = {"hwnd": hwnd, "title": title, "class": cls}
                if not _selector_pattern_for(win):
                    return
                errors: list = []
                confirmed: set = set()
                mkey, mspec = _selector_pattern_for(win)
                outcome = _auto_answer_selector(win, mkey, mspec, confirmed, errors)
                if outcome is not None:
                    answered.append(f"selector:{mkey} '{(title or cls) or 'untitled'}' -> {outcome}")
            except Exception:
                return

        win32gui.EnumWindows(_enum_callback, None)
    except Exception:
        pass
    return answered


def _load_imports() -> Optional[str]:
    """Import pyautogui/PIL/pywin32 once. Returns None on success, else a reason
    string (headless box, non-Windows dev machine, missing wheel). Never raises."""
    try:
        import pyautogui  # noqa: F401
        from PIL import Image  # noqa: F401

        import win32api  # noqa: F401
        import win32gui  # noqa: F401
        import win32process  # noqa: F401
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None


def _normalize_returncode(code: Optional[int]) -> Optional[int]:
    """Windows reports negative exit codes as their unsigned 32-bit wraparound
    (see core.process._normalize_returncode); undo that."""
    if code is not None and code > 0x7FFFFFFF:
        return code - 0x100000000
    return code


def _screenshot(shot_dir: Path, seq: int, errors: list) -> Optional[Path]:
    """Capture the screen to shot_dir/screen_<seq:02d>.png. Never raises."""
    try:
        import pyautogui

        path = shot_dir / f"screen_{seq:02d}.png"
        pyautogui.screenshot().save(path)
        return path
    except Exception as e:
        errors.append(f"screenshot: {e}")
        return None


def _try_dismiss(win: dict, confirmed: set, errors: list) -> Optional[str]:
    """Best-effort dismissal of one dialog window. Returns a description of what
    was done (for dismissed_dialogs) or None if nothing was attempted (window
    already gone or already handled). Never raises.

    Ladder:
      1. Classic Win32: find the first child button whose window text matches a
         confirm word and post WM_COMMAND/BN_CLICKED to it (what
         win32gui_helper already uses for #32770 dialogs).
      2. Coordinate-click fallback: click the matched child's center with
         pyautogui (covers buttons that ignore message posting).
      3. Textless dialogs (Qt): focus + VK_RETURN, VK_SPACE, then WM_CLOSE.
    """
    if not win32gui_helper._WIN32:
        return None
    import win32gui

    hwnd = win["hwnd"]
    try:
        if not win32gui.IsWindow(hwnd):
            return None
    except Exception:
        return None
    if hwnd in confirmed:
        return None

    for word in CONFIRM_BUTTON_WORDS:
        child = win32gui_helper._find_child_by_text(hwnd, word)
        if not child:
            continue
        try:
            import win32api
            import win32con

            win32api.PostMessage(child, win32con.WM_COMMAND, win32con.BN_CLICKED, 0)
        except Exception as e:
            errors.append(f"WM_COMMAND {word!r}: {e}")
            continue
        confirmed.add(hwnd)
        return word

    try:
        import pyautogui

        rect = win32gui.GetWindowRect(hwnd)
        sw, sh = pyautogui.size()
        for word in CONFIRM_BUTTON_WORDS:
            child = win32gui_helper._find_child_by_text(hwnd, word)
            if not child:
                continue
            crect = win32gui.GetWindowRect(child)
            cx = (crect[0] + crect[2]) // 2
            cy = (crect[1] + crect[3]) // 2
            if not (rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]):
                continue
            pyautogui.click(max(0, min(cx, sw - 1)), max(0, min(cy, sh - 1)))
            confirmed.add(hwnd)
            return f"{word} (coordinate-click)"
    except Exception as e:
        errors.append(f"coordinate-click: {e}")

    try:
        import win32api
        import win32con

        try:
            win32gui.SetFocus(hwnd)
        except Exception:
            pass
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        time.sleep(0.1)
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_SPACE, 0)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_SPACE, 0)
        time.sleep(0.15)
        if win32gui.IsWindow(hwnd):
            win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    except Exception as e:
        errors.append(f"key/WM_CLOSE fallback: {e}")
    confirmed.add(hwnd)
    return "Enter/Space/WM_CLOSE (no button text found)"


def _blocking_attach_monitor(
    pid: int,
    shot_dir: Path,
    timeout_s: float,
    interval: float,
    max_dismiss_attempts: int,
    return_at_timeout: bool = False,
    on_running_long=None,
) -> tuple[str, Optional[int], list, list[Path], list]:
    """Attach to an already-running process and screenshot/dismiss dialogs.
    Returns (status, returncode, dismissed_dialogs, screenshots, error_notes).
    NEVER kills the attached process; the caller owns that lifecycle.

    `return_at_timeout` controls what happens once the process has outlived
    `timeout_s`:
      * True  -> return status="running_long" immediately (one-shot caller
        that only wants to know "is this still going?").
      * False -> keep screenshotting + dismissing for the process's whole
        lifetime (JobManager path: the job stays tracked and the screenshots
        folder keeps growing until the tool really exits). The
        running_long event is still recorded in error_notes so the job record
        can surface it, but the monitor does not end early.
    """
    errors: list = []
    shots: list[Path] = []
    dismissed: list = []
    confirmed: set = set()
    start = time.monotonic()
    seq = 0
    attempts = 0
    reported_long = False

    while True:
        # 1) Screenshot: for a GUI tool the screen IS the log.
        shot = _screenshot(shot_dir, seq, errors)
        if shot is not None:
            shots.append(shot)
        seq += 1

        # 2) Process exited?
        rc = _peek_exit_code(pid)
        if rc is not None:
            rc = _normalize_returncode(rc)
            status = "success" if rc == 0 else "failed"
            final_shot = _screenshot(shot_dir, seq, errors)
            if final_shot is not None:
                shots.append(final_shot)
            errors.append(
                f"attached monitor: process {pid} exited with code {rc} "
                f"after {(time.monotonic() - start):.0f}s of screen monitoring"
            )
            return (status, rc, dismissed, shots, errors)

        # 3) Past timeout_s while still alive: a long-running simulator, NOT
        #    a hang. One-shot callers report running_long and return;
        #    lifetime callers keep monitoring and get a one-shot callback.
        if time.monotonic() - start >= timeout_s:
            if return_at_timeout:
                errors.append(
                    f"process still running after {timeout_s:.0f}s; returned "
                    "running_long without touching the process (caller keeps it "
                    "running and manages its lifecycle)"
                )
                return ("running_long", None, dismissed, shots, errors)
            if not reported_long:
                reported_long = True
                errors.append(
                    f"process still running after {timeout_s:.0f}s: RUNNING_LONG "
                    "(long simulator run, not a hang); continuing to screenshot "
                    "until it exits"
                )
                if on_running_long is not None:
                    try:
                        on_running_long(timeout_s)
                    except Exception as e:
                        errors.append(f"on_running_long callback: {e}")

        # 4) Dialog handling.
        try:
            dialogs = win32gui_helper.find_dialogs(pid)
        except Exception as e:
            dialogs = []
            errors.append(f"find_dialogs: {e}")
        if dialogs:
            d = dialogs[0]
            errors.append(f"dialog found: class={d.get('class')!r} title={d.get('title')!r}")
            # Selection modals (select a tree / proxy / internet-waiting) need a
            # SELECTION answer, not a bare OK — that's what most 'blocked' runs stuck
            # on. Check the selection ladder first, then the generic confirm ladder.
            matched = _selector_pattern_for(d)
            if matched is not None:
                mkey, mspec = matched
                outcome = _auto_answer_selector(d, mkey, mspec, confirmed, errors)
            else:
                outcome = _try_dismiss(d, confirmed, errors)
            if outcome is not None:
                attempts += 1
                dismissed.append(f"{d.get('title') or '<untitled>'} -> {outcome}")
            if attempts >= max_dismiss_attempts:
                if shots:
                    stuck = shots[-1].with_name(f"{shots[-1].stem}_STUCK_Here.png")
                    try:
                        shots[-1].rename(stuck)
                        shots[-1] = stuck
                    except OSError as e:
                        errors.append(f"rename STUCK screenshot: {e}")
                errors.append(
                    f"dialog still present after {attempts} dismissal attempts; a "
                    "human needs to click it (see STUCK_Here screenshot)"
                )
                # Leave the process RUNNING: JobManager owns it, keeps the job
                # in needs_user_intervention, and the caller can still
                # cancel() it.
                return ("needs_user_intervention", None, dismissed, shots, errors)
        time.sleep(interval)


def _peek_exit_code(pid: int) -> Optional[int]:
    """Return the process's exit code if it has already exited, else None.
    OpenProcess(PROCESS_QUERY_INFORMATION)+GetExitCodeProcess works for
    same-user processes (every Sigrity tool on this machine is launched by
    this server's user). A process that is alive but has no retrievable code
    (rare: still_active or a transient open failure) reads as None and is
    kept polling -- the attached monitor is a side observation, and the
    JobManager's own proc.wait() is the authoritative exit signal."""
    try:
        import ctypes

        PROCESS_QUERY_INFORMATION = 0x0400
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            return None
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        if ok and code.value != STILL_ACTIVE:
            return code.value
        return None
    except Exception:
        return None


def _blocking_launch_monitor(
    exe: str,
    args: list,
    workdir: str,
    timeout_s: float,
    shot_dir: Path,
    interval: float,
    max_dismiss_attempts: int,
) -> tuple[str, Optional[int], list, list[Path], list]:
    """Convenience: launch AND monitor, as a one-shot. The process is owned by
    THIS function and is reaped on every outcome except running_long/
    needs_user_intervention (both left running for the caller, who is
    expected to manage/cancel them). The JobManager path does NOT use this:
    it launches the process itself and calls run_gui_tool(pid=...) so that
    _procs/cancel() stay in control of the lifecycle."""
    try:
        proc = subprocess.Popen(
            [exe, *args],
            cwd=workdir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except OSError as e:
        return ("failed", None, [], [], [f"could not launch {Path(exe).name}: {e}"])
    status, rc, dismissed, shots, errors = _blocking_attach_monitor(
        proc.pid,
        shot_dir,
        timeout_s,
        interval,
        max_dismiss_attempts,
        return_at_timeout=True,
    )
    if status in ("success", "failed", "timeout"):
        # Already exited (success/failed) or the monitor died (timeout): make
        # sure the process is really down before returning.
        try:
            proc.wait(timeout=10)
        except Exception:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
    return (status, rc, dismissed, shots, errors)


async def run_gui_tool(
    exe_path: Path,
    args: list,
    workdir: Path,
    timeout_s: float,
    job_name: str,
    pid: Optional[int] = None,
    screenshot_interval: float = DEFAULT_SCREENSHOT_INTERVAL,
    max_dismiss_attempts: int = MAX_DISMISS_ATTEMPTS,
    on_running_long: Optional[Callable[[float], None]] = None,
) -> GuiToolResult:
    """Monitor a GUI tool run: screenshot the screen, dismiss dialogs, report.

    Two modes:
      * `pid=None` (default): LAUNCH `exe_path *args` in `workdir`, then
        monitor (and reap, per mode) that new process. One-shot convenience
        for MCP tool callers that want the whole run tracked here.
      * `pid=<int>`: DO NOT launch; ATTACH to the already-running process and
        monitor it for its whole lifetime (return_at_timeout=False): keep
        screenshotting until the process actually exits. This is the
        JobManager path -- it launched the exe itself so that _procs/cancel/
        get()/wait() stay the lifecycle authority. The attached process is
        NEVER killed by this function.

    Screenshot layout: `workdir / screenshots / screen_01.png`, `screen_02.png`,
    ... A dialog that survives `max_dismiss_attempts` dismissal attempts
    renames the latest shot to `screen_NN_STUCK_Here.png` and the status
    becomes "needs_user_intervention" (NOT a license failure -- this install
    is no-license-required; an un-clicked dialog is the whole story). If the
    process outlives `timeout_s`, the status is "running_long" (long simulator
    run, NOT a stall) and, in attach mode, monitoring continues until exit.

    `on_running_long(timeout_s)`: in attach mode, fired exactly once when the
    process first outlives `timeout_s` (so the caller can surface RUNNING_LONG
    on the job record while screenshots keep accumulating); unused in launch
    mode except as a diagnostic.

    Headless / non-Windows / missing wheels: returns "needs_user_intervention"
    with a clear error instead of raising, and launches nothing.
    `job_name` is accepted for API symmetry (the runner keys everything off
    `workdir`); it is not used to build paths.
    """
    del job_name
    workdir = Path(workdir)
    shot_dir = workdir / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    # PRE-SEED (phase 1): clear any stale selection modal (tree/proxy/waiting/product)
    # left open on the desktop by a prior run BEFORE launching, so the new process
    # doesn't inherit it and freeze at 100% CPU with an empty log. Idempotent; no-op if
    # the screen is clear. This is the direct answer to "every open asks to select a
    # tree / proxy / internet-waiting".
    preseeded = preseed_selection(note=f"pre-launch preseed for {Path(exe_path).name}")

    unavailable = _load_imports()
    if unavailable is not None:
        return GuiToolResult(
            status="needs_user_intervention",
            screenshots=[],
            dismissed_dialogs=[],
            error=(
                f"GUI tool runner unavailable on this host ({unavailable}). "
                f"Launch '{Path(exe_path).name}' manually on an interactive "
                "desktop: this tool opens GUI windows and its startup dialogs "
                "need a screen to watch and dismiss."
            ),
            returncode=None,
        )

    loop = asyncio.get_running_loop()
    try:
        if pid is None:
            outcome = await loop.run_in_executor(
                None,
                lambda: _blocking_launch_monitor(
                    str(exe_path),
                    list(args),
                    str(workdir),
                    float(timeout_s),
                    shot_dir,
                    screenshot_interval,
                    max_dismiss_attempts,
                ),
            )
        else:
            outcome = await loop.run_in_executor(
                None,
                lambda: _blocking_attach_monitor(
                    int(pid),
                    shot_dir,
                    float(timeout_s),
                    screenshot_interval,
                    max_dismiss_attempts,
                    return_at_timeout=False,
                    on_running_long=on_running_long,
                ),
            )
    except Exception as e:
        return GuiToolResult(
            status="failed",
            screenshots=[],
            dismissed_dialogs=[],
            error=f"gui_tool_runner internal error: {type(e).__name__}: {e}",
            returncode=None,
        )

    status, rc, dismissed, shots, errors = outcome
    # Pre-launch pre-seeded selection modals are part of "what the runner dismissed" —
    # surface them first so a run that auto-answered a stale tree/proxy/waiting dialog
    # before launching is never mistaken for a stuck/blocked launch.
    dismissed = list(preseeded) + list(dismissed)
    error_notes = " ".join(dict.fromkeys(errors)) or None
    if status == "failed" and rc is not None and error_notes is None:
        error_notes = f"process exited with return code {rc}"
    if status == "running_long":
        suffix = (
            "process still running after the timeout window; it was LEFT RUNNING "
            "-- keep polling the job (screenshots keep growing) or cancel it"
        )
        error_notes = f"{error_notes} {suffix}" if error_notes else suffix
    return GuiToolResult(
        status=status,
        screenshots=[p for p in shots if p.is_file()],
        dismissed_dialogs=dismissed,
        error=error_notes,
        returncode=rc,
    )
