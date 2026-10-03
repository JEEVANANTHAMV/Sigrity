"""Reusable Win32 dialog-observation / auto-dismiss helper for Cadence tools that pop
GUI confirmations in batch/headless mode.

Several Cadence exes (Celsius3D, Allegro, orCAD Capture, T2B, T2B's HSpice client)
initialise a Qt or classic-Win32 GUI even when driven from the command line, and block
on a modal dialog when they detect something that "should" be confirmed by a human —
overwriting an existing result folder, a "Product Choices" picker, an error/warning
before launch, etc.  In a headless MCP job there is no one to click the button, so the
tool hangs indefinitely with an empty log and JobManager has to kill it on timeout.

This module is a best-effort companion to any job launch that can run in two modes:

  * `find_process_windows(pid)` / `find_dialogs(pid)` — pure observation: list the
    top-level windows (and specifically the dialog windows) a process has open.  Use
    this from a job watcher or a side-task to see WHY a tool is stuck.

  * `auto_dismiss_dialogs(pid, ...)` — poll, find every dialog window the process owns,
    and drive it closed the way a human would: click the Yes/OK/Confirm child by its
    window text (works for classic Win32 "#32770" dialogs), fall back to posting a
    VK_RETURN/VK_SPACE to the dialog (works for Qt dialogs that honour the default
    button), then a final WM_CLOSE.  Never raises; safe to run from an async job
    watcher as a side-task.

CONFIRMED BEHAVIOUR ON THIS MACHINE (Sigrity 2024.0):
  * Celsius3D.exe -tcl <case.tcl> — a "fresh" run actually COMPLETES the full
    simulation and writes the entire `case_SS_W/` result set (including a 21 MB
    SR3d.dat and `case_Result_Summary.dat/.json`), and THEN leaves the Celsius3D.exe
    process alive and idle (CPU frozen, main Qt workbench window open, NO modal
    dialog in the window tree).  The "hang" a first-time run appears to show is a
    post-completion exit stall, not an overwrite-confirmation prompt.  There is no
    button in the process's window tree to click, so `auto_dismiss_dialogs`
    correctly polls to its timeout and returns without dismissing anything.  It is
    the RIGHT general-purpose scaffolding for a tool that DOES pop a real dialog
    (the "Product Choices" dialog that initially blocked allegro.exe/Capture.exe,
    per the module docstring in allegro_project_tools.py), but it is NOT what is
    needed to unblock the Celsius3D re-run specifically — the confirmed workaround
    for Celsius3D (see celsius3d_tools.py) remains: copy the project to a fresh
    location before re-running.
  * T2B.exe -help (or any T2B invocation) — does not exit on -help; runs
    indefinitely.  No HSpice COM object is registered
    (HKCR\\HSpice.Application / HKCR\\HSpice.HSpice both absent from the registry)
    and no HSpice engine ships with Sigrity Suite 2024.0 — only hspiceD Artist
    library templates under the SPB_22.1 install and `.t2b` sample files under
    share/SpeedXP/Samples/T2B.  T2B expects to invoke an EXTERNAL HSPICE process
    (or a HSPICE server in Client-Server mode) — see the "Running HSPICE in
    Client-Server Mode" section of doc/t2b_qref and doc/t2b_hspice.  No Cadence
    COM-based SPICE alternative (HSpice COM, chsim COM, SimSrvr COM) is registered
    on this machine — chsim.exe/SimSrvr.exe/tlsim.exe/cktsim.exe exist as SPB
    CLI/GUI simulators but none expose a COM interface T2B can drive.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Sequence

try:
    import win32api
    import win32con
    import win32gui
    import win32process

    _WIN32 = True
except Exception:  # non-Windows dev machine
    win32api = win32con = win32gui = win32process = None  # type: ignore
    _WIN32 = False

# Child-control window-text substrings (case-insensitive) that, if matched under a
# dialog, mark it as a dismissal candidate for a "yes, do it" response.  Ordered by
# preference — the first one found is the one we click.
DEFAULT_CONFIRM_WORDS: tuple[str, ...] = ("yes", "ok", "okay", "confirm", "continue",
                                          "overwrite", "replace")

# Window class names that mark a top-level window as a MODAL DIALOG worth dismissing,
# as opposed to the app's main shell window (which we must never close).  A classic
# Win32 dialog has class "#32770"; a Qt dialog typically has a class like
# "Qt5159QWindow..." (version varies) and is NOT the largest visible window the
# process owns.
_DIALOG_CLASSES = {"#32770", "Dialog"}

# Classes that are DEFINITELY main-shell windows we must never touch.
_SHELL_CLASS_HINTS = ("qmain", "mainwindow", "mdi", "frame")


def _window(pid_filter: int | None):
    """Yield (hwnd, class, title, rect, visible) for every TOP-LEVEL window whose owner
    PID matches `pid_filter` (or every top-level window if `pid_filter is None`)."""
    if not _WIN32:
        return
    collect: list = []

    def _cb(hwnd, _):
        try:
            _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return
        if pid_filter is not None and win_pid != pid_filter:
            return
        try:
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            rect = list(win32gui.GetWindowRect(hwnd))
            visible = win32gui.IsWindowVisible(hwnd)
        except Exception:
            return
        collect.append((hwnd, cls, title, rect, visible))

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    for item in collect:
        yield item


def find_process_windows(pid: int) -> list[dict]:
    """All top-level windows owned by `pid`, as [{hwnd, class, title, rect, visible}, ...]."""
    return [
        {"hwnd": h, "class": c, "title": t, "rect": r, "visible": v}
        for (h, c, t, r, v) in _window(pid)
    ]


def _is_dialog_class(cls: str) -> bool:
    return cls in _DIALOG_CLASSES


def _looks_like_shell(cls: str, rect, largest: bool, title: str) -> bool:
    """Heuristic: `True` if this window is almost certainly the app's main shell and
    must NOT be closed regardless of dialog heuristics."""
    lc = cls.lower()
    if any(h in lc for h in _SHELL_CLASS_HINTS):
        return True
    # A window whose rect covers nearly the whole monitor is very likely the main
    # workbench, even if its class happens to match a dialog class.
    try:
        w, h = (rect[2] - rect[0]), (rect[3] - rect[1])
        sw, sh = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        if largest and sw and sh and (w > 0.9 * sw and h > 0.7 * sh):
            return True
    except Exception:
        return False
    return False


def find_dialogs(pid: int) -> list[dict]:
    """Top-level windows owned by `pid` that look like a MODAL DIALOG worth dismissing
    (i.e. NOT the app's main shell).  Same dict shape as find_process_windows."""
    wins = find_process_windows(pid)
    if not wins:
        return []
    # Largest visible window area, for the shell heuristic below.
    def area(r):
        return max(0, r[2] - r[0]) * max(0, r[3] - r[1])
    visible = [w for w in wins if w["visible"]]
    if not visible:
        return []
    max_a = max(area(w["rect"]) for w in visible)
    out = []
    for w in wins:
        if not w["visible"]:
            continue
        is_dialog = _is_dialog_class(w["class"]) or ("qt" in w["class"].lower()
                                                     and "icon" in w["class"].lower())
        if not is_dialog:
            continue
        if _looks_like_shell(w["class"], w["rect"], area(w["rect"]) == max_a, w["title"]):
            continue
        out.append(w)
    return out


def _post_click(child_hwnd) -> None:
    if not _WIN32 or not child_hwnd:
        return
    try:
        win32api.PostMessage(child_hwnd, win32con.WM_COMMAND, win32con.BN_CLICKED, 0)
    except Exception:
        pass


def _post_key(hwnd, vk) -> None:
    if not _WIN32:
        return
    try:
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)
    except Exception:
        pass


