"""Pentagram hook differential model. Functional proof; native pace measured separately."""
from . import z80n,rzx,nextboot
from .dizzy6 import _rw_simulator
from .hooklib import CMP_R
import collections
Sim=_rw_simulator()
class Model:
 def __init__(self,p,mem,regs,speed=0):
  self.p=p;self.sim=Sim(list(mem),config={'int_active':0});self.sim.registers[:]=regs;self.mem=self.sim.memory
  self.pages={}
  for b,d in p.extra_banks.items():self.pages[b*2]=bytearray(d[:8192]);self.pages[b*2+1]=bytearray(d[8192:])
  self.rom=nextboot.alt_image(p);self.maps={0:255,1:255,6:0,7:1};self.nr={7:speed};self.sel=0;self.line=0;self.ports=[];self.reads=[]
  self.reset(mem,regs);z80n.install(self.sim,self.nextreg);self.sim.set_tracer(self)
 def reset(self,mem,regs):
  assert self.maps=={0:255,1:255,6:0,7:1},self.maps
  self.mem[:16384]=list(self.rom);self.mem[16384:]=list(mem[16384:]);self.sim.registers[:]=regs
  for a,o,n in self.p.sites:self.mem[a:a+len(n)]=list(n)
 def nextreg(self,reg,val):
  self.nr[reg]=val
  if 0x50<=reg<=0x57:
   sl=reg-0x50;at=sl*8192;old=self.maps.get(sl)
   if old is not None and old!=255:self.pages[old][:]=bytes(self.mem[at:at+8192])
   self.mem[at:at+8192]=list(self.rom[at:at+8192]if val==255 else self.pages.setdefault(val,bytearray(8192)));self.maps[sl]=val
 def read_port(self,r,port):
  if port==0x253b:
   if self.sel==7:return self.nr[7]|(self.nr[7]<<4)
   if self.sel==0x1e:return self.line>>8
   if self.sel==0x1f:
    x=self.line&255;self.line=(self.line+1)%312;return x
   return self.nr.get(self.sel,0)
  self.reads.append(port);return 255
 def write_port(self,r,port,value,*rest):
  if port==0x243b:self.sel=value
  else:self.ports.append((port,value,self.nr[7]))
 def runto(self,target,limit=2000000):
  r=self.sim.registers;n=0;self.min_sp=r[12];self.entry_sp=r[12];self.nested=[];outer=r[24]
  while n==0 or r[24]!=target:
   pc=r[24]
   if outer==0xB03B and pc in(0xB3EA,0xB3ED):self.nested.append((pc,list(r),bytes(self.mem),self.min_sp))
   self.sim.opcodes[self.mem[pc]]();n+=1;self.min_sp=min(self.min_sp,r[12])
   if n>=limit:raise ValueError(('limit',hex(pc),hex(target)))
  return n

