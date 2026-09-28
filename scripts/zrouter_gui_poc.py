"""Proof-of-concept: drive zrouter non-interactively.

WHAT I FOUND (why the GUI/win32 approach does NOT apply)
--------------------------------------------------------
Standalone `zrouter.exe` is NOT a modal GUI. When launched on its own with a board file
it runs as a CONSOLE program that interactively (re)prompts on stdin:

    I/O pin connections file name:
    X-grid spacing value:
    Y-grid spacing value:
    X-grid offset value:
    Y-grid offset value:
    minimum I/O pad to via pad spacing value:

With no console (detached/pipe) it loops on `illegal value ''` (EOF -> empty string) and
exits quietly. The doc's "Z router D ialog Box" (doc/zcoms/zchap.html, "Running zrouter")
is the DIALOG SHOWN INSIDE A LIVE ALLEGRO PCB EDITOR session: "Choose Route -> Zrouter to
display the Zrouter dialog box. Alternatively, type zrouter in the Command window." So the
actual GUI is Allegro's, and the only real Run path is inside Allegro.

HOW THIS POC DRIVES IT
----------------------
Launch `allegro.exe -s <macro.scr> <board.brd>` (the project's proven batch mechanism,
see allegro_tools.py) where the first macro line is the bare `zrouter` command. Allegro
loads the board, replays `zrouter`, and the Zrouter dialog opens. This script then:
  1. waits for a top-level window owned by the allegro.exe pid that looks like the
     Zrouter dialog (title contains "Zrouter" or "zrouter", else falls back to any new
     child dialog),
  2. enumerates child controls (class + caption + rect, logged so a permanent wrapper can
     hardcode the real values),
  3. fills the Edit fields in layout order = [connections_file, x_grid, y_grid, x_off,
     y_off, min_dist] (the doc's exact field order),
  4. clicks the button whose caption contains "Run" (BM_CLICK, 0x00F5),
  5. reports completion + Zrouter.log.

The win32 mechanics reuse this project's existing ctypes helpers pattern
(sigrity_mcp/domains/cad/capture_tools.py's _find_window/_click_button_in_window), plus
WM_SETTEXT for the text fields. It uses pywin32 only for the process handle/wait; the
window automation is pure ctypes so it matches the suite's other dialog handlers.

Caveats (why this stays a PoC until the dialog's real control class/captions are
observed once and hardcoded):
  - the dialog's Edit controls may report class "Edit" or a Cadence custom class;
  - the "Run" button caption may be "Run"/"Run Zrouter"/"OK";
  - zrouter only routes vias on MLC-module I/O pins to ETCH subclasses, so it needs a
    board+cnv whose nets/refdes actually match; a mismatch is a real but silent no-op;
  - licensing: a live Allegro session must hold a license.

Usage:
    python scripts/zrouter_gui_poc.py <board.brd> <connections.cnv>
Env: SIGRITY_ZROUTER_TIMEOUT (seconds, default 90)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
from pathlib import Path

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

_PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]

ALLEGRO = r"C:\Cadence\SPB_22.1\tools\allegro.exe" if os.path.exists(r"C:\Cadence\SPB_22.1\tools\allegro.exe") else (
    r"C:\Cadence\SPB_22.1\tools\bin\allegro.exe"
)

# doc field order for the Zrouter dialog:
#   [Connections file name] [X-grid spacing] [Y-grid spacing]
#   [X-grid offset] [Y-grid offset] [Min. Distance between via and pad edge]
FIELD_DEFAULTS = [None, "0", "0", "0", "0", "0"]


def _get_pid(hwnd) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(pid))
    return pid.value


def _enum_children(hwnd: int) -> list[int]:
    found: list[int] = []

    def _c(h, _l):
        found.append(h)
        return True

    user32.EnumChildWindows.argtypes = [wt.HWND, _PROC, wt.LPARAM]
    user32.EnumChildWindows.restype = wt.BOOL
    user32.EnumChildWindows(wt.HWND(hwnd), _PROC(_c), 0)
    return found


def _info(hwnd: int) -> dict:
    cls = ctypes.create_unicode_buffer(128)
    txt = ctypes.create_unicode_buffer(512)
    user32.GetClassNameW(wt.HWND(hwnd), cls, 128)
    user32.GetWindowTextW(wt.HWND(hwnd), txt, 512)
    rect = wt.RECT()
    user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(rect))
    return {
        "hwnd": hwnd,
        "class": cls.value,
        "text": txt.value,
        "rect": (rect.left, rect.top, rect.right, rect.bottom),
        "visible": bool(user32.IsWindowVisible(wt.HWND(hwnd))),
        "enabled": bool(user32.IsWindowEnabled(wt.HWND(hwnd))),
    }


def _set_text(hwnd: int, text: str) -> bool:
    buf = ctypes.create_unicode_buffer(text)
    # WM_SETTEXT = 0x000C
    return bool(user32.SendMessageW(wt.HWND(hwnd), 0x000C, 0, ctypes.cast(buf, ctypes.c_wchar_p)))


def _click(hwnd: int) -> None:
    user32.SendMessageW(wt.HWND(hwnd), 0x00F5, 0, 0)  # BM_CLICK


def _find_allegro_top_windows(pid: int) -> list[int]:
    found: list[int] = []

    def _cb(hwnd, _l):
        if _get_pid(hwnd) == pid and user32.IsWindowVisible(wt.HWND(hwnd)):
            found.append(hwnd)
    user32.EnumWindows.argtypes = [_PROC, wt.LPARAM]
    user32.EnumWindows.restype = wt.BOOL
    user32.EnumWindows(_PROC(_cb), 0)
    return found


def _find_zrouter_dialog(pid: int, timeout: float) -> int:
    """Find the Zrouter dialog window. Prefer one whose title contains 'zrouter' (case-
    insensitive); fall back to any small top-level/child dialog window owned by pid that
    is not the main Allegro editor frame."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for hwnd in _find_allegro_top_windows(pid):
            txt = _info(hwnd)["text"].lower()
            if "zrouter" in txt:
                return hwnd
        time.sleep(0.5)
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    board = str(Path(sys.argv[1]).resolve())
    conn = str(Path(sys.argv[2]).resolve())
    timeout = float(os.environ.get("SIGRITY_ZROUTER_TIMEOUT", "90"))

    for p, label in [(board, "board"), (conn, "connections file"), (ALLEGRO, "allegro.exe")]:
        if not Path(p).is_file():
            print(f"[zrouter-poc] FAIL: {label} missing: {p}")
            return 1

    # Build a macro that opens (via the positional arg) then invokes zrouter.
    macro = Path(board).with_name("zrouter_poc.scr")
    macro.write_text("zrouter\n", encoding="ascii")
    print(f"[zrouter-poc] macro: {macro}\n  {macro.read_text()!r}")

    proc = subprocess.Popen(
        [ALLEGRO, "-s", str(macro), board],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=str(Path(board).parent),
    )
    print(f"[zrouter-poc] launched allegro.exe pid={proc.pid}")

    try:
        hwnd = 0
        # The dialog should appear shortly after Allegro loads the board.
        t0 = time.time()
        while time.time() - t0 < timeout and not hwnd:
            if proc.poll() is not None:
                print(f"[zrouter-poc] FAIL: allegro exited early, code={proc.returncode}")
                return 1
            hwnd = _find_zrouter_dialog(proc.pid, 0.5)
            time.sleep(0.3)

        if not hwnd:
            print(f"[zrouter-poc] no 'zrouter' dialog titled window found within {timeout}s. "
                  f"Listing ALL visible allegro top-level windows:")
            for w in _find_allegro_top_windows(proc.pid):
                print(f"   hwnd={w} title={_info(w)['text']!r}")
            # Fallback: also look for child dialogs of the main frame.
            print("   (If the dialog is a child window rather than a top-level, this PoC's "
                  "dialog-finder needs to walk child windows too — inspect above.)")
            return 1

        print(f"[zrouter-poc] Zrouter dialog hwnd={hwnd} class={_info(hwnd)['class']!r} "
              f"text={_info(hwnd)['text']!r}")
        print(f"[zrouter-poc] {len(_enum_children(hwnd))} child controls:")
        for ch in _enum_children(hwnd):
            i = _info(ch)
            print(f"  hwnd={i['hwnd']} class={i['class']!r} text={i['text']!r} rect={i['rect']}")

        # Fill Edit controls in layout order = doc field order.
        edits = sorted(
            (ch for ch in _enum_children(hwnd) if _info(ch)["class"].upper() in ("EDIT",) and _info(ch)["enabled"]),
            key=lambda ch: (_info(ch)["rect"][1], _info(ch)["rect"][0]),
        )
        vals = list(FIELD_DEFAULTS)
        vals[0] = conn
        for idx, ch in enumerate(edits[: len(vals)]):
            _set_text(ch, vals[idx])
            print(f"  edit[{idx}] hwnd={ch} = {vals[idx]!r}")
        if not edits:
            print("  FAIL: no Edit controls (class 'Edit') in the dialog — the control class "
                  "is likely Cadence-custom; inspect the child list above and adjust.")
            return 1

        # Click the Run button.
        run_btn = None
        for ch in _enum_children(hwnd):
            i = _info(ch)
            if i["class"].upper() in ("BUTTON", "MFCBUTTON") and "run" in i["text"].lower():
                run_btn = ch
                break
        if run_btn is None:
            print("  FAIL: no 'Run' button found; list buttons:")
            for ch in _enum_children(hwnd):
                i = _info(ch)
                if i["class"].upper() in ("BUTTON", "MFCBUTTON"):
                    print(f"    button text={i['text']!r}")
            return 1

        print(f"[zrouter-poc] clicking Run (hwnd={run_btn} text={_info(run_btn)['text']!r})")
        _click(run_btn)

        # Wait for zrouter to finish routing; the dialog closes and the board gains vias.
        print(f"[zrouter-poc] waiting up to {timeout}s for routing to complete...")
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"[zrouter-poc] timeout — killing allegro (routing may have hung).")
            proc.kill()
            return 1
        print(f"[zrouter-poc] allegro exited code={proc.returncode}")

        log = Path(board).parent / "Zrouter.log"
        if log.is_file():
            print(f"[zrouter-poc] Zrouter.log at {log}:\n{log.read_text(errors='replace')[:3000]}")
            return 0
        print("[zrouter-poc] no Zrouter.log — routing may have been a no-op (no matching "
              "MLC-module I/O pins) or the Run click did not land. Inspect the printed "
              "dialog children list above to confirm the real control class/captions.")
        return 0
    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
