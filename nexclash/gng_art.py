"""Content-checked artwork atlas for the Ghosts 'n Goblins runtime renderer."""
import json,os,math
HERE=os.path.dirname(__file__)
GRAPHICS=os.path.join(HERE,'..','docs','profiles','ghosts_n_goblins_graphics.json')
INDEX_PAGE=36
DATA_PAGE=37
STRIDE={'m3':10,'o3':6,'x2':4}
LAYOUT={'m3':[[(5,4),(3,2),(1,0)],[(6,4),(7,2),(9,8)]], 'o3':[[(2,None),(1,None),(0,None)],[(3,None),(4,None),(5,None)]], 'x2':[[(0,None),(1,None)],[(2,None),(3,None)]]}
# The catalogue stores no game bytes: each entry names where the player's own copy holds the graphic (the
# snapshot at an address; a reference recording at a frame and address; or a slice of its parent entry), and its
# id is the SHA-256 (first 20 hex digits) of kind + rows + the bytes. catalog() reads every graphic from those
# sources at build time and refuses any that does not hash to its id. The sources: use_game(z80, rzx dirs or files);
# without it, the game's reference folder as selftest finds it ($NEXCLASH_REFERENCE, ./reference, ../specnext/reference).
RECORD_REF=('ghosts_n_goblins','ghosts_n_goblins.z80')
_GAME={'z80':None,'rzx':[]}
_CAT=[None]
def use_game(z80,rzx=()):
 _GAME['z80']=z80;_GAME['rzx']=list(rzx);_CAT[0]=None
def _ident(q,raw):
 import hashlib
 return hashlib.sha256(q['kind'].encode()+bytes([q['rows']])+bytes(raw)).hexdigest()[:20]
def _sources():
 z80=_GAME['z80'];dirs=[]
 if z80 is None:
  root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  for d in (os.environ.get('NEXCLASH_REFERENCE'),os.path.join(root,'reference'),os.path.join(root,'..','specnext','reference')):
   if d and os.path.isfile(os.path.join(d,*RECORD_REF)):
    z80=os.path.join(d,*RECORD_REF);break
  if z80 is None:raise FileNotFoundError("Ghosts 'n Goblins graphics: no game given (gng_art.use_game) and none in the reference folder")
 rz={}
 for p in [os.path.dirname(os.path.abspath(z80))]+_GAME['rzx']:
  if os.path.isdir(p):
   for f in os.listdir(p):
    if f.endswith('.rzx'):rz.setdefault(f,os.path.join(p,f))
  elif p.endswith('.rzx'):rz[os.path.basename(p)]=p
 return z80,rz
def catalog():
 if _CAT[0] is not None:return _CAT[0]
 from . import z80tonex as zt,rzx as RZ
 qs=json.load(open(GRAPHICS));z80,rz=_sources();snap=zt.Z80Snapshot(z80);by={q['number']:q for q in qs}
 def put(q,raw):
  if _ident(q,raw)!=q['id']:raise ValueError("Ghosts 'n Goblins graphic %d (%s): the bytes found do not hash to its id: not the expected game or recording"%(q['number'],q['id']))
  q['data']=bytes(raw).hex()
 for q in qs:
  sr=q['source']
  if 'snapshot' in sr:put(q,[snap.read(a) for a in range(sr['snapshot'],sr['snapshot']+q['size'])])
 want={}
 for q in qs:
  if 'rzx' in q['source']:want.setdefault(q['source']['rzx'],{}).setdefault(q['source']['frame'],[]).append(q)
 for name,frames in sorted(want.items()):
  if name not in rz:raise FileNotFoundError("Ghosts 'n Goblins graphics: recording %s not found beside the game"%name)
  last=max(frames)
  def on_frame(frame,m,frames=frames,last=last):
   for q in frames.get(frame,()):
    a=q['source']['addr'];put(q,m[a:a+q['size']])
   return frame>=last
  RZ.scan(rz[name],on_frame)
  miss=[q['number'] for fs in frames.values() for q in fs if 'data' not in q]
  if miss:raise ValueError('graphics %s not reached in %s'%(miss,name))
 for q in sorted(qs,key=lambda q:q['number']):
  sr=q['source']
  if 'parent' in sr:
   p=by[sr['parent']];put(q,bytes.fromhex(p['data'])[sr['offset']:sr['offset']+q['size']])
 _CAT[0]=qs
 return qs
def checksum(raw):
 lo=hi=0
 for v in raw:lo=(lo+v)&255;hi=(hi+lo)&255
 return lo,hi
def pixels(q,cmap=None):
 raw=bytes.fromhex(q['data']);can=[[0]*32 for _ in range(32)]
 for row in range(q['rows']):
  for yy,line in enumerate(LAYOUT[q['kind']]):
   for col,(go,mo) in enumerate(line):
    off=row*STRIDE[q['kind']]+go;v=raw[off];mask=raw[row*STRIDE[q['kind']]+mo] if mo is not None else 255
    key=q.get('paint_id',q['id'])+':%02X'%(off+q.get('paint_offset',0));e=(cmap or {}).get(key)
    for bit in range(8):
     ink=bool(v&(128>>bit));code=1 if ink else (0 if mask&(128>>bit) else 2)
     if e and e[0]==v:
      if len(e)>3 and e[3]&(128>>bit):
       if code!=2:raise ValueError('Only original black mask padding may be cleared')
       code=0
      elif ink and e[2][bit]:code=e[2][bit]
     can[2*row+yy][8*col+bit]=code
 return can
