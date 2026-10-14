"""Camera enumeration and a self-healing capture thread.

Cameras are identified by the device name Windows reports (plus "#2", "#3" for identically named devices), NOT by OpenCV index.
"""
from __future__ import annotations
import logging,os,threading,time
from dataclasses import dataclass
from typing import Callable,List,Optional,Tuple
from .config import Config
log=logging.getLogger(__name__)
class CamState: CLOSED="CLOSED"; OPENING="OPENING"; ACTIVE="ACTIVE"; RECONNECTING="RECONNECTING"; ERROR="ERROR"
@dataclass(frozen=True)
class CameraInfo:
 index:int; name:str; key:str
 @property
 def display(self): return self.key
@dataclass
class CameraStatus:
 state:str=CamState.CLOSED; key:str=""; name:str=""; message:str=""; fallback_from:str=""
def make_camera_infos(names):
 seen={}; infos=[]
 for index,name in enumerate(names):
  seen[name]=seen.get(name,0)+1; key=name if seen[name]==1 else f"{name} #{seen[name]}"; infos.append(CameraInfo(index,name,key))
 return infos
_com=threading.local()
def windows_device_names():
 if os.name!="nt": return None
 try:
  if not getattr(_com,"ready",False): import comtypes; comtypes.CoInitialize(); _com.ready=True
  from pygrabber.dshow_graph import FilterGraph
  return list(FilterGraph().get_input_devices())
 except Exception as exc: log.warning("Could not read camera names (is pygrabber installed?): %s",exc); return None
def probe_camera_indices(max_index=6):
 try: import cv2
 except ImportError: return []
 working=[]
 for i in range(max_index):
  cap=cv2.VideoCapture(i,cv2.CAP_DSHOW) if os.name=="nt" else cv2.VideoCapture(i)
  if cap.isOpened(): working.append(i)
  cap.release()
 if not working: return []
 return [f"Camera {i}" if i in working else f"Camera {i} (unavailable)" for i in range(max(working)+1)]
def enumerate_cameras():
 names=windows_device_names()
 if names is None: names=probe_camera_indices()
 return make_camera_infos(names)
def open_capture(index,backend,width,height,fps):
 import cv2
 apis={"dshow":[cv2.CAP_DSHOW],"msmf":[cv2.CAP_MSMF],"auto":[cv2.CAP_DSHOW,cv2.CAP_MSMF]}.get(backend,[cv2.CAP_DSHOW,cv2.CAP_MSMF])
 for api in apis:
  cap=cv2.VideoCapture(index,api)
  if cap.isOpened():
   cap.set(cv2.CAP_PROP_FRAME_WIDTH,width); cap.set(cv2.CAP_PROP_FRAME_HEIGHT,height); cap.set(cv2.CAP_PROP_FPS,fps); cap.set(cv2.CAP_PROP_BUFFERSIZE,1); return cap
  cap.release()
 return None
