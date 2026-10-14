from facemouse.config import Config
from facemouse.face_tracker import FaceResult
FPS=30

def run(machine,segs,t0=0.0):
    t,events,states,out=t0,[],[],None
    for seg in segs:
        dur,l,r=seg[:3]; ex=seg[3] if len(seg)>3 else {}
        for _ in range(max(1,round(dur*FPS))):
            out=machine.update(t,ex.get("face_ok",True),l,r,ex.get("lr"),ex.get("rr"),ex.get("pose_ok",True)); events += [(t,e) for e in out.events]
            if not states or states[-1]!=out.state: states.append(out.state)
            t += 1.0/FPS
    return events,states,t,out

def names(events): return [e for _,e in events]
def face(left_ear=0.27,right_ear=0.27,nose=(320.0,240.0),found=True,yaw=0.0,iod=60.0):
    return FaceResult(found=found,left_ear=left_ear,right_ear=right_ear,nose_x=nose[0],nose_y=nose[1],iod=iod,yaw=yaw,frame_w=640,frame_h=480)
def cfg(**kw):
    c=Config()
    for k,v in kw.items(): setattr(c,k,v)
    return c.validate()
