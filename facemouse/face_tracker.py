"""Facial landmarks (MediaPipe Face Mesh) -> eye aspect ratios and head position."""
from __future__ import annotations
import math
from dataclasses import dataclass,field
from typing import List,Tuple
RIGHT_EYE=(33,160,158,133,153,144); LEFT_EYE=(362,385,387,263,373,380); NOSE_TIP=1
class TrackerError(RuntimeError): pass
@dataclass
class FaceResult:
 found:bool=False; left_ear:float=0.0; right_ear:float=0.0; nose_x:float=0.0; nose_y:float=0.0; iod:float=1.0; yaw:float=0.0; frame_w:int=640; frame_h:int=480; draw:List[Tuple[float,float,str]]=field(default_factory=list)
def _dist(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])
def eye_aspect_ratio(p):
 horizontal=_dist(p[0],p[3])
 if horizontal<1e-6:return 0.0
 return (_dist(p[1],p[5])+_dist(p[2],p[4]))/(2.0*horizontal)
def metrics_from_landmarks(lm,w,h,want_draw=False):
 def px(i): return (lm[i].x*w,lm[i].y*h)
 right=[px(i) for i in RIGHT_EYE]; left=[px(i) for i in LEFT_EYE]; rc=((right[0][0]+right[3][0])/2,(right[0][1]+right[3][1])/2); lc=((left[0][0]+left[3][0])/2,(left[0][1]+left[3][1])/2); iod=_dist(rc,lc); result=FaceResult(frame_w=w,frame_h=h)
 if iod<8:return result
 nose=px(NOSE_TIP); result.found=True; result.left_ear=eye_aspect_ratio(left); result.right_ear=eye_aspect_ratio(right); result.nose_x,result.nose_y,result.iod=nose[0],nose[1],iod; result.yaw=(nose[0]-(rc[0]+lc[0])/2)/iod
 if want_draw:
  for idx in LEFT_EYE: result.draw.append((lm[idx].x,lm[idx].y,"L"))
  for idx in RIGHT_EYE: result.draw.append((lm[idx].x,lm[idx].y,"R"))
  result.draw.append((lm[NOSE_TIP].x,lm[NOSE_TIP].y,"N"))
 return result
class FaceTracker:
 def __init__(self,want_draw=True):
  try: import mediapipe as mp
  except ImportError as exc: raise TrackerError("mediapipe is not installed. Run: pip install -r requirements.txt") from exc
  try: self._mesh=mp.solutions.face_mesh.FaceMesh(static_image_mode=False,max_num_faces=1,refine_landmarks=False,min_detection_confidence=0.5,min_tracking_confidence=0.5)
  except AttributeError as exc: raise TrackerError("This mediapipe build has no legacy 'solutions' API. Install the version pinned in requirements.txt (mediapipe 0.10.x).") from exc
  self.want_draw=want_draw
 def process(self,frame_bgr):
  import cv2
  h,w=frame_bgr.shape[:2]; rgb=cv2.cvtColor(frame_bgr,cv2.COLOR_BGR2RGB); rgb.flags.writeable=False; res=self._mesh.process(rgb)
  if not res.multi_face_landmarks:return FaceResult(frame_w=w,frame_h=h)
  return metrics_from_landmarks(res.multi_face_landmarks[0].landmark,w,h,self.want_draw)
 def close(self):
  try:self._mesh.close()
  except Exception:pass
