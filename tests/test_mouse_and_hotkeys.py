import ctypes
import unittest
from facemouse.hotkeys import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey
from facemouse.mouse_controller import MemoryBackend, MouseController, _INPUT
class MouseControllerTests(unittest.TestCase):
    def setUp(self): self.b=MemoryBackend(1000,800); self.m=MouseController(self.b)
    def test_press_release_tracks_state_once(self):
        self.assertTrue(self.m.press("left")); self.assertFalse(self.m.press("left")); self.assertTrue(self.m.is_held("left")); self.m.release("left"); self.m.release("left"); self.assertEqual(self.b.events(),[("down","left"),("up","left")])
    def test_click_is_down_up_and_not_held(self): self.m.click("right"); self.assertEqual(self.b.events(),[("down","right"),("up","right")]); self.assertFalse(self.m.any_held)
    def test_release_all_and_force(self):
        self.m.press("left"); self.m.press("right"); self.m.release_all(); self.assertFalse(self.m.any_held); self.assertEqual(self.b.events()[-2:],[("up","left"),("up","right")]); n=len(self.b.events()); self.m.release_all(force=True); self.assertEqual(len(self.b.events()),n+2)
    def test_release_retries_after_backend_failure(self):
        self.m.press("left"); self.b.fail_release=1; self.m.release("left"); self.assertFalse(self.m.is_held("left")); self.assertEqual(self.b.events()[-1],("up","left"))
    def test_release_all_survives_persistent_failure(self):
        self.m.press("left"); self.b.fail_release=5; self.m.release_all(); self.assertFalse(self.m.any_held)
    def test_emergency_release_inhibits_everything(self):
        self.m.press("left"); self.m.emergency_release(); self.assertFalse(self.m.any_held); self.assertFalse(self.m.press("left")); self.assertFalse(self.m.click("left")); start=self.b.pos; self.m.move_by(50,50); self.assertEqual(self.b.pos,start); self.m.inhibit(False); self.assertTrue(self.m.press("left"))
    def test_move_subpixel_accumulation_and_clamp(self):
        x0,y0=self.b.pos
        for _ in range(10): self.m.move_by(0.3,0)
        self.assertEqual(self.b.pos[0],x0+3); self.m.move_by(-5000,5000); self.assertEqual(self.b.pos,(0,799))
    def test_resync_when_user_moves_real_mouse(self):
        self.m.move_by(10,0); self.b.pos=(100,100); self.m.move_by(5,0); self.assertEqual(self.b.pos,(105,100))
    def test_input_struct_matches_win64_layout(self):
        if ctypes.sizeof(ctypes.c_void_p)==8: self.assertEqual(ctypes.sizeof(_INPUT),40)
class HotkeyParseTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_hotkey("ctrl+alt+f12"),(MOD_CONTROL|MOD_ALT,0x7B)); self.assertEqual(parse_hotkey("Ctrl + Shift + Q"),(MOD_CONTROL|MOD_SHIFT,ord("Q"))); self.assertEqual(parse_hotkey("ctrl+alt+esc")[1],0x1B)
    def test_invalid(self):
        for bad in ("","ctrl+","ctrl+alt+nope","hyper+f1","q"):
            with self.assertRaises(ValueError,msg=bad): parse_hotkey(bad)
if __name__=="__main__": unittest.main()
