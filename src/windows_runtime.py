"""Small Win32 boundary: window/focus, global controls, and explicit input."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import os
import threading

from .live_capture import Region

DEFAULT_WINDOW_TITLE = "hololive-Dreams"


def user32():
    if os.name != "nt":
        raise RuntimeError("Live capture and Assist hotkeys require Windows")
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.GetForegroundWindow.restype = w.HWND
    api.GetAsyncKeyState.argtypes = [ctypes.c_int]
    api.GetAsyncKeyState.restype = ctypes.c_short
    api.IsWindow.argtypes = [w.HWND]
    api.IsWindowVisible.argtypes = [w.HWND]
    api.IsIconic.argtypes = [w.HWND]
    api.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    api.ClientToScreen.argtypes = [w.HWND, ctypes.POINTER(w.POINT)]
    api.GetWindowTextLengthW.argtypes = [w.HWND]
    api.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    return api


def enable_dpi_awareness():
    api = user32()
    try:
        api.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        api.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        api.SetProcessDPIAware()


def primary_monitor_bounds():
    api = user32()
    return api.GetSystemMetrics(0), api.GetSystemMetrics(1)


def list_windows():
    api = user32()
    found = []
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        if api.IsWindowVisible(hwnd):
            length = api.GetWindowTextLengthW(hwnd)
            if length:
                title = ctypes.create_unicode_buffer(length+1)
                api.GetWindowTextW(hwnd, title, length+1)
                found.append((int(hwnd), title.value))
        return True
    callback = callback_type(visit)
    api.EnumWindows.argtypes = [callback_type, w.LPARAM]
    api.EnumWindows(callback, 0)
    return found


class WindowTarget:
    def __init__(self, title):
        matches = [(h, t) for h, t in list_windows() if title.casefold() in t.casefold()]
        exact = [(h, t) for h, t in matches if title.casefold() == t.casefold()]
        if len(exact) == 1:
            matches = exact
        if len(matches) != 1:
            raise ValueError(f"Window title must identify exactly one visible window; found {len(matches)}. Use --list-windows or an exact title: {matches}")
        self.hwnd, self.title = matches[0]
        self.api = user32()

    def client_region(self):
        if not self.api.IsWindow(self.hwnd) or self.api.IsIconic(self.hwnd):
            raise ValueError("Game window is missing or minimized")
        rect, point = w.RECT(), w.POINT()
        if not self.api.GetClientRect(self.hwnd, ctypes.byref(rect)) or not self.api.ClientToScreen(self.hwnd, ctypes.byref(point)):
            raise OSError("Cannot obtain the physical window client rectangle")
        return Region(point.x, point.y, rect.right-rect.left, rect.bottom-rect.top)

    def monitor_region(self):
        """Return the complete physical display containing the game window."""
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize",w.DWORD),("rcMonitor",w.RECT),
                        ("rcWork",w.RECT),("dwFlags",w.DWORD)]
        self.api.MonitorFromWindow.argtypes = [w.HWND,w.DWORD]
        self.api.MonitorFromWindow.restype = ctypes.c_void_p
        self.api.GetMonitorInfoW.argtypes = [ctypes.c_void_p,ctypes.POINTER(MonitorInfo)]
        self.api.GetMonitorInfoW.restype = w.BOOL
        monitor = self.api.MonitorFromWindow(self.hwnd,2)  # MONITOR_DEFAULTTONEAREST
        info = MonitorInfo(); info.cbSize = ctypes.sizeof(MonitorInfo)
        if not monitor or not self.api.GetMonitorInfoW(monitor,ctypes.byref(info)):
            raise OSError("Cannot obtain the physical display containing the game window")
        rect = info.rcMonitor
        return Region(rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top)

    def focused(self):
        return bool(self.api.IsWindow(self.hwnd) and not self.api.IsIconic(self.hwnd) and
                    self.api.GetForegroundWindow() == self.hwnd)


def overlay_overlaps(title, region):
    api = user32()
    api.FindWindowW.argtypes = [w.LPCWSTR, w.LPCWSTR]
    api.FindWindowW.restype = w.HWND
    api.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    hwnd = api.FindWindowW(None, title)
    if not hwnd or api.IsIconic(hwnd) or not api.IsWindowVisible(hwnd):
        return False
    rect = w.RECT()
    if not api.GetWindowRect(hwnd, ctypes.byref(rect)):
        return True
    left, top, right, bottom = region.bounds
    return rect.left < right and rect.right > left and rect.top < bottom and rect.bottom > top


def modifiers_down():
    api = user32()
    return any(api.GetAsyncKeyState(vk) & 0x8000 for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C))


class GlobalControls:
    """RegisterHotKey avoids key-repeat toggles; Esc/F12 are polled globally."""
    def __init__(self, on_toggle, on_stop, assist=False):
        self.on_toggle, self.on_stop, self.assist = on_toggle, on_stop, assist
        self.stop_event, self.ready = threading.Event(), threading.Event()
        self.thread, self.error = None, None
        self.registration_ok = False

    def start(self):
        self.thread = threading.Thread(target=self._run, name="holodream-hotkeys", daemon=False)
        self.thread.start()
        if not self.ready.wait(2):
            self.close()
            raise RuntimeError("Global controls did not initialize")
        if self.error:
            self.close()
            raise RuntimeError(str(self.error))
        return self

    def _run(self):
        api = None
        registered = False
        try:
            api = user32()
            api.RegisterHotKey.argtypes = [w.HWND, ctypes.c_int, w.UINT, w.UINT]
            api.UnregisterHotKey.argtypes = [w.HWND, ctypes.c_int]
            api.PeekMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
            registered = bool(api.RegisterHotKey(None, 1, 0x4000 | 1 | 2 | 4, ord("Q")))
            self.registration_ok = registered
            if self.assist and not registered:
                raise RuntimeError("Ctrl+Shift+Alt+Q is unavailable; assist mode remains disabled. Close the conflicting hotkey application.")
            self.ready.set()
            msg = w.MSG()
            while not self.stop_event.is_set():
                # F12 is reserved by Windows debuggers, so poll instead of
                # registering it. This also works when the overlay is unfocused.
                if any(api.GetAsyncKeyState(vk) & 0x8000 for vk in (0x1B, 0x7B)):
                    self.on_stop()
                    return
                while api.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):
                    if msg.wParam == 1:
                        self.on_toggle()
                self.stop_event.wait(.005)
        except Exception as error:
            self.error = error
            self.on_stop()
        finally:
            self.ready.set()
            if registered and api:
                api.UnregisterHotKey(None, 1)

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                raise RuntimeError("Global control thread did not stop")


class WindowsActuator:
    """Ordinary SendInput, constructed only for explicit live assist mode."""
    def __init__(self,input_mode="scan_code"):
        if input_mode not in ("scan_code","virtual_key"):
            raise ValueError("Keyboard input mode must be scan_code or virtual_key")
        self.api = user32()
        self.input_mode = input_mode
        self.api.MapVirtualKeyW.argtypes = [w.UINT,w.UINT]
        self.api.MapVirtualKeyW.restype = w.UINT
        self.scan_codes = {key:int(self.api.MapVirtualKeyW(ord(key),0)) for key in "SDFJKL"}
        if any(not 0<scan<0x100 for scan in self.scan_codes.values()):
            raise ValueError("Cannot map the six supported keys to ordinary keyboard scan codes")
        ulong_ptr = ctypes.c_size_t
        class Keyboard(ctypes.Structure):
            _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD),
                        ("time", w.DWORD), ("extra", ulong_ptr)]
        class Mouse(ctypes.Structure):
            _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("data", w.DWORD),
                        ("flags", w.DWORD), ("time", w.DWORD), ("extra", ulong_ptr)]
        class Hardware(ctypes.Structure):
            _fields_ = [("message", w.DWORD), ("low", w.WORD), ("high", w.WORD)]
        class Payload(ctypes.Union):
            _fields_ = [("keyboard", Keyboard), ("mouse", Mouse), ("hardware", Hardware)]
        class Input(ctypes.Structure):
            _fields_ = [("type", w.DWORD), ("payload", Payload)]
        self.Keyboard, self.Input = Keyboard, Input
        self.api.SendInput.argtypes = [w.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.api.SendInput.restype = w.UINT

    def _send(self, key, up):
        if key not in "SDFJKL" or len(key) != 1:
            raise ValueError("Only the six mapped tap keys are supported")
        packet = self.Input()
        packet.type = 1
        flags = (8 if self.input_mode=="scan_code" else 0) | (2 if up else 0)
        packet.payload.keyboard = self.Keyboard(0 if self.input_mode=="scan_code" else ord(key),
                                               self.scan_codes[key],flags,0,0)
        if self.api.SendInput(1, ctypes.byref(packet), ctypes.sizeof(packet)) != 1:
            raise OSError("SendInput failed; input disabled. No elevation/protection workaround is attempted.")

    def key_down(self, key):
        self._send(key, False)

    def key_up(self, key):
        self._send(key, True)
