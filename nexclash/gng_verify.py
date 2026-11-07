"""Ghosts 'n Goblins verifier extensions (from the .nxc work's movement01/verify_smooth.py and ground01/verify.py, as
the published 1.6 was proved): the Copper commit of the full positions and the intermediate (half-step) positions
checked against independently tracked original object positions, and the carried item clipped at its zombie's
exposed body. install() puts them in place for gng.verify; it is idempotent."""
import collections
from . import gng as G, rzx as Z
original_trace=Z.trace
ACTIVE=None
def ACTIVE_ENGINE():return ACTIVE
BaseEngine=G.Engine;BaseNext=G.NextState;
class CopperNext(BaseNext):
 def __init__(self):
  super().__init__();self.cp=bytearray(2048);self.cpaddr=0;self.mode=0
 def nextreg(self,reg,val):
  if reg==0x60:self.cp[self.cpaddr]=val;self.cpaddr=(self.cpaddr+1)&2047
  elif reg==0x61:self.cpaddr=(self.cpaddr&0x700)|val
  elif reg==0x62:self.cpaddr=(self.cpaddr&255)|((val&7)<<8);self.mode=val>>6
  else:return super().nextreg(reg,val)
  self.nr[reg]=val

class SmoothEngine(BaseEngine):
 def __init__(self,patch):
  global ACTIVE
  super().__init__(patch);self.ns=CopperNext();self.obj=0;self.history={};self.tick=0;self.camera=None;self.scroll=True;self.expected={};self.audit=collections.Counter();ACTIVE=self
 def object_store(self,get,r):
  obj=(r[6]<<8|r[7])+1;self.obj=(obj&0xff00)|((obj)&255)
  rr,ov,t,done,romw=super().hook(get,r,self.patch.syms['e_object'],35899)
  expected=list(r);expected[24]=35899;expected[15]=(r[15]&128)|((r[15]+1)&127)
  assert done and not romw and ov=={49028:r[0]},('object overlay',done,romw,ov)
  assert all(rr[i]==expected[i] for i in G.CMP),('object registers',[(i,expected[i],rr[i]) for i in G.CMP if rr[i]!=expected[i]])
  self.audit['object hooks']+=1
 def offset(self,get):
  obj=self.obj
  if obj>>8!=0xdf or obj&15!=2 or obj&255<18:return (0,0)
  typ=get(obj+1);x=(get(obj+4)*4+get(obj+3))&255;y=get(obj+5)
  old=self.history.get(obj);dx=dy=0
  if old and old['type']==typ:
   if old['tick']==self.tick:return old['delta']
   if old['tick']==(self.tick-1)&255 and not self.scroll:
    def limited(a,b):
     v=((a-b+128)&255)-128;return v if -8<=v<=8 else 0
    dx,dy=limited(old['x'],x),limited(old['y'],y)
  self.history[obj]={'type':typ,'x':x,'y':y,'tick':self.tick,'delta':(dx,dy)}
  return dx,dy
 def hook(self,get,regs,start,stop,sp=None):
  s=self.patch.syms;plot=start in [s['e_m3'],s['e_o3'],s['e_x2']];reset=start in [s['e_cls'],s['e_cls2'],s['e_init']]
  n0=self.page[s['nsp']-0x2000]
  if reset:
   self.history.clear();self.obj=0;self.expected.clear()
  if plot:
   if n0==0:
    cam=get(49026)+256*get(49027);self.scroll=cam!=self.camera;self.camera=cam;self.expected.clear()
   dx,dy=self.offset(get)
  rr,ov,t,done,romw=super().hook(get,regs,start,stop,sp)
  if plot:
   actual=(self.page[s['sm_dx']-0x2000],self.page[s['sm_dy']-0x2000]);assert actual==(dx&255,dy&255),('offset',self.obj,self.tick,actual,(dx,dy))
   n1=self.page[s['nsp']-0x2000]
   # Only undo the independently predicted midpoint displacement. The original
   # checker then validates the full coordinates and every original ink pixel.
   for n in range(n0,n1):
    a=self.ns.attr[n];half_x=a[0]|((a[2]&1)<<8);half_y=a[1]
    full_x=(half_x-dx)&511;full_y=(half_y-dy)&255
    self.expected[n]=(full_x,full_y)
    a[0]=full_x&255;a[1]=full_y;a[2]=(a[2]&254)|(full_x>>8)
   self.audit['plots']+=1
   if dx or dy:self.audit['interpolated plots']+=1
   if self.scroll:self.audit['camera snap plots']+=1
  if start==s['e_tick']:
   if n0:
    assert self.ns.mode==1 and self.ns.cp[:2]==b'\x80\x00','copper mode/wait'
    got={};slot=None;halt=False
    for i in range(2,2048,2):
     reg,val=self.ns.cp[i:i+2]
     if (reg,val)==(255,255):halt=True;break
     assert reg in (0x34,0x35,0x36,0x37),('unexpected copper reg',reg)
     if reg==0x34:slot=val;assert slot not in got;got[slot]={}
     else:assert slot is not None;got[slot][reg]=val
    assert halt and set(got)==set(range(n0)),('copper slots',n0,got)
    for slot,v in got.items():
     assert set(v)=={0x35,0x36,0x37}
     assert (v[0x35]|((v[0x37]&1)<<8),v[0x36])==self.expected[slot],('copper full position',slot,v,self.expected[slot])
    self.audit['copper commits']+=1
   else:assert self.ns.mode==0
   self.history={k:v for k,v in self.history.items() if v['tick']==self.tick}
   self.obj=0;self.tick=(self.tick+1)&255
  return rr,ov,t,done,romw