def patterns(q,cmap=None):
 can=pixels(q,cmap);out=bytearray()
 for cy,cx in [(0,0),(0,16),(16,0),(16,16)]:
  for y in range(cy,cy+16):
   for x in range(cx,cx+16,2):out.append(can[y][x]*16+can[y][x+1])
 return bytes(out)
def fast_safe_images(qs,cmap):
 # A clipped bitmap can be shared by differently painted complete images. Only
 # use its context-free fast entry when every possible parent gives the same
 # pattern. Owner edits can change this decision without changing hook code.
 if not cmap:return {q['number'] for q in qs}
 roots=[q for q in qs if not q['parents']];raws={q['id']:bytes.fromhex(q['data']) for q in roots};safe=set()
 for q in qs:
  raw=bytes.fromhex(q['data']);want=patterns(q,cmap);ambiguous=False
  for root in roots:
   if root['kind']!=q['kind'] or root['rows']<q['rows']:continue
   data=raws[root['id']]
   for off in range(0,len(data)-len(raw)+1,STRIDE[q['kind']]):
    if data[off:off+len(raw)]!=raw:continue
    child=dict(q,paint_id=root['id'],paint_offset=off)
    if patterns(child,cmap)!=want:ambiguous=True;break
   if ambiguous:break
  if not ambiguous:safe.add(q['number'])
 return safe

class PaintOracle:
 """Resolve the painted image from the complete live graphic, including clipping.

 The reference works from catalogue pixels, independently of packed atlas bytes
 and the hook cache. Identical fragments in differently painted parents must not
 borrow each other's colours.
 """
 def __init__(self,cmap):
  self.cmap=cmap;qs=catalog();safe=fast_safe_images(qs,cmap)
  self.fast={(q['kind'],q['rows'],bytes.fromhex(q['data'])):patterns(q,cmap) for q in qs if q['number'] in safe}
  self.roots=[(q,bytes.fromhex(q['data'])) for q in qs if not q['parents']]
 def expected(self,kind,g,rows,get):
  length=STRIDE[kind]*rows;raw=bytes(get(g+j) for j in range(length))
  direct=self.fast.get((kind,rows,raw))
  if direct is not None:return direct
  for q,data in self.roots:
   if q['kind']!=kind:continue
   for address in q['addresses']:
    off=g-address
    if off<0 or off%STRIDE[kind] or off+length>len(data):continue
    if bytes(get(address+j) for j in range(len(data)))!=data:continue
    return patterns(dict(q,rows=rows,data=raw.hex(),paint_offset=off),self.cmap)
  return None

