"""Configuration: one dataclass, validation/clamping and JSON persistence."""
from __future__ import annotations
import json,logging,os
from dataclasses import dataclass,fields
from pathlib import Path
from typing import Optional
log=logging.getLogger(__name__); APP_NAME="FaceMouse"
@dataclass
class Config:
 camera_key:str=""; camera_backend:str="auto"; camera_width:int=640; camera_height:int=480; target_fps:int=30; camera_fallback_after_s:float=6.0; preview_enabled:bool=False
 mirror_x:bool=True; neutral_x:float=0.5; neutral_y:float=0.5; sensitivity:float=5.0; dead_zone:float=0.025; head_range:float=0.15; smoothing:float=0.6; response_exponent:float=1.5; max_speed_px_s:float=3000.0
 baseline_left_ear:float=0.27; baseline_right_ear:float=0.27; ear_close_ratio:float=0.60; ear_open_ratio:float=0.75; eye_debounce_frames:int=2; adaptive_baseline:bool=True
 min_click_ms:int=90; max_click_ms:int=450; hold_ms:int=600; click_confirm_ms:int=60; cooldown_ms:int=300; release_debounce_ms:int=90; reopen_ms:int=100; face_loss_release_ms:int=500; other_eye_min_ratio:float=0.70; yaw_limit:float=0.5; enable_right_hold:bool=True
 emergency_hotkey:str="ctrl+alt+f12"; toggle_hotkey:str="ctrl+alt+f11"; recenter_hotkey:str="ctrl+alt+f10"; watchdog_s:float=1.0
 def validate(self):
  defaults=Config.__dataclass_fields__
  for name,(lo,hi,_step) in RANGES.items():
   default=defaults[name].default; value=getattr(self,name)
   try: value=float(value); assert value==value
   except (TypeError,ValueError,AssertionError): value=float(default)
   value=min(max(value,lo),hi); setattr(self,name,int(round(value)) if isinstance(default,int) else value)
  if self.camera_backend not in ("auto","dshow","msmf"): self.camera_backend="auto"
  self.camera_key=str(self.camera_key or "")
  for name in ("emergency_hotkey","toggle_hotkey","recenter_hotkey"): setattr(self,name,str(getattr(self,name)).strip().lower())
  if self.ear_open_ratio<self.ear_close_ratio+0.05: self.ear_open_ratio=min(0.98,self.ear_close_ratio+0.05)
  if self.min_click_ms>=self.max_click_ms: self.min_click_ms=max(30,self.max_click_ms-50)
  if self.hold_ms<self.max_click_ms+100: self.hold_ms=self.max_click_ms+100
  return self
RANGES={"camera_width":(320,1920,1),"camera_height":(240,1080,1),"target_fps":(10,60,1),"camera_fallback_after_s":(1.0,60.0,1.0),"neutral_x":(0.0,1.0,0.01),"neutral_y":(0.0,1.0,0.01),"sensitivity":(1.0,10.0,0.5),"dead_zone":(0.0,0.15,0.005),"head_range":(0.05,0.5,0.01),"smoothing":(0.0,0.95,0.05),"response_exponent":(1.0,2.5,0.1),"max_speed_px_s":(300.0,8000.0,100.0),"baseline_left_ear":(0.08,0.6,0.005),"baseline_right_ear":(0.08,0.6,0.005),"ear_close_ratio":(0.3,0.85,0.01),"ear_open_ratio":(0.4,0.98,0.01),"eye_debounce_frames":(1,5,1),"min_click_ms":(30,400,10),"max_click_ms":(150,1200,10),"hold_ms":(250,2500,50),"click_confirm_ms":(0,250,10),"cooldown_ms":(0,1500,10),"release_debounce_ms":(0,400,10),"reopen_ms":(0,500,10),"face_loss_release_ms":(100,3000,50),"other_eye_min_ratio":(0.3,0.95,0.01),"yaw_limit":(0.15,1.0,0.01),"watchdog_s":(0.3,5.0,0.1)}
SETTINGS_SPEC=[("Cursor","sensitivity","Sensitivity (1-10)"),("Cursor","dead_zone","Dead zone"),("Cursor","smoothing","Smoothing"),("Cursor","head_range","Head range for 1x speed"),("Cursor","response_exponent","Response curve"),("Cursor","max_speed_px_s","Max speed (px/s)"),("Eyes","ear_close_ratio","Closed below (x open baseline)"),("Eyes","ear_open_ratio","Open above (x open baseline)"),("Eyes","other_eye_min_ratio","Other eye must stay above"),("Eyes","eye_debounce_frames","Debounce (frames)"),("Gestures","min_click_ms","Min click closure (ms)"),("Gestures","max_click_ms","Max click closure (ms)"),("Gestures","hold_ms","Hold threshold (ms)"),("Gestures","click_confirm_ms","Click confirm delay (ms)"),("Gestures","cooldown_ms","Cooldown after click (ms)"),("Gestures","release_debounce_ms","Release debounce (ms)"),("Gestures","face_loss_release_ms","Release if face lost (ms)"),("Gestures","yaw_limit","Ignore gestures beyond yaw"),("System","target_fps","Processing FPS"),("System","watchdog_s","Watchdog timeout (s)")]
def default_config_path():
 if os.name=="nt": base=Path(os.environ.get("APPDATA") or Path.home()/"AppData"/"Roaming"); return base/APP_NAME/"config.json"
 return Path.home()/".config"/APP_NAME.lower()/"config.json"
def load_config(path:Optional[Path]=None):
 path=Path(path) if path else default_config_path(); cfg=Config()
 try:
  data=json.loads(path.read_text(encoding="utf-8"));
  if not isinstance(data,dict): raise ValueError("config root must be an object")
 except FileNotFoundError:return cfg.validate()
 except (OSError,ValueError) as exc: log.warning("Ignoring unreadable config %s: %s",path,exc); return cfg.validate()
 for f in fields(Config):
  if f.name not in data: continue
  value,expected=data[f.name],type(f.default)
  if expected is bool and isinstance(value,bool): setattr(cfg,f.name,value)
  elif expected is not bool and isinstance(value,(int,float)) and not isinstance(value,bool) and expected in (int,float): setattr(cfg,f.name,value)
  elif expected is str and isinstance(value,str): setattr(cfg,f.name,value)
 return cfg.validate()
def save_config(cfg,path:Optional[Path]=None):
 path=Path(path) if path else default_config_path()
 try:
  path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps({f.name:getattr(cfg,f.name) for f in fields(Config)},indent=2),encoding="utf-8"); os.replace(tmp,path)
 except OSError as exc: log.error("Could not save config to %s: %s",path,exc)