def trace(path,pcs,cb,**kw):
 if not {G.CLS,G.INIT}.issubset(pcs):return original_trace(path,pcs,cb,**kw)
 def wrapped(pc,sim):
  if pc==35896:ACTIVE.object_store(sim.memory.__getitem__,list(sim.registers))
  else:cb(pc,sim)
 return original_trace(path,set(pcs)|{35896},wrapped,**kw)

def relation(get,obj):
 if not (0xdf12<=obj<=0xdff2 and obj&15==2):return None
 if get(obj+1)==76:return ('body',obj)
 if get(obj+1)!=62 or get(obj+9)&8:return None
 ptr=get(obj+2)
 if ptr&15!=5 or ptr<21:return None
 parent=0xdf00|(ptr-3)
 if get(parent+1)!=76:return None
 return ('item',parent)

def clip(get,obj,y,rows):
 rel=relation(get,obj)
 if not rel or rel[0]!='item':return rows
 floor=2*(get(rel[1]+5)+get(rel[1]+11))
 return max(0,min(rows,(floor-y)//2))

def cropped(pixels,rows):
 if pixels is None:return None
 out=bytearray(pixels)
 for tile in range(4):
  for y in range(16):
   if (tile//2)*16+y>=2*rows:out[tile*128+y*8:tile*128+y*8+8]=bytes(8)
 return bytes(out)

class Oracle:
 def __init__(self,base):self.base=base
 def expected(self,kind,g,rows,get):
  want=self.base.expected(kind,g,rows,get);e=ACTIVE_ENGINE()
  if kind=='m3' and e.context is not None:want=cropped(want,e.context['keep'])
  return want

class Engine(SmoothEngine):
 def __init__(self,p):super().__init__(p);self.context=None;self.ground_counts=collections.Counter()
 def offset(self,get):
  dx,dy=super().offset(get)
  return (dx,0) if relation(get,self.obj) else (dx,dy)
 def hook(self,get,r,start,stop,sp=None):
  self.context=None;s=self.patch.syms;n0=self.page[s['nsp']-0x2000]
  if start==s['e_m3']:
   a=r[6]*256+r[7];y,x=G.scr_yx(a);rows=r[2]+4*(r[19]-1)+r[18];rel=relation(get,self.obj);keep=clip(get,self.obj,y,rows)
   self.context={'keep':keep,'rows':rows,'x':(x-2)*8,'y':y,'relation':rel,'n0':n0}
  result=super().hook(get,r,start,stop,sp)
  if self.context:
   ctx=self.context;n1=self.page[s['nsp']-0x2000];keep=ctx['keep']
   if ctx['relation'] and ctx['relation'][0]=='item':
    # Check even invisible slots' positions, rather than deriving their expected
    # Copper coordinates solely from what the hook happened to write.
    ncols=2;nrows=1 if max(keep,1)<=8 else 2
    assert n1-n0==ncols*nrows,('item tile count',ctx,n1)
    for k in range(n1-n0):
     a=self.ns.attr[n0+k];x=a[0]|((a[2]&1)<<8);y=a[1]
     assert (x,y)==((ctx['x']+32+(k%2)*16)&511,(ctx['y']+32+(k//2)*16)&255),('hidden/full item position',ctx,(x,y))
     assert bool(a[3]&128)==bool(keep),('item visibility',ctx,a)
    label='hidden' if not keep else 'partial' if keep<ctx['rows'] else 'full'
    self.ground_counts[label]+=1
   elif self.obj and get(self.obj+1) in (62,64):self.ground_counts['unclipped other/released item']+=1
  return result

def check(eng,slots,get,kind,g,rows,x,y,painted=None):
 keep=clip(get,eng.obj,y,rows) if kind=='m3' else rows
 if keep==0:return None if not slots else ('underground item visible',slots)
 return original_check(eng,slots,get,kind,g,keep,x,y,painted)

original_check=G.check_plot
import contextlib
@contextlib.contextmanager
def installed():
 saved=(G.Engine,G.check_plot,Z.trace)
 G.Engine=Engine;G.check_plot=check;Z.trace=trace
 try:yield
 finally:G.Engine,G.check_plot,Z.trace=saved
def oracle(patch):
 if not isinstance(patch.art_expected,Oracle):patch.art_expected=Oracle(patch.art_expected)
 return patch
