import ctypes
import ctypes.wintypes as wt
import sys

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]

TARGET_PID = int(sys.argv[1]) if len(sys.argv) > 1 else None
found = []


def _cb(hwnd, lparam):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == TARGET_PID:
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        visible = user32.IsWindowVisible(hwnd)
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        found.append((hex(hwnd), str(buf.value), bool(visible), str(class_buf.value)))
    return True


cb = WNDENUMPROC(_cb)
user32.EnumWindows(cb, 0)
print(f"windows owned by PID {TARGET_PID}: {len(found)}")
for w in found:
    print(w)
