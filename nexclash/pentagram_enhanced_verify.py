"""Pentagram Enhanced: persistent hardware model and independent original-pixel oracle.
Timing is proven separately in the native emulator; this model proves functional behaviour.
"""
import collections,copy,hashlib
from .hooklib import CMP_R
from . import pentagram_colour as PC
from . import z80n,nextboot,rzx
from .dizzy6 import _rw_simulator
from .dma import DMA
import numpy as np
class Live:
 def __init__(self,p,mem,regs,speed=0):
  self.patch=p;self.pages={}
  for b,d in p.extra_banks.items():self.pages[b*2]=bytearray(d[:8192]);self.pages[b*2+1]=bytearray(d[8192:])
  self.rom=nextboot.alt_image(p);self.maps=[255,255,10,11,4,5,0,1]
  self.nr={7:speed,1:0x33,0xc0:0,0x12:29,0x15:0,0x64:0};self.sel=0;self.line=0;self.input_values=[];self.outputs=[];self.uploads=0
  self.sim=_rw_simulator()(list(mem),config={'int_active':0});self.mem=self.sim.memory;self.mem[:16384]=list(self.rom)
  self.patterns=bytearray(16384);self.attrs=bytearray(640);self.psel=0;self.asel=0;self.apos=0
  self.dma=DMA(self.mem.__getitem__,self.mem.__setitem__,lambda port,v:self.write_port(self.sim.registers,port,v))
  z80n.install(self.sim,self.nextreg,strict=False);self.sim.set_tracer(self);self.reset_game(mem,regs)
 def flush(self):
  for sl,pg in enumerate(self.maps):
   if pg!=255:self.pages.setdefault(pg,bytearray(8192))[:]=bytes(self.mem[sl*8192:(sl+1)*8192])
 def reset_game(self,mem,regs):
  assert self.maps==[255,255,10,11,4,5,0,1],self.maps
  self.flush();self.mem[16384:]=list(mem[16384:]);self.sim.registers[:]=regs
  for sl,pg in enumerate(self.maps[2:],2):self.pages[pg]=bytearray(mem[sl*8192:(sl+1)*8192])
  for a,o,n in self.patch.sites:self.mem[a:a+len(n)]=n
 def nextreg(self,reg,val):
  self.nr[reg]=val
  if 0x50<=reg<=0x57:
   sl=reg-0x50;at=sl*8192;old=self.maps[sl]
   if old!=255:self.pages[old][:]=bytes(self.mem[at:at+8192])
   self.maps[sl]=val;self.mem[at:at+8192]=list(self.rom[at:at+8192]if val==255 else self.pages.setdefault(val,bytearray(8192)))
  elif reg==0x34:self.asel=val&127;self.apos=0
  elif 0x35<=reg<=0x39:self.attrs[self.asel*5+reg-0x35]=val
  elif reg==0x78:self.attrs[self.asel*5+3]=val;self.asel=(self.asel+1)&127
 def read_port(self,r,port):
  if port==0x253b:
   if 0x50<=self.sel<=0x57:return self.maps[self.sel-0x50]
   if self.sel==7:return self.nr[7]&3|((self.nr[7]&3)<<4)
   if self.sel==0x1e:return self.line>>8
   if self.sel==0x1f:
    v=self.line&255;self.line=(self.line+1)%312;return v
   return self.nr.get(self.sel,0)
  if self.input_values:
   expected,v=self.input_values.pop(0);assert expected==port,('input port',hex(expected),hex(port));return v
  raise AssertionError(('unexpected input',hex(port)))
 def write_port(self,r,port,v,*unused):
  if port==0x243b:self.sel=v
  elif port==0x253b:self.nextreg(self.sel,v)
  elif port&255==0x6b:self.dma.feed(v)
  elif port==0x303b:self.psel=(v&63)*256;self.asel=v&127;self.apos=0
  elif port&255==0x5b:
   if self.nr.get(0x15,0)&1:
    live={self.attrs[i*5+3]&63 for i in range(128)if self.attrs[i*5+3]&128}
    assert self.psel//256 not in live or self.patterns[self.psel]==v,('live pattern overwrite',self.psel,v)
   self.patterns[self.psel&16383]=v;self.psel=(self.psel+1)&16383;self.uploads+=1
  elif port&255==0x57:
   self.attrs[self.asel*5+self.apos]=v;self.apos+=1
   if self.apos==5 or(self.apos==4 and not(v&64)):self.apos=0;self.asel=(self.asel+1)&127
  else:self.outputs.append((port,v,self.nr[7]))
 def runto(self,target,limit=5000000,watch=None):
  r=self.sim.registers;n=0;self.min_sp=r[12]
  while n==0 or r[24]!=target:
   if watch:watch(r[24],self)
   self.sim.opcodes[self.mem[r[24]]]();self.min_sp=min(self.min_sp,r[12]);n+=1
   if n>=limit:raise AssertionError(('limit',hex(r[24]),hex(target)))
  return n
 def call(self,name):
  r=self.sim.registers;r[24]=self.patch.syms[name];r[12]=0x5DFA;self.mem[0x5DFA:0x5DFC]=[0xF0,0x1F];self.nextreg(0x51,26);return self.runto(0x1FF0)
 def canvas(self,base=52):
  self.flush();return np.frombuffer(b''.join(self.pages.setdefault(p,bytearray(8192))for p in range(base,base+6)),dtype=np.uint8).reshape(192,256)
 def state(self,key):
  self.flush();return self.pages[26][self.patch.syms[key]&8191]
 def displayed(self):
  screen=self.canvas(self.nr[0x12]*2).copy()if self.nr.get(0x69,0)&128 else np.full((192,256),255,dtype=np.uint8)
  if self.nr.get(0x15,0)&1:
   for i in range(128):
    x,y,fl,pt,ex=self.attrs[i*5:i*5+5]
    if not pt&128:continue
    assert not(ex&128),('not8bpp',i,ex)
    x=(x|((fl&1)<<8))-32;y-=32;tile=np.frombuffer(self.patterns[(pt&63)*256:(pt&63)*256+256],dtype=np.uint8).reshape(16,16)
    x0=max(0,x);x1=min(256,x+16);y0=max(0,y);y1=min(192,y+16)
    if x1>x0 and y1>y0:
     t=tile[y0-y:y1-y,x0-x:x1-x];dst=screen[y0:y1,x0:x1];mask=t!=255;dst[mask]=t[mask]
  screen[screen==254]=255;return screen

