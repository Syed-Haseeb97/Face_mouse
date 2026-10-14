import unittest
from types import SimpleNamespace
from facemouse.eye_detector import EyeStateDetector, classify
from facemouse.face_tracker import LEFT_EYE, NOSE_TIP, RIGHT_EYE, eye_aspect_ratio, metrics_from_landmarks
from tests.helpers import cfg
class ClassificationTests(unittest.TestCase):
 def test_hysteresis(self):
  self.assertTrue(classify(0.5,False,0.6,0.75)); self.assertFalse(classify(0.7,False,0.6,0.75)); self.assertTrue(classify(0.7,True,0.6,0.75)); self.assertFalse(classify(0.8,True,0.6,0.75))
 def test_debounce_ignores_single_frame_noise(self):
  d=EyeStateDetector(cfg(eye_debounce_frames=2)); d.update(0.27,0.27); r=d.update(0.05,0.27); self.assertFalse(r.left_closed); r=d.update(0.27,0.27); self.assertFalse(r.left_closed); d.update(0.05,0.27); r=d.update(0.05,0.27); self.assertTrue(r.left_closed); self.assertFalse(r.right_closed)
 def test_eyes_are_independent(self):
  d=EyeStateDetector(cfg());
  for _ in range(3): r=d.update(0.27,0.05)
  self.assertFalse(r.left_closed); self.assertTrue(r.right_closed)
 def test_reopen_needs_open_threshold(self):
  d=EyeStateDetector(cfg());
  for _ in range(3): d.update(0.05,0.27)
  for _ in range(3): r=d.update(0.27*0.68,0.27)
  self.assertTrue(r.left_closed)
  for _ in range(3): r=d.update(0.27,0.27)
  self.assertFalse(r.left_closed)
 def test_reset_clears_state_keeps_baseline(self):
  d=EyeStateDetector(cfg(baseline_left_ear=0.3));
  for _ in range(3): d.update(0.05,0.27)
  d.reset(); self.assertFalse(d.left.closed); self.assertAlmostEqual(d.left.baseline,0.3)
 def test_adaptive_baseline_is_bounded(self):
  d=EyeStateDetector(cfg(baseline_left_ear=0.27));
  for _ in range(2000): d.update(0.9,0.27)
  self.assertLessEqual(d.left.baseline,0.27*1.4+1e-9)
def lm_set(open_h=0.03,nose=(0.5,0.55),eye_w=0.06):
 pts={}
 def eye(idx,cx):
  p1,p2,p3,p4,p5,p6=idx; pts[p1]=(cx-eye_w/2,0.4); pts[p4]=(cx+eye_w/2,0.4); pts[p2]=(cx-eye_w/6,0.4-open_h/2); pts[p3]=(cx+eye_w/6,0.4-open_h/2); pts[p6]=(cx-eye_w/6,0.4+open_h/2); pts[p5]=(cx+eye_w/6,0.4+open_h/2)
 eye(RIGHT_EYE,0.40); eye(LEFT_EYE,0.60); pts[NOSE_TIP]=nose; n=max(pts)+1; return [SimpleNamespace(x=pts.get(i,(0,0))[0],y=pts.get(i,(0,0))[1]) for i in range(n)]
class FaceMetricsTests(unittest.TestCase):
 def test_ear_open_vs_closed(self):
  pts=[(0,0),(1,-1),(2,-1),(3,0),(2,1),(1,1)]; self.assertAlmostEqual(eye_aspect_ratio(pts),2/3,places=3); closed=[(0,0),(1,-0.05),(2,-0.05),(3,0),(2,0.05),(1,0.05)]; self.assertLess(eye_aspect_ratio(closed),0.05)
 def test_metrics_from_landmarks(self):
  f=metrics_from_landmarks(lm_set(),640,480); self.assertTrue(f.found); self.assertAlmostEqual(f.left_ear,f.right_ear,places=3); self.assertGreater(f.left_ear,0.2); self.assertAlmostEqual(f.yaw,0.0,places=2); self.assertAlmostEqual(f.iod,0.2*640,places=3)
 def test_closed_eye_lowers_only_that_eye(self):
  lm=lm_set();
  for i in LEFT_EYE[1:3]: lm[i].y=0.4
  for i in LEFT_EYE[4:6]: lm[i].y=0.4
  f=metrics_from_landmarks(lm,640,480); self.assertLess(f.left_ear,0.02); self.assertGreater(f.right_ear,0.2)
 def test_yaw_sign_and_degenerate_face(self):
  f=metrics_from_landmarks(lm_set(nose=(0.56,0.55)),640,480); self.assertGreater(f.yaw,0.2); tiny=metrics_from_landmarks(lm_set(eye_w=0.0001),640,480); flat=lm_set();
  for p in flat: p.x=p.y=0.5
  self.assertFalse(metrics_from_landmarks(flat,640,480).found)
if __name__=="__main__": unittest.main()
