import json,tempfile,unittest
from pathlib import Path
from facemouse.calibration import CalibrationSession
from facemouse.config import Config,load_config,save_config
from facemouse.head_motion import HeadMotionMapper
from tests.helpers import cfg,face
class HeadMotionTests(unittest.TestCase):
 def feed(self,mapper,nose,n=60):
  v=(0,0)
  for _ in range(n): v=mapper.update(face(nose=nose),1/30)
  return v
 def test_still_head_and_tiny_jitter_do_not_move_cursor(self):
  m=HeadMotionMapper(cfg()); self.assertEqual(self.feed(m,(320,240)),(0.0,0.0)); import random; random.seed(1)
  for _ in range(300): self.assertEqual(m.update(face(nose=(320+random.uniform(-0.6,0.6),240+random.uniform(-0.6,0.6))),1/30),(0.0,0.0))
 def test_directions_mirrored(self):
  m=HeadMotionMapper(cfg()); vx,vy=self.feed(m,(332,240)); self.assertLess(vx,0); self.assertEqual(vy,0.0); m=HeadMotionMapper(cfg()); vx,_=self.feed(m,(308,240)); self.assertGreater(vx,0); m=HeadMotionMapper(cfg()); _,vy=self.feed(m,(320,228)); self.assertLess(vy,0); m=HeadMotionMapper(cfg()); _,vy=self.feed(m,(320,252)); self.assertGreater(vy,0)
 def test_unmirrored(self): self.assertGreater(self.feed(HeadMotionMapper(cfg(mirror_x=False)),(332,240))[0],0)
 def test_speed_increases_with_deflection_and_is_capped(self):
  small=abs(self.feed(HeadMotionMapper(cfg()),(326,240))[0]); big=abs(self.feed(HeadMotionMapper(cfg()),(334,240))[0]); self.assertGreater(big,small); self.assertLessEqual(abs(self.feed(HeadMotionMapper(cfg(max_speed_px_s=500)),(360,240))[0]),500)
 def test_sensitivity_scales_speed(self): self.assertGreater(abs(self.feed(HeadMotionMapper(cfg(sensitivity=8)),(332,240))[0]),abs(self.feed(HeadMotionMapper(cfg(sensitivity=2)),(332,240))[0]))
 def test_smoothing_delays_response(self):
  m=HeadMotionMapper(cfg(smoothing=0.8)); m.update(face(nose=(320,240)),1/30); first=abs(m.update(face(nose=(340,240)),1/30)[0]); settled=abs(self.feed(m,(340,240))[0]); self.assertLess(first,settled)
 def test_neutral_offset_respected(self): self.assertEqual(self.feed(HeadMotionMapper(cfg(neutral_x=0.6)),(384,240)),(0.0,0.0))
class ConfigTests(unittest.TestCase):
 def test_defaults_valid_and_clamped(self):
  c=Config(sensitivity=99,dead_zone=-1,hold_ms=10,max_click_ms=500,target_fps="x").validate(); self.assertEqual(c.sensitivity,10.0); self.assertEqual(c.dead_zone,0.0); self.assertGreaterEqual(c.hold_ms,c.max_click_ms+100); self.assertEqual(c.target_fps,30)
 def test_threshold_relationships_enforced(self):
  c=Config(ear_close_ratio=0.8,ear_open_ratio=0.5,min_click_ms=400,max_click_ms=300).validate(); self.assertGreater(c.ear_open_ratio,c.ear_close_ratio); self.assertLess(c.min_click_ms,c.max_click_ms)
 def test_roundtrip_and_bad_files(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"sub"/"config.json"; c=Config(camera_key="Phone Camera",sensitivity=7.5); save_config(c,p); loaded=load_config(p); self.assertEqual(loaded.camera_key,"Phone Camera"); self.assertEqual(loaded.sensitivity,7.5); p.write_text("{not json"); self.assertEqual(load_config(p).sensitivity,Config().sensitivity); p.write_text(json.dumps({"sensitivity":"fast","unknown":1,"mirror_x":3,"hold_ms":800})); c=load_config(p); self.assertEqual(c.sensitivity,Config().sensitivity); self.assertTrue(c.mirror_x); self.assertEqual(c.hold_ms,800); self.assertEqual(load_config(Path(d)/"missing.json").hold_ms,Config().hold_ms)
class CalibrationTests(unittest.TestCase):
 def test_hints_for_bad_framing(self):
  self.assertIn("No face",CalibrationSession.centering_hint(face(found=False))); self.assertIn("LEFT",CalibrationSession.centering_hint(face(nose=(560,240)))); self.assertIn("RIGHT",CalibrationSession.centering_hint(face(nose=(80,240)))); self.assertIn("straight",CalibrationSession.centering_hint(face(yaw=0.4))); self.assertIn("eyes open",CalibrationSession.centering_hint(face(left_ear=0.05))); self.assertIsNone(CalibrationSession.centering_hint(face()))
 def test_apply_neutral_and_thresholds(self):
  s=CalibrationSession()
  for i in range(30): s.add_neutral(face(left_ear=0.30,right_ear=0.28,nose=(300+i%3,250)))
  for _ in range(20): s.add_closed("left",face(left_ear=0.06)); s.add_closed("right",face(right_ear=0.07))
  c=Config(); r=s.apply(c); self.assertAlmostEqual(c.neutral_x,301/640,places=3); self.assertAlmostEqual(c.baseline_left_ear,0.30,places=2); self.assertAlmostEqual(c.baseline_right_ear,0.28,places=2); self.assertTrue(0.35<=c.ear_close_ratio<c.ear_open_ratio<=0.95); self.assertLess(c.ear_close_ratio,0.7)
 def test_skip_wink_steps_keeps_thresholds_and_needs_enough_neutral(self):
  s=CalibrationSession();
  with self.assertRaises(ValueError): s.compute()
  for _ in range(12): s.add_neutral(face())
  c=Config(); before=(c.ear_close_ratio,c.ear_open_ratio); s.apply(c); self.assertEqual((c.ear_close_ratio,c.ear_open_ratio),before)
 def test_rejected_frames_not_counted(self):
  s=CalibrationSession(); s.add_neutral(face(found=False)); s.add_neutral(face(nose=(600,240))); self.assertEqual(s.neutral_count,0)
if __name__=="__main__": unittest.main()
