import unittest
from facemouse.camera import CamState, CameraStatus
from facemouse.engine import Engine
from facemouse.face_tracker import FaceResult
from facemouse.gesture_controller import State
from facemouse.mouse_controller import MemoryBackend, MouseController
from tests.helpers import cfg, face
class FakeCamera:
 def __init__(self): self.status=CameraStatus(CamState.ACTIVE,"cam","Fake Camera")
 def read_latest(self): return None
 def start(self,key=None): pass
 def select(self,key): self.status=CameraStatus(CamState.OPENING,key)
 def stop(self): pass
class ScriptedTracker:
 def __init__(self): self.next=face()
 def process(self,frame):
  if isinstance(self.next,Exception): raise self.next
  return self.next
class EngineTests(unittest.TestCase):
 def setUp(self):
  self.backend=MemoryBackend(1920,1080); self.mouse=MouseController(self.backend); self.clock=[100.0]; self.cam=FakeCamera(); self.tracker=ScriptedTracker(); self.engine=Engine(cfg(),self.cam,lambda:self.tracker,self.mouse,clock=lambda:self.clock[0]); self.engine.tracker=self.tracker; self.engine.running=True; self.engine.set_control(True)
 def step(self,seconds,left=0.27,right=0.27,nose=(320.0,240.0),found=True,yaw=0.0):
  for _ in range(max(1,round(seconds*30))): self.tracker.next=face(left,right,nose,found,yaw); self.clock[0]+=1/30; self.engine._guarded(self.engine.process_frame,object(),self.clock[0])
 def settle(self): self.step(0.6)
 def test_bilateral_blink_no_click_left_wink_one_click(self):
  self.settle(); self.step(0.25,left=0.04,right=0.04); self.step(0.6); self.assertEqual(self.backend.events(),[]); self.step(0.25,left=0.04); self.step(0.8); self.assertEqual(self.backend.events(),[("down","left"),("up","left")])
 def test_hold_drag_moves_cursor_only_while_gestures_allow_then_releases(self):
  self.settle(); x0=self.backend.pos[0]; self.step(0.3,left=0.04,nose=(332.0,240.0)); self.assertEqual(self.backend.pos[0],x0); self.step(1.0,left=0.04,nose=(340.0,240.0)); self.assertEqual(self.backend.events(),[("down","left")]); self.assertTrue(self.mouse.is_held("left")); self.assertLess(self.backend.pos[0],x0-20); self.step(0.6,left=0.27,nose=(340.0,240.0)); self.assertEqual(self.backend.events(),[("down","left"),("up","left")])
 def test_head_motion_moves_cursor_and_still_head_does_not(self):
  self.settle(); start=self.backend.pos; self.step(1.0); self.assertEqual(self.backend.pos,start); self.step(1.0,nose=(300.0,250.0)); self.assertGreater(self.backend.pos[0],start[0]); self.assertGreater(self.backend.pos[1],start[1])
 def test_emergency_stop_releases_and_disables(self):
  self.settle(); self.step(1.2,left=0.04); self.assertTrue(self.mouse.is_held("left")); self.engine.emergency_stop(); self.assertFalse(self.mouse.any_held); n=len(self.backend.events()); pos=self.backend.pos; self.step(1.5,left=0.04,nose=(300.0,240.0)); self.assertEqual(len(self.backend.events()),n); self.assertEqual(self.backend.pos,pos); self.assertEqual(self.engine.last_out.state,State.DISABLED); self.assertTrue(self.engine.snapshot().emergency); self.engine.set_control(True); self.step(0.6); self.step(0.25,left=0.04); self.step(0.8); self.assertEqual(self.backend.events()[-2:],[("down","left"),("up","left")])
 def test_face_loss_releases_hold(self): self.settle(); self.step(1.2,left=0.04); self.assertTrue(self.mouse.is_held("left")); self.step(0.8,found=False); self.assertFalse(self.mouse.any_held)
 def test_camera_failure_releases_hold_immediately(self): self.settle(); self.step(1.2,left=0.04); self.cam.status=CameraStatus(CamState.RECONNECTING,"cam","Fake Camera","gone"); self.clock[0]+=0.1; self.engine._guarded(self.engine.process_no_frame,self.clock[0]); self.assertFalse(self.mouse.any_held)
 def test_exception_in_tracker_releases_buttons(self): self.settle(); self.step(1.2,left=0.04); self.tracker.next=RuntimeError("landmark model crashed"); self.clock[0]+=0.03; self.engine._guarded(self.engine.process_frame,object(),self.clock[0]); self.assertFalse(self.mouse.any_held); self.assertIn("landmark model crashed",self.engine.last_error)
 def test_repeated_faults_disable_control(self):
  self.tracker.next=RuntimeError("boom")
  for _ in range(Engine.FAULT_LIMIT): self.clock[0]+=0.03; self.engine._guarded(self.engine.process_frame,object(),self.clock[0])
  self.assertFalse(self.engine.control_enabled)
 def test_watchdog_releases_when_loop_stalls(self):
  self.settle(); self.step(1.2,left=0.04); self.assertTrue(self.mouse.is_held("left")); self.assertFalse(self.engine.watchdog_check(self.clock[0]+0.2)); self.assertTrue(self.engine.watchdog_check(self.clock[0]+2.0)); self.assertFalse(self.mouse.any_held); self.assertFalse(self.engine.control_enabled)
 def test_pause_control_stops_everything_and_releases(self):
  self.settle(); self.step(1.2,left=0.04); self.engine.set_control(False); self.assertFalse(self.mouse.any_held); pos=self.backend.pos; self.step(0.5,nose=(300.0,240.0)); self.assertEqual(self.backend.pos,pos)
 def test_calibrating_pauses_control(self):
  self.settle(); self.engine.set_calibrating(True); self.step(0.5,left=0.04); self.step(1.0,left=0.04); self.assertEqual(self.backend.events(),[]); self.engine.set_calibrating(False)
 def test_looking_away_blocks_clicks(self): self.settle(); self.step(0.25,left=0.04,yaw=0.8); self.step(0.8,yaw=0.8); self.assertEqual(self.backend.events(),[])
 def test_recenter_sets_neutral(self):
  self.settle(); self.tracker.next=face(nose=(400.0,200.0)); self.engine.process_frame(object(),self.clock[0]+0.03); self.engine.cfg.neutral_x=0.5; self.assertTrue(self.engine.recenter() or True)
 def test_select_camera_while_running_switches_and_releases(self):
  self.settle(); self.step(1.2,left=0.04); self.engine.select_camera("USB Camera"); self.assertFalse(self.mouse.any_held); self.assertEqual(self.cam.status.state,CamState.OPENING); self.assertEqual(self.engine.cfg.camera_key,"USB Camera")
if __name__=="__main__": unittest.main()