def atlas(cmap=None):
 if not os.path.exists(GRAPHICS):raise FileNotFoundError(GRAPHICS)
 # Legacy byte-address maps keep using the verified old fallback route.
 if cmap and not any(':' in k for k in cmap):
  disabled=bytearray(42*8192);disabled[41*8192]=255;return bytes(disabled)
 qs=catalog();safe=fast_safe_images(qs,cmap);out=bytearray(8192+math.ceil(len(qs)/8)*8192);at=0
 for i,q in enumerate(qs):
  raw=bytes.fromhex(q['data']);assert len(raw)<=160
  shape=q['rows']|({'m3':0,'o3':1,'x2':2}[q['kind']]<<5);lo,hi=checksum(raw);page=DATA_PAGE+i//8;off=(i%8)*1024
  if q['number'] in safe:
   out[at:at+5]=bytes([shape,lo,hi,page,off>>8]);at+=5
  o=8192+i*1024;out[o:o+len(raw)]=raw;out[o+256:o+768]=patterns(q,cmap)
 assert at<8192
 # A compact parent-image colour table covers every possible clipped fragment,
 # including heights/offsets absent from the recordings. Whole-parent bytes must
 # match before these colours can be used.
 # 315 recorded/audited variants: atlas pages 36..76, parent index 77,
 # complete parent pixels at 78+. Keep in sync with parent_find.
 assert len(out)==41*8192
 index=bytearray([255])+bytearray(8191);data=bytearray(8192);pos=0;page=78;di=0
 for q in qs:
  if q['parents']:continue
  raw=bytes.fromhex(q['data']);cols=bytearray(len(raw)*4);can=pixels(q,cmap)
  for row in range(q['rows']):
   for yy,line in enumerate(LAYOUT[q['kind']]):
    for col,(go,mo) in enumerate(line):
     off=row*STRIDE[q['kind']]+go
     # Complete output pixels, including opaque black and transparent padding.
     # The parent fallback copies these exactly, just like the fast atlas.
     for bit in range(8):cols[off*4+bit//2]|=can[2*row+yy][8*col+bit]<<(4 if bit%2==0 else 0)
  block=raw+cols
  if pos+len(block)>8192:page+=1;pos=0;data.extend(bytes(8192))
  data[(page-78)*8192+pos:(page-78)*8192+pos+len(block)]=block
  for address in q['addresses']:
   index[di:di+7]=bytes([{'m3':0,'o3':1,'x2':2}[q['kind']],address&255,address>>8,len(raw),page,pos&255,pos>>8]);di+=7
  pos+=len(block)
 index[di]=255
 assert di<8192 and page<92, (di,page)  # leave whole-ROM source banks 46/47 free
 return bytes(out+index+data)

def identity():
 import hashlib
 return {'schema':1,'game':'ghosts_n_goblins','engine':'gng','keys':'gng-full-image-sha256-20:offset-bit','inputs':hashlib.sha256(open(GRAPHICS,'rb').read()).hexdigest(),'geometry':None}

def part(q):
 raw=bytes.fromhex(q['data']);ps=[];entries={};w=16 if q['kind']=='x2' else 24
 for row in range(q['rows']):
  for yy,line in enumerate(LAYOUT[q['kind']]):
   for col,(go,mo) in enumerate(line):
    off=row*STRIDE[q['kind']]+go;v=raw[off];mask=raw[row*STRIDE[q['kind']]+mo] if mo is not None else 255
    key=q.get('paint_id',q['id'])+':%02X'%(off+q.get('paint_offset',0));entries[key]=[v,'g']
    for bit in range(8):
     code=1 if v&(128>>bit) else (0 if mask&(128>>bit) else 2)
     ps.append((col*8+bit,row*2+yy,key,bit,code,code))
 return {'id':'%03d_%s'%(q['number'],q['kind']),'size':1,'w':w,'h':q['rows']*2,'x':0,'y':0,'mir':0,'pixels':ps,'entries':entries,'dx':0,'dy':0,'dmir':0,'vmir':0,'group':'figures'}

def sheets(out_dir,cmap,palette,prefix='GHOSTS_N_GOBLINS'):
 from pathlib import Path
 from . import coloursheet as C
 out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);qs=catalog()
 for label,images in [('PAINTING',[q for q in qs if not q['parents']]),('REFERENCE_ALL',qs)]:
  comps=[{'count':q['count'],'group':'figures','parts':[part(q)]} for q in images]
  stem=out/(prefix+'_'+label+'_SPRITES')
  C.write(comps,str(stem)+'.png',str(stem)+'_layout.json',C.palette_rgb(palette),colours=cmap,identity=identity())
 return len([q for q in qs if not q['parents']]),len(qs)

# Carried-item ground clipping (v1.4). The original draws a zombie's carried pot at
# full height while the zombie itself is still partly underground. The hooks clip it
# to the carrier's live foot line; these 28 prepainted partial pots (4 pot drawings x
# 1..7 rows) sit on 8K pages 96..99, beyond the converter's whole-ROM sources at 92..95.
GROUND_PAGES=(96,97,98,99)
HIDDEN_ROM_PAGES=(92,93,94,95)
POT_ADDRESSES=(0xc8aa,0xc9aa,0xcaaa,0xcbaa)
def ground_atlas(pl,cmap,base_page):
 """Plane bytes (starting at 8K page base_page) -> plane extended with the partial-pot atlas."""
 qs=catalog();roots=[q for q in qs if not q['parents']]
 pots=[q for q in roots if q['kind']=='m3' and q['rows']==8 and any(a in q['addresses'] for a in POT_ADDRESSES)]
 assert len(pots)==4
 children=[]
 for q in pots:
  for rows in range(1,8):
   children.append(dict(q,rows=rows,data=q['data'][:rows*20],number=len(qs)+len(children),parents=[q['id']]))
 # Never insert an ambiguous fragment in the content-only fast path. Validate
 # every possible complete parent, with the current colours, first.
 safe=fast_safe_images(roots+children,cmap)
 assert all(q['number'] in safe for q in children),'Ambiguous partial pot colours'
 p=bytearray(pl);index=(INDEX_PAGE-base_page)*8192;at=index
 while p[at]:at+=5
 assert at+len(children)*5<index+8192
 start=(GROUND_PAGES[0]-base_page)*8192;assert len(p)<=start
 p.extend(bytes(start+len(GROUND_PAGES)*8192-len(p)))
 for i,q in enumerate(children):
  raw=bytes.fromhex(q['data']);lo,hi=checksum(raw);page=GROUND_PAGES[0]+i//8;off=(i%8)*1024
  p[at:at+5]=bytes([q['rows'],lo,hi,page,off>>8]);at+=5
  dest=(page-base_page)*8192+off
  p[dest:dest+len(raw)]=raw;p[dest+256:dest+768]=patterns(q,cmap)
 # The whole-ROM source pages stay empty here: the converter owns them.
 h0=(HIDDEN_ROM_PAGES[0]-base_page)*8192;assert not any(p[h0:h0+len(HIDDEN_ROM_PAGES)*8192])
 return bytes(p)
