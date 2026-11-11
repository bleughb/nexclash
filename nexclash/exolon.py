"""Exolon exact128K release: original-paced figures and optional painted colours."""
import json,hashlib,os,copy
from pathlib import Path
from . import z80tonex as zt,hooklib,simpool
SOURCE_MD5='87515df87645c4179a9ef90663774c7f'
COLOUR_MD5='7c7348250d324c2a4211236414e1dbd4'
LOADING_MD5='e57f1a46fed24dfb566ff09f95e64a38'
TRAINERS={'Infinite lives':{0x9d1d:0},'Infinite ammo':{0x836e:0},'Infinite grenades':{0x9250:0},'Mines harmless':{0x9cae:201},'Immunity':{0x9cb8:201}}
SITES={0x9e85:(bytes.fromhex("3A989E"),"padding_in",0x9e88),0x9e8a:(bytes.fromhex("D0473E1090"),"padding_branch",0x9e8f),0x9e95:(bytes.fromhex("10FBC9"),"padding_next",0x9e98),0x9e92:(bytes.fromhex("CDFB92"),"dummy_effect",0x9e95),0x7ce7:(bytes.fromhex("E1D1C1"),"paint_exit",0x7cea),0xb04b:(bytes.fromhex("0E0021FF5A"),"clear_all",0xb050),0xb061:(bytes.fromhex("0E00210058"),"clear_play",0xb066),0x76da:(b'\xf5\xc5\xd5','large_in',0x76dd),0x795c:(b'\xf5\xc5\xd5','small_in',0x795f),0x92fb:(b'\xf5\xc5\xd5','effect_in',0x92fe),0x7897:(b'\xe1\xdd\xe1','large_exit',0x789a),0x7ab0:(b'\xe1\xdd\xe1','small_exit',0x7ab3),0x935d:(b'\xe1\xd1\xc1','effect_exit',0x9360)}
def profile():return json.loads((Path(__file__).resolve().parents[1]/'docs/profiles/exolon.json').read_text())
def load_profile():return profile()
def is_exolon(snap):
 from .simrun import addr_view
 m=addr_view(snap)
 return getattr(snap,'machine','')=='128K' and all(bytes(m[a:a+len(old)])==old for a,(old,_,_)in SITES.items())
