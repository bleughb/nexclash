"""Pentagram (Ultimate,1986), exact 48K archive. Original presentation with paced renderer.
Enhanced uses owner-approved part colours over the exact original masked drawing order.
"""
from pathlib import Path
import json
from .build import rom48
from .hooklib import CMP_R
RECORD='pentagram';CMP=CMP_R;TAIL_ADDR=0x5B00
ROOT=Path(__file__).resolve().parents[1]
SITES_ORIG={0xB03B:bytes.fromhex('cd9eb1'),0xB952:bytes.fromhex('d3fd'),0xB3EA:bytes.fromhex('dd7e1a'),0xB075:bytes.fromhex('cd78b1'),0xC344:bytes.fromhex('cd78b1')}
INTERIORS=tuple(a+i for a,b in SITES_ORIG.items()for i in range(1,len(b)))
def _profile_path():return ROOT/'docs/profiles/pentagram.json'
def load_profile():return json.loads(_profile_path().read_text())
def is_pentagram(snap):
 if getattr(snap,'is128',False):return False
 try:
  mem=snap.memory;sig=load_profile()['signature'];addr=sig['addr'];sigbytes=bytes.fromhex(sig['bytes'])
  return bytes(mem[addr:addr+len(sigbytes)])==sigbytes and all(bytes(mem[a:a+len(b)])==b for a,b in SITES_ORIG.items())and bytes(mem[0xB3D3:0xB3D8])==bytes.fromhex('dd7e00fe01')
 except(TypeError,IndexError,AttributeError):return False
