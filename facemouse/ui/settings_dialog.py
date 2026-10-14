"""Settings window generated from config.SETTINGS_SPEC."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from ..config import RANGES, SETTINGS_SPEC, Config, save_config

def add_slider(parent,row,cfg,field,label,vars_):
    lo,hi,step=RANGES[field]; var=tk.DoubleVar(value=getattr(cfg,field)); vars_[field]=var
    ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w",pady=2)
    tk.Scale(parent,from_=lo,to=hi,resolution=step,orient="horizontal",length=220,variable=var).grid(row=row,column=1,padx=6)

class SettingsDialog:
    def __init__(self,root,engine,cfg:Config,config_path):
        self.engine,self.cfg,self.config_path=engine,cfg,config_path; self.vars={}; self.top=tk.Toplevel(root); self.top.title("Settings")
        nb=ttk.Notebook(self.top); nb.grid(padx=8,pady=8); tabs={}
        for tab,field,label in SETTINGS_SPEC:
            if tab not in tabs: tabs[tab]=ttk.Frame(nb,padding=8); nb.add(tabs[tab],text=tab)
            add_slider(tabs[tab],len(tabs[tab].grid_slaves())//2,cfg,field,label,self.vars)
        self.bools={}
        for field,label,tab in (("mirror_x","Mirror horizontal movement (head left = cursor left)","Cursor"),("adaptive_baseline","Adapt to slow changes in eye openness","Eyes"),("enable_right_hold","Right eye held = hold right button","Gestures")):
            var=tk.BooleanVar(value=getattr(cfg,field)); self.bools[field]=var; ttk.Checkbutton(tabs[tab],text=label,variable=var).grid(columnspan=2,sticky="w")
        sysf=tabs["System"]; self.backend=tk.StringVar(value=cfg.camera_backend); ttk.Label(sysf,text="Camera backend").grid(sticky="w"); ttk.Combobox(sysf,textvariable=self.backend,values=["auto","dshow","msmf"],state="readonly",width=8).grid(row=sysf.grid_size()[1]-1,column=1,sticky="w")
        self.hot={}
        for field,label in (("emergency_hotkey","Emergency stop hotkey"),("toggle_hotkey","Pause/resume hotkey"),("recenter_hotkey","Recenter hotkey")):
            self.hot[field]=tk.StringVar(value=getattr(cfg,field)); r=sysf.grid_size()[1]; ttk.Label(sysf,text=label).grid(row=r,column=0,sticky="w"); ttk.Entry(sysf,textvariable=self.hot[field],width=18).grid(row=r,column=1,sticky="w")
        ttk.Label(sysf,text="Hotkey and backend changes apply after restarting the app.",foreground="#555").grid(columnspan=2,sticky="w")
        bar=ttk.Frame(self.top,padding=8); bar.grid(); ttk.Button(bar,text="Save",command=self.save).pack(side="left",padx=4); ttk.Button(bar,text="Defaults",command=self.defaults).pack(side="left",padx=4); ttk.Button(bar,text="Close",command=self.top.destroy).pack(side="left",padx=4)
    def save(self):
        for field,var in self.vars.items(): setattr(self.cfg,field,var.get())
        for field,var in self.bools.items(): setattr(self.cfg,field,var.get())
        for field,var in self.hot.items(): setattr(self.cfg,field,var.get())
        self.cfg.camera_backend=self.backend.get(); self.engine.apply_config(); save_config(self.cfg,self.config_path)
        for field,var in self.vars.items(): var.set(getattr(self.cfg,field))
    def defaults(self):
        default=Config()
        for field,var in self.vars.items(): var.set(getattr(default,field))
        for field,var in self.bools.items(): var.set(getattr(default,field))
