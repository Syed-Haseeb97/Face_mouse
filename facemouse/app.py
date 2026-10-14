"""Application entry point: wiring, safety nets, command-line options."""
from __future__ import annotations
import argparse, atexit, logging, os, signal, sys, threading
from . import __version__
from .camera import CameraManager, enumerate_cameras
from .config import default_config_path, load_config
from .engine import Engine
from .face_tracker import FaceTracker
from .hotkeys import HotkeyManager
from .mouse_controller import MemoryBackend, MouseController, WindowsMouseBackend, enable_dpi_awareness
log=logging.getLogger("facemouse")
def install_safety_nets(mouse):
    atexit.register(lambda: mouse.release_all(force=True)); previous_hook=sys.excepthook
    def hook(exc_type,exc,tb): mouse.emergency_release(); previous_hook(exc_type,exc,tb)
    sys.excepthook=hook
    def thread_hook(args): mouse.emergency_release(); log.error("Unhandled exception in thread %s",args.thread,exc_info=args.exc_info)
    threading.excepthook=thread_hook
    def on_signal(signum,_frame): mouse.emergency_release(); os._exit(0) if signum!=signal.SIGINT else sys.exit(0)
    for name in ("SIGINT","SIGTERM","SIGBREAK"):
        sig=getattr(signal,name,None)
        if sig is not None:
            try: signal.signal(sig,on_signal)
            except (ValueError,OSError): pass
def main(argv=None):
    parser=argparse.ArgumentParser(prog="facemouse",description="Hands-free mouse: head moves the cursor, eye gestures click.")
    parser.add_argument("--list-cameras",action="store_true"); parser.add_argument("--dry-run",action="store_true"); parser.add_argument("--config"); parser.add_argument("--log-level",default="INFO"); args=parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging,args.log_level.upper(),logging.INFO),format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.list_cameras:
        cams=enumerate_cameras()
        if not cams: print("No cameras found."); return 1
        for cam in cams: print(f"[{cam.index}] {cam.key}")
        return 0
    if args.dry_run: backend=MemoryBackend(verbose=True)
    elif os.name=="nt": enable_dpi_awareness(); backend=WindowsMouseBackend()
    else: print("Face Mouse sends input through the Windows API. Run on Windows, or use --dry-run."); return 2
    config_path=args.config or default_config_path(); cfg=load_config(config_path); mouse=MouseController(backend); install_safety_nets(mouse); camera=CameraManager(cfg); engine=Engine(cfg,camera,FaceTracker,mouse,config_path=config_path)
    hotkeys=HotkeyManager(); hotkeys.register("emergency stop",cfg.emergency_hotkey,engine.emergency_stop); hotkeys.register("toggle control",cfg.toggle_hotkey,engine.toggle_control); hotkeys.register("recenter",cfg.recenter_hotkey,engine.recenter); hotkeys.start()
    for problem in hotkeys.errors: log.warning("Hotkey: %s",problem)
    import tkinter as tk
    from .ui.main_window import MainWindow
    root=tk.Tk(); MainWindow(root,engine,cfg,config_path,hotkeys,__version__)
    try: root.mainloop()
    finally: engine.stop(); hotkeys.stop(); mouse.release_all(force=True)
    return 0