def verify(p,rzx_path,stop=None,collect=0,progress=None):
 counts=collections.Counter();examples={};states=collections.defaultdict(list);pending=None;model=None;source_sim=None;nested=[];patch={a+i:b for a,o,n in p.sites for i,b in enumerate(n)}
 sites={0xB03B:0xB03E,0xB952:0xB954,0xB3EA:0xB3ED,0xB075:0xB078,0xC344:0xC347};interiors={a+i for a,old,new in p.sites for i in range(1,len(old))};iff=collections.Counter();dead=collections.Counter()
 def fail(k,x):
  if counts[k+'!']==0 and progress:progress({'first_failure':k,'example':x})
  counts[k+'!']+=1;examples.setdefault(k,[]);examples[k]=examples[k][:4]+[x]
 def ramdiff(original,actual,low,sp,live=()):
  want=bytearray(original[16384:]);got=bytes(actual[16384:])
  for a,b in patch.items():want[a-16384]=b
  # Only bytes reached by this hook's real stack and now below original SP.
  lo=max(low,0x5D00);hi=min(sp,0x5E00)
  for a in range(lo,hi):
   if want[a-16384]!=got[a-16384]:dead[a]+=1
  if lo<hi:want[lo-16384:hi-16384]=got[lo-16384:hi-16384]
  for a in live:want[a-16384]=got[a-16384]
  if want==got:return []
  return [(a+16384,x,y)for a,(x,y)in enumerate(zip(want,got))if x!=y]
 def at(pc,s):
  nonlocal pending,model,nested,source_sim
  source_sim=s
  if pc in interiors:fail('instruction interior',hex(pc));return
  if pending and pending[0]==0xB03B and pc in(0xB3EA,0xB3ED):
   if not nested:fail('nested missing',(hex(pc),));return
   ep,er,em,low=nested.pop(0);orig=s.registers
   if ep!=pc:fail('nested order',(hex(pc),hex(ep)))
   diff=[(i,orig[i],er[i])for i in CMP_R+[24]if orig[i]!=er[i]]
   if diff:fail('nested register',(hex(pc),diff))
   ra=model.entry_sp-2;rv=p.syms['h_render_after'];want_return=bytes([rv&255,rv>>8])
   if em[ra:ra+2]!=want_return or bytes(s.memory[ra:ra+2])!=bytes.fromhex('3eb0'):fail('live return word',(ra,em[ra:ra+2].hex(),list(s.memory[ra:ra+2])))
   bad=ramdiff(s.memory,em,low,orig[12],(ra,ra+1))
   if bad:fail('nested RAM',(hex(pc),bad[:12]))
   counts['nested boundary '+hex(pc)]+=1
   if pc==0xB3EA:counts['nested original plot']+=1
   return
  if pending and pc==pending[1]:
   a,target=pending;pending=None
   if nested:fail('nested leftover',len(nested));nested=[]
   r=model.sim.registers;orig=s.registers
   diff=[(i,orig[i],r[i])for i in CMP_R+[24]if orig[i]!=r[i]]
   if diff:fail('register',(hex(a),diff))
   if model.nr[7]!=0:fail('speed',(hex(a),model.nr[7]))
   if model.maps!={0:255,1:255,6:0,7:1}:fail('maps',model.maps)
   bad=ramdiff(s.memory,model.mem,model.min_sp,orig[12])
   if bad:fail('RAM',(hex(a),bad[:20]))
   if model.reads:fail('unexpected input',(hex(a),model.reads[:10]))
   if model.ports:fail('unexpected output',(hex(a),model.ports[:10]))
   counts['completed '+hex(a)]+=1
  if pc not in sites:return
  if pending:
   if pending[0]==0xB03B and pc==0xB3EA:counts['nested original plot']+=1;return
   fail('nested',(hex(pc),pending));return
  iff[s.registers[26]]+=1
  if len(states[pc])<collect:states[pc].append((bytes(s.memory),list(s.registers)))
  if model is None:model=Model(p,s.memory,list(s.registers))
  else:model.reset(s.memory,list(s.registers))
  model.ports=[];model.reads=[];model.runto(sites[pc]);nested=list(model.nested);pending=(pc,sites[pc]);counts['taken '+hex(pc)]+=1
  if progress and counts['taken '+hex(pc)]%100==0:progress(dict(counts))
 watched=set(sites)|set(sites.values())|interiors
 n,e=rzx.trace(str(rzx_path),watched,at,stop=stop);counts['frames']=n
 if pending and not e:
  # Finish only the already-started, input-free hook from the exact final RZX state.
  # Never invent keyboard/joystick values or continue another game update.
  class TailIO:
   def read_port(self,r,port):raise AssertionError(('unrecorded tail input',port))
   def write_port(self,r,port,value,*rest):
    if pending[0]!=0xB952 or port&255!=253:raise AssertionError(('unrecorded tail output',port,value))
  tail=Sim(list(source_sim.memory),config={'int_active':0});tail.registers[:]=source_sim.registers;tail.set_tracer(TailIO());target=pending[1];start=tail.registers[24];steps=0
  while tail.registers[24]!=target:
   pc=tail.registers[24]
   if pc in watched and not(steps==0 and pc==pending[0]):at(pc,tail)
   tail.opcodes[tail.memory[pc]]();steps+=1
   if steps>2000000:raise AssertionError(('tail limit',start,target))
  at(target,tail);counts['input-free boundary tail instructions']=steps;examples['boundary_tail']=dict(start_pc=start,continuation=target,instructions=steps,external_inputs=0)
 if e:fail('replay',e)
 counts['IFF0 hooks']=iff[0];counts['IFF1 hooks']=iff[1];examples['dead_stack_bytes']={f'{a:04X}':n for a,n in sorted(dead.items())}
 if pending:examples['unfinished_boundary_hook']=pending
 return(counts,examples,states)if collect else(counts,examples)
