"""Compact control window (no always-on overlay)."""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, ttk
from ..camera import CamState
from ..config import save_config
from .calibration_dialog import CalibrationDialog
from .settings_dialog import SettingsDialog

class MainWindow:
    POLL_MS=100
    def __init__(self,root,engine,cfg,config_path,hotkeys,version=""):
        self.root,self.engine,self.cfg,self.config_path,self.hotkeys=root,engine,cfg,config_path,hotkeys; self._cams=[]; self._photo=None
        root.title(f"Face Mouse {version}"); root.resizable(False,False); root.protocol("WM_DELETE_WINDOW",self.close)
        f=ttk.Frame(root,padding=8); f.grid(sticky="nsew")
        ttk.Label(f,text="Camera:").grid(row=0,column=0,sticky="w"); self.cam_var=tk.StringVar(); self.cam_box=ttk.Combobox(f,textvariable=self.cam_var,state="readonly",width=34); self.cam_box.grid(row=0,column=1,sticky="ew",padx=4); self.cam_box.bind("<<ComboboxSelected>>",self._on_camera); ttk.Button(f,text="Refresh",width=8,command=self.refresh_cameras).grid(row=0,column=2)
        self.vars={}; rows=[("Camera status","cam"),("Face","face"),("Eye state","eyes"),("Gesture","gesture"),("Left button","lbtn"),("Right button","rbtn"),("Mouse control","control"),("FPS","fps")]
        for i,(label,key) in enumerate(rows,start=1): ttk.Label(f,text=label+":").grid(row=i,column=0,sticky="w"); self.vars[key]=tk.StringVar(value="-"); ttk.Label(f,textvariable=self.vars[key],wraplength=300,justify="left").grid(row=i,column=1,columnspan=2,sticky="w",padx=4)
        r=len(rows)+1; self.start_btn=ttk.Button(f,text="Start",command=self._start_stop); self.start_btn.grid(row=r,column=0,sticky="ew",pady=(8,2)); self.ctl_btn=ttk.Button(f,text="Pause mouse control",command=self._toggle_control); self.ctl_btn.grid(row=r,column=1,sticky="ew",padx=4,pady=(8,2)); ttk.Button(f,text="Recenter",command=self._recenter).grid(row=r,column=2,pady=(8,2))
        tk.Button(f,text="EMERGENCY STOP  (%s)"%self.cfg.emergency_hotkey.upper(),bg="#c62828",fg="white",activebackground="#8e0000",activeforeground="white",font=("Segoe UI",10,"bold"),command=self.engine.emergency_stop).grid(row=r+1,column=0,columnspan=3,sticky="ew",pady=2)
        ttk.Label(f,text="Sensitivity:").grid(row=r+2,column=0,sticky="w"); self.sens=tk.DoubleVar(value=cfg.sensitivity); scale=ttk.Scale(f,from_=1,to=10,variable=self.sens,command=self._on_sens); scale.grid(row=r+2,column=1,sticky="ew",padx=4); scale.bind("<ButtonRelease-1>",lambda _e:save_config(self.cfg,self.config_path)); self.sens_lbl=ttk.Label(f,text=f"{cfg.sensitivity:.1f}"); self.sens_lbl.grid(row=r+2,column=2)
        ttk.Button(f,text="Calibrate...",command=self._calibrate).grid(row=r+3,column=0,sticky="ew",pady=4); ttk.Button(f,text="Settings...",command=self._settings).grid(row=r+3,column=1,sticky="ew",padx=4); self.prev_var=tk.BooleanVar(value=cfg.preview_enabled); ttk.Checkbutton(f,text="Preview",variable=self.prev_var,command=self._toggle_preview).grid(row=r+3,column=2); self.preview_lbl=ttk.Label(f); self.preview_lbl.grid(row=r+4,column=0,columnspan=3)
        self.hint=ttk.Label(f,foreground="#555",wraplength=360,justify="left",text=f"Hotkeys: emergency stop {cfg.emergency_hotkey} | pause/resume {cfg.toggle_hotkey} | recenter {cfg.recenter_hotkey}"); self.hint.grid(row=r+5,column=0,columnspan=3,sticky="w",pady=(6,0))
        if hotkeys.errors: ttk.Label(f,foreground="#b00020",wraplength=360,text="Hotkey problem: "+"; ".join(hotkeys.errors)).grid(row=r+6,column=0,columnspan=3,sticky="w")
        self.refresh_cameras(); self._poll()
    def refresh_cameras(self):
        self._cams=self.engine.camera.list_cameras(); self.cam_box["values"]=[c.display for c in self._cams]; current=next((c.display for c in self._cams if c.key==self.cfg.camera_key),"");
        if not current and self._cams and not self.cfg.camera_key: current=self._cams[0].display
        self.cam_var.set(current or (self.cfg.camera_key and f"{self.cfg.camera_key} (not connected)") or "")
    def _on_camera(self,_event=None):
        cam=next((c for c in self._cams if c.display==self.cam_var.get()),None)
        if cam: self.engine.select_camera(cam.key)
    def _start_stop(self):
        if self.engine.running: self.engine.stop(); return
        try: self.refresh_cameras(); self.engine.start()
        except Exception as exc: messagebox.showerror("Cannot start",str(exc))
    def _toggle_control(self): self.engine.toggle_control()
    def _recenter(self):
        if not self.engine.recenter(): messagebox.showinfo("Recenter","No face detected - look at the camera and try again.")
    def _on_sens(self,value): self.cfg.sensitivity=round(float(value)*2)/2; self.sens_lbl.config(text=f"{self.cfg.sensitivity:.1f}")
    def _toggle_preview(self):
        self.cfg.preview_enabled=self.prev_var.get()
        if not self.cfg.preview_enabled: self.preview_lbl.config(image=""); self._photo=None
        save_config(self.cfg,self.config_path)
    def _settings(self): SettingsDialog(self.root,self.engine,self.cfg,self.config_path)
    def _calibrate(self): CalibrationDialog(self.root,self.engine,self.cfg,self.config_path)
    def _poll(self):
        s=self.engine.snapshot(); cam_text=s.camera_message or s.camera_state
        if s.camera_state==CamState.ACTIVE: cam_text=f"Active: {s.camera_name}"+(f"  [{s.camera_message}]" if "unavailable" in s.camera_message else "")
        self.vars["cam"].set(cam_text); self.vars["face"].set("Face detected" if s.face_found else "No face detected"); self.vars["eyes"].set(f"{s.gesture_state}   (L {'closed' if s.left_closed else 'open'} {s.left_ratio:.2f}, R {'closed' if s.right_closed else 'open'} {s.right_ratio:.2f})"); self.vars["gesture"].set(s.gesture); self.vars["lbtn"].set("HELD" if s.left_held else "up"); self.vars["rbtn"].set("HELD" if s.right_held else "up")
        control="EMERGENCY STOPPED - press Resume" if s.emergency else ("ENABLED" if s.control_enabled else "paused"); self.vars["control"].set(control+(f"   {s.error}" if s.error else "")); self.vars["fps"].set(f"{s.fps:.0f}" if s.running else "-"); self.start_btn.config(text="Stop" if s.running else "Start"); self.ctl_btn.config(text="Pause mouse control" if s.control_enabled else "Resume mouse control",state="normal" if s.running else "disabled")
        if self.cfg.preview_enabled and s.preview:
            w,h,data=s.preview; self._photo=tk.PhotoImage(data=b"P6 %d %d 255\n"%(w,h)+data,format="PPM"); self.preview_lbl.config(image=self._photo)
        self.root.after(self.POLL_MS,self._poll)
    def close(self):
        try: save_config(self.cfg,self.config_path); self.engine.emergency_stop()
        finally: self.root.destroy()