class PentagramPatch:
 name='Pentagram original presentation, paced renderer'
 def __init__(self,enhanced=False,game=None,colours=None):
  p=load_profile();self.syms={k:int(v,16)for k,v in p['hooks']['syms'].items()};self.enhanced=False
  self.rom_code=bytes.fromhex(p['hooks']['rom']);self.setup_code=bytes.fromhex(p['hooks']['setup']);self.regblock=0x2000+len(self.rom_code)
  self.slot1=(24,self.regblock);self.altrom=(0x2000,self.regblock+20)
  page=bytearray(rom48()[8192:]);page[:len(self.rom_code)]=self.rom_code;self.page=bytes(page)
  self.setup_call=0xD000;self.stub_extra=self.setup_code;self.hook_page_data=b''
  self.uses_printer_buffer=False;self.keep_printer_buffer=True;self.tail_addr=TAIL_ADDR;self.max_tail=128
  self.sites=[(0xB03B,SITES_ORIG[0xB03B],b'\xcd'+self.syms['h_render'].to_bytes(2,'little')),
              (0xB952,SITES_ORIG[0xB952],b'\x18\x00')]
  for addr,sym in((0xB3EA,'h_plot_tick'),(0xB075,'h_copy_room'),(0xC344,'h_copy_menu')):self.sites.append((addr,SITES_ORIG[addr],b'\xcd'+self.syms[sym].to_bytes(2,'little')))
  self.extra_banks={12:self.page+bytes(8192),13:self.page+bytes(8192)}
  if enhanced:self.init_enhanced(game,colours)
 def init_enhanced(self,game,colours=None):
  from . import pentagram_colour as PC
  from skoolkit.snapshot import Snapshot
  if game is None:raise ValueError('Enhanced needs the original game snapshot to compile its owner colours')
  mem=Snapshot.get(str(game)).memory[0:65536] if isinstance(game,(str,Path))else game
  if len(mem)!=65536:raise ValueError('Expected original48K memory image with address space')
  self.source_memory=bytes(mem);self.colours=PC.load_colours()if colours is None else colours
  profile=json.loads((ROOT/'docs/profiles/pentagram_enhanced.json').read_text());self.enhanced=True;self.name='Pentagram approved Enhanced colours'
  self.syms={k:int(v,16)for k,v in profile['hooks']['syms'].items()};self.rom_code=bytes.fromhex(profile['hooks']['rom']);self.setup_code=bytes.fromhex(profile['hooks']['setup']);self.stub_extra=self.setup_code;self.regblock=0x3C00;self.slot1=(24,self.regblock);self.altrom=(0x2000,0x3C14)
  page=bytearray(rom48()[8192:]);page[:len(self.rom_code)]=self.rom_code;self.page=bytes(page);self.extra_banks={12:self.page+bytes(8192),13:self.page+bytes(8192)};aux=bytes.fromhex(profile['hooks']['aux']);self.extra_banks[42]=aux+bytes(16384-len(aux))
  pages,palette=PC.compile_pages(lambda a:mem[a],self.colours)
  if self.setup_code[-512:]!=palette:raise ValueError('Enhanced palette does not match emitted setup')
  self.art_pages=set(pages)
  for bank in sorted({p//2 for p in pages}):self.extra_banks[bank]=pages.get(bank*2,bytes(8192))+pages.get(bank*2+1,bytes(8192))
  sites={0xAFCB:('cdb6c6','h_room_init'),0xB03B:('cd9eb1','h_render'),0xB3EA:('dd7e1a','h_plot'),0xB075:('cd78b1','h_copy_room'),0xC344:('cd78b1','h_copy_menu'),0xB242:('cdddb6','h_clear'),0xCB81:('010018','h_fullclear'),0xCB5F:('110140','h_hide')}
  self.sites=[(a,bytes.fromhex(old),b'\xcd'+self.syms[name].to_bytes(2,'little'))for a,(old,name)in sites.items()]+[(0xB952,b'\xd3\xfd',b'\x18\x00')]
  self.sites.append((0xAFDA,bytes.fromhex('cdabcb'),b'\xcd'+self.syms['h_actor_open'].to_bytes(2,'little')))
  self.sites.append((0xB5A3,bytes.fromhex('ed5319a7'),b'\xcd'+self.syms['h_sort_tick'].to_bytes(2,'little')+b'\0'))
  self.sound_sites={0xC1B5:(0xD629,0xC3),0xC588:(0xD5E4,0xCD),0xC5AE:(0xD635,0xCD),0xC114:(0xD64E,0xCD),0xBB91:(0xD69C,0xCD),0xD0F1:(0xD6B5,0xCD),0xC320:(0xD6B5,0xCD),0xC34A:(0xD6B5,0xCD),0xAFBC:(0xD6B5,0xCD)}
  for addr,(target,opcode)in self.sound_sites.items():self.sites.append((addr,bytes([opcode])+target.to_bytes(2,'little'),bytes([opcode])+self.syms[f'h_sound_{target:04X}'].to_bytes(2,'little')))
 def apply(self,snap):
  if snap.is128:raise ValueError('Pentagram exact48K release required')
  ram=bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
  for a,old,new in self.sites:
   actual=bytes(ram[a-16384:a-16384+len(old)])
   if actual!=old:raise ValueError(f'{a:04X}: {actual.hex()} != {old.hex()}')
   ram[a-16384:a-16384+len(new)]=new
  snap.banks[5],snap.banks[2],snap.banks[0]=bytes(ram[:16384]),bytes(ram[16384:32768]),bytes(ram[32768:]);restore_tail(self,snap)
def restore_tail(p,snap):
 from . import z80tonex as Z
 backup,entry=0x3900,0x3940;tail,_,restore,_=Z.build_tail(snap,p.tail_addr,p.slot1,True)
 if len(tail)>64:raise ValueError('tail backup capacity')
 original=bytes(snap.read(p.tail_addr+i)for i in range(len(tail)))
 code=b'\xF3\x21'+Z.w16(backup)+b'\x11'+Z.w16(p.tail_addr)+b'\x01'+Z.w16(len(tail))+b'\xED\xB0'+tail[restore:]
 if entry+len(code)>=0x3A00:raise ValueError('tail restorer capacity')
 assert set(rom48()[backup:entry+len(code)])=={255}
 page=bytearray(p.page);page[backup-8192:backup-8192+len(original)]=original;page[entry-8192:entry-8192+len(code)]=code;p.page=bytes(page)
 p.extra_banks[12]=p.page+p.extra_banks[12][8192:];p.altrom=(min(backup,p.altrom[0]),max(entry+len(code),p.altrom[1]));p.original_pc=snap.pc;p.tail_restore_bytes=len(tail);snap.pc=entry

def colour_set_layout(default,enhanced):
 """Give both menu modes the same NEX bank bitmap. Extra default banks stay unused."""
 for bank in enhanced.extra_banks:default.extra_banks.setdefault(bank,bytes(16384))
 return default

def build(z80,out):
 from .z80tonex import convert
 p=PentagramPatch();info=convert(str(z80),str(out),TAIL_ADDR,True,quiet=True,patch=p);return p,info

def verify(patch,rzx_path,stop=None,collect=0,progress=None):
 if patch.enhanced:
  from .pentagram_enhanced_verify import verify as run
 else:
  from .pentagram_verify import verify as run
 return run(patch,rzx_path,stop,collect,progress)

def unit_tests(patch,states,neg=True):
 if patch.enhanced:
  from .pentagram_enhanced_verify import unit_tests as run
  return run(patch,states,neg)
 from .pentagram_verify import Model,Sim
 from collections import Counter
 import copy
 c=Counter();examples=[];states={site:list(ss)for site,ss in states.items()}
 if 0xC344 not in states and states:
  mem,regs=next(ss[0]for ss in states.values()if ss);regs=list(regs);regs[24]=0xC344;states[0xC344]=[(mem,regs)]
 for site,ss in states.items():
  target={0xB03B:0xB03E,0xB952:0xB954,0xB3EA:0xB3ED,0xB075:0xB078,0xC344:0xC347}[site]
  for mem,regs in ss:
   for speed in range(4):
    for iff in(0,1):
     for rv in(0,127,128,255):
      regs=list(regs);regs[15]=rv;regs[26]=iff
      org=Sim(list(mem),config={'int_active':0});org.registers[:]=regs;io=Model(patch,mem,regs,speed);org.set_tracer(io)
      while org.registers[24]!=target:org.opcodes[org.memory[org.registers[24]]]()
      io.ports=[];io.runto(target);diff=[i for i in CMP+[24]if io.sim.registers[i]!=org.registers[i]]
      patchbytes={a+i:b for a,old,new in patch.sites for i,b in enumerate(new)}
      expected=bytearray(org.memory[16384:]);actual=bytes(io.mem[16384:])
      for a,b in patchbytes.items():expected[a-16384]=b
      low=max(io.min_sp,0x5D00);high=min(org.registers[12],0x5E00)
      if low<high:expected[low-16384:high-16384]=actual[low-16384:high-16384]
      ram_ok=expected==actual;maps_ok=io.maps=={0:255,1:255,6:0,7:1}
      if diff or io.nr[7]!=speed or not ram_ok or not maps_ok:c['ABI!']+=1;examples.append((site,speed,iff,rv,diff,io.nr[7],ram_ok,maps_ok))
      else:c['ABI cases']+=1
 if neg:
  for kind,broken,site,target in negative_patches(patch):
   if site not in states:continue
   mem,regs=states[site][0];org=Sim(list(mem),config={'int_active':0});org.registers[:]=regs
   while org.registers[24]!=target:org.opcodes[org.memory[org.registers[24]]]()
   m=Model(broken,mem,regs);m.runto(target)
   caught=(m.sim.registers[15]!=org.registers[15])if kind=='R'else(m.nr[7]!=0)if kind=='speed'else(bytes(m.mem[16384:22528])!=bytes(org.memory[16384:22528]))
   c[kind+' negative caught'if caught else kind+' negative missed!']+=1
 return c,examples


def negative_patches(patch):
 """Break the emitted build's own code; each control has a specific observable fault."""
 import copy
 out=[]
 for kind in('R','speed','bitmap'):
  p=copy.deepcopy(patch);code=bytearray(p.rom_code)
  if kind=='R':
   off=code.index(bytes.fromhex('3ef7'),p.syms['h_render']-8192)+1;code[off]=0xf8
  elif kind=='speed':
   latch=p.syms['v_speed'];pattern=b'\xf5\x3a'+latch.to_bytes(2,'little')+bytes.fromhex('ed9207f1')
   off=code.index(pattern,p.syms['h_render_after']-8192)+1;code[off:off+3]=bytes.fromhex('3e0300')
  else:p.sites.append((0xB179,bytes.fromhex('8fd8'),bytes.fromhex('90d8')))
  p.rom_code=bytes(code);page=bytearray(p.page);page[:len(code)]=code;p.page=bytes(page)
  for bank in(12,13):p.extra_banks[bank]=p.page+p.extra_banks[bank][8192:]
  out.append((kind,p,0xB075 if kind=='bitmap'else 0xB03B,0xB078 if kind=='bitmap'else 0xB03E))
 return out


def boot_check(nex,z80,patch):
 from . import z80tonex as Z,nextboot
 expected=Z.Z80Snapshot(str(z80));p=PentagramPatch();p.sites=list(patch.sites);p.apply(expected);ram=expected.banks[5]+expected.banks[2]+expected.banks[0];bad=[]
 for nexload in(False,True):
  st=nextboot.boot(str(nex),p.original_pc,nexload=nexload);r=st['R'];w=lambda n:r[n]*256+r[n+1]
  dif=[a for a in range(16384,65536)if st['mem'][a]!=ram[a-16384]]
  if dif:bad.append(('RAM',nexload,dif[:20]))
  for i,v in((0,expected.a),(1,expected.f),(12,expected.sp),(14,expected.i),(15,expected.r),(26,expected.iff1),(27,expected.im)):
   if r[i]!=v:bad.append(('register',nexload,i,r[i],v))
  for i,v in((2,expected.bc),(4,expected.de),(6,expected.hl),(8,expected.ix),(10,expected.iy),(16,expected.a_*256+expected.f_),(18,expected.bc_),(20,expected.de_),(22,expected.hl_)):
   if w(i)!=v:bad.append(('register',nexload,i,w(i),v))
  if st['bad']:bad.append(('loader',nexload,st['bad']))
 return bad

def loading_screen(folder):
 import functools,operator
 for f in sorted(Path(folder).glob('*.tap')):
  d=f.read_bytes();i=0
  while i+2<=len(d):
   n=int.from_bytes(d[i:i+2],'little');b=d[i+2:i+2+n];i+=n+2
   if len(b)==6914 and b[0]==255 and functools.reduce(operator.xor,b)==0:return b[1:-1]
 return None

def add_loading(nex,screen):
 h=bytearray(nex[:512])
 if h[10] or len(screen)!=6912:raise ValueError('Expected base NEX plus exactULA screen')
 h[10]=2;h[133]=50;return bytes(h)+bytes(screen)+nex[512:]

def auto(a,z80,name,out,say):
 from . import z80tonex as Z
 import hashlib
 out=Path(out);out.mkdir(parents=True,exist_ok=True);ok=True;say('Game      : '+name);say('Engine    : pentagram (original appearance by default; optional approved Enhanced part colours)')
 reference=PentagramPatch(enhanced=True,game=z80)
 for mode,suffix in(('Plain',''),('Sprites','_sprites'),('Enhanced','_enhanced')):
  p=PentagramPatch(enhanced=mode=='Enhanced',game=z80)
  if mode=='Sprites':colour_set_layout(p,reference)
  if mode=='Plain':p.sites=[s for s in p.sites if s[0]==0xB952]
  dest=out/(name+suffix+'.nex');Z.convert(str(z80),str(dest),TAIL_ADDR,True,quiet=True,patch=p);bad=boot_check(dest,z80,p);ok=ok and not bad
  say('%-10s: %s  %s boot %s'%(mode,dest.name,hashlib.md5(dest.read_bytes()).hexdigest(),'OK'if not bad else repr(bad)))
  screen=loading_screen(Path(z80).parent)
  if screen:(out/(name+suffix+'_loading.nex')).write_bytes(add_loading(dest.read_bytes(),screen))
 rzxs=list(getattr(a,'rzx',None)or[])
 for enhanced in(False,True):
  patch=PentagramPatch(enhanced=enhanced,game=z80);states=None
  for path in rzxs:
   counts,examples,states=verify(patch,path,stop=getattr(a,'quick',None),collect=1);fails={k:v for k,v in counts.items()if k.endswith('!')};ok=ok and not fails
   say('Verify    : %s %s frames=%d completed=%d pictures=%d %s'%('Enhanced'if enhanced else'Default',Path(path).name,counts['frames'],sum(v for k,v in counts.items()if k.startswith('completed ')),counts['publication pictures'],'IDENTICAL'if not fails else repr(fails)))
   if fails:say('            '+repr(examples))
  if states and states.get(0xB03B):
   c,e=unit_tests(patch,states);fails={k:v for k,v in c.items()if k.endswith('!')};ok=ok and not fails;say('Unit      : %s %s'%('Enhanced'if enhanced else'Default',dict(c)))
   if fails:say('            '+repr(e))
 if rzxs:
  from .pentagram_enhanced_verify import negative_patches as negatives
  for kind,broken in negatives(PentagramPatch(enhanced=True,game=z80)):
   if kind in('R','speed','bitmap'):continue
   counts,examples=verify(broken,rzxs[0],stop=min(getattr(a,'quick',None)or 1800,1800));failure=examples.get('failure','');expected='display'if kind=='position'else'canvas';caught=bool(counts['differential!'])and expected in failure;ok=ok and caught;say('Negative  : %s %s%s'%(kind,'caught'if caught else'FAILED',(' '+failure)if not caught else''))
 else:say('Verify    : not requested; build/boot only, no replay or timing claim')
 painting=out/(name+'_PAINTING_SPRITES.png')
 if not painting.exists():sheets(z80,out,prefix=name,say=say)
 else:say('Sheets    : existing editable sheet preserved')
 say('Result    : '+('PASSED'if ok else'FAILED'));return ok


# Shared editable-sheet/recolour interface.
from .pentagram_colour import RECOLOUR,recolour,colour_identity,sheets
