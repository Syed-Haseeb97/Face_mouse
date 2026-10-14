"""Mouse output: native Windows SendInput backend, a memory backend for tests/dry-run,
and a controller that tracks button state so nothing can ever stay stuck down."""
from __future__ import annotations

import ctypes
import logging
import os
import threading
from typing import List, Optional, Set, Tuple

log = logging.getLogger(__name__)

RESYNC_PX = 3


class MouseBackend:
    def get_pos(self) -> Tuple[int, int]: raise NotImplementedError
    def move_to(self, x: int, y: int) -> None: raise NotImplementedError
    def button(self, name: str, down: bool) -> None: raise NotImplementedError
    def bounds(self) -> Tuple[int, int, int, int]: raise NotImplementedError


class MemoryBackend(MouseBackend):
    def __init__(self, width: int = 1920, height: int = 1080, verbose: bool = False):
        self.pos = (width // 2, height // 2)
        self._bounds = (0, 0, width, height)
        self.log: List[Tuple[str, ...]] = []
        self.verbose = verbose
        self.fail_release = 0

    def get_pos(self): return self.pos
    def move_to(self, x, y): self.pos = (x, y)
    def button(self, name, down):
        if not down and self.fail_release > 0:
            self.fail_release -= 1
            raise OSError("simulated SendInput failure")
        self.log.append(("down" if down else "up", name))
        if self.verbose: log.info("[dry-run] %s %s at %s", name, "DOWN" if down else "UP", self.pos)
    def bounds(self): return self._bounds
    def events(self) -> List[Tuple[str, str]]: return list(self.log)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32), ("mouseData", ctypes.c_uint32),
                ("dwFlags", ctypes.c_uint32), ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]

class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT)]

class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_uint32), ("u", _INPUTUNION)]

class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]

_MOVE, _LDOWN, _LUP, _RDOWN, _RUP = 0x0001, 0x0002, 0x0004, 0x0008, 0x0010
_VIRTUALDESK, _ABSOLUTE = 0x4000, 0x8000
_BUTTON_FLAGS = {("left", True): _LDOWN, ("left", False): _LUP,
                 ("right", True): _RDOWN, ("right", False): _RUP}


def enable_dpi_awareness() -> None:
    if os.name != "nt": return
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass


class WindowsMouseBackend(MouseBackend):
    def __init__(self):
        if os.name != "nt": raise RuntimeError("WindowsMouseBackend only works on Windows (use --dry-run elsewhere)")
        self._u32 = ctypes.windll.user32
        self._u32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int)
        self._u32.SendInput.restype = ctypes.c_uint

    def _send(self, flags: int, dx: int = 0, dy: int = 0) -> None:
        inp = _INPUT(type=0)
        inp.mi = _MOUSEINPUT(dx, dy, 0, flags, 0, 0)
        if self._u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) != 1:
            raise OSError(f"SendInput failed (error {ctypes.GetLastError()}); input to elevated windows is blocked unless Face Mouse runs as administrator")

    def get_pos(self):
        pt = _POINT(); self._u32.GetCursorPos(ctypes.byref(pt)); return pt.x, pt.y
    def bounds(self):
        gm = self._u32.GetSystemMetrics; left, top, width, height = gm(76), gm(77), gm(78), gm(79)
        return left, top, left + width, top + height
    def move_to(self, x, y):
        left, top, right, bottom = self.bounds(); w, h = max(right-left-1, 1), max(bottom-top-1, 1)
        nx, ny = round((x-left)*65535/w), round((y-top)*65535/h)
        self._send(_MOVE | _ABSOLUTE | _VIRTUALDESK, nx, ny)
    def button(self, name, down): self._send(_BUTTON_FLAGS[(name, down)])


class MouseController:
    def __init__(self, backend: MouseBackend):
        self.backend = backend; self._lock = threading.RLock(); self._held: Set[str] = set()
        self._inhibited = False; self._fx = self._fy = 0.0; self._last_set: Optional[Tuple[int,int]] = None

    @property
    def held(self):
        with self._lock: return set(self._held)
    @property
    def any_held(self): return bool(self._held)
    def is_held(self, button): return button in self._held
    @property
    def inhibited(self): return self._inhibited
    def inhibit(self, flag):
        with self._lock: self._inhibited = flag

    def move_by(self, dx, dy):
        with self._lock:
            if self._inhibited: return
            ax, ay = self.backend.get_pos()
            if self._last_set is None or abs(ax-self._last_set[0]) > RESYNC_PX or abs(ay-self._last_set[1]) > RESYNC_PX:
                self._fx, self._fy = float(ax), float(ay)
            left, top, right, bottom = self.backend.bounds()
            self._fx = min(max(self._fx+dx, left), right-1); self._fy = min(max(self._fy+dy, top), bottom-1)
            nx, ny = int(round(self._fx)), int(round(self._fy))
            if (nx, ny) != (ax, ay): self.backend.move_to(nx, ny)
            self._last_set = (nx, ny)

    def press(self, button):
        with self._lock:
            if self._inhibited or button in self._held: return False
            self.backend.button(button, True); self._held.add(button); return True

    def release(self, button):
        with self._lock:
            if button not in self._held: return
            try: self.backend.button(button, False)
            except Exception:
                log.exception("Releasing %s failed; retrying once", button); self.backend.button(button, False)
            self._held.discard(button)

    def click(self, button):
        with self._lock:
            if self._inhibited or button in self._held: return False
            self.backend.button(button, True)
            try: self.backend.button(button, False)
            except Exception:
                self._held.add(button); raise
            return True

    def release_all(self, force=False):
        with self._lock:
            targets = ["left", "right"] if force else sorted(self._held)
            for button in targets:
                for attempt in range(2):
                    try: self.backend.button(button, False); break
                    except Exception: log.exception("release_all: %s up failed (attempt %d)", button, attempt+1)
            self._held.clear()

    def emergency_release(self):
        self._inhibited = True
        self.release_all(force=True)
