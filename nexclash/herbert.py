"""Herbert's Dummy Run, Mikro-Gen 48K: private candidate engine."""
import collections,json,re,subprocess
from pathlib import Path
from .build import rom48,altrom_image
from .z80tonex import Z80Snapshot
ROOT=Path(__file__).resolve().parents[1]
SITES={0x8ca3:'or',0x93ba:'m16',0x9336:'hero',0x931c:'a32',0x9330:'b32',0x96bc:'reset',0xa298:'room',0x943c:'clear',0x97c0:'copy',0x97d7:'copytest',0x9261:'paint',0x92dd:'unpaint'}
SITES.update({0xc136:'effect',0x9c7e:'attrs',0x9c88:'bgclean',0x9c23:'bgdisplay',0xa324:'bgobject',0x9cb7:'bgfinish',0x9c5e:'bgdisplayfinish'})
def memory(path):
 s=Z80Snapshot(str(path));return list(rom48()+s.banks[5]+s.banks[2]+s.banks[0])
def assemble(mem,work):
 work=Path(work).resolve();work.mkdir(exist_ok=True,parents=True)
 (work/'paint.bin').write_bytes(bytes(mem[0x9261:0x92bd]));(work/'unpaint.bin').write_bytes(bytes(mem[0x92dd:0x931b]))
 src=(ROOT/'asm/herbert_hooks.asm').read_text().replace('"paint.bin"','"'+str(work/'paint.bin')+'"').replace('"unpaint.bin"','"'+str(work/'unpaint.bin')+'"')
 (work/'hooks.asm').write_text(src)
 exe=ROOT/'tools/sjasmplus/sjasmplus-1.24.0-linux-x86_64'
 r=subprocess.run([str(exe),'--zxnext','--sym=hooks.sym','hooks.asm'],cwd=work,capture_output=True,text=True)
 (work/'assembly.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 syms={m[1]:int(m[2],16) for m in re.finditer(r'^([\w.]+): EQU 0x([0-9A-Fa-f]+)',(work/'hooks.sym').read_text(),re.M)}
 return {k:(work/f'herbert_{k}.bin').read_bytes() for k in ['rom','hook','setup']},syms

def colours(censuses):
 if not censuses:
  return {int(k):v for k,v in json.loads((ROOT/'docs/profiles/herbert.json').read_text())['colours'].items()}
 counts=collections.defaultdict(collections.Counter)
 for p in censuses:
  for e in json.loads(Path(p).read_text())['shapes'].values():
   if e['site']==0x8d02:continue
   for a,n in e['colours'].items():
    a=int(a);ink=(a&7)+(8 if a&64 else 0)
    if ink&7:counts[e['gfx']][ink]+=n
 result={g:c.most_common(1)[0][0] for g,c in counts.items()}
 for g in range(0xf4b0,65536,128):result[g]=14
 return result

class HerbertPatch:
 name="Herbert's Dummy Run: hardware sprite candidate"
 def __init__(self,mem,work,censuses=(),target=377,enhanced=False):
  blocks,self.syms=assemble(mem,work)
  self.rom_code,self.page_code,self.setup=[blocks[k] for k in ['rom','hook','setup']]
  self.page,self.regblock,self.altrom=altrom_image(rom48(),0x386e,self.rom_code)
  self.slot1=(24,self.regblock);self.tail_addr=0x5b00;self.max_tail=80
  self.stub_extra=self.setup;self.setup_call=0xd000;self.hook_page_data=b'';self.uses_printer_buffer=True
  self.keep_printer_buffer=True
  h=bytearray(8192);h[0x100:0x100+len(self.page_code)]=self.page_code
  for mask in range(16):
   for ink in range(16):
    pix=[1 if ink&(8>>k) else 0 if mask&(8>>k) else 8 for k in range(4)]
    off=0x1800+(mask*16+ink)*2;h[off:off+2]=bytes([(pix[0]<<4)|pix[1],(pix[2]<<4)|pix[3]])
  # Spectrum RGB333 converted to Next RGB332, palette zero is transparent.
  for c in range(16):
   v=7 if c&8 else 5;r=v if c&2 else 0;g=v if c&4 else 0;b=(3 if c&8 else 2) if c&1 else 0
   h[0x1c00+c*16+1]=(r<<5)|(g<<2)|b
  from .herbert_colours import PALETTE,tables
  for c in range(16):
   for index,(r,g,b) in PALETTE.items():h[0x1c00+c*16+index]=(r<<5)|(g<<2)|b
  h[56]=int(enhanced);self.enhanced=enhanced
  h[40:42]=int(target).to_bytes(2,'little')
  from skoolkit.simulator import Simulator
  sim=Simulator(list(mem),{'PC':0x97c0,'SP':0xfff0,'R':0})
  while sim.registers[24]!=0x97da:sim.opcodes[sim.memory[sim.registers[24]]]()
  h[43]=sim.registers[15]&127
  self.scratch=bytes(h);self.copy_delta=h[43]
  self.colours=colours(censuses);tab=bytearray([15])*32768
  for a,c in self.colours.items():
   if 0x8000<=a<65536:tab[a-0x8000]=c
  self.extra_banks={12:self.page+bytes(8192),13:self.scratch+bytes(8192),14:bytes(16384),15:bytes(16384),16:bytes(16384),17:bytes(16384),20:bytes(tab[:16384]),21:bytes(tab[16384:])}
  # Give images used in the same room different cache slots. Unknown images
  # retain a safe hashed slot; complete raw-byte comparisons still decide hits.
  indices=bytearray(((a>>5)^(a>>11))&63 for a in range(0x8000,65536))
  for a,i in json.loads((ROOT/'docs/profiles/herbert.json').read_text())['cache_indices'].items():indices[int(a)-0x8000]=i
  self.extra_banks.update({22:bytes(indices[:16384]),23:bytes(indices[16384:])})
  painted,self.colour_stats=tables(mem);self.extra_banks.update(painted)
  from .herbert_scenery import tables as scenery_tables
  self.extra_banks.update(scenery_tables(mem))
  self.sites=[(a,bytes(mem[a:a+3]),b'\xc3'+self.syms['e_'+name].to_bytes(2,'little')) for a,name in SITES.items()]
 def apply(self,snap):
  for a,old,new in self.sites:
   b=(5,2,0)[(a>>14)-1];off=a&16383;d=bytearray(snap.banks[b])
   if d[off:off+len(old)]!=old:raise ValueError(f'wrong code at {a:04x}')
   d[off:off+len(new)]=new;snap.banks[b]=bytes(d)

