import ctypes
import sys

from ctypes import wintypes as wt

user32 = ctypes.windll.user32
PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [PROC, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, PROC, wt.LPARAM]
HINT = sys.argv[1] if len(sys.argv) > 1 else ""

found = []


def _find(hwnd, _l):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    cls = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, cls, 128)
    visible = user32.IsWindowVisible(hwnd)
    if buf.value and (not HINT or HINT in buf.value):
        found.append((hex(hwnd), str(buf.value), str(cls.value), bool(visible)))
    return True


user32.EnumWindows(PROC(_find), 0)
print(f"matching top-level windows: {len(found)}")
for f in found:
    print(f)
if HINT in found or found:
    if HINT:
        targets = [f for f in found if HINT in f[1]]
    else:
        targets = found
    for t in targets:
        top = int(t[0], 16)
        kids = []

        def _walk(hwnd, _l):
            if hwnd != top:
                buf = ctypes.create_unicode_buffer(1024)
                user32.GetWindowTextW(hwnd, buf, 1024)
                cls = ctypes.create_unicode_buffer(128)
                user32.GetClassNameW(hwnd, cls, 128)
                kids.append((str(cls.value), str(buf.value)))
            return True

        user32.EnumChildWindows(top, PROC(_walk), 0)
        print(f"  children of {t[0]}: {len(kids)}")
        for k in kids:
            print("   ", k)
