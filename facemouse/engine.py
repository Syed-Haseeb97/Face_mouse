"""Processing engine: camera frames -> landmarks -> eye state -> gestures -> mouse.

`process_frame` / `process_no_frame` are plain methods driven by the worker thread but
callable directly (tests feed scripted frames with a fake clock). Safety:
 * emergency_stop() works from any thread and never waits on the processing loop;
 * a watchdog releases buttons if the loop stalls;
 * any exception in the loop, camera failure or face loss releases buttons.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .camera import CamState
from .config import Config, save_config
from .eye_detector import EyeReading, EyeStateDetector
from .face_tracker import FaceResult
from .gesture_controller import GestureController, GestureOutput, State
from .head_motion import HeadMotionMapper

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    running: bool = False
    control_enabled: bool = False
    emergency: bool = False
    camera_state: str = CamState.CLOSED
    camera_name: str = ""
    camera_message: str = ""
    face_found: bool = False
    left_closed: bool = False
    right_closed: bool = False
    left_ratio: float = 1.0
    right_ratio: float = 1.0
    gesture_state: str = State.DISABLED
    gesture: str = "None"
    left_held: bool = False
    right_held: bool = False
    sensitivity: float = 5.0
    fps: float = 0.0
    error: str = ""
    preview: Optional[Tuple[int, int, bytes]] = None


class Engine:
    FAULT_LIMIT = 5
    STALE_FRAME_S = 0.3

    def __init__(self, cfg: Config, camera, tracker_factory: Callable[[], object], mouse,
                 clock: Callable[[], float] = time.monotonic, config_path=None):
        self.cfg, self.camera, self.mouse = cfg, camera, mouse
        self._tracker_factory = tracker_factory
        self._clock = clock
        self._config_path = config_path
        self.tracker = None
        self.eyes = EyeStateDetector(cfg)
        self.head = HeadMotionMapper(cfg)
        self.gestures = GestureController(cfg, mouse)
        self.running = False
        self.control_enabled = False
        self.emergency = False
        self.calibrating = False
        self.preview_override = False
        self.last_error = ""
        self.last_face = FaceResult()
        self.last_reading: Optional[EyeReading] = None
        self.last_out = GestureOutput(state=State.DISABLED, allow_move=False)
        self.face_counter = 0
        self.fps = 0.0
        self._preview = None
        self._last_preview_t = 0.0
        self._last_t: Optional[float] = None
        self._last_tick = clock()
        self._faults = 0
        self._stop = threading.Event()
        self._threads = []

    def start(self, control: bool = True) -> None:
        if self.running:
            if control:
                self.set_control(True)
            return
        if self.tracker is None:
            self.tracker = self._tracker_factory()
        self.camera.start(self.cfg.camera_key)
        self._stop.clear()
        self._last_tick = self._clock()
        self.running = True
        for target, name in ((self._loop, "engine"), (self._watchdog_loop, "watchdog")):
            th = threading.Thread(target=target, name=name, daemon=True)
            th.start()
            self._threads.append(th)
        if control:
            self.set_control(True)

    def stop(self) -> None:
        self.set_control(False)
        self._stop.set()
        for th in self._threads:
            if th is not threading.current_thread():
                th.join(2.0)
        self._threads.clear()
        self.camera.stop()
        self.mouse.release_all(force=True)
        if self.tracker is not None:
            close = getattr(self.tracker, "close", None)
            if close:
                close()
            self.tracker = None
        self.running = False

    def set_control(self, enabled: bool) -> None:
        if enabled:
            self.mouse.inhibit(False)
            self.emergency = False
            self.head.reset()
            self.control_enabled = True
        else:
            self.control_enabled = False
            self.mouse.release_all()

    def toggle_control(self) -> None:
        if self.control_enabled:
            self.set_control(False)
        elif self.running:
            self.set_control(True)

    def emergency_stop(self) -> None:
        self.control_enabled = False
        self.emergency = True
        self.mouse.emergency_release()
        log.warning("EMERGENCY STOP")

    def select_camera(self, key: str) -> None:
        self.cfg.camera_key = key
        save_config(self.cfg, self._config_path)
        self.eyes.reset()
        self.mouse.release_all()
        self.camera.select(key)

    def recenter(self) -> bool:
        face = self.last_face
        if not face.found:
            return False
        self.cfg.neutral_x = face.nose_x / face.frame_w
        self.cfg.neutral_y = face.nose_y / face.frame_h
        self.head.reset()
        save_config(self.cfg, self._config_path)
        return True

    def apply_config(self) -> None:
        self.cfg.validate()
        self.eyes.apply_config()
        self.head.apply_config()

    def set_calibrating(self, flag: bool) -> None:
        self.calibrating = flag
        if flag:
            self.mouse.release_all()

    def latest_face(self) -> Tuple[FaceResult, int]:
        return self.last_face, self.face_counter

    def _dt(self, t: float) -> float:
        dt = (t - self._last_t) if self._last_t is not None else 1.0 / max(self.cfg.target_fps, 1)
        self._last_t = t
        return min(max(dt, 0.001), 0.25)

    def _drive(self, t: float, dt: float, face: FaceResult, reading: Optional[EyeReading]) -> None:
        cfg = self.cfg
        control = self.control_enabled and not self.calibrating
        if control != self.gestures.enabled:
            self.gestures.set_enabled(control)
        pose_ok = face.found and abs(face.yaw) <= cfg.yaw_limit
        r = reading
        out = self.gestures.update(
            t, face.found, bool(r and r.left_closed), bool(r and r.right_closed),
            r.left_ratio if r else None, r.right_ratio if r else None, pose_ok)
        self.last_out = out
        if face.found:
            vx, vy = self.head.update(face, dt)
            holding = out.state in (State.LEFT_HOLD, State.RIGHT_HOLD)
            eye_moving = (reading is not None and not holding and
                          min(reading.left_ratio, reading.right_ratio) < cfg.ear_open_ratio)
            if control and out.allow_move and not eye_moving:
                self.mouse.move_by(vx * dt, vy * dt)
        else:
            self.head.reset()
        self._last_tick = self._clock()

    def process_frame(self, frame, t: float) -> None:
        dt = self._dt(t)
        face = self.tracker.process(frame)
        self.last_face = face
        self.face_counter += 1
        self.last_reading = self.eyes.update(face.left_ear, face.right_ear) if face.found else None
        if not face.found:
            self.eyes.reset()
        self._drive(t, dt, face, self.last_reading)
        self._faults = 0
        if (self.cfg.preview_enabled or self.preview_override) and t - self._last_preview_t >= 0.1:
            self._last_preview_t = t
            self._build_preview(frame, face)
        elif not (self.cfg.preview_enabled or self.preview_override):
            self._preview = None

    def process_no_frame(self, t: float) -> None:
        dt = self._dt(t)
        face = FaceResult()
        self.last_face, self.last_reading = face, None
        self.eyes.reset()
        if self.camera.status.state != CamState.ACTIVE:
            self.gestures.abort(t)
        self._drive(t, dt, face, None)

    def _guarded(self, fn, *args) -> None:
        try:
            fn(*args)
        except Exception as exc:
            log.exception("Processing error")
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._faults += 1
            try:
                self.mouse.release_all(force=True)
                self.gestures.abort(args[-1] if args else self._clock())
            except Exception:
                log.exception("Cleanup after fault failed")
            if self._faults >= self.FAULT_LIMIT:
                self.control_enabled = False
                self.last_error += " - control disabled after repeated errors"

    def _build_preview(self, frame, face: FaceResult) -> None:
        try:
            import cv2
            small = cv2.resize(frame, (320, 240))
            colors = {"L": (0, 255, 0), "R": (255, 160, 0), "N": (0, 0, 255)}
            reading = self.last_reading
            for x, y, kind in face.draw:
                color = colors[kind]
                if reading and ((kind == "L" and reading.left_closed) or (kind == "R" and reading.right_closed)):
                    color = (0, 0, 255)
                cv2.circle(small, (int(x * 320), int(y * 240)), 2, color, -1)
            if self.cfg.mirror_x:
                small = cv2.flip(small, 1)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            self._preview = (320, 240, rgb.tobytes())
        except Exception:
            log.exception("Preview failed")
            self._preview = None

    def _loop(self) -> None:
        last_seq, last_frame_t = -1, self._clock()
        while not self._stop.is_set():
            t0 = self._clock()
            period = 1.0 / max(self.cfg.target_fps, 1)
            pack = self.camera.read_latest()
            if pack is not None and pack[1] != last_seq:
                last_seq, last_frame_t = pack[1], t0
                self._guarded(self.process_frame, pack[0], t0)
                self.fps = 0.9 * self.fps + 0.1 * (1.0 / max(self._clock() - t0 + 1e-3, 1e-3)) if self.fps else 30.0
            elif t0 - last_frame_t > self.STALE_FRAME_S or self.camera.status.state != CamState.ACTIVE:
                self._guarded(self.process_no_frame, t0)
                self.fps = 0.0
            self._last_tick = self._clock()
            self._stop.wait(max(period - (self._clock() - t0), 0.002))

    def watchdog_check(self, now: float) -> bool:
        if self.mouse.any_held and now - self._last_tick > self.cfg.watchdog_s:
            log.error("Watchdog: processing stalled for %.1fs with a button held - releasing", now - self._last_tick)
            self.control_enabled = False
            self.mouse.emergency_release()
            self.last_error = "Watchdog released buttons (processing stalled)"
            return True
        return False

    def _watchdog_loop(self) -> None:
        while not self._stop.wait(0.25):
            try:
                self.watchdog_check(self._clock())
            except Exception:
                log.exception("Watchdog error")

    def snapshot(self) -> Snapshot:
        cam = self.camera.status
        r, out, face = self.last_reading, self.last_out, self.last_face
        return Snapshot(
            running=self.running, control_enabled=self.control_enabled and not self.calibrating,
            emergency=self.emergency, camera_state=cam.state, camera_name=cam.name,
            camera_message=cam.message, face_found=face.found,
            left_closed=bool(r and r.left_closed), right_closed=bool(r and r.right_closed),
            left_ratio=r.left_ratio if r else 1.0, right_ratio=r.right_ratio if r else 1.0,
            gesture_state=out.state, gesture=out.gesture,
            left_held=self.mouse.is_held("left"), right_held=self.mouse.is_held("right"),
            sensitivity=self.cfg.sensitivity, fps=self.fps, error=self.last_error,
            preview=self._preview)
