"""Pentagram owner-colour compiler. Graphics are read from the caller's original game."""
from pathlib import Path
import json,hashlib
from . import coloursheet as CS,recolour as RC
ROOT=Path(__file__).resolve().parents[1]
COLOURS=ROOT/'docs/profiles/pentagram_colours.json'
def art_profile():return json.loads((ROOT/'docs/profiles/pentagram_art.json').read_text())
def load_colours(path=None):return CS.load(str(path or RC.build_colours_path(str(COLOURS))))
def canonical_memory(peek):
 m=bytearray(peek(a)for a in range(65536));seen=set()
 for r in art_profile()['graphics']:
  p,w,h=r['addr'],r['width'],r['height']
  if p in seen:continue
  seen.add(p)
  if (m[p]&15)*8!=w or m[p+1]!=h:raise ValueError('Pentagram graphic geometry differs at %04X'%p)
  rel=(m[p]^r['flags'])&192;rows=[]
  for y in range(h):
   row=[list(m[p+2+(y*(w//8)+x)*2:p+4+(y*(w//8)+x)*2])for x in range(w//8)]
   if rel&64:row=[[int(f'{v:08b}'[::-1],2)for v in pair]for pair in row[::-1]]
   rows.append(row)
  if rel&128:rows.reverse()
  raw=bytes(v for row in rows for pair in row for v in pair);m[p+2:p+2+len(raw)]=raw;m[p]=(m[p]&63)|(r['flags']&192)
 return m

def compile_pages(peek,colours=None):
 m=canonical_memory(peek);meta=art_profile();records=meta['graphics'];byid={r['id']:r for r in records};byaddr={r['addr']:r for r in records}
 colour=load_colours()if colours is None else colours;fills=meta['approved_interior_fills'];fillkeys={(r['key'],r['bit']):r['palette_index']for r in fills};palette=meta['palette'];static=set(meta['static_ids'])
 allowed={f"{r['addr']:04x}:{y:02x}:{x}":r['addr']for r in records for y in range(r['height'])for x in range(r['width']//8)}
 for key,entry in colour.items():
  if key not in allowed or entry[:2]!=[allowed.get(key),2]or len(entry)<3 or len(entry[2])!=8 or any(not isinstance(v,int)or not 0<=v<16 for v in entry[2]):raise ValueError('Invalid Pentagram colour entry: '+key)
  if len(entry)>3 and entry[3]:raise ValueError('Pentagram sheets edit colours, not original opaque masks: '+key)
 # Work52..57, displays58..63+70..75, directory76/77, hardware cache88/89.
 available=list(range(28,52))+list(range(64,70))+list(range(86,88))+list(range(90,94))
 pages={p:bytearray(8192)for p in available};current=0;offset=0;used=set();locations={};srcstats=[];canonical={};exception_rows={}
 for ptr,r in byaddr.items():
  w,h=r['width'],r['height'];pixels=[];exceptions=[]
  for dy in range(h):
   y=h-1-dy
   for x in range(w):
    a=ptr+2+(dy*(w//8)+x//8)*2;mask,ink=m[a:a+2];bit=128>>(x&7);key=f'{ptr:04x}:{y:02x}:{x//8}';entry=colour.get(key);idx=entry[2][x&7]if entry else 0
    if entry:assert entry[:2]==[ptr,2],(key,entry[:2])
    opaque=bool((mask|ink)&bit)
    if not opaque:
     if idx:
      assert (key,x&7)in fillkeys,('unapproved exterior paint',key,x&7,idx)
      opaque=True
     else:idx=255
    if opaque:
     idx=idx or(2 if ink&bit else 1)
     assert 0<=idx<16,(key,idx)
    pixels.append(idx)
    if ink&bit and not mask&bit:exceptions.append((x,dy))
  canonical[ptr]=bytes(pixels);exception_rows[ptr]=exceptions
  for flip in (0,1):
   xs=[pixels[dy*w+(w-1-x if flip else x)]for dy in range(h)for x in range(w)]
   for tag in (0,128):
    raw=bytes(v|tag if v!=255 else 255 for v in xs);key=(ptr,flip,tag)
    if offset+len(raw)>8192:current+=1;offset=0
    assert current<len(available),'1MB source page budget'
    page=available[current];pages[page][offset:offset+len(raw)]=raw;used.add(page);locations[key]=(page,offset);offset+=len(raw)
  srcstats.append(dict(ptr=ptr,width=w,height=h,exceptions=exceptions))
 # The populated IDs stop atAB. Unused rowsB0..FF are checked before lookup and
 # contain tiny exception lists, retaining one8K directory per source role.
 for role,page in [('world',76),('hud',77)]:
  directory=bytearray(8192);ep=0x1600;shared={}
  for gid,r in byid.items():
   ptr,w,h=r['addr'],r['width'],r['height'];tag=128 if role=='hud'or gid in static else 0
   for flag in (0,64,128,192):
    rel=flag^r['flags'];flip=bool(rel&64);p,off=locations[ptr,int(flip),tag];exc=[]
    for x,y in exception_rows[ptr]:exc.append((w-1-x if flip else x,h-1-y if rel&128 else y))
    ekey=tuple(exc)
    if not exc:xp=0
    elif ekey in shared:xp=shared[ekey]
    else:
     raw=bytes([len(exc)]+[v for xy in exc for v in xy]);xp=ep;directory[ep:ep+len(raw)]=raw;ep+=len(raw);shared[ekey]=xp
    at=gid*32+(flag>>6)*8;directory[at:at+8]=bytes([p,off&255,off>>8,w,h,(rel&128)|(tag>>7),xp&255,xp>>8])
  assert ep<=8192
  pages[page]=directory
 for p in list(pages):
  if p in available and p not in used:del pages[p]
 for p in list(range(52,64))+list(range(70,76))+list(range(78,84)):pages[p]=bytearray([255])*8192
 for p in (88,89):pages[p]=bytearray(8192)
 pal=[]
 for i in range(256):
  if i in (254,255):pal.extend((0xE3,1));continue
  r,g,b=palette[i&127]if(i&127)<len(palette)else(0,0,0)
  rr,gg,bb=round(r*7/255),round(g*7/255),round(b*7/255);pal.extend((rr*32+gg*4+(bb>>1),bb&1))
 return {p:bytes(raw)for p,raw in pages.items()},bytes(pal)

def colour_identity(peek):
 m=canonical_memory(peek);meta=art_profile();records={r['addr']:r for r in meta['graphics']};raw=b''.join(bytes(m[p:p+2+r['width']*r['height']//4])for p,r in sorted(records.items()))
 return dict(schema=1,game='pentagram',engine='pentagram',keys='pentagram-canonical-mask-ink-v1: pointer:top-down-row:byte-column; bit=left-to-right pixel',inputs=hashlib.md5(raw).hexdigest(),geometry=hashlib.md5(json.dumps(meta['graphics'],sort_keys=True).encode()).hexdigest())

def group(gid):
 if gid in range(2,6):return 'border'
 if gid in(6,7,12,13,14,15):return 'trees'
 if gid in(8,9)or gid in range(0x34,0x3a):return 'stone'
 if gid in(0xa,0x49):return 'wood'
 if gid in range(0x20,0x30):return 'wizard'
 if gid in(0x30,0x31):return 'ghost'
 if gid in range(0x90,0x95):return 'runes'
 if gid in range(0xa0,0xac)or gid in(0x50,0x51,0x56):return 'creatures'
 return 'magic_effects'if gid in range(0x3a,0x3f)or gid in range(0x40,0x49)or gid in range(0x80,0x90)or gid in range(0x95,0x98)else'objects'

def composites(peek):
 import copy
 m=canonical_memory(peek);records=art_profile()['graphics'];byid={r['id']:r for r in records};parts={}
 for r in records:
  p,w,h=r['addr'],r['width'],r['height']
  if p in parts:continue
  pixels=[];entries={}
  for y in range(h):
   for x in range(w):
    a=p+2+((h-1-y)*(w//8)+x//8)*2;mask,ink=m[a:a+2];bit=128>>(x&7);code=1 if ink&bit else 2 if mask&bit else 0;key=f'{p:04x}:{y:02x}:{x//8}';entries[key]=[p,2];pixels.append((x,y,key,x&7,code,2 if code==1 else 1 if code==2 else 0))
  parts[p]=dict(id=r['id'],size=h,w=w,h=h,x=0,y=0,mir=0,dx=0,dy=0,dmir=0,vmir=0,pixels=pixels,entries=entries,group=group(r['id']))
 result=[];used=set()
 for n in range(8):
  up,low=byid[0x28+n],byid[0x20+n];u=copy.deepcopy(parts[up['addr']]);b=copy.deepcopy(parts[low['addr']]);b['dy']=22;result.append(dict(group='wizard',count=1,parts=[b,u]));used.update((up['addr'],low['addr']))
 for p,part in parts.items():
  if p not in used:result.append(dict(group=part['group'],count=1,parts=[part]))
 order=['wizard','creatures','ghost','objects','magic_effects','runes','stone','trees','wood','border'];result.sort(key=lambda q:order.index(q['group']));return result

def sheets(game,out_dir,prefix='pentagram',colours=None,say=print):
 from skoolkit.snapshot import Snapshot
 mem=Snapshot.get(str(game)).memory;peek=lambda a:mem[a];out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);comps=composites(peek);cmap=load_colours()if colours is None else colours;palette=[tuple(c)for c in art_profile()['palette']];ident=colour_identity(peek);result=[]
 for suffix,unique in(('PAINTING_SPRITES',True),('REFERENCE_ALL_SPRITES',False)):
  name=out/(prefix+'_'+suffix);png=Path(str(name)+'.png');layout=Path(str(name)+'_layout.json')
  if png.exists()or layout.exists():raise FileExistsError('Refusing to overwrite an editable sheet: '+str(name))
  n=CS.write(comps,str(png),str(layout),palette,colours=cmap,width=320,unique=unique,paint_clear=True,identity=ident);result.append(n)
 say('Sheets    : %d painting composites, %d reference composites'%tuple(result));return tuple(result)


RECOLOUR={'game':'pentagram','output':'enhanced','colours':'docs/profiles/pentagram_colours.json','clear':False,
 'note':'Canonical original mask/ink pixels; owner-approved colours. One explicitly approved enclosed rune pinhole may be painted; exterior pixels are rejected.'}

def recolour(nex,cmap):
 """Recompile visual pages only; original game, code and loading state stay byte-exact."""
 from .pentagram import PentagramPatch
 peek=RC.nex_peek(nex);ident=colour_identity(peek);expected=art_profile()['source_identity']
 if ident!=expected:raise ValueError('Pentagram graphics do not match the recorded original source')
 mem=bytes(peek(a)for a in range(65536));patch=PentagramPatch(enhanced=True,game=mem,colours=cmap);banks=RC.banks(nex)
 required=set(patch.extra_banks)|{0,2,5,47}
 if not required<=banks.keys():raise ValueError('Not a Pentagram Enhanced build; required banks missing')
 for addr,old,new in patch.sites:
  if bytes(peek(addr+i)for i in range(len(new)))!=new:raise ValueError('Pentagram hook differs at %04X'%addr)
 if banks[13]!=patch.extra_banks[13]or banks[42]!=patch.extra_banks[42]:raise ValueError('Pentagram runtime differs; rebuild with the matching engine')
 # Bank12 carries loader register/tail state; compare only immutable runtime code.
 lo,hi=0x3900-8192,0x3A00-8192;rb=patch.regblock-8192
 if banks[12][:lo]!=patch.page[:lo]or banks[12][hi:rb]!=patch.page[hi:rb]or banks[12][rb+20:8192]!=patch.page[rb+20:]:raise ValueError('Pentagram hidden-ROM runtime differs')
 artbanks={p//2 for p in patch.art_pages};out,changed=RC.splice(nex,{b:patch.extra_banks[b]for b in artbanks})
 return out,{'banks changed':changed,'colour-map entries':len(cmap),'original game and hook code':'unchanged'}
