"""Eye-gesture state machine (time-injected, no I/O) and its mouse dispatcher.

States: BOTH_OPEN, BOTH_CLOSED, LEFT_ONLY_CLOSED, RIGHT_ONLY_CLOSED, LEFT_HOLD,
RIGHT_HOLD, plus LOCKOUT and DISABLED.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .config import Config

log = logging.getLogger(__name__)


class State:
    DISABLED = "DISABLED"; BOTH_OPEN = "BOTH_OPEN"; BOTH_CLOSED = "BOTH_CLOSED"
    LEFT_ONLY_CLOSED = "LEFT_ONLY_CLOSED"; RIGHT_ONLY_CLOSED = "RIGHT_ONLY_CLOSED"
    LEFT_HOLD = "LEFT_HOLD"; RIGHT_HOLD = "RIGHT_HOLD"; LOCKOUT = "LOCKOUT"

LEFT_CLICK, RIGHT_CLICK = "left_click", "right_click"
LEFT_DOWN, LEFT_UP = "left_down", "left_up"; RIGHT_DOWN, RIGHT_UP = "right_down", "right_up"
_PENDING = {"left": State.LEFT_ONLY_CLOSED, "right": State.RIGHT_ONLY_CLOSED}
_HOLD = {"left": State.LEFT_HOLD, "right": State.RIGHT_HOLD}; _CLICK = {"left": LEFT_CLICK, "right": RIGHT_CLICK}
_DOWN = {"left": LEFT_DOWN, "right": RIGHT_DOWN}; _UP = {"left": LEFT_UP, "right": RIGHT_UP}
_OTHER = {"left": "right", "right": "left"}; _MOVE_STATES = (State.BOTH_OPEN, State.LEFT_HOLD, State.RIGHT_HOLD)


@dataclass
class GestureOutput:
    events: List[str] = field(default_factory=list); state: str = State.BOTH_OPEN; allow_move: bool = True
    gesture: str = "None"; left_held: bool = False; right_held: bool = False


class GestureStateMachine:
    GESTURE_DISPLAY_S = 1.5
    def __init__(self, cfg: Config):
        self.cfg=cfg; self.enabled=True; self.state=State.BOTH_OPEN; self.held={"left":False,"right":False}
        self.last_gesture="None"; self.last_gesture_t=-1e9; self._eye:Optional[str]=None; self._start=0.0
        self._release_t=None; self._hold_open_since=None; self._open_since=None; self._cooldown_until=-1e9; self._lost_since=None
    def _note(self,t,text): self.last_gesture,self.last_gesture_t=text,t
    def _enter_lockout(self,t,cooldown_s=0.0):
        self.state=State.LOCKOUT; self._cooldown_until=max(self._cooldown_until,t+cooldown_s); self._open_since=None; self._release_t=None
    def _release_all_held(self,t,note):
        events=[]
        for eye in ("left","right"):
            if self.held[eye]: events.append(_UP[eye]); self.held[eye]=False
        self._enter_lockout(t,self.cfg.cooldown_ms/1000.0)
        if events: self._note(t,note)
        return events
    def _out(self,events,t):
        if self.state==State.LEFT_HOLD: label="Left hold (drag)"
        elif self.state==State.RIGHT_HOLD: label="Right hold (drag)"
        elif t-self.last_gesture_t<self.GESTURE_DISPLAY_S: label=self.last_gesture
        else: label="None"
        return GestureOutput(events,self.state,self.state in _MOVE_STATES,label,self.held["left"],self.held["right"])
    def disable(self):
        events=[]
        for eye in ("left","right"):
            if self.held[eye]: events.append(_UP[eye]); self.held[eye]=False
        self.enabled=False; self.state=State.DISABLED; return events
    def enable(self):
        if not self.enabled or self.state==State.DISABLED:
            self.enabled=True; self.state=State.LOCKOUT; self._open_since=None; self._cooldown_until=-1e9; self._lost_since=None
    def abort(self,t):
        if not self.enabled: return []
        events=self._release_all_held(t,"Aborted - released"); self._enter_lockout(t,self.cfg.cooldown_ms/1000.0); return events
    def update(self,t,face_ok,left_closed,right_closed,left_ratio=None,right_ratio=None,pose_ok=True):
        cfg,ev=self.cfg,[]
        if not self.enabled: self.state=State.DISABLED; return self._out(ev,t)
        if self.state==State.DISABLED: self.enable()
        holding=self.state in (State.LEFT_HOLD,State.RIGHT_HOLD)
        if not face_ok:
            if self._lost_since is None: self._lost_since=t
            if holding:
                if t-self._lost_since>=cfg.face_loss_release_ms/1000.0: ev+=self._release_all_held(t,"Face lost - released")
            elif self.state==State.LOCKOUT: self._open_since=None
            else: self._enter_lockout(t)
            return self._out(ev,t)
        self._lost_since=None
        if not pose_ok and not holding:
            if self.state==State.LOCKOUT: self._open_since=None
            else: self._enter_lockout(t)
            return self._out(ev,t)
        closed={"left":left_closed,"right":right_closed}; ratio={"left":left_ratio,"right":right_ratio}; state=self.state
        if state==State.LOCKOUT:
            if not left_closed and not right_closed:
                if self._open_since is None: self._open_since=t
                if t>=self._cooldown_until and t-self._open_since>=cfg.reopen_ms/1000.0: self.state=State.BOTH_OPEN
            else: self._open_since=None
        elif state==State.BOTH_OPEN:
            if left_closed and right_closed: self.state=State.BOTH_CLOSED; self._note(t,"Blink ignored")
            elif left_closed or right_closed:
                eye="left" if left_closed else "right"; self.state,self._eye=_PENDING[eye],eye; self._start,self._release_t=t,None
        elif state==State.BOTH_CLOSED:
            if not left_closed and not right_closed: self.state=State.BOTH_OPEN
        elif state in (State.LEFT_ONLY_CLOSED,State.RIGHT_ONLY_CLOSED): ev+=self._update_pending(t,closed,ratio)
        elif holding:
            eye="left" if state==State.LEFT_HOLD else "right"
            if closed[eye]: self._hold_open_since=None
            else:
                if self._hold_open_since is None: self._hold_open_since=t
                if t-self._hold_open_since>=cfg.release_debounce_ms/1000.0:
                    self.held[eye]=False; ev.append(_UP[eye]); self._note(t,f"{eye.title()} released"); self._enter_lockout(t,cfg.cooldown_ms/1000.0)
        return self._out(ev,t)
    def _update_pending(self,t,closed,ratio):
        cfg,eye=self.cfg,self._eye; other=_OTHER[eye]
        if closed[other]: self.state=State.BOTH_CLOSED; self._note(t,"Blink ignored"); return []
        if ratio[other] is not None and ratio[other]<cfg.other_eye_min_ratio: self._enter_lockout(t); self._note(t,"Squint ignored"); return []
        if closed[eye]:
            self._release_t=None
            if t-self._start>=cfg.hold_ms/1000.0:
                if eye=="right" and not cfg.enable_right_hold: self._enter_lockout(t); return []
                self.held[eye]=True; self.state=_HOLD[eye]; self._hold_open_since=None; self._note(t,f"{eye.title()} hold (drag)"); return [_DOWN[eye]]
            return []
        if self._release_t is None: self._release_t=t
        if t-self._release_t<cfg.click_confirm_ms/1000.0: return []
        duration=self._release_t-self._start
        if cfg.min_click_ms/1000.0<=duration<=cfg.max_click_ms/1000.0:
            self._note(t,f"{eye.title()} click"); self._enter_lockout(t,cfg.cooldown_ms/1000.0); return [_CLICK[eye]]
        self.state=State.BOTH_OPEN; self._note(t,"Closure ignored (too short/long)"); return []


class GestureController:
    def __init__(self,cfg,mouse): self.cfg=cfg; self.mouse=mouse; self.machine=GestureStateMachine(cfg)
    @property
    def enabled(self): return self.machine.enabled
    def update(self,t,face_ok,left_closed,right_closed,left_ratio=None,right_ratio=None,pose_ok=True):
        out=self.machine.update(t,face_ok,left_closed,right_closed,left_ratio,right_ratio,pose_ok); self._dispatch(out.events)
        for button in ("left","right"):
            if self.mouse.is_held(button) and not self.machine.held[button]: self.mouse.release(button)
        return out
    def _dispatch(self,events):
        for event in events:
            try:
                if event==LEFT_CLICK: self.mouse.click("left")
                elif event==RIGHT_CLICK: self.mouse.click("right")
                elif event==LEFT_DOWN: self.mouse.press("left")
                elif event==LEFT_UP: self.mouse.release("left")
                elif event==RIGHT_DOWN: self.mouse.press("right")
                elif event==RIGHT_UP: self.mouse.release("right")
            except Exception:
                log.exception("Mouse dispatch failed for %s",event); self.mouse.release_all(force=True)
    def set_enabled(self,enabled):
        if enabled: self.machine.enable()
        else: self._dispatch(self.machine.disable()); self.mouse.release_all()
    def abort(self,t): self._dispatch(self.machine.abort(t)); self.mouse.release_all()
    def emergency_stop(self): self.machine.disable(); self.mouse.emergency_release()
