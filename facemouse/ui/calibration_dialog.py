"""Guided calibration: centre face -> neutral pose + open-eye baseline -> (optional) wink samples
-> sensitivity / hold / smoothing / dead zone. Mouse control is paused while it is open."""
from __future__ import annotations
import time
import tkinter as tk
from tkinter import messagebox, ttk
from ..calibration import CalibrationSession
from ..config import save_config
from .settings_dialog import add_slider
NEUTRAL_S,WINK_S,WINK_SKIP_S=3.0,2.5,0.8
class CalibrationDialog:
    def __init__(self,root,engine,cfg,config_path):
        self.root,self.engine,self.cfg,self.config_path=root,engine,cfg,config_path; self.session=CalibrationSession(); self.step="intro"; self.step_start=0.0; self.last_counter=-1; self.vars={}; self._photo=None
        try:
            if not engine.running: engine.start(control=False)
        except Exception as exc: messagebox.showerror("Calibration",str(exc)); return
        engine.set_calibrating(True); engine.preview_override=True; self.top=tk.Toplevel(root); self.top.title("Calibration"); self.top.protocol("WM_DELETE_WINDOW",self.close)
        self.msg=tk.StringVar(value="Sit comfortably, centre your face in the picture and look at the screen.\nPress Start."); ttk.Label(self.top,textvariable=self.msg,wraplength=340,justify="left").grid(padx=10,pady=8); self.preview=ttk.Label(self.top); self.preview.grid(); self.bar=ttk.Progressbar(self.top,length=320,maximum=100); self.bar.grid(pady=6); self.extra=ttk.Frame(self.top,padding=6); self.extra.grid(); row=ttk.Frame(self.top,padding=6); row.grid(); self.go=ttk.Button(row,text="Start",command=self.begin); self.go.pack(side="left",padx=4); self.skip=ttk.Button(row,text="Skip step",command=self.next_step,state="disabled"); self.skip.pack(side="left",padx=4); ttk.Button(row,text="Cancel",command=self.close).pack(side="left",padx=4); self._tick()
    def begin(self): self.go.config(state="disabled"); self.session=CalibrationSession(); self._enter("neutral")
    def _enter(self,step):
        self.step,self.step_start=step,time.monotonic(); self.skip.config(state="normal" if step in ("left","right") else "disabled"); prompts={"neutral":"Step 1/3: Look straight at the screen, relax your head, keep BOTH eyes open (don't blink hard).","left":"Step 2/3: Close ONLY your LEFT eye and hold it closed. Keep the right eye open. (Skip to keep default thresholds.)","right":"Step 3/3: Close ONLY your RIGHT eye and hold it closed. Keep the left eye open."}
        if step in prompts: self.msg.set(prompts[step])
        if step=="done": self._finish()
    def next_step(self):
        order={"neutral":"left","left":"right","right":"done"}
        if self.step in order: self._enter(order[self.step])
    def _finish(self):
        try: result=self.session.apply(self.cfg)
        except ValueError as exc: messagebox.showwarning("Calibration",str(exc)); self.go.config(state="normal"); self.step="intro"; return
        self.engine.apply_config(); save_config(self.cfg,self.config_path); text=f"Saved. Neutral position set; open-eye baseline L {result.baseline_left:.2f} / R {result.baseline_right:.2f}."
        if result.close_ratio is not None: text+=f"\nBlink thresholds: closed < {result.close_ratio:.2f}, open > {result.open_ratio:.2f}."
        text+="\nFine-tune below, then press Save & close."; self.msg.set(text)
        for i,(field,label) in enumerate((("sensitivity","Cursor sensitivity"),("hold_ms","Hold duration (ms)"),("smoothing","Smoothing"),("dead_zone","Dead zone"))): add_slider(self.extra,i,self.cfg,field,label,self.vars)
        self.go.config(text="Save & close",state="normal",command=self.save_close); self.step="tuning"
    def save_close(self):
        for field,var in self.vars.items(): setattr(self.cfg,field,var.get())
        self.engine.apply_config(); save_config(self.cfg,self.config_path); self.close()
    def close(self):
        self.step="closed"; self.engine.preview_override=False; self.engine.set_calibrating(False)
        if self.top.winfo_exists(): self.top.destroy()
    def _tick(self):
        if self.step=="closed": return
        face,counter=self.engine.latest_face(); new=counter!=self.last_counter; self.last_counter=counter; elapsed=time.monotonic()-self.step_start
        if self.step=="neutral":
            hint=CalibrationSession.centering_hint(face)
            if hint: self.msg.set("Step 1/3: "+hint); self.step_start=time.monotonic(); self.session.neutral.clear(); self.bar["value"]=0
            elif new: self.session.add_neutral(face); self.bar["value"]=min(100,100*elapsed/NEUTRAL_S)
            if not hint and elapsed>=NEUTRAL_S: self._enter("left")
        elif self.step in ("left","right"):
            if new and elapsed>=WINK_SKIP_S: self.session.add_closed(self.step,face)
            self.bar["value"]=min(100,100*elapsed/WINK_S)
            if elapsed>=WINK_S: self.next_step()
        snap=self.engine.snapshot()
        if snap.preview:
            w,h,data=snap.preview; self._photo=tk.PhotoImage(data=b"P6 %d %d 255\n"%(w,h)+data,format="PPM"); self.preview.config(image=self._photo)
        self.root.after(50,self._tick)
