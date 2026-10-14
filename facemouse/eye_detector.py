"""Per-eye open/closed classification from eye-aspect-ratio (EAR) values."""
from __future__ import annotations
from dataclasses import dataclass
from .config import Config
@dataclass
class EyeReading:
 left_ratio:float=1.0; right_ratio:float=1.0; left_closed:bool=False; right_closed:bool=False
def classify(ratio,was_closed,close_ratio,open_ratio): return ratio<open_ratio if was_closed else ratio<close_ratio
class _Eye:
 def __init__(self,baseline): self.initial=baseline; self.baseline=baseline; self.closed=False; self.pending=0
class EyeStateDetector:
 def __init__(self,cfg): self.cfg=cfg; self.left=_Eye(cfg.baseline_left_ear); self.right=_Eye(cfg.baseline_right_ear)
 def apply_config(self): self.left=_Eye(self.cfg.baseline_left_ear); self.right=_Eye(self.cfg.baseline_right_ear)
 def reset(self):
  for eye in (self.left,self.right): eye.closed=False; eye.pending=0
 def _step(self,eye,ear):
  cfg=self.cfg; ratio=ear/eye.baseline if eye.baseline>0 else 1.0; raw_closed=classify(ratio,eye.closed,cfg.ear_close_ratio,cfg.ear_open_ratio)
  if raw_closed!=eye.closed:
   eye.pending+=1
   if eye.pending>=cfg.eye_debounce_frames: eye.closed,eye.pending=raw_closed,0
  else: eye.pending=0
  if cfg.adaptive_baseline and not eye.closed and ratio>cfg.ear_open_ratio+0.1:
   eye.baseline+=0.01*(ear-eye.baseline); eye.baseline=min(max(eye.baseline,0.7*eye.initial),1.4*eye.initial)
  return ratio
 def update(self,left_ear,right_ear):
  lr=self._step(self.left,left_ear); rr=self._step(self.right,right_ear); return EyeReading(lr,rr,self.left.closed,self.right.closed)