class CameraManager:
 READ_FAIL_LIMIT=8; STALE_S=1.5; OPEN_VERIFY_TRIES=30
 def __init__(self,cfg,enumerate_fn=None,capture_factory=None,clock=time.monotonic,sleep=time.sleep):
  self.cfg=cfg; self._enumerate=enumerate_fn or enumerate_cameras; self._factory=capture_factory or open_capture; self._clock,self._sleep=clock,sleep; self._lock=threading.RLock(); self._cap=None; self._frame=None; self._seq=0; self._status=CameraStatus(); self._requested=""; self._startup=False; self._was_active=False; self._failing_since=None; self._next_try=0.0; self._reopen=False; self._fail=0; self._last_ok=0.0; self._thread=None; self._stop=threading.Event()
 @property
 def status(self):
  with self._lock: s=self._status; return CameraStatus(s.state,s.key,s.name,s.message,s.fallback_from)
 def list_cameras(self):
  try: return self._enumerate()
  except Exception: log.exception("Camera enumeration failed"); return []
 def start(self,preferred_key=None):
  with self._lock:
   self._requested=self.cfg.camera_key if preferred_key is None else preferred_key; self._startup,self._was_active=True,False; self._failing_since,self._next_try,self._reopen=None,0.0,False; self._status=CameraStatus(CamState.OPENING,message="Opening camera...")
  if self._thread is None or not self._thread.is_alive(): self._stop.clear(); self._thread=threading.Thread(target=self._run,name="camera",daemon=True); self._thread.start()
 def select(self,key):
  with self._lock: self._requested=key; self._startup,self._was_active=False,False; self._failing_since,self._next_try,self._reopen=None,0.0,True; self._status=CameraStatus(CamState.OPENING,key=key,message=f"Opening '{key}'...")
 def stop(self):
  self._stop.set(); thread=self._thread
  if thread and thread.is_alive() and thread is not threading.current_thread(): thread.join(3.0)
  with self._lock: self._release_locked(); self._status=CameraStatus(CamState.CLOSED,message="Camera stopped")
 def read_latest(self):
  with self._lock:
   if self._frame is None or self._status.state!=CamState.ACTIVE: return None
   return self._frame,self._seq
 def _release_locked(self):
  cap,self._cap,self._frame=self._cap,None,None
  if cap is not None:
   try: cap.release()
   except Exception: log.exception("Releasing camera failed")
 def _run(self):
  while not self._stop.is_set():
   try: self.pump()
   except Exception:
    log.exception("Camera thread error")
    with self._lock: self._release_locked(); self._status=CameraStatus(CamState.RECONNECTING,self._requested,message="Camera error - retrying"); self._next_try=self._clock()+1.0
   if self._cap is None: self._stop.wait(0.1)
 def pump(self):
  now=self._clock()
  with self._lock:
   if self._reopen: self._release_locked(); self._reopen=False
   cap=self._cap
  if cap is None:
   if now>=self._next_try: self._attempt_open(now)
   return False
  try: ok,frame=cap.read()
  except Exception: ok,frame=False,None
  if ok and frame is not None:
   with self._lock: self._frame,self._seq=frame,self._seq+1
   self._fail,self._last_ok=0,now; return True
  self._fail+=1
  if self._fail>=self.READ_FAIL_LIMIT or now-self._last_ok>self.STALE_S: self._on_disconnect(now)
  return False
 def _on_disconnect(self,now):
  with self._lock:
   name=self._status.name or self._requested; self._release_locked(); self._failing_since=now; self._next_try=now+0.5; self._status=CameraStatus(CamState.RECONNECTING,self._status.key,name,f"Camera '{name}' disconnected - trying to reconnect")
  log.warning("Camera disconnected: %s",name)
 def _attempt_open(self,now):
  try: cams=self._enumerate()
  except Exception: log.exception("Camera enumeration failed"); cams=[]
  if not cams: self._open_failed(now,"No cameras found. Connect a camera, or close apps that are using it."); return
  wanted=next((c for c in cams if c.key==self._requested),None) if self._requested else cams[0]
  fallback_ok=self._startup or (self._was_active and self._failing_since is not None and now-self._failing_since>=self.cfg.camera_fallback_after_s)
  candidates=[wanted] if wanted else []
  if fallback_ok: candidates += [c for c in cams if c is not wanted]
  if not candidates: self._open_failed(now,f"Camera '{self._requested}' is not available"); return
  reason=""
  for cam in candidates:
   if self._stop.is_set(): return
   result,reason=self._try_open(cam)
   if result is not None: self._activate(cam,wanted,result,now); return
  first=candidates[0]; self._open_failed(now,f"Camera '{first.name}' unavailable: {reason}")
 def _try_open(self,cam):
  cfg=self.cfg
  try: cap=self._factory(cam.index,cfg.camera_backend,cfg.camera_width,cfg.camera_height,cfg.target_fps)
  except Exception as exc: return None,f"{exc}"
  if cap is None or not cap.isOpened():
   if cap is not None: cap.release()
   return None,"could not be opened (in use by another application, disconnected, or blocked by Windows camera privacy settings)"
  for _ in range(self.OPEN_VERIFY_TRIES):
   if self._stop.is_set(): break
   ok,frame=cap.read()
   if ok and frame is not None: return (cap,frame),""
   self._sleep(0.1)
  cap.release(); return None,"opened but delivered no frames (it may be in use by another application)"
 def _activate(self,cam,wanted,result,now):
  cap,frame=result; fallback_from=""; message=f"Using '{cam.name}'"
  if cam is not wanted: fallback_from=self._requested or ""; message=f"Using '{cam.name}' (selected camera '{self._requested}' is unavailable)"
  with self._lock: self._cap,self._frame,self._seq=cap,frame,self._seq+1; self._status=CameraStatus(CamState.ACTIVE,cam.key,cam.name,message,fallback_from); self._startup,self._was_active=False,True; self._failing_since,self._fail,self._last_ok=None,0,now
  log.info(message)
 def _open_failed(self,now,message):
  with self._lock:
   state=CamState.RECONNECTING if self._was_active else CamState.ERROR
   if self._failing_since is None: self._failing_since=now
   self._status=CameraStatus(state,self._requested,self._status.name,message); self._next_try=now+(1.0 if self._was_active else 2.0)
  log.warning(message)
