import unittest
from facemouse.camera import CamState, CameraInfo, CameraManager, make_camera_infos
from tests.helpers import cfg
class FakeCap:
    def __init__(self,name,opened=True,frames=True): self.name,self.opened,self.frames,self.released=name,opened,frames,False; self.reads=0
    def isOpened(self): return self.opened and not self.released
    def read(self): self.reads+=1; return (True,f"{self.name}-frame{self.reads}") if self.frames else (False,None)
    def release(self): self.released=True
class World:
    def __init__(self,names): self.names,self.caps,self.broken=list(names),[],{}
    def enumerate(self): return make_camera_infos(self.names)
    def factory(self,index,backend,w,h,fps):
        name=self.names[index]; mode=self.broken.get(name)
        if mode=="busy": return None
        cap=FakeCap(name,frames=(mode!="noframes")); self.caps.append(cap); return cap
    def manager(self,**kw):
        self.clock=[0.0]; c=cfg(**kw); return CameraManager(c,self.enumerate,self.factory,clock=lambda:self.clock[0],sleep=lambda s:None)
def pump(mgr,world,n=3,step=0.0):
    for _ in range(n): mgr.pump(); world.clock[0]+=step
class EnumerationTests(unittest.TestCase):
    def test_duplicate_names_get_distinct_keys(self):
        infos=make_camera_infos(["Integrated Camera","USB Camera","USB Camera"]); self.assertEqual([i.key for i in infos],["Integrated Camera","USB Camera","USB Camera #2"]); self.assertEqual([i.index for i in infos],[0,1,2])
class CameraManagerTests(unittest.TestCase):
    def manual(self,w,**kw): m=w.manager(**kw); m._requested,m._startup=m.cfg.camera_key,True; return m
    def test_opens_preferred_camera_by_name_not_index(self):
        w=World(["Integrated Camera","Phone Camera"]); m=self.manual(w,camera_key="Phone Camera"); pump(m,w); self.assertEqual((m.status.state,m.status.name),(CamState.ACTIVE,"Phone Camera")); w.names.insert(0,"New USB Cam"); m.select("Phone Camera"); pump(m,w); self.assertEqual(m.status.name,"Phone Camera"); self.assertEqual(w.caps[-1].name,"Phone Camera")
    def test_first_run_uses_first_camera(self):
        w=World(["Integrated Camera","USB Camera"]); m=self.manual(w); pump(m,w); self.assertEqual(m.status.name,"Integrated Camera"); self.assertIsNotNone(m.read_latest())
    def test_switch_releases_old_and_resumes(self):
        w=World(["Integrated Camera","USB Camera"]); m=self.manual(w); pump(m,w); first=w.caps[0]; m.select("USB Camera"); self.assertEqual(m.status.state,CamState.OPENING); pump(m,w,2); self.assertTrue(first.released); self.assertEqual((m.status.state,m.status.name),(CamState.ACTIVE,"USB Camera")); seq=m.read_latest()[1]; pump(m,w); self.assertGreater(m.read_latest()[1],seq)
    def test_startup_falls_back_and_reports_it(self):
        w=World(["Integrated Camera"]); m=self.manual(w,camera_key="Phone Camera"); pump(m,w); s=m.status; self.assertEqual((s.state,s.name,s.fallback_from),(CamState.ACTIVE,"Integrated Camera","Phone Camera")); self.assertIn("unavailable",s.message)
    def test_explicit_select_of_unavailable_camera_errors_without_fallback(self):
        w=World(["Integrated Camera","USB Camera"]); m=self.manual(w); pump(m,w); w.broken["USB Camera"]="busy"; m.select("USB Camera"); pump(m,w,2); self.assertEqual(m.status.state,CamState.ERROR); self.assertIn("USB Camera",m.status.message); self.assertIsNone(m.read_latest())
    def test_camera_in_use_and_no_frames_are_reported(self):
        w=World(["USB Camera"]); w.broken["USB Camera"]="noframes"; m=self.manual(w,camera_key="USB Camera"); m._startup=False; pump(m,w); self.assertEqual(m.status.state,CamState.ERROR); self.assertIn("no frames",m.status.message)
    def test_no_cameras(self):
        w=World([]); m=self.manual(w); pump(m,w); self.assertEqual(m.status.state,CamState.ERROR); self.assertIn("No cameras",m.status.message)
    def test_disconnect_then_reconnect_same_device(self):
        w=World(["Integrated Camera","Phone Camera"]); m=self.manual(w,camera_key="Phone Camera"); m._startup=False; pump(m,w); phone=w.caps[-1]; phone.frames=False; pump(m,w,CameraManager.READ_FAIL_LIMIT+1); self.assertEqual(m.status.state,CamState.RECONNECTING); self.assertTrue(phone.released); self.assertIsNone(m.read_latest()); w.clock[0]+=1.0; pump(m,w,2); self.assertEqual((m.status.state,m.status.name),(CamState.ACTIVE,"Phone Camera"))
    def test_long_disconnect_falls_back_to_other_camera(self):
        w=World(["Integrated Camera","Phone Camera"]); m=self.manual(w,camera_key="Phone Camera"); m._startup=False; pump(m,w); w.caps[-1].frames=False; pump(m,w,CameraManager.READ_FAIL_LIMIT+1); w.names.remove("Phone Camera")
        for _ in range(12): w.clock[0]+=1.0; pump(m,w)
        s=m.status; self.assertEqual((s.state,s.name),(CamState.ACTIVE,"Integrated Camera")); self.assertEqual(s.fallback_from,"Phone Camera")
    def test_stop_releases_camera(self):
        w=World(["Integrated Camera"]); m=self.manual(w); pump(m,w); m.stop(); self.assertTrue(w.caps[0].released); self.assertEqual(m.status.state,CamState.CLOSED); self.assertIsNone(m.read_latest())
if __name__=="__main__": unittest.main()
