"""Global hotkeys via the Win32 RegisterHotKey API (runs in its own thread, so the
emergency stop keeps working even if the camera/face pipeline is stuck)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import threading
from typing import Callable, Dict, List, Tuple

log = logging.getLogger(__name__)

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

_MODS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "control": MOD_CONTROL, "shift": MOD_SHIFT,
         "win": MOD_WIN, "windows": MOD_WIN}
_NAMED = {"esc": 0x1B, "escape": 0x1B, "space": 0x20, "pause": 0x13, "home": 0x24, "end": 0x23,
          "insert": 0x2D, "delete": 0x2E, "pageup": 0x21, "pagedown": 0x22, "tab": 0x09,
          "backspace": 0x08}


def parse_hotkey(spec: str) -> Tuple[int, int]:
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    *mods, key = parts
    mask = 0
    for m in mods:
        if m not in _MODS:
            raise ValueError(f"unknown modifier '{m}' in '{spec}'")
        mask |= _MODS[m]
    if key in _NAMED:
        vk = _NAMED[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        raise ValueError(f"unknown key '{key}' in '{spec}'")
    if mask == 0 and not (0x70 <= vk <= 0x87):
        raise ValueError("hotkeys need at least one modifier (or be a function key)")
    return mask, vk


class HotkeyManager:
    def __init__(self):
        self._bindings: Dict[int, Tuple[str, str, int, int, Callable[[], None]]] = {}
        self._thread = None
        self._thread_id = None
        self._ready = threading.Event()
        self.errors: List[str] = []

    def register(self, name: str, spec: str, callback: Callable[[], None]) -> None:
        try:
            mods, vk = parse_hotkey(spec)
        except ValueError as exc:
            self.errors.append(f"{name}: {exc}")
            return
        self._bindings[len(self._bindings) + 1] = (name, spec, mods, vk, callback)

    def start(self) -> None:
        if os.name != "nt":
            self.errors.append("Global hotkeys are only available on Windows")
            return
        self._thread = threading.Thread(target=self._run, name="hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)

    def _run(self) -> None:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        for hid, (name, spec, mods, vk, _cb) in self._bindings.items():
            if not user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                self.errors.append(f"{name}: could not register '{spec}' (already used by another app?)")
        self._ready.set()
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in self._bindings:
                name, _spec, _m, _vk, callback = self._bindings[msg.wParam]
                try:
                    callback()
                except Exception:
                    log.exception("Hotkey '%s' handler failed", name)
        for hid in self._bindings:
            user32.UnregisterHotKey(None, hid)

    def stop(self) -> None:
        if self._thread and self._thread_id and os.name == "nt":
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(1.0)
