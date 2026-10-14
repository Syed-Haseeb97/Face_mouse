import unittest
from facemouse.gesture_controller import (GestureController,GestureStateMachine,State,LEFT_CLICK,LEFT_DOWN,LEFT_UP,RIGHT_CLICK,RIGHT_DOWN,RIGHT_UP)
from facemouse.mouse_controller import MemoryBackend,MouseController
from tests.helpers import cfg,names,run
OPEN=(0.6,False,False)
class GestureMachineTests(unittest.TestCase):
 def setUp(self): self.m=GestureStateMachine(cfg())
 def test_left_wink_clicks_once(self): ev,states,_,_=run(self.m,[OPEN,(0.2,True,False),(1.0,False,False)]); self.assertEqual(names(ev),[LEFT_CLICK]); self.assertIn(State.LEFT_ONLY_CLOSED,states); self.assertEqual(states[-1],State.BOTH_OPEN)
 def test_right_wink_clicks_once(self): ev,states,_,_=run(self.m,[OPEN,(0.2,False,True),(1.0,False,False)]); self.assertEqual(names(ev),[RIGHT_CLICK]); self.assertIn(State.RIGHT_ONLY_CLOSED,states)
 def test_bilateral_blink_ignored(self):
  for dur in (0.1,0.2,0.4,1.5):
   m=GestureStateMachine(cfg()); ev,states,_,_=run(m,[OPEN,(dur,True,True),(1.0,False,False)]); self.assertEqual(ev,[],dur); self.assertIn(State.BOTH_CLOSED,states)
 def test_bilateral_blink_with_asynchronous_closing_and_opening(self):
  ev,_,_,_=run(self.m,[OPEN,(0.2,True,False),(0.2,True,True),(0.1,False,True),(1.0,False,False)]); self.assertEqual(ev,[])
 def test_right_lags_so_left_reopens_first_no_click(self):
  ev,_,_,_=run(self.m,[OPEN,(0.2,True,False),(0.03,False,False),(0.2,False,True),(1.0,False,False)]); self.assertNotIn(LEFT_CLICK,names(ev))
 def test_too_short_and_in_between_closures_ignored(self):
  ev,_,_,_=run(self.m,[OPEN,(0.033,True,False),(1.0,False,False)]); self.assertEqual(ev,[]); ev,_,_,_=run(GestureStateMachine(cfg()),[OPEN,(0.52,True,False),(1.0,False,False)]); self.assertEqual(ev,[])
 def test_other_eye_squint_blocks_click(self): ev,_,_,_=run(self.m,[OPEN,(0.25,True,False,{"rr":0.6}),(1.0,False,False)]); self.assertEqual(ev,[])
 def test_left_hold_drag_and_release(self):
  ev,states,_,out=run(self.m,[OPEN,(1.5,True,False)]); self.assertEqual(names(ev),[LEFT_DOWN]); self.assertEqual(out.state,State.LEFT_HOLD); self.assertTrue(out.allow_move and out.left_held); ev2,_,_,out2=run(self.m,[(1.0,False,False)],t0=3.0); self.assertEqual(names(ev2),[LEFT_UP]); self.assertFalse(out2.left_held)
 def test_hold_not_released_by_single_frame_flicker(self):
  ev,_,_,out=run(self.m,[OPEN,(1.0,True,False),(0.033,False,False),(0.5,True,False)]); self.assertEqual(names(ev),[LEFT_DOWN]); self.assertEqual(out.state,State.LEFT_HOLD)
 def test_right_hold_and_disabled_right_hold(self):
  ev,_,_,_=run(self.m,[OPEN,(1.0,False,True),(1.0,False,False)]); self.assertEqual(names(ev),[RIGHT_DOWN,RIGHT_UP]); m=GestureStateMachine(cfg(enable_right_hold=False)); ev,_,_,_=run(m,[OPEN,(1.5,False,True),(1.0,False,False)]); self.assertEqual(ev,[])
 def test_other_eye_blinking_during_hold_is_ignored(self): ev,_,_,out=run(self.m,[OPEN,(1.0,True,False),(0.2,True,True),(0.3,True,False)]); self.assertEqual(names(ev),[LEFT_DOWN]); self.assertEqual(out.state,State.LEFT_HOLD)
 def test_cooldown_blocks_immediate_second_click(self):
  segs=[OPEN,(0.2,True,False),(0.1,False,False),(0.2,True,False),(1.0,False,False)]; ev,_,t,_=run(self.m,segs); self.assertEqual(names(ev),[LEFT_CLICK]); ev2,_,_,_=run(self.m,[(0.2,True,False),(1.0,False,False)],t0=t); self.assertEqual(names(ev2),[LEFT_CLICK])
 def test_face_loss_before_gesture_cancels_it_and_recovers(self):
  segs=[OPEN,(0.15,True,False),(0.5,False,False,{"face_ok":False}),(0.3,False,False)]; ev,states,t,_=run(self.m,segs); self.assertEqual(ev,[]); self.assertIn(State.LOCKOUT,states); ev2,_,_,_=run(self.m,[(1.0,False,False),(0.2,True,False),(1.0,False,False)],t0=t); self.assertEqual(names(ev2),[LEFT_CLICK])
 def test_brief_face_loss_during_hold_keeps_hold(self): ev,_,_,out=run(self.m,[OPEN,(1.0,True,False),(0.2,True,False,{"face_ok":False}),(0.3,True,False)]); self.assertEqual(names(ev),[LEFT_DOWN]); self.assertEqual(out.state,State.LEFT_HOLD)
 def test_long_face_loss_releases_hold_and_does_not_rehold(self): ev,_,_,out=run(self.m,[OPEN,(1.0,True,False),(0.8,True,False,{"face_ok":False}),(1.5,True,False)]); self.assertEqual(names(ev),[LEFT_DOWN,LEFT_UP]); self.assertEqual(out.state,State.LOCKOUT); self.assertFalse(out.left_held)
 def test_looking_away_blocks_gestures_but_not_hold(self):
  ev,_,_,_=run(self.m,[OPEN,(0.2,True,False,{"pose_ok":False}),(1.0,False,False)]); self.assertEqual(ev,[]); m=GestureStateMachine(cfg()); ev,_,_,out=run(m,[OPEN,(1.0,True,False),(0.5,True,False,{"pose_ok":False})]); self.assertEqual(out.state,State.LEFT_HOLD)
 def test_disable_releases_and_blocks(self): run(self.m,[OPEN,(1.0,True,False)]); self.assertEqual(self.m.disable(),[LEFT_UP]); ev,_,_,out=run(self.m,[(1.0,True,False)],t0=5.0); self.assertEqual(ev,[]); self.assertEqual(out.state,State.DISABLED)
 def test_reenable_requires_open_eyes(self): self.m.disable(); self.m.enable(); ev,_,_,_=run(self.m,[(1.5,True,False),(1.0,False,False)]); self.assertEqual(ev,[])