def _post_close(hwnd) -> None:
    if not _WIN32:
        return
    try:
        win32api.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    except Exception:
        pass


def _find_child_by_text(parent_hwnd, word: str) -> int:
    """Return the first child window of `parent_hwnd` whose window text == `word`
    (case-insensitive), else 0."""
    if not _WIN32:
        return 0
    word_u = word.upper().strip()
    found = [0]

    def _cb(child, _):
        if found[0]:
            return
        try:
            t = win32gui.GetWindowText(child).upper().strip()
        except Exception:
            return
        if t == word_u:
            found[0] = child

    try:
        win32gui.EnumChildWindows(parent_hwnd, _cb, None)
    except Exception:
        pass
    return found[0]


def auto_dismiss_dialogs(
    pid: int,
    poll_seconds: float = 0.25,
    timeout: float = 30.0,
    confirm_words: Sequence[str] = DEFAULT_CONFIRM_WORDS,
    on_dialog_found: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Poll for dialog windows owned by `pid` and drive each one closed, for up to
    `timeout` seconds.  Returns {"dismissed": [(hwnd, title), ...], "polled": int,
    "errors": [str, ...]}.  Never raises.

    Dismissal steps, in order, per discovered dialog:
      1. Find a child button whose window text exactly matches one of `confirm_words`
         (Yes/OK/Confirm/...); post WM_COMMAND BN_CLICKED to it.  This is what
         dissolves a classic Win32 "#32770" overwrite-confirmation dialog.
      2. Focus the dialog and post a WM_KEYDOWN/UP for VK_RETURN, then VK_SPACE —
         covers Qt dialogs that expose no window text for their buttons but honour
         a default-button Enter.
      3. If the dialog still exists a beat later, post WM_CLOSE.
    """
    if not _WIN32:
        return {"dismissed": [], "polled": 0, "errors": ["win32 not available on this platform"]}
    dismissed: list = []
    errors: list = []
    seen: set = set()
    deadline = time.monotonic() + timeout
    polled = 0

    while time.monotonic() < deadline:
        polled += 1
        try:
            for d in find_dialogs(pid):
                hwnd = d["hwnd"]
                if hwnd in seen:
                    continue
                seen.add(hwnd)
                if on_dialog_found:
                    try:
                        on_dialog_found(d)
                    except Exception as e:  # pragma: no cover
                        errors.append(f"on_dialog_found: {e}")
                clicked = False
                for word in confirm_words:
                    child = _find_child_by_text(hwnd, word)
                    if child:
                        _post_click(child)
                        clicked = True
                        break
                if not clicked:
                    try:
                        win32gui.SetFocus(hwnd)
                    except Exception:
                        pass
                    _post_key(hwnd, win32con.VK_RETURN)
                    time.sleep(0.05)
                    _post_key(hwnd, win32con.VK_SPACE)
                # Give a beat for the click/key to land, then a final WM_CLOSE if
                # the window is still there.
                time.sleep(0.15)
                try:
                    if win32gui.IsWindow(hwnd):
                        _post_close(hwnd)
                except Exception as e:  # pragma: no cover
                    errors.append(f"WM_CLOSE: {e}")
                try:
                    title = win32gui.GetWindowText(hwnd)
                except Exception:
                    title = d["title"]
                dismissed.append((hwnd, title))
        except Exception as e:  # pragma: no cover
            errors.append(str(e))
            break
        time.sleep(poll_seconds)
    return {"dismissed": dismissed, "polled": polled, "errors": errors}


def launch_and_dismiss(exe: str, args: Sequence[str], cwd: Optional[str] = None,
                       timeout: float = 120.0,
                       confirm_words: Sequence[str] = DEFAULT_CONFIRM_WORDS) -> dict:
    """Spawn `exe *args` as a detached new-process-group child and run
    `auto_dismiss_dialogs` on it for up to `timeout` seconds.

    For proof-of-concept use.  Production MCP jobs already run through
    core.jobs.JobManager and should run this as a side-task in parallel with the
    job's `_watch`, keyed on the JobRecord.pid, rather than spawning a second copy
    of the tool here (see celsius3d_tools / the integration note in core.jjobs).

    Returns {"pid": int, "proc": Popen, "dismiss": dict}.
    """
    if not _WIN32:
        raise RuntimeError("launch_and_dismiss requires pywin32 (Windows only)")
    import subprocess

    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    proc = subprocess.Popen(
        [exe, *args],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
    )
    dismiss = auto_dismiss_dialogs(proc.pid, timeout=timeout, confirm_words=confirm_words)
    return {"pid": proc.pid, "proc": proc, "dismiss": dismiss}


class DismissWatcher:
    """Background daemon thread that keeps calling `auto_dismiss_dialogs` against one
    `pid` for as long as the watcher is running, so a dialog is caught and dismissed
    whenever it appears during the process's lifetime -- not just during one bounded
    polling window a caller remembered to kick off by hand.

    ROOT CAUSE this exists to fix: an interactive Allegro session job
    (`allegro.exe -s <script.scr> <board.brd>`, launched via `core.jobs.JobManager.submit`)
    can raise a short-lived modal dialog during startup -- CONFIRMED live on this machine
    via a fresh repro against the Fault-Detector reference board: a top-level window
    (class `Qt5QWindowIcon`, title identical to the app's own name -- Qt's default
    caption for a `QMessageBox`/similar with no explicit title set, which is why a naive
    title-text search for something distinctive misses it) appears a fraction of a
    second into the run, and the MAIN shell window's `enabled` bit flips to 0 (truly
    WS_DISABLED, i.e. a real native-modal relationship) for as long as it is up. The
    dialog can disappear again within a couple of seconds on its own in some runs,
    but there is no guarantee of that -- without something polling fast enough to catch
    and dismiss it while it is up, the handful of runs where it does NOT self-clear hang
    the whole job indefinitely with an empty `run.log` (the banner is the only thing ever
    printed to stdout; everything else goes to Allegro's own journal/trace files, not the
    job's log). Previously this only ever got dismissed if the calling LLM agent (or a
    one-off script like `scripts/smoke_multilayer_stackup.py`) remembered to separately
    poll `auto_dismiss_dialogs(pid)` concurrently -- which a plain MCP tool caller has no
    way to do. `core.jobs.JobManager.submit(..., dismiss_dialogs=True)` now starts one of
    these automatically for every interactive Allegro session job and stops it the
    moment the job ends, so this is no longer something any caller has to remember.

    Runs in a real OS thread (not an asyncio task) deliberately: `auto_dismiss_dialogs`
    blocks for its whole `dialog_timeout` on every call (it polls to the full deadline
    even when nothing is found, by design), and `JobManager.submit`/`_watch` run on the
    single asyncio event loop that every other concurrent MCP tool call shares -- calling
    it there directly would stall the whole server for `dialog_timeout` seconds at a time.
    """

    def __init__(
        self,
        pid: int,
        poll_seconds: float = 0.5,
        dialog_timeout: float = 1.0,
        confirm_words: Sequence[str] = DEFAULT_CONFIRM_WORDS,
        on_dialog_found: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.pid = pid
        self.poll_seconds = poll_seconds
        self.dialog_timeout = dialog_timeout
        self.confirm_words = confirm_words
        self.on_dialog_found = on_dialog_found
        self.dismissed: list = []
        self.errors: list = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> "DismissWatcher":
        if not _WIN32:
            # Nothing to watch on a non-Windows dev/CI machine -- stop()/join() below
            # are safe no-ops since self._thread stays None.
            return self
        self._thread = threading.Thread(
            target=self._run, name=f"dismiss-watcher-{self.pid}", daemon=True
        )
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                result = auto_dismiss_dialogs(
                    self.pid,
                    timeout=self.dialog_timeout,
                    confirm_words=self.confirm_words,
                    on_dialog_found=self.on_dialog_found,
                )
                self.dismissed.extend(result["dismissed"])
                self.errors.extend(result["errors"])
            except Exception as e:  # pragma: no cover - a watcher must never crash the job
                self.errors.append(str(e))
            self._stop.wait(self.poll_seconds)

    def stop(self, join_timeout: float = 5.0) -> None:
        """Idempotent: safe to call more than once (e.g. once from a job's normal
        completion path and once from an explicit cancel())."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)


def spawn_dismiss_watcher(pid: int, **kwargs) -> DismissWatcher:
    """Create and start a `DismissWatcher` for `pid`. Caller owns the returned object and
    must call `.stop()` once the watched process's job is done (whether it succeeded,
    failed, or was cancelled) to stop the background thread."""
    return DismissWatcher(pid, **kwargs).start()
