"""Head position -> cursor velocity (rate control with dead zone and smoothing)."""
from __future__ import annotations
from typing import Optional,Tuple
from .config import Config
from .face_tracker import FaceResult
BASE_SPEED_PX_S=1200.0
class HeadMotionMapper:
 def __init__(self,cfg:Config): self.cfg=cfg; self._fx:Optional[float]=None; self._fy:Optional[float]=None
 def reset(self): self._fx=self._fy=None
 def apply_config(self): self.reset()
 def offset(self,face): return ((face.nose_x-self.cfg.neutral_x*face.frame_w)/face.iod,(face.nose_y-self.cfg.neutral_y*face.frame_h)/face.iod)
 def update(self,face,dt):
  cfg=self.cfg; ox,oy=self.offset(face)
  if self._fx is None:self._fx,self._fy=ox,oy
  else:
   keep=cfg.smoothing**max(dt*30.0,0.0); self._fx=keep*self._fx+(1-keep)*ox; self._fy=keep*self._fy+(1-keep)*oy
  vx=self._speed(self._fx); vy=self._speed(self._fy); return (-vx if cfg.mirror_x else vx),vy
 def _speed(self,value):
  cfg=self.cfg; excess=abs(value)-cfg.dead_zone
  if excess<=0:return 0.0
  d=min(excess/cfg.head_range,1.5); speed=BASE_SPEED_PX_S*(cfg.sensitivity/5.0)*d**cfg.response_exponent; speed=min(speed,cfg.max_speed_px_s); return speed if value>0 else -speed