class GestureControllerTests(unittest.TestCase):
 def setUp(self): self.backend=MemoryBackend(); self.mouse=MouseController(self.backend); self.gc=GestureController(cfg(),self.mouse)
 def drive(self,segs,t0=0.0):
  t=t0
  for dur,l,r in segs:
   for _ in range(round(dur*30)): self.gc.update(t,True,l,r); t+=1/30
  return t
 def test_wink_produces_exactly_one_mouse_click(self): self.drive([OPEN,(0.2,True,False),(1.0,False,False)]); self.assertEqual(self.backend.events(),[("down","left"),("up","left")])
 def test_bilateral_blink_produces_no_mouse_events(self): self.drive([OPEN,(0.2,True,True),(1.0,False,False)]); self.assertEqual(self.backend.events(),[])
 def test_hold_presses_once_then_releases(self): self.drive([OPEN,(2.0,True,False)]); self.assertEqual(self.backend.events(),[("down","left")]); self.assertTrue(self.mouse.is_held("left")); self.drive([(1.0,False,False)],t0=5.0); self.assertEqual(self.backend.events(),[("down","left"),("up","left")]); self.assertFalse(self.mouse.any_held)
 def test_emergency_stop_releases_and_blocks_further_input(self):
  t=self.drive([OPEN,(1.5,True,False)]); self.assertTrue(self.mouse.is_held("left")); self.gc.emergency_stop(); self.assertFalse(self.mouse.any_held); self.assertIn(("up","left"),self.backend.events()); n=len(self.backend.events()); self.drive([(2.0,True,False),(1.0,False,False)],t0=t); self.assertEqual(len(self.backend.events()),n); self.assertFalse(self.mouse.press("left"))
 def test_disable_via_set_enabled_releases(self): self.drive([OPEN,(1.5,True,False)]); self.gc.set_enabled(False); self.assertFalse(self.mouse.any_held)
 def test_abort_releases_held_button(self): t=self.drive([OPEN,(1.5,True,False)]); self.gc.abort(t); self.assertFalse(self.mouse.any_held)
 def test_stray_held_button_is_released(self): self.mouse.press("right"); self.gc.update(0.0,True,False,False); self.assertFalse(self.mouse.is_held("right"))
if __name__=="__main__": unittest.main()