SITES.update({0x8333:(bytes.fromhex('D1E1C1'),'bullet_exit',0x8336),0x906c:(bytes.fromhex('E1D1C1'),'cannon_exit',0x906f)})
class Patch:
 name="Exolon"
 uses_printer_buffer=False
 setup_call=0xd000
 hook_page_data=b""
 tail_addr=0x5b00
 def __init__(self,enabled=True,k=104,debt=76,colour_source=None,palette_source=None,painting=None,trainers=()):
  self.painting=painting;self.paint_overrides={};self.paint_changes=0;self.trainers=tuple(trainers)
  if set(self.trainers)-TRAINERS.keys():raise ValueError('Unknown Exolon trainer')
  h=profile()['hooks'];self.syms={k:int(v,16)for k,v in h['syms'].items()};self.code=bytes.fromhex(h['rom']);self.stub_extra=bytes.fromhex(h['setup']);self.enabled=enabled;self.colour_source=colour_source;self.palette_source=palette_source;self.pages={}
  self.slot1=(24,self.syms['regblock']);self.altrom=self.altrom0=(0x2000,0x3e00)
  self.page=bytearray(zt.rom48()[0x2000:0x4000]);self.page[0x800:0x800+len(self.code)]=self.code;self.page[0x1e00:0x1f00]=bytes(256);self.page[0x1e10]=k;self.page[0x1e14]=104;self.page[0x1e15]=45;self.page[0x1e12]=debt;self.page[0x1e11]=1;self.page[0x1e13]=bool(colour_source);self.page[0x1800:0x1880]=bytes(128);self.page[0x1900:0x1940]=bytes(range(64));self.page[0x1a00:0x1a80]=bytes([0xF0]*128);self.page[0x1a80:0x1b00]=bytes([1]*128);self.page[0x1b00:0x1e00]=bytes(768);self.page[0x200:0x400]=bytes(512);self.page[0x400:0x450]=bytes(range(80));self.page[0x1e7c]=80
  render=bytes.fromhex(h.get("render",""));self.page[0x1000:0x1000+len(render)]=render
  extra=bytes.fromhex(h.get("extras",""));self.page[0x1400:0x1400+len(extra)]=extra
  padding=bytes.fromhex(h.get("padding",""));self.page[:len(padding)]=padding
  projectiles=bytes.fromhex(h.get('projectiles',''));self.page[0x500:0x500+len(projectiles)]=projectiles
  self.sites=[(a,o,bytes([0xcd if n=='dummy_effect' else 0xc3])+zt.w16(self.syms[n]))for a,(o,n,_)in SITES.items()]if enabled else [];self.extra_banks={}
  # Enhanced pixels already carry their colours; the ULA painter still runs,
  # but its otherwise empty sprite-palette exit hook is unnecessary.
  if colour_source:self.sites=[s for s in self.sites if s[0]!=0x7ce7]
  self.page[0x1eb0]=1 # Boot probes the physical CTC; model entry supplies its clock.
 def apply(self,snap):
  backup=snap.banks[5][0x1b00:0x1d00]
  self.entry=snap.pc
  for k,v,w in [('boot_r',((snap.r-5)&127)|(snap.r&128),1),('boot_sp',snap.sp,2),('boot_jump',snap.pc,2)]:
   off=self.syms[k]-0x2000+1;self.page[off:off+w]=v.to_bytes(w,'little')
  ram=bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
  if self.colour_source:
   raw=list(map(int,Path(self.palette_source).read_text().split()))
   if len(raw)!=768:raise ValueError('Palette length')
   self.source_rgb=[tuple(raw[i:i+3])for i in range(0,768,3)]
   self.palette=[tuple(round(v*7/255)for v in rgb)for rgb in self.source_rgb]
   if self.painting:self.paint_overrides,self.paint_changes=import_painting(self)
  self.pages,directory=assets(self.colour_source,getattr(self,"asset_mem",bytes(16384)+ram),self.paint_overrides)
  self.pages[34]=bytes(backup).ljust(8192,b"\0")
  self.page[0x1700:0x1700+len(directory)]=directory
  self.page[0x1600:0x1667]=ram[0x52fb:0x5362]
  for page,data in self.pages.items():
   bank=self.extra_banks.setdefault(page//2,bytearray(16384));bank[(page&1)*8192:(page&1)*8192+8192]=data
  if self.colour_source:
   pal=self.palette
  else:
   pal=[]
   for n in range(256):
    ink=n//16;v=7 if ink&8 else 6
    pal.append((v if ink&2 else 0,v if ink&4 else 0,v if ink&1 else 0))
  self.stub_extra+=bytes(v for r,g,b in pal for v in ((r<<5)|(g<<2)|(b>>1),b&1))
  for a,o,n in self.sites:
   if ram[a-0x4000:a-0x4000+len(o)]!=o:raise ValueError('Patch site differs '+hex(a))
   ram[a-0x4000:a-0x4000+len(n)]=n
  for trainer in self.trainers:
   for address,value in TRAINERS[trainer].items():ram[address-0x4000]=value
  snap.banks[5],snap.banks[2],snap.banks[0]=bytes(ram[:16384]),bytes(ram[16384:32768]),bytes(ram[32768:])
  for i,(frm,x,y)in enumerate(getattr(self,'initial_effects',())):
   if i>=80:raise ValueError('Effect seed pool full')
   key=((y<<1)|(y>>7))&255;key^=x^frm
   self.page[0x300+i]=self.page[0x200+key];self.page[0x200+key]=i+1
   self.page[0x1b00+2*i:0x1b02+2*i]=bytes((x,y));self.page[0x1c00+i]=frm;self.page[0x1d00+i]=1
  used=len(getattr(self,'initial_effects',()));self.page[0x400:0x400+80-used]=bytes(range(used,80));self.page[0x1e7c]=80-used
  self.extra_banks[12]=bytes(self.page)+bytes(8192);snap.pc=self.syms['boot_resume']
def build(source,destination,enabled=True,checkpoint=None,k=104,debt=76,colour_source=None,palette_source=None,initial_effects=(),painting=None,trainers=(),loading=None):
 if hashlib.md5(Path(source).read_bytes()).hexdigest()!=SOURCE_MD5:raise ValueError('Unsupported archive')
 patch=Patch(enabled,k,debt,colour_source,palette_source,painting,trainers)
 from skoolkit.snapshot import Snapshot
 from .simrun import addr_view
 patch.asset_mem=bytes(addr_view(Snapshot.get(str(source))))
 patch.initial_effects=list(initial_effects)
 zt.convert(str(checkpoint or source),str(destination),tail_req=0x5b00,quiet=True,patch=patch)
 if loading is not None:
  screen=Path(loading).read_bytes()
  if hashlib.md5(screen).hexdigest()!=LOADING_MD5:raise ValueError('Use the original Exolon loading screen')
  data=Path(destination).read_bytes();head=bytearray(data[:512]);head[10],head[133]=2,50
  Path(destination).write_bytes(bytes(head)+screen+data[512:])
 return patch

def boot_check(nex,source,patch):
 from . import nextboot
 from skoolkit import CSimulator
 from skoolkit.snapshot import Snapshot
 from skoolkit.simutils import from_snapshot
 snap=Snapshot.get(str(source));sim=from_snapshot(CSimulator,snap,config={'int_active':0})
 expected=list(sim.memory);bad=[]
 for a,o,n in patch.sites:expected[a:a+len(n)]=n
 for trainer in patch.trainers:
  for a,v in TRAINERS[trainer].items():expected[a]=v
 banks,_,_=nextboot.load_nex(str(nex))
 rom_patch=copy.copy(patch);rom_patch.page=bytearray(patch.page)
 block=zt.build_tail(zt.Z80Snapshot(str(source)),0x5b00,patch.slot1,True)[3]
 offset=patch.syms['regblock']-0x2000;rom_patch.page[offset:offset+len(block)]=block
 for b in(1,3,4,6,7):
  if bytes(banks[b])!=bytes(sim.memory.banks[b]):bad.append(('unmapped original bank',b))
 for nl in(False,True):
  st=nextboot.boot(str(nex),patch.entry,nexload=nl,sysrom=nextboot.system_rom3()[0])
  bad.extend(('register',nl,i)for i in hooklib.CMP_R if(bool(sim.registers[i])!=bool(st['R'][i])if i==26 else sim.registers[i]!=st['R'][i]))
  if bytes(expected[0x4000:])!=bytes(st['mem'][a]for a in range(0x4000,65536)):bad.append(('RAM',nl))
  for n,img in((0,nextboot.alt_image0(rom_patch)),(1,nextboot.alt_image(rom_patch))):
   if bytes(st['alt'][n])!=bytes(img):bad.append(('hidden ROM',nl,n))
  bad.extend(('ROM access',nl,x)for x in st['bad'])
 return bad
class View:
 def __init__(self,mem,patch=None,page=None):
  self.mem=bytearray(mem);self.patch=patch;self.page=bytearray(page or(patch.page if patch else bytes(8192)));self.model=None
  if patch:
   for a,o,n in patch.sites:self.mem[a:a+len(n)]=n
 def __len__(self):return 65536
 def __getitem__(self,a):
  if isinstance(a,slice):return [self[i]for i in range(*a.indices(65536))]
  if self.patch and 0x2000<=a<0x4000:
   if self.model.nr.get(0x51,255)==24:return self.page[a-0x2000]
   return self.patch.page[a-0x2000]
  if self.patch and 0x8000<=a<0xa000 and self.model.nr.get(0x54,4)!=4:return self.patch.pages[self.model.nr[0x54]][a&8191]
  return self.mem[a]
 def __setitem__(self,a,v):
  if self.patch and 0x2000<=a<0x4000 and self.model.nr.get(0x51,255)==24:self.page[a-0x2000]=v
  elif a>=0x4000:self.mem[a]=v
class Model(hooklib.NextModel):
 def __init__(self,sim,speed=0):super().__init__(sim,speed,lines=311,t_line=228);self.nr[0x51]=255;self.nr[0x54]=4;self.io=[];self.ctc_phase=0;self.ctc_present=True;self.ctc_reads=[]
 def read_port(self,r,p):
  if p==0x1b3b:
   now=self.now();self.ctc_reads.append(now)
   return (-int((now+self.ctc_phase)//32))&255 if self.ctc_present else 255
  return super().read_port(r,p)
 def write_port(self,r,p,v,*a):
  if p==0x1b3b:return
  if p in(0x243b,0x253b,0x303b)or p&255 in(0x57,0x5b):return super().write_port(r,p,v,*a)
  self.io.append((p,v))
def run(mem,regs,patch=None,page=None,speed=0,stop=None,hardware=None,clock_phase=0,clock_present=True):
 from .dizzy6 import _rw_simulator
 Simulator=_rw_simulator()
 v=View(mem,patch,page);s=simpool.machine(Simulator,v,list(regs),'exolon-patched'if patch else'exolon-original');n=Model(s,speed);v.model=n;n.ctc_phase=clock_phase;n.ctc_present=clock_present
 if patch and not hardware and 33 in patch.pages:n.pattern[48*256:58*256]=patch.pages[33][5120:7680]
 if hardware:
  n.pattern[:]=hardware.pattern;n.attrs=[a[:]for a in hardware.attrs]
 r=s.registers;end=stop if stop is not None else v[r[12]]+256*v[(r[12]+1)&65535];sp=r[12]if stop is not None else(r[12]+2)&65535
 if isinstance(stop,tuple):end,sp=stop
 for k in range(2000000):
  if k and r[24]==end and r[12]==sp:return list(r),v,n
  s.opcodes[v[r[24]]]()
 raise ValueError(('hook timeout',hex(r[24]),hex(end),r[12],sp))

def assets(source,mem,overrides=None):
 data=Path(source).read_bytes()if source else None
 if data and hashlib.md5(data).hexdigest()!=COLOUR_MD5:raise ValueError('Unsupported colour source')
 output=bytearray();directory=bytearray()
 for large,frame,flip in [(True,i,f)for f in (False,True)for i in range(24)]+[(False,i,False)for i in range(48)]+[(True,24,False)]:
  w,h,base=(24,32,0xef80+frame*96)if large else(16,16,0xf8e0+frame*32)
  canvas=bytearray([227]*(32*32 if large else 256));stride=32 if large else 16
  for y in range(h):
   for x in range(w):
    q=w-1-x if flip else x;a=base+y*(w//8)+q//8;off=(a&16383)*9
    if data and mem[a]!=data[off+8]:raise ValueError('Graphics mismatch '+hex(a))
    v=sum(((data[off+k]>>(7-q%8))&1)<<k for k in range(8))if data else(1 if mem[a]&(128>>(q%8))else 0)
    if v or mem[a]&(128>>(q%8)):canvas[y*stride+x]=(overrides or {}).get((a,q%8),v)
  directory.extend((26+len(output)//8192,0x80+(len(output)%8192)//256))
  for sy,sx in (((0,0),(0,16),(16,0),(16,16))if large else((0,0),)):
   for y in range(16):output.extend(canvas[(sy+y)*stride+sx:(sy+y)*stride+sx+16])
 for frame in range(8):
  canvas=bytearray([227]*256)
  for y in range(8):
   for x in range(16):
    a=0xed40+64*frame+y*2+x//8;off=(a&16383)*9
    if data and mem[a]!=data[off+8]:raise ValueError('Effect graphics mismatch '+hex(a))
    v=sum(((data[off+k]>>(7-x%8))&1)<<k for k in range(8))if data else(1 if mem[a]&(128>>(x%8))else 0)
    if v or mem[a]&(128>>(x%8)):canvas[y*16+x]=(overrides or {}).get((a,x%8),v)
  output.extend(canvas)
 for value,height in ((mem[0x8301],1),(mem[0x904a]<<6,2)):
  canvas=bytearray([227]*256)
  for y in range(height):
   for x in range(8):
    if value&(128>>x):canvas[y*16+x]=255 if data else 1
  output.extend(canvas)
 return {26+i//8192:bytes(output[i:i+8192]).ljust(8192,b'\xe3')for i in range(0,len(output),8192)},bytes(directory)


def painting_frames():
 i=0
 for kind,base,n,w,h,step in [('player',0xef80,25,24,32,96),('small',0xf8e0,48,16,16,32),('projectile',0xed40,8,16,8,64)]:
  for frame in range(n):
   yield dict(kind=kind,index=frame,addr=base+step*frame,w=w,h=h,x=i%12*40,y=i//12*48)
   i+=1

def source_pixel(data,mem,a,bit):
 off=(a&16383)*9
 if data[off+8]!=mem[a]:raise ValueError('Colour graphics differ at '+hex(a))
 return sum(((data[off+k]>>(7-bit))&1)<<k for k in range(8))

def import_painting(patch):
 from PIL import Image
 path=Path(patch.painting)
 if path.is_dir():path=path/'EXOLON_PAINTING_SPRITES.png'
 im=Image.open(path).convert('RGBA')
 if im.size!=(480,336):raise ValueError('Keep the native480x336 Exolon sheet')
 data=Path(patch.colour_source).read_bytes();mem=patch.asset_mem
 if hashlib.md5(data).hexdigest()!=COLOUR_MD5:raise ValueError('Unsupported colour master')
 pixels=[];used={0,227,255};occupied=set()
 for f in painting_frames():
  for y in range(f['h']):
   for x in range(f['w']):
    a=f['addr']+y*(f['w']//8)+x//8;bit=x%8;old=source_pixel(data,mem,a,bit)
    opaque=bool(old or mem[a]&(128>>bit));used.add(old)
    pos=(f['x']+x,f['y']+y);occupied.add(pos);pixels.append((a,bit,old,opaque,im.getpixel(pos)))
 changes={}
 for a,bit,old,opaque,pixel in pixels:
  if pixel[3]not in(0,255):raise ValueError('Partial alpha in Exolon figure')
  if bool(pixel[3])!=opaque:raise ValueError('Keep the original Exolon figure edge')
  if not opaque or pixel[:3]==patch.source_rgb[old]:continue
  rgb=tuple(round(v*7/255)for v in pixel[:3])
  index=next((i for i,c in enumerate(patch.palette)if i!=227 and c==rgb),None)
  if index is None:
   index=next((i for i in range(256)if i not in used),None)
   if index is None:raise ValueError('Exolon palette has no free opaque entry')
   patch.palette[index]=rgb
  used.add(index);changes[a,bit]=index
 if any(im.getpixel((x,y))[3]for y in range(336)for x in range(480)if(x,y)not in occupied):raise ValueError('Paint outside Exolon figure cells')
 return changes,len(changes)

def painting_sheets(patch,destination):
 from PIL import Image
 folder=Path(destination);folder.mkdir(parents=True,exist_ok=True);path=folder/'EXOLON_PAINTING_SPRITES.png'
 if path.exists():return
 data=Path(patch.colour_source).read_bytes();mem=patch.asset_mem;im=Image.new('RGBA',(480,336));frames=list(painting_frames())
 for f in frames:
  for y in range(f['h']):
   for x in range(f['w']):
    a=f['addr']+y*(f['w']//8)+x//8;v=source_pixel(data,mem,a,x%8)
    if v or mem[a]&(128>>(x%8)):im.putpixel((f['x']+x,f['y']+y),(*patch.source_rgb[v],255))
 im.save(path);path.with_suffix('.layout.json').write_text(json.dumps(dict(schema=1,frames=frames,palette=patch.source_rgb),indent=2)+'\n')

# Independent absolute-coordinate oracle. It reads the supplied graphics, not
# the build's pattern directory, owner tables or generated asset banks.
class PixelOracle:
 def __init__(self,patch):
  self.overrides=patch.paint_overrides
  self.mem=patch.asset_mem;self.col=Path(patch.colour_source).read_bytes()if patch.colour_source else None
  self.groups={};self.owners={};self.effects={};self.free=list(range(80));self.colours=[15]*128;self.pending=None;self.last=None
 def colour(self,slot,pos):
  self.last=(slot,pos)
  if self.pending and self.pending[0]==pos:self.colours[slot]=self.pending[1];self.pending=None
 def picture(self,base,w,h,flip=False,literal=None):
  out={}
  for y in range(h):
   for x in range(w):
    q=w-1-x if flip else x;a=base+y*(w//8)+q//8;bit=128>>(q%8)
    if literal is not None:
     if literal&bit:out[x,y]=255 if self.col else 1
     continue
    mono=self.mem[a];off=(a&16383)*9
    colour=sum(((self.col[off+k]>>(7-q%8))&1)<<k for k in range(8))if self.col else(1 if mono&bit else 0)
    if colour or mono&bit:out[x,y]=self.overrides.get((a,q%8),colour)
  return out
 def event(self,pc,mem,r):
  if pc in(0xb04b,0xb061):
   self.groups.clear();self.owners.clear();self.effects.clear();self.free=list(range(80));self.pending=None;self.last=None;return
  pos=(r[5]*2,r[4]);frame=r[0];owner=(r[6]<<8)|r[7]
  if pc in(0x7c5f,0x7c77,0x7c8f):
   if self.col:return
   colour=(r[3]&7)|((r[3]>>3)&8);self.pending=(pos,colour)
   if self.last and self.last[1]==pos:
    slot=self.last[0];self.colours[slot]=colour
    for s,item in self.groups.items():
     if item['owner']==slot:item['colour']=colour
   return
  if pc==0x9e85:return
  if pc in(0x92fb,0x82fc,0x903d):
   frame={0x82fc:8,0x903d:9}.get(pc,frame)
   if frame==6:return
   key=(frame,pos)
   if key in self.effects:
    slot=self.effects.pop(key);self.groups.pop(slot,None);self.free.append(slot-48);return
   slot=48+self.free.pop();self.effects[key]=slot;self.colour(slot,pos)
   if frame>=8:self.colours[slot]=15
   image=self.picture(0xed40+64*frame,16,8)if frame<8 else self.picture(0,8,1 if frame==8 else 2,literal=self.mem[0x8301]if frame==8 else self.mem[0x904a]<<6)
   self.groups[slot]=dict(pos=pos,pixels=image,colour=self.colours[slot],owner=slot);return
  if owner==0xb101:return
  if pc==0x76da:
   if frame>24 or(frame==24 and owner not in(0xb201,0xb281,0xb301,0xb381)):return
   slot=0 if frame<24 else ((owner-0xb181)//128)*4
   image=self.picture(0xef80+96*frame,24,32,frame<24 and bool(mem[0x7bda]));parts=4
  else:
   if owner==0xb181:slot=0
   else:
    if owner not in self.owners:
     if frame==0:return
     self.owners[owner]=20+len(self.owners)
    slot=self.owners[owner]
   for s in range(slot,slot+(4 if slot==0 else 1)):self.groups.pop(s,None)
   if frame==0:return
   image=self.picture(0xf8e0+32*frame,16,16);parts=1
  self.colour(slot,pos)
  for part in range(parts):
   dx=(part%2)*16 if parts==4 else 0;dy=(part//2)*16 if parts==4 else 0;x,y=pos[0]+dx,pos[1]+dy
   if x>=256:self.groups.pop(slot+part,None);continue
   pixels={}
   for (px,py),v in image.items():
    sx,sy=pos[0]+px,pos[1]+py
    if dx<=px<dx+16 and dy<=py<dy+16 and sy<176 and mem[0x5b00+(sy//8)*32+(sx//8)]&(128>>(sx%8)):pixels[px-dx,py-dy]=v
   self.groups[slot+part]=dict(pos=(x,y),pixels=pixels,colour=self.colours[slot],owner=slot)
 def compare(self,hardware):
  errors=[]
  for slot,attrs in enumerate(hardware.attrs):
   want=self.groups.get(slot);shown=bool(attrs[3]&128)
   if shown!=(want is not None):errors.append(('visible',slot,shown,want is not None));continue
   if not shown:continue
   pos=((attrs[0]|((attrs[2]&1)<<8))-32,attrs[1]-32)
   pixels={(i%16,i//16):v for i,v in enumerate(hardware.slot(attrs[3]&63))if v!=227}
   if pos!=want['pos']:errors.append(('position',slot,pos,want['pos']))
   if pixels!=want['pixels']:errors.append(('pixels',slot,len(pixels),len(want['pixels'])))
   colour=attrs[2]>>4;expected=0 if self.col else want['colour']
   if colour!=expected:errors.append(('colour',slot,colour,expected))
  return errors

CMP=hooklib.CMP_R
EVENTS={0x76da,0x795c,0x92fb,0x82fc,0x903d,0xb04b,0xb061,0x7c5f,0x7c77,0x7c8f,0x9e85}
ROM_DELAY_BYTES=bytes.fromhex('C5D5E5210000110000EDB0E1D1C1C9')
ROM_DELAY_KNOWN=((1,0x2000,0x3fff,'B0C0 self-copy delay only; replay guard and whole-loop ABI/time proof'),)
def rom_delay_read_safe(a,pc,r):
 hl=r[6]*256+r[7];de=r[4]*256+r[5];bc=r[2]*256+r[3]
 # LDIR writes each byte back to itself. Final flags depend on the LAST
 # byte; require that byte to be unchanged game RAM, not the replaced ROM.
 return pc==0xb0c0 and hl==de==a and ((hl+(bc or 65536)-1)&65535)>=0x4000 and not r[26]

def rom_delay_audit(recording,stop=None):
 from .simrun import play_rzx,rzx_frames
 class Audit:
  def __init__(self):self.reads=0;self.bad=[]
  def on_sim(self,sim):
   self.sim=sim
   if bytes(sim.memory[a]for a in range(0xb0b7,0xb0c6))!=ROM_DELAY_BYTES:self.bad.append('Delay code differs')
  def on_read(self,a,pc,mem):
   if 0x2000<=a<0x4000:
    self.reads+=1
    if not rom_delay_read_safe(a,pc,self.sim.registers)and len(self.bad)<8:self.bad.append((hex(a),hex(pc)))
  def on_desync(self,f,msg):self.bad.append(('desync',f,msg))
 audit=Audit();frames=play_rzx(str(recording),audit,stop=stop);total=rzx_frames(str(recording))[0]
 want=min(total,stop)if stop else total
 if frames<want:audit.bad.append(('partial',frames,want))
 return dict(frames=min(frames,want),rom_delay_reads=audit.reads,errors=audit.bad)

CAPTURE_EVENTS={0x9576,0xb0b7}
def verify(patch,rzx_path,stop=None,collect=0,progress=None):
 from collections import Counter
 from .rzx import trace
 counts=Counter();examples=[];states={};page=None;hardware=None;oracle=PixelOracle(patch)
 def hit(pc,sim):
  nonlocal page,hardware
  r=list(sim.registers);mem=bytes(sim.memory)
  if pc==0xb0b7:
   cases=states.setdefault(pc,[])
   if collect and not any(q[2:4]==r[2:4]for _,q in cases):cases.append((mem,r))
   return
  if pc in CAPTURE_EVENTS:
   if collect and len(states.setdefault(pc,[]))<8 and (r[5]+mem[(r[6]*256+r[7])+1])%256<120 and (r[4]+mem[(r[6]*256+r[7])+2])%256<169:states[pc].append((mem,r))
   return
  if pc==0x92fb and mem[r[12]]+256*mem[r[12]+1]==0x9e95:return
  if collect and len(states.setdefault(pc,[]))<collect:states[pc].append((mem,r))
  ro,vo,no=run(mem,r);rp,vp,n=run(mem,r,patch,page,hardware=hardware)
  bad=[('register',i,ro[i],rp[i])for i in CMP if ro[i]!=rp[i]]
  expected=bytearray(vo.mem)
  for a,o,z in patch.sites:expected[a:a+len(z)]=z
  if expected[0x4000:]!=vp.mem[0x4000:]:bad.append(('RAM',))
  if no.io!=n.io:bad.append(('ports',))
  if n.nr[7]or n.nr[0x51]!=255 or n.nr[0x54]!=4:bad.append(('mapping',))
  if n.c['upload into a shown pattern!']:bad.append(('visible upload',))
  if vp.page[0x1e6a]:bad.append(('pool overflow',))
  oracle.event(pc,mem,r);bad.extend(oracle.compare(n))
  counts[f'{pc:04x}']+=1
  counts['hooks']+=1;counts['R comparisons']+=1;counts['RAM bytes compared']+=49152
  if bad:
   for kind,*_ in bad:counts[kind+'!']+=1
   if len(examples)<5:examples.append(dict(pc=hex(pc),frame=sim.tracer.context.frame_count,bad=bad[:8]))
   if len(examples)==5:raise ValueError(examples)
  page=bytes(vp.page);hardware=n
  if progress and counts['hooks']%1000==0:progress(f"frame{sim.tracer.context.frame_count}, {counts['hooks']} hooks")
 frames,desync=trace(str(rzx_path),EVENTS|CAPTURE_EVENTS,hit,stop=stop)
 counts['frames']=frames
 if desync:counts['replay desync!']+=1;examples.append(desync)
 return (counts,examples,states)if collect else(counts,examples)

def compare_case(patch,mem,r,speed=0,page=None,hardware=None,**kw):
 ro,vo,no=run(mem,r,speed=speed,**{k:v for k,v in kw.items()if k=='stop'})
 rp,vp,n=run(mem,r,patch,page,speed=speed,hardware=hardware,**kw)
 bad=[('register',i)for i in CMP if ro[i]!=rp[i]]
 expected=bytearray(vo.mem)
 for a,o,z in patch.sites:expected[a:a+len(z)]=z
 if expected[0x4000:]!=vp.mem[0x4000:]:bad.append(('RAM',))
 if no.io!=n.io:bad.append(('ports',))
 if n.nr[7]!=speed or n.nr[0x51]!=255 or n.nr[0x54]!=4:bad.append(('mapping',))
 if n.c['upload into a shown pattern!']:bad.append(('visible upload',))
 return bad,vp,n,np_delta(no,n)

def np_delta(original,patched):return patched.now()-original.now()

def unit_tests(patch,states):
 from collections import Counter
 counts=Counter();patch.unit_failures=[]
 def check(name,bad):
  counts[name+' cases']+=1
  if bad:counts[name+'!']+=1
 for pc in EVENTS:
  if not states.get(pc):counts['missing ABI state!']+=1;continue
  m,base=states[pc][0]
  for speed in range(4):
   for iff in(0,1):
    for refresh in(0,1,126,127,128,129,254,255):
     r=list(base);r[15]=refresh;r[26]=iff
     bad,_,_,_=compare_case(patch,m,r,speed);check('ABI',bad)
 # Enumerate every stored figure/frame, both player directions, clipping
 # edges and a nontrivial independent foreground mask. No replay table reused.
 if not states.get(0x76da)or not states.get(0x795c):counts['missing pixel state!']+=1
 else:
  for pc,frames in((0x76da,range(25)),(0x795c,range(48)),(0x92fb,range(6)),(0x82fc,(0,)),(0x903d,(0,))):
   if not states.get(pc):counts['missing pixel state!']+=1;continue
   memory,base=states[pc][0]
   for frame in frames:
    for x,y in((0,0),(19,57),(119,153),(127,175)):
     for flip in(range(2)if pc==0x76da and frame<24 else(0,)):
      m=bytearray(memory);r=list(base);r[0]=frame;r[5]=x;r[4]=y;r[6:8]=[0xb1,0x81];r[12]=0xff00;m[0xff00:0xff02]=b'\x00\x70';m[0x7bda]=flip
      m[0x5b00:0x5dc0]=bytes(255 if i%3 else 0 for i in range(704))
      if pc==0x795c:r[6:8]=[0xb1,0x41] # ordinary enemy owner, not the player's4-slot group
      if pc==0x76da and frame==24:r[6:8]=[0xb2,0x01] # the first original fixture owner
      bad,v,n,_=compare_case(patch,m,r);oracle=PixelOracle(patch);oracle.event(pc,m,r);bad.extend(oracle.compare(n));check('source pixel',bad)
      if bad:patch.unit_failures.append(dict(group='pixels',pc=hex(pc),frame=frame,x=x,y=y,flip=flip,bad=bad[:5]))
 # Initialisation/reset must empty both render and XOR owner tables.
 if states.get(0xb061):
  m,r=states[0xb061][0];dirty=bytearray(patch.page);dirty[0x1800:0x1880]=b'\x55'*128;dirty[0x200:0x400]=b'\x55'*512;dirty[0x1d00:0x1d50]=b'\x01'*80
  bad,v,n,_=compare_case(patch,m,r,page=dirty)
  if n.visible()or any(v.page[0x1800:0x1880])or any(v.page[0x200:0x400])or v.page[0x1e7c]!=80:bad.append(('reset state',))
  check('reset lifecycle',bad)
 # Whole original two-plot/palette/noise iteration, not just FE event counts.
 if not states.get(0x9576):counts['missing noise state!']+=1
 for m,r in states.get(0x9576,[]):
  p=copy.deepcopy(patch);p.initial_effects=[]
  frame,x,y=2,r[5],r[4];key=(((y<<1)|(y>>7))&255)^x^frame
  p.page[0x200:0x400]=bytes(512);p.page[0x200+key]=1;p.page[0x1b00:0x1b02]=bytes((x,y));p.page[0x1c00]=frame;p.page[0x1d00]=1;p.page[0x400:0x44f]=bytes(range(1,80));p.page[0x1e7c]=79
  for phase in range(32):
   bad,_,_,delta=compare_case(p,m,r,stop=(0x95a5,r[12]+2),clock_phase=phase)
   if abs(delta)>64:bad.append(('noise deadline',delta))
   check('noise phase',bad)
  q=copy.deepcopy(p);off=q.syms['effect_clock_wait']-8192
  for old,new in([(21,31)]if p.colour_source else[(13,23),(14,24)]):
   at=q.page.index(bytes((0x1e,old)),off);q.page[at+1]=new
  _,_,_,delta=compare_case(q,m,r,stop=(0x95a5,r[12]+2));counts['negative late deadline'+(' caught'if abs(delta)>300 else'!')]+=1
 # Missing or stalled timer must terminate and preserve the original ABI.
 if states.get(0x92fb):
  m,r=states[0x92fb][0]
  for ready in(0,1):
   p=copy.deepcopy(patch);p.page[0x1eb0]=ready
   bad,_,_,_=compare_case(p,m,r,clock_present=False);check('absent clock',bad)
  r=list(r);r[0]=2;p=copy.deepcopy(patch);p.page[0x1e7c]=0
  bad,v,n,_=compare_case(p,m,r)
  if v.page[0x1e6a]!=1 or v.page[0x1e7c]!=0 or n.visible():bad.append(('full effect pool',))
  check('full effect pool',bad)
  q=copy.deepcopy(p);off=q.page.index(bytes.fromhex('3A7C3EB720'));q.page[off+4]=0x18
  _,v,n,_=compare_case(q,m,r);counts['negative pool guard'+(' caught'if v.page[0x1e6a]!=1 or v.page[0x1e7c]!=0 or n.visible()else'!')]+=1
 if states.get(0x795c):
  m,r=states[0x795c][0];r=list(r);r[0]=1;r[6:8]=[0xb5,0x81];p=copy.deepcopy(patch)
  p.page[0x1800:0x1838]=b'\x22\x22'*28
  bad,v,n,_=compare_case(p,m,r)
  if v.page[0x1e6a]!=1 or n.visible():bad.append(('full owner table',))
  check('full owner table',bad)
 if states.get(0x76da):
  m=bytearray(states[0x76da][0][0]);r=list(states[0x76da][0][1]);r[0]=0;r[5]=20;r[4]=64;r[6:8]=[0xb1,0x81];m[0x7bda]=0;m[0x5b00:0x5dc0]=bytes(255 if i%3 else 0 for i in range(704))
  def negative(name,q,speed=0):
   bad,v,n,_=compare_case(q,m,r,speed);oracle=PixelOracle(patch);oracle.event(0x76da,m,r);bad.extend(oracle.compare(n));counts['negative '+name+(' caught'if bad else'!')]+=1
  q=copy.deepcopy(patch);at=q.page.index(bytes.fromhex('3A633EC620'));q.page[at+4]=33;negative('position',q)
  q=copy.deepcopy(patch);at=q.page.index(bytes.fromhex('CB23CB127E2338'));q.page[at+6]=0x18;negative('foreground mask',q)
  q=copy.deepcopy(patch);q.page[:]=q.page.replace(bytes.fromhex('3EE8'),bytes.fromhex('3EE9'));negative('R',q)
  q=copy.deepcopy(patch);q.page[:]=q.page.replace(bytes.fromhex('ED9151FF'),bytes.fromhex('ED915118'));negative('MMU',q)
  q=copy.deepcopy(patch);q.page[:]=q.page.replace(bytes.fromhex('3A043EED9207'),bytes.fromhex('AF0000ED9207'));negative('speed restore',q,2)
  q=copy.deepcopy(patch);data=bytearray(q.pages[26]);at=next(i for i,v in enumerate(data[:1024])if v!=227);data[at]=(data[at]+1)%227;q.pages[26]=bytes(data);negative('source pixel',q)
 counts.update(unit_trainers(patch.asset_mem,states))
 # B0B7 is unchanged original code, not an added hook. The ROM audit may
 # exempt its self-copy reads only after its observable ABI/time agree.
 if not states.get(0xb0b7):counts['missing ROM delay state!']+=1
 for m,base in states.get(0xb0b7,[]):
  for a in(0,7,255):
   r=list(base);r[0]=a
   bad,_,_,delta=compare_case(patch,m,r)
   if delta:bad.append(('delay time',delta))
   check('ROM self-copy delay',bad)
 r=[0]*32;r[6:8]=r[4:6]=[0x20,0];r[2:4]=[0xe0,0]
 if not rom_delay_read_safe(0x2000,0xb0c0,r):counts['ROM read guard!']+=1
 for name,pc,change in(('consumer',0x9000,{}),('different destination',0xb0c0,{5:1}),('ROM final byte',0xb0c0,{2:0,3:1}),('interruptible delay',0xb0c0,{26:1})):
  q=list(r)
  for i,v in change.items():q[i]=v
  counts['negative ROM '+name+(' caught'if not rom_delay_read_safe(0x2000,pc,q)else'!')]+=1
 return counts

def unit_trainers(memory,states):
 from collections import Counter
 counts=Counter();base=list(next(iter(states.values()))[0][1])
 for counter in(1,7,99):
  for name,pc,stop,var in [('Infinite lives',0x9d1a,0x9d21,0x8e7a),('Infinite ammo',0x836b,0x8372,0x8e5a),('Infinite grenades',0x924d,0x9254,0x8e66)]:
   m=bytearray(memory);r=base[:];r[24]=pc;r[12]=0xff00;m[0xff00:0xff02]=b'\x00\x70';m[var]=counter
   _,a,_=run(m,r,stop=stop)
   for at,value in TRAINERS[name].items():m[at]=value
   _,b,_=run(m,r,stop=stop);counts['trainer behaviour cases']+=1
   if a[var]!=counter-1 or b[var]!=counter:counts['trainer behaviour!']+=1
 for name,pc in [('Mines harmless',0x9caa),('Immunity',0x9caf)]:
  m=bytearray(memory);r=base[:];r[24]=pc;r[12]=0xff00;m[0xff00:0xff02]=b'\x00\x70'
  for at in(0x9ed8,0x9ce2,0x768d):m[at]=0
  m[0x82f5:0x82f7]=bytes((20,80));_,a,_=run(m,r)
  for at,value in TRAINERS[name].items():m[at]=value
  _,b,_=run(m,r);counts['trainer behaviour cases']+=1
  if a[0x9ce2]!=46 or b[0x9ce2]!=0:counts['trainer behaviour!']+=1
 return counts

def auto(a,z80,name,out,say):
 from . import nextboot,runchecks
 out=Path(out);out.mkdir(parents=True,exist_ok=True);inputs=Path(z80).resolve().parent
 colour=inputs/'colour-source.256';palette=inputs/'source-palette.pal';loading=inputs/'EXOLON.scr';painting=os.environ.get('NEXCLASH_EXOLON_PAINTING')
 for key,value in dict(patch_by='Jon Attree',title='Exolon',publisher='Hewson Consultants,1987',colours_by='Jao Paulo (Spec256)',fix_label='Colour clash').items():
  if not getattr(a,key,None):setattr(a,key,value)
 from skoolkit.snapshot import Snapshot
 from .simrun import addr_view
 memory=bytes(addr_view(Snapshot.get(str(z80))));pok=''
 for title,items in TRAINERS.items():
  pok+='N'+title+'\n'+''.join(('Z'if i==len(items)-1 else'M')+f' 8 {address} {value} {memory[address]}\n'for i,(address,value)in enumerate(items.items()))
 pok+='Y\n';trainer_path=out/(name+'_verified.pok');trainer_path.write_text(pok)
 if getattr(a,'pok',None)and Path(a.pok).read_text()!=pok:raise ValueError('Use the verified Exolon trainers generated by this engine')
 a.pok=str(trainer_path);ok=True;patches=[];say('Game      : '+name)
 for label,suffix,enabled,enhanced in(('Plain','',False,False),('Sprites','_sprites',True,False),('Enhanced','_enhanced',True,True)):
  path=out/(name+suffix+'.nex');options=dict(enabled=enabled,colour_source=colour if enhanced else None,palette_source=palette,painting=painting if enhanced else None)
  patch=build(z80,path,**options);bad=boot_check(path,z80,patch);ok &= not bad
  say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK'if not bad else bad))
  if enabled:
   loaded=out/(name+suffix+'_loading.nex');build(z80,loaded,loading=loading,**options);bad=boot_check(loaded,z80,patch);ok &= not bad;patches.append(patch)
   if bad:say('Loading   : '+str(bad))
  if enhanced and not painting:painting_sheets(patch,out)
 recordings=list(getattr(a,'rzx',None)or[])
 for patch in patches:
  states={};mode='enhanced'if patch.colour_source else'default'
  for recording in recordings:
   counts,examples,captured=verify(patch,recording,stop=getattr(a,'quick',None),collect=1,progress=lambda s:say('Progress  : '+mode+' '+s))
   for pc,cases in captured.items():
    if cases and (pc not in states or len(cases)>len(states[pc])):states[pc]=cases
   ok &= not examples and not any(v for k,v in counts.items()if k.endswith('!'))
   say('Verify    : %s %s %s'%(Path(recording).name,mode,dict(counts)))
   (out/(name+'_'+Path(recording).stem+'_'+mode+'_verification.json')).write_text(json.dumps(dict(counts=counts,examples=examples),indent=2)+'\n')
  if recordings:
   units=unit_tests(patch,states);ok &= not any(v for k,v in units.items()if k.endswith('!'))
   say('Unit      : '+mode+' '+str(dict(units)));say('Coverage  : '+mode+' '+','.join(hex(k)for k in sorted(states)))
   (out/(name+'_'+mode+'_units.json')).write_text(json.dumps(dict(counts=units,examples=patch.unit_failures),indent=2)+'\n')
 if recordings:
  nexes=sorted(str(p)for p in out.glob(name+'*.nex'))
  audits={Path(r).name:rom_delay_audit(r,getattr(a,'quick',None))for r in recordings}
  guarded=all(not r['errors']for r in audits.values());ok &= guarded
  say('ROM delay : '+str(audits));(out/(name+'_rom_delay_audit.json')).write_text(json.dumps(audits,indent=2)+'\n')
  runchecks.add(runchecks.RUN,'rom_self_copy_delay','pass'if guarded else'fail','All replaced-ROM reads are unmodified B0C0 self-copies, DI, ending in RAM'if guarded else str(audits))
  report=nextboot.rom_paths(nexes,recordings,stop=getattr(a,'quick',None),z80=str(z80),known=ROM_DELAY_KNOWN if guarded else())
  status,why,coverage=runchecks.rom_paths(report,recordings,nexes);runchecks.add(runchecks.RUN,'rom_paths',status,why,coverage=coverage);ok &= status=='pass'
  for result in report.values():
   for line in result[1]:say('ROM paths : '+line)
 say('Result    : '+('PASSED'if ok else'FAILED'));return bool(ok)