class Oracle:
 def __init__(self,patch):
  meta=PC.art_profile();self.byaddr={r['addr']:r for r in meta['graphics']};self.colours=patch.colours;self.static=set(meta['static_ids']);self.fills={(q['key'],q['bit'])for q in meta['approved_interior_fills']}
  self.canvas=np.full((192,256),255,dtype=np.uint8)
 def plot(self,mem,ix,ptr):
  canvas=self.canvas;gid=mem[ix];x,y=mem[ix+26:ix+28];rec=self.byaddr[ptr];w,h=rec['width'],rec['height'];rel=(mem[ptr]^rec['flags'])&192;tag=128 if not 42863<=ix<44591 or gid in self.static else 0
  for dy in range(h):
   if y+dy>=192:break
   for dx in range(w):
    off=(y+dy)*256+x+dx
    if off>=49152:continue
    cx=w-1-dx if rel&64 else dx;cy=dy if rel&128 else h-1-dy;key=f'{ptr:04x}:{cy:02x}:{cx//8}';entry=self.colours.get(key);idx=entry[2][cx&7]if entry else 0
    a=ptr+2+(dy*(w//8)+dx//8)*2;bit=128>>(dx&7);mask=mem[a]&bit;ink=mem[a+1]&bit
    if not(mask or ink):
     if not idx:continue
     assert(key,cx&7)in self.fills,('unapproved opacity',key,cx&7)
    else:
     idx=idx or(2 if ink else 1)
     if x&7 and ink and not mask and mem[0xD88F+off//8]&(128>>(off&7)):idx=1
    canvas[191-off//256,off%256]=idx|tag
 def clear(self,x,y,w,h):
  for dy in range(h):
   for b in range(w):
    off=(y+dy)*32+x//8+b
    if 0<=off<6144:self.canvas[191-off//32,(off%32)*8:(off%32)*8+8]=255

SITES={0xB5A3:0xB5A7,0xAFDA:0xAFDD,0xAFCB:0xAFCE,0xB03B:0xB03E,0xB3EA:0xB3ED,0xB075:0xB078,0xC344:0xC347,0xB242:0xB245,0xCB81:0xCB84,0xCB5F:0xCB62,0xB952:0xB954}

def verify(p,rzx_path,stop=None,collect=0,progress=None):
 counts=collections.Counter();dead=collections.Counter();states=collections.defaultdict(list);pending=None;q=None;events=[];oracle=Oracle(p);canvas=oracle.canvas;patch={a+i:v for a,o,n in p.sites for i,v in enumerate(n)};source_sim=None;examples={};iff=collections.Counter()
 sites=dict(SITES);sound=getattr(p,'sound_sites',{});sites.update({a:(a+3 if op==205 else 0xB00C)for a,(target,op)in sound.items()});watched=set(sites)|set(sites.values());interiors={a+i for a,o,n in p.sites for i in range(1,len(o))}
 # Gather only real recorded sound I/O, so keyboard-interruptible tunes never
 # invent input values. Every original port and value is checked on consumption.
 sound_events=[];pre=None
 def pre_at(pc,sim):
  nonlocal pre
  if pre and pc==pre['target']:pre=None
  if pre and pc==0xB954:
   tr=sim.tracer;pre['inputs'].append(((sim.registers[0]<<8)|254,tr.data[tr.index]))
  if pre and pc in(0xD684,0xD68B,0xD6E8,0xD6F3):pre['outputs'].append(((sim.registers[0]<<8)|254,sim.registers[0]))
  if pc in sound:
   assert pre is None,('nested sound prepass',pc,pre)
   target=pc+3 if sound[pc][1]==205 else sim.memory[sim.registers[12]]+256*sim.memory[sim.registers[12]+1]
   pre={'site':pc,'target':target,'inputs':[],'outputs':[]};sound_events.append(pre)
 npre,epre=rzx.trace(str(rzx_path),range(65536),pre_at,stop=stop)
 if epre:
  counts['sound prepass!']+=1;examples['failure']=epre
  return(counts,examples,states)if collect else(counts,examples)
 sound_cursor=0
 watched.update(e['target']for e in sound_events)
 def compare(s,regs,mem,low,site,live_return=None):
  diff=[(i,s.registers[i],regs[i])for i in CMP_R+[24]if s.registers[i]!=regs[i]];assert not diff,('register',hex(site),diff)
  want=bytearray(s.memory[16384:]);got=bytes(mem[16384:])
  for addr,v in patch.items():want[addr-16384]=v
  if live_return:
   addr,value,original=live_return;assert bytes(s.memory[addr:addr+2])==original and bytes(mem[addr:addr+2])==value,('live return',hex(site),addr,list(s.memory[addr:addr+2]),list(mem[addr:addr+2]));want[addr-16384:addr-16384+2]=value
  lo=max(low,0x5D00);hi=min(s.registers[12],0x5E00)
  for addr in range(lo,hi):
   if want[addr-16384]!=got[addr-16384]:dead[addr]+=1
  if lo<hi:want[lo-16384:hi-16384]=got[lo-16384:hi-16384]
  assert want==got,('RAM',hex(site),[(i+16384,x,y)for i,(x,y)in enumerate(zip(want,got))if x!=y][:15])
 def at(pc,s):
  nonlocal pending,q,events,source_sim,sound_cursor
  source_sim=s;assert pc not in interiors,('interior',pc)
  if pending and pc==pending['target']:
   assert not events,('leftover',len(events));compare(s,list(q.sim.registers),q.mem,q.min_sp,pending['site']);assert q.nr[7]==pending['clock'] and q.maps==[255,255,10,11,4,5,0,1],('exit state',q.nr[7],q.maps);assert not q.input_values,('unused inputs',q.input_values);assert q.outputs==pending['outputs'],('outputs',q.outputs[:8],pending['outputs'][:8]);bad=np.argwhere(q.canvas()!=canvas);assert not len(bad),('canvas',hex(pending['site']),bad[:8].tolist())
   counts['completed '+hex(pending['site'])]+=1
   if pending['site']in(0xB03B,0xB075,0xC344):
    want=canvas.copy();want[want!=255]&=127;got=q.displayed();got[got!=255]&=127;bad=np.argwhere(got!=want);assert not len(bad),('display',hex(pending['site']),bad[:8].tolist());counts['publication pictures']+=1
   pending=None
  elif pending and pc in watched:
   assert events,('missing nested',hex(pc));ep,er,em,low=events.pop(0);assert ep==pc,('eventorder',hex(ep),hex(pc));rt=None
   if pending['site']in(0xAFCB,0xB03B,0xB075,0xC344):
    sym={0xAFCB:'h_room_init_after',0xB03B:'h_render_after',0xB075:'h_copy_room_after',0xC344:'h_copy_menu_after'}[pending['site']];rt=(pending['sp']-2,p.syms[sym].to_bytes(2,'little'),pending['target'].to_bytes(2,'little'))
   if pending['site']in sound:
    ra=pending['sp']-(2 if sound[pending['site']][1]==205 else 0);rt=(ra,p.syms['h_sound_after'].to_bytes(2,'little'),pending['target'].to_bytes(2,'little'))
   compare(s,er,em,low,pc,rt);counts['nested '+hex(pc)]+=1
  if pc in sites and len(states[pc])<collect:states[pc].append((bytes(s.memory),list(s.registers)))
  if pc==0xCB81:canvas[:]=255;counts['full clear']+=1
  elif pc==0xB242:
   off=s.registers[6]*256+s.registers[7]-0xD88F;oracle.clear((off%32)*8,off//32,s.registers[2],s.registers[3]);counts['clear']+=1
  elif pc==0xB3EA:
   ix=s.registers[8]*256+s.registers[9];ptr=s.registers[4]*256+s.registers[5];oracle.plot(s.memory,ix,ptr);counts['plots']+=1
  if pc not in sites or pending:return
  iff[s.registers[26]]+=1
  if q is None:q=Live(p,s.memory,list(s.registers))
  else:q.reset_game(s.memory,list(s.registers))
  q.outputs=[];events=[];clock=q.nr[7];expected=[];target=sites[pc]
  if pc==0xAFDA:clock=3
  elif pc in(0xB03B,0xCB81,0xCB5F,0xAFCB,0xB075,0xC344)and q.state('v_actor_active'):clock=q.state('v_actor_speed')
  if pc in sound:
   ev=sound_events[sound_cursor];sound_cursor+=1;assert ev['site']==pc,('sound event order',pc,ev['site']);target=ev['target'];q.input_values=list(ev['inputs']);expected=[(port,value,0)for port,value in ev['outputs']]
  pending=dict(site=pc,target=target,sp=s.registers[12],clock=clock,outputs=expected);first=True
  def model_at(mp,live):
   nonlocal first
   if first:first=False;return
   if mp in watched and mp!=target:events.append((mp,list(live.sim.registers),bytes(live.mem),live.min_sp))
  q.runto(target,watch=model_at)
  if pc==0xAFDA:assert q.state('v_actor_speed')==0,('actor latched accelerated caller',q.state('v_actor_speed'))
  counts['taken '+hex(pc)]+=1
  if progress and sum(v for k,v in counts.items()if k.startswith('taken'))%100==0:progress(dict(counts))
 try:
  n,e=rzx.trace(str(rzx_path),watched|interiors,at,stop=stop);counts['frames']=n;assert not e,('replay',e)
  if pending:
   class NoIO:
    def read_port(self,r,port):raise AssertionError(('boundary input',port))
    def write_port(self,r,port,v,*unused):assert pending['site']==0xB952 and port&255==253,('boundary output',port,v)
   tail=_rw_simulator()(list(source_sim.memory),config={'int_active':0});tail.registers[:]=source_sim.registers;tail.set_tracer(NoIO());steps=0;target=pending['target']
   while tail.registers[24]!=target:
    pc=tail.registers[24]
    if pc in watched and not(steps==0 and pc==pending['site']):at(pc,tail)
    tail.opcodes[tail.memory[pc]]();steps+=1;assert steps<3000000,('tail limit',pc)
   at(target,tail);counts['boundary tail instructions']=steps
 except(AssertionError,ValueError)as exc:
  counts['differential!']+=1;examples['failure']=repr(exc)
 counts['sound calls']=sound_cursor;counts['IFF0 hooks']=iff[0];counts['IFF1 hooks']=iff[1];examples['dead_stack_bytes']={f'{a:04X}':n for a,n in sorted(dead.items())};examples['page_sha256']=hashlib.sha256(p.page).hexdigest()
 if pending:examples['unfinished_boundary_hook']=pending
 return(counts,examples,states)if collect else(counts,examples)

def negative_patches(p):
 """Mutate this build's emitted code/data, retaining the good original-pixel oracle."""
 out=[]
 for kind in('R','speed','position','opacity','classification','orientation','bitmap'):
  q=copy.deepcopy(p);code=bytearray(q.page)
  if kind=='R':
   at=code.index(bytes.fromhex('3ef7'),q.syms['h_render']-8192)+1;code[at]=0xf8
  elif kind=='speed':
   pattern=b'\xf5\x3a'+q.syms['v_render_speed'].to_bytes(2,'little')+bytes.fromhex('ed9207f1')
   at=code.index(pattern,q.syms['h_render_after']-8192)+1;code[at:at+3]=bytes.fromhex('3e0300')
  elif kind=='position':
   aux=bytearray(q.extra_banks[42]);at=aux.index(bytes.fromhex('c62077'),q.syms['fg_attribute']-0xA000)+1;aux[at]=33;q.extra_banks[42]=bytes(aux)
  elif kind=='bitmap':q.sites.append((0xB179,bytes.fromhex('8fd8'),bytes.fromhex('90d8')))
  else:
   pages={n:bytearray(q.extra_banks[n//2][(n%2)*8192:(n%2+1)*8192])for n in q.art_pages}
   if kind=='orientation':
    for gid in range(172):
     for flag in range(4):
      at=gid*32+flag*8
      if pages[76][at]:pages[76][at+5]^=128
   else:
    sourcepages=set(pages)-set(range(52,64))-set(range(70,84))-{88,89}
    for n in sourcepages:
     raw=pages[n]
     for i,v in enumerate(raw):
      if kind=='opacity'and v in(1,129):raw[i]=255
      elif kind=='classification'and v<128:raw[i]=v|128
   for b in {n//2 for n in pages}:q.extra_banks[b]=bytes(pages.get(2*b,q.extra_banks[b][:8192]))+bytes(pages.get(2*b+1,q.extra_banks[b][8192:]))
  if kind in('R','speed'):
   q.page=bytes(code);q.rom_code=q.page[:len(q.rom_code)]
   for bank in(12,13):q.extra_banks[bank]=q.page+q.extra_banks[bank][8192:]
  out.append((kind,q))
 return out

def unit_tests(p,states,neg=True):
 counts=collections.Counter();examples={};dead=collections.Counter();ss={a:list(v)for a,v in states.items()}
 if 0xC344 not in ss and ss:
  mem,regs=next(v[0]for v in ss.values()if v);regs=list(regs);regs[24]=0xC344;ss[0xC344]=[(mem,regs)]
 class IO:
  def read_port(self,r,port):raise AssertionError(('unexpected original input',hex(port)))
  def write_port(self,r,port,v,*unused):assert port&255==253,('unexpected original output',hex(port),v)
 for site,cases in sorted(ss.items()):
  if site in getattr(p,'sound_sites',{}):continue
  for mem,regs in cases:
   for speed in range(4):
    for iff in(0,1):
     for rv in(0,127,128,255):
      try:
       regs=list(regs);regs[24]=site;regs[26]=iff;regs[15]=rv;org=_rw_simulator()(list(mem),config={'int_active':0});org.registers[:]=regs;org.set_tracer(IO());q=Live(p,mem,regs,speed);steps=0
       while org.registers[24]!=SITES[site]:org.opcodes[org.memory[org.registers[24]]]();steps+=1;assert steps<3000000
       q.runto(SITES[site]);diff=[(i,org.registers[i],q.sim.registers[i])for i in CMP_R+[24]if org.registers[i]!=q.sim.registers[i]];assert not diff,('register',hex(site),speed,iff,rv,diff)
       want=bytearray(org.memory[16384:]);got=bytes(q.mem[16384:])
       for addr,old,new in p.sites:want[addr-16384:addr-16384+len(new)]=new
       lo=max(q.min_sp,0x5D00);hi=min(org.registers[12],0x5E00)
       for addr in range(lo,hi):
        if want[addr-16384]!=got[addr-16384]:dead[addr]+=1
       if lo<hi:want[lo-16384:hi-16384]=got[lo-16384:hi-16384]
       assert want==got,('RAM',hex(site),[(i+16384,x,y)for i,(x,y)in enumerate(zip(want,got))if x!=y][:12]);assert q.nr[7]==(3 if site==0xAFDA else speed)and q.maps==[255,255,10,11,4,5,0,1],('mapping/speed',hex(site),q.nr[7],speed,q.maps);assert not q.outputs,q.outputs[:6];counts['ABI cases']+=1
      except(AssertionError,ValueError)as exc:counts['ABI!']+=1;examples.setdefault('ABI',[]).append(repr(exc))
 if neg:
  for kind,q in negative_patches(p):
   if kind not in('R','speed','bitmap'):continue
   site=0xB075 if kind=='bitmap'else 0xB03B
   if site not in ss:counts['negative fixture missing!']+=1;continue
   mem,regs=ss[site][0];org=_rw_simulator()(list(mem),config={'int_active':0});org.registers[:]=regs
   while org.registers[24]!=SITES[site]:org.opcodes[org.memory[org.registers[24]]]()
   model=Live(q,mem,regs);model.runto(SITES[site]);caught=(model.sim.registers[15]!=org.registers[15])if kind=='R'else(model.nr[7]!=0)if kind=='speed'else(bytes(model.mem[16384:22528])!=bytes(org.memory[16384:22528]))
   counts[kind+' negative caught'if caught else kind+' negative missed!']+=1
 examples['dead_stack_bytes']={f'{a:04X}':n for a,n in sorted(dead.items())};sc,se=sound_unit_tests(p,ss);counts.update(sc);examples.update(se);return counts,examples


def sound_unit_tests(p,states):
 """Whole effects, including tail-JP and tune paths; compare every FE interval."""
 counts=collections.Counter();examples={}
 if not states:return counts,examples
 _,initial=next(v[0]for v in states.values()if v)
 class IO:
  def __init__(self):self.out=[]
  def read_port(self,r,port):return 255
  def write_port(self,r,port,v,*u):
   if port&255==254:self.out.append((port,v,r[25]))
 class SoundLive(Live):
  def read_port(self,r,port):return 255 if port&255==254 else super().read_port(r,port)
  def write_port(self,r,port,v,*unused):
   if port&255==254:self.sfx.append((port,v,r[25],self.nr[7]));return
   super().write_port(r,port,v,*unused)
 for site,(target,opcode)in p.sound_sites.items():
  for speed in range(4):
   for active in(0,1):
    for iff in(0,1):
     mem=list(p.source_memory);mem[:16384]=nextboot.alt_image(p)[:16384];r=list(initial);r[24]=site;r[12]=0x5DF0;r[4],r[5]=0xD8,0x33;r[2],r[3]=0x20,4;r[15]=(0,127,128,255)[speed];r[26]=iff;continuation=site+3 if opcode==205 else 0xB00C
     if opcode!=205:mem[r[12]:r[12]+2]=[12,176]
     try:
      org=_rw_simulator()(list(mem),config={'int_active':0});org.registers[:]=r;io=IO();org.set_tracer(io);steps=0
      while org.registers[24]!=continuation:org.opcodes[org.memory[org.registers[24]]]();steps+=1;assert steps<3000000,('sound limit',site)
      q=SoundLive(p,mem,r,3 if active else speed);q.sfx=[];q.pages[26][p.syms['v_actor_active']&8191]=active;q.pages[26][p.syms['v_actor_speed']&8191]=speed;q.runto(continuation)
      diff=[(i,org.registers[i],q.sim.registers[i])for i in CMP_R+[24]if org.registers[i]!=q.sim.registers[i]];assert not diff,('sound registers',site,speed,active,iff,diff)
      assert q.nr[7]==(3 if active else speed)and q.maps==[255,255,10,11,4,5,0,1],('sound clock/maps',site)
      assert [(a,b)for a,b,t in io.out]==[(a,b)for a,b,t,c in q.sfx],('sound FE sequence',site)
      assert all(c==speed for a,b,t,c in q.sfx),('sound FE clock',site)
      assert [b[2]-a[2]for a,b in zip(io.out,io.out[1:])]==[b[2]-a[2]for a,b in zip(q.sfx,q.sfx[1:])],('sound waveform',site)
      want=bytearray(org.memory[16384:]);got=bytes(q.mem[16384:])
      for a,o,n in p.sites:want[a-16384:a-16384+len(n)]=n
      lo=max(q.min_sp,0x5D00);hi=min(org.registers[12],0x5E00)
      if lo<hi:want[lo-16384:hi-16384]=got[lo-16384:hi-16384]
      assert want==got,('sound RAM',site);counts['whole-sound cases']+=1;counts['whole-sound FE edges']+=len(io.out)
     except(AssertionError,ValueError)as exc:counts['whole-sound!']+=1;examples.setdefault('sound',[]).append(repr(exc))
 return counts,examples
