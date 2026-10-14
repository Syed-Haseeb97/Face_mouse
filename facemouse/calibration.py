"""Calibration logic (no UI): neutral head pose, open-eye baseline, blink thresholds."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import Config
from .face_tracker import FaceResult

MIN_OPEN_EAR = 0.12        # below this the eye is not really "open" for baseline purposes
CENTER_TOL_X, CENTER_TOL_Y = 0.20, 0.25


@dataclass
class CalibrationResult:
    neutral_x: float
    neutral_y: float
    baseline_left: float
    baseline_right: float
    close_ratio: Optional[float] = None
    open_ratio: Optional[float] = None


def _low_half_median(values: List[float]) -> float:
    ordered = sorted(values)
    return statistics.median(ordered[: max(1, len(ordered) // 2)])


class CalibrationSession:
    def __init__(self):
        self.neutral: List[FaceResult] = []
        self.closed: Dict[str, List[float]] = {"left": [], "right": []}

    @staticmethod
    def centering_hint(face: FaceResult) -> Optional[str]:
        """None if the face is centred, facing the camera and eyes are open; else a hint."""
        if not face.found:
            return "No face detected"
        cx, cy = face.nose_x / face.frame_w, face.nose_y / face.frame_h
        if cx < 0.5 - CENTER_TOL_X:
            return "Move to the RIGHT (towards the middle of the picture)"
        if cx > 0.5 + CENTER_TOL_X:
            return "Move to the LEFT (towards the middle of the picture)"
        if abs(cy - 0.5) > CENTER_TOL_Y:
            return "Move so your face is vertically centred"
        if abs(face.yaw) > 0.25:
            return "Face the camera straight on"
        if face.left_ear < MIN_OPEN_EAR or face.right_ear < MIN_OPEN_EAR:
            return "Keep both eyes open"
        return None

    def add_neutral(self, face: FaceResult) -> Optional[str]:
        hint = self.centering_hint(face)
        if hint is None:
            self.neutral.append(face)
        return hint

    def add_closed(self, eye: str, face: FaceResult) -> None:
        if face.found:
            self.closed[eye].append(face.left_ear if eye == "left" else face.right_ear)

    @property
    def neutral_count(self) -> int:
        return len(self.neutral)

    def compute(self) -> CalibrationResult:
        if len(self.neutral) < 10:
            raise ValueError("Not enough neutral samples - keep your face centred and eyes open")
        nx = statistics.median(f.nose_x / f.frame_w for f in self.neutral)
        ny = statistics.median(f.nose_y / f.frame_h for f in self.neutral)
        bl = statistics.median(f.left_ear for f in self.neutral)
        br = statistics.median(f.right_ear for f in self.neutral)
        result = CalibrationResult(nx, ny, bl, br)
        ratios = []
        for eye, base in (("left", bl), ("right", br)):
            if len(self.closed[eye]) >= 8 and base > 0:
                ratios.append(_low_half_median(self.closed[eye]) / base)
        if ratios:
            closed_ratio = min(max(sum(ratios) / len(ratios), 0.05), 0.7)
            result.close_ratio = min(max(closed_ratio + 0.40 * (1 - closed_ratio), 0.35), 0.8)
            result.open_ratio = min(max(closed_ratio + 0.65 * (1 - closed_ratio), result.close_ratio + 0.08), 0.95)
        return result

    def apply(self, cfg: Config) -> CalibrationResult:
        r = self.compute()
        cfg.neutral_x, cfg.neutral_y = r.neutral_x, r.neutral_y
        cfg.baseline_left_ear, cfg.baseline_right_ear = r.baseline_left, r.baseline_right
        if r.close_ratio is not None:
            cfg.ear_close_ratio, cfg.ear_open_ratio = r.close_ratio, r.open_ratio
        cfg.validate()
        return r
