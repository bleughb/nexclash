"""Robin of the Wood 128K hardware-sprite conversion.

The owned pilot evidence contains continuous differential replay, renderer
fixtures, interrupt-injection and JNext checks. The standalone build entry
requires the exact archive MD5. No game graphics are stored in this module.
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import hashlib, json, struct
from .build import rom48
from .z80tonex import convert
from . import robin_enhanced as _enh

PROFILE=Path(__file__).resolve().parents[1]/'docs/profiles/robin_of_the_wood.json'
INPUT_MD5='d2fa7f2eeb8ccb75c30edbacb432a8b5'
CMP=tuple(i for i in range(30) if i not in (15,25,29))

def load_profile():
    return json.loads(PROFILE.read_text())

# Original ink indexes remain unchanged. Unused palette entries hold body
# shades of the same hue; no new costume colours and no optional colour set.
FILL = {3:2, 5:5, 6:6, 7:1, 8:8, 10:9, 11:2, 12:4, 13:5, 14:6, 15:1}
FILL_RGB = {1:(109,109,109), 2:(109,0,109), 4:(0,109,0), 9:(109,0,0), 20:(109,109,0), 36:(0,109,109)}

@lru_cache(maxsize=2048)
def closed_shape(points,width,height):
    """Ikari rule: original ink, bounded 1–2 pixel seams, row/column interior.

    No dilation or external border. Seams are measured from original ink,
    before enclosure, so a bow/arm or leg channel is included deliberately.
    """
    ink=set(points);seams=set()
    rows={y:sorted(x for x,yy in ink if yy==y) for y in range(height)}
    cols={x:sorted(y for xx,y in ink if xx==x) for x in range(width)}
    for y,xs in rows.items():
        for a,b in zip(xs,xs[1:]):
            if 1<b-a<=3:seams.update((x,y) for x in range(a+1,b))
    for x,ys in cols.items():
        for a,b in zip(ys,ys[1:]):
            if 1<b-a<=3:seams.update((x,y) for y in range(a+1,b))
    seed=ink|seams
    rows={y:[x for x,yy in seed if yy==y] for y in range(height)}
    cols={x:[y for xx,y in seed if xx==x] for x in range(width)}
    body=seed|{(x,y) for y in range(height) for x in range(width)
               if rows[y] and cols[x] and min(rows[y])<x<max(rows[y])
               and min(cols[x])<y<max(cols[x])}
    return frozenset(body),frozenset(seams)

def figure_palette(ink):
    colours=set(ink.values())
    if 3 in colours and 6 in colours:return 1
    if colours=={13} or (7 in colours and 13 in colours):return 2
    return 0

@lru_cache(maxsize=2048)
def solid_pixels(entries,width,height,palette=0):
    ink=dict(entries);body,seams=closed_shape(frozenset(ink),width,height)
    pixels=dict(ink);coloured={p:c for p,c in ink.items() if c!=8} or ink
    for x,y in body-ink.keys():
        distance=min(abs(x-xx)+abs(y-yy) for xx,yy in coloured)
        counts=Counter(c for (xx,yy),c in coloured.items()
                       if abs(x-xx)+abs(y-yy)==distance)
        colour=max(counts,key=lambda c:(counts[c],c))
        pixels[x,y]=(20 if palette==1 and colour in (6,14) else 36 if palette==2 and colour in (5,13) else FILL[colour])
    return pixels,len(seams)

def pack(pixels,width,height):
    data=bytearray()
    for ty in range(height//16):
        for tx in range(width//16):
            for y in range(16):
                for x in range(0,16,2):data.append((pixels.get((tx*16+x,ty*16+y),0)&15)*16+(pixels.get((tx*16+x+1,ty*16+y),0)&15))
    return bytes(data)

def finish(ink,width,height,cmap=None,key=''):
    pixels,seams=solid_pixels(tuple(sorted(ink.items())),width,height,figure_palette(ink) if key else 0)
    pixels=dict(pixels)
    for p in pixels:
        if cmap and f'{key}:{p[0]},{p[1]}' in cmap:pixels[p]=int(cmap[f'{key}:{p[0]},{p[1]}'])&15
    return pack(pixels,width,height),pixels,seams

# Figure tables: 0x8C25 Robin (34 entries), 0x8C69 guards and escort (19), 0x8C8F others (20).
def families(peek):
    out={}
    for table,count in ((0x8C25,34),(0x8C69,19),(0x8C8F,20)):
        for index in range(count):
            a=peek(table+2*index)+256*peek(table+2*index+1)
            fam=_enh.family_of(table,index)
            if out.setdefault(a,fam)!=fam:raise ValueError(f'graphic {a:04X} in two figure types')
    return out

def variant_enhanced(peek,addr,mirror,phase,family):
    """The Enhanced colour set's variant: the default variant's opaque pixels, painted by parts."""
    tiled=peek(addr)&15>=4;width=64 if tiled else 32
    data,pixels,n=variant(peek,addr,mirror,phase)
    base_ink=variant(peek,addr,False,0,raw=True);base=variant(peek,addr,False,0)[1]
    body,seams=closed_shape(frozenset(base_ink),width,48)
    painted=_enh.paint(family,addr,tiled,base_ink,set(base),seams,pixels,mirror)
    if set(painted)!=set(pixels) or 0 in painted.values():raise ValueError(f'Enhanced silhouette differs at {addr:04X}')
    return pack(painted,width,48),painted,n

def variant(peek,addr,mirror,phase,cmap=None,raw=False):
    header=peek(addr);ink={}
    if header&15>=4:
        # C67E: six by five 8px tiles; requested facing mirrors columns AND bits.
        for ty in range(5):
            for tx in range(6):
                n=ty*6+(5-tx if mirror else tx);tile=peek(addr+1+n)
                at=peek(addr+31+(0 if header&128 else n));co=(at&7)|((at&64)>>3) or 8
                if not tile:continue
                for y in range(8):
                    b=peek(0x9958+tile*8+y)
                    for x in range(8):
                        if b&(1<<(x if mirror else 7-x)):ink[tx*8+x+1,ty*8+y+1]=co
        if raw:return ink
        return finish(ink,64,48,cmap,f'{addr:04x}:{int(mirror)}:0')
    height,ac=peek(addr+1),peek(addr+2)
    ap=peek(0x8CB7+2*(ac&63))+256*peek(0x8CB8+2*(ac&63))
    for y in range(height):
        row=sum(peek(addr+3+3*y+k)<<(16-8*k) for k in range(3))
        for x in range(24):
            sx=23-x if bool(header&128)!=mirror else x
            if row&(1<<(23-sx)):
                ar=(phase+y)//8 if ac&64 else 0
                if ac&128:raise ValueError('unexpected column-dependent bitmap colours')
                at=peek(ap+ar);co=(at&7)|((at&64)>>3) or 8
                ink[x+1,y+1]=co
    if raw:return ink
    return finish(ink,32,48,cmap,f'{addr:04x}:{int(mirror)}:{phase}')

def item_variant(peek,index,raw=False):
    """D702/D75E glyph stream and its following attribute rows, IDs 0..7."""
    a=0xD89F+index*2;ptr=peek(a)+256*peek(a+1);x=y=0;flip=False;bits=set()
    while True:
        ptr+=1;c=peek(ptr)
        if c==0:break
        if c==1:y+=8;x=0;continue
        if c==2:flip=True;continue
        if c==3:flip=False;continue
        if c<32:continue
        for dy in range(8):
            b=peek(0xAAEF+c*8+dy)
            for dx in range(8):
                if b&(1<<(dx if flip else 7-dx)):bits.add((x+dx,y+dy))
        x+=8
    attrs={};x=y=0
    while True:
        ptr+=1;c=peek(ptr)
        if not c:break
        if c&128:y+=1;x=0;continue
        attrs[x,y]=c;x+=1
    ink={}
    for x,y in bits:
        at=attrs.get((x//8,y//8),0);ink[x+1,y+1]=(at&7)|((at&64)>>3) or 8
    if raw:return ink
    width=((max(x for x,y in bits)+3+15)//16)*16
    height=((max(y for x,y in bits)+3+15)//16)*16
    return width//16,height//16,finish(ink,width,height)

class RobinPatch:
    name='Robin of the Wood 128K figure sprites'
    uses_printer_buffer=True
    def __init__(self,cmap=None,enhanced=False):
        self.prof=load_profile();self.cmap=cmap or {};self.enhanced=enhanced
        h=self.prof['hooks'];self.syms={k:int(v,16) for k,v in h['syms'].items()}
        self.stub_extra=bytes.fromhex(h['setup']);self.setup_call=0xD000
        if enhanced:
            # the setup routine loads 16 palette entries per figure type's bank as well (ld b,48 -> 144)
            setup=bytearray(self.stub_extra)
            if setup[11:13]!=b'\x06\x30' or setup[8:11]!=b'\x21\x43\xd0' or len(setup)!=0x43+96:raise ValueError('setup layout')
            setup[12]=16*enhanced_banks()
            self.stub_extra=bytes(setup[:0x43])+_enh.palette_bytes(setup[0x43:])
        self.hook_page_data=b'';self.regblock=self.syms['rom_end']
        self.slot1=(24,self.regblock);self.altrom=(0x386E,self.regblock+20)
        page=bytearray(rom48()[0x2000:0x4000]); code=bytes.fromhex(h['rom'])
        page[0x186E:0x186E+len(code)]=code;self.page=bytes(page)
        self.sites=[(0xC7DD,bytes.fromhex('CD7EC6'),'e_gfx'),
                    (0xC08D,bytes.fromhex('CD55C9'),'e_commit'),
                    (0xC16B,bytes.fromhex('21027C'),'e_room'),
                    (0xC05F,bytes.fromhex('CD73CE'),'e_menu'),
                    (0xBBB5,bytes.fromhex('CDECBB'),'e_arrow_erase'),
                    (0xBBCB,bytes.fromhex('CDECBB'),'e_arrow_draw'),
                    (0xD702,bytes.fromhex('32C2D8'),'e_item'),
                    (0xD6F1,bytes.fromhex('AF321DD8'),'e_hud')]
        self.data_sites=[(a,0x77,0) for a in (0xC829,0xC82D,0xC831,0xC835,0xC704,0xBBF3)]
        self.extra_banks={};self.stats={};self.sheet=[]

    def apply(self,snap):
        if not snap.is128: raise ValueError('requires 128K')
        def peek(a):
            bank={1:5,2:2,3:0}[a>>14]
            return snap.banks[bank][a&16383]
        for a,old,_ in self.sites:
            if bytes(peek(a+i) for i in range(len(old)))!=old:
                raise ValueError(f'patch-site mismatch {a:04X}')
        raw=bytearray.fromhex(self.prof['hooks']['page'])
        graphics=sorted(set(peek(a)+256*peek(a+1) for a in range(0x8C25,0x8CB7,2)))
        table=bytearray([len(graphics)]);pages={};page_no=28;off=0;dedup={}
        seam_pixels=0;variants=0
        def put(data):
            nonlocal off,page_no
            if data in dedup:return dedup[data]
            if off+len(data)>8192:page_no+=1;off=0
            pages.setdefault(page_no,bytearray(8192))[off:off+len(data)]=data
            result=struct.pack('<BH',page_no,0x8000+off);dedup[data]=result;off+=len(data)
            return result
        fams=families(peek) if self.enhanced else {}
        for addr in graphics:
            bank=_enh.BANK[fams[addr]] if self.enhanced else figure_palette(variant(peek,addr,False,0,raw=True))
            table+=struct.pack('<HB',addr,int(peek(addr)&15>=4)|(bank<<4))
            for mirror in (False,True):
                for phase in range(8):
                    if self.enhanced:data,pixels,n=variant_enhanced(peek,addr,mirror,phase,fams[addr])
                    else:data,pixels,n=variant(peek,addr,mirror,phase,self.cmap)
                    table+=put(data);seam_pixels+=n;variants+=1
                    if not mirror and not phase:self.sheet.append((addr,pixels))
        items=bytearray()
        for index in range(8):
            cols,rows,(data,pixels,n)=item_variant(peek,index)
            items+=bytes((cols,rows))+put(data);seam_pixels+=n
        raw[self.syms['item_table']-0x6000:self.syms['item_table']-0x6000+40]=items
        data,pixels,n=finish({(x+1,1):14 for x in range(8)},16,16)
        seam_pixels+=n
        raw[self.syms['arrow_pattern']-0x6000:self.syms['arrow_pattern']-0x6000+3]=put(data)
        if page_no>=96:raise ValueError('exceeds unexpanded Next RAM')
        table_off=self.syms['table']-0x6000
        raw=raw[:table_off]+table
        if len(raw)>8192:raise ValueError('hook page full')
        raw+=bytes(8192-len(raw))
        self.extra_banks={12:self.page+bytes(8192),13:bytes(raw)+bytes(8192)}
        for pn,data in pages.items():
            bank=pn//2;buf=bytearray(self.extra_banks.get(bank,bytes(16384)))
            buf[(pn%2)*8192:(pn%2+1)*8192]=data;self.extra_banks[bank]=bytes(buf)
        if self.enhanced:
            # a colour set changes banks of the same build: hold the default's bank list, unused ones zero
            import copy
            default=RobinPatch(self.cmap);default.apply(copy.deepcopy(snap))
            if not set(self.extra_banks)<=set(default.extra_banks):raise ValueError('Enhanced needs more banks than the default')
            for bank in default.extra_banks:self.extra_banks.setdefault(bank,bytes(16384))
        changed={b:bytearray(snap.banks[b]) for b in (0,2,5)}
        for a,old,sym in self.sites:
            bank={1:5,2:2,3:0}[a>>14];off=a&16383
            changed[bank][off:off+len(old)]=b'\xcd'+struct.pack('<H',self.syms[sym])+bytes(len(old)-3)
        for a,old,new in self.data_sites:
            bank={1:5,2:2,3:0}[a>>14];off=a&16383
            if changed[bank][off]!=old:raise ValueError(f'data site mismatch {a:04X}')
            changed[bank][off]=new
        for b,data in changed.items():snap.banks[b]=bytes(data)
        self.stats={'graphics':len(graphics),'variants':variants,'seam_pixels_closed':seam_pixels,'highest_page':page_no,
                    'colour_set':'Enhanced' if self.enhanced else 'default','coverage':'all 3 figure tables, arrows, collectible IDs 0..7; see pilot evidence','hardware':'none'}

def enhanced_banks():
    return _enh.BANKS

def build(snapshot,output,colours=None,enhanced_set=False):
    if hashlib.md5(Path(snapshot).read_bytes()).hexdigest()!=INPUT_MD5:
        raise ValueError('input snapshot MD5 differs from the specified release')
    p=RobinPatch(json.loads(Path(colours).read_text()) if colours else {},enhanced=enhanced_set)
    convert(snapshot,output,patch=p)
    Path(output).with_suffix('.build.json').write_text(json.dumps(p.stats,indent=2)+'\n')
    return p

# ---------------------------------------------------------------------------------------------
# Differential verification (imported 2026-11-04 from the pilot's work/enh/verify_enh.py, the fix3
# verifier made colour-set aware, and work/fix2_reference.py: the same checks; its PNG captures and
# the "previous" negative, which needs the pilot's 9304cc0e build, are left in the pilot folder).
# Continuous RZX pair replay (original and patched CSimulator), hooks run from the assembled code on a
# Z80N simulator with the sprite hardware modelled from every attribute bit and the shipped palette;
# every figure checked against an independent closed-silhouette reference; RAM, registers, ports and
# inputs compared at every frame; asset negatives forked at real commits.
# ---------------------------------------------------------------------------------------------

_REF_FILL = {3: 2, 5: 5, 6: 6, 7: 1, 8: 8, 10: 9, 11: 2, 12: 4, 13: 5, 14: 6, 15: 1}


@lru_cache(maxsize=2048)
def reference(entries):
 ink=dict(entries);w=max(x for x,y in ink)+2;h=max(y for x,y in ink)+2
 mask=[[False]*w for _ in range(h)]
 for x,y in ink:mask[y][x]=True
 seams=set()
 for transpose in (False,True):
  for a in range(w if transpose else h):
   line=[mask[b][a] if transpose else mask[a][b] for b in range(h if transpose else w)];b=0
   while b<len(line):
    if line[b]:b+=1;continue
    start=b
    while b<len(line) and not line[b]:b+=1
    if start>0 and b<len(line) and b-start<=2:
     for c in range(start,b):seams.add((a,c) if transpose else (c,a))
 seed=set(ink)|seams;body=set(seed)
 for y in range(h):
  for x in range(w):
   if any((xx,y) in seed for xx in range(x)) and any((xx,y) in seed for xx in range(x+1,w)) and any((x,yy) in seed for yy in range(y)) and any((x,yy) in seed for yy in range(y+1,h)):body.add((x,y))
 out=dict(ink);coloured={p:c for p,c in ink.items() if c!=8} or ink
 for p in body-set(ink):
  distances={q:abs(p[0]-q[0])+abs(p[1]-q[1]) for q in coloured};best=min(distances.values());freq=Counter(coloured[q] for q,d in distances.items() if d==best)
  c=sorted(freq,key=lambda c:(freq[c],c))[-1];colours=set(ink.values());pal=1 if 3 in colours and 6 in colours else 2 if colours=={13} or (7 in colours and 13 in colours) else 0
  out[p]=20 if pal==1 and c in (6,14) else 36 if pal==2 and c in (5,13) else _REF_FILL[c]
 return out,frozenset(seams)


NEGATIVES = ('position', 'colour', 'outline', 'hide', 'reset', 'register', 'outside', 'seam', 'hollow', 'late',
             'pal_guard0', 'pal_robin15')
# Enhanced: 'hollow' corrupts the default art, which the Enhanced paint replaces (UNDETECTED in the pilot too, by design:
# enh_hollow is its Enhanced form); 'outside' is refused by the build's own silhouette guard (a ValueError = detected).
NEGATIVES_ENH = tuple(m for m in NEGATIVES if m != 'hollow') + ('enh_palette', 'enh_default_art', 'enh_hollow', 'enh_outline')


def inventory(peek):
    """The figure tables 0x8C25 / 0x8C69 / 0x8C8F: [{table, index, address}] (the pilot's work/figure_inventory.json)."""
    w = lambda a: peek(a) + 256 * peek(a + 1)
    return [dict(table=base, index=i, address=w(a)) for base, end in ((0x8C25, 0x8C69), (0x8C69, 0x8C8F), (0x8C8F, 0x8CB7))
            for i, a in enumerate(range(base, end, 2))]


def verify(path, z80, mode='normal', enh=False, limit=None, progress=None):
    """-> (Counter, failures). mode 'normal' = the replay; any other = a negative (must fail)."""
    import sys, time
    from skoolkit import CSimulator
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    from . import z80n
    from .rzx import read_segments
    from .z80tonex import Z80Snapshot
    engine = sys.modules[__name__]
    ENHMOD = _enh
    variant_enhanced, item_variant, fig_families = engine.variant_enhanced, engine.item_variant, engine.families
    ENH, MODE = enh, mode
    ENH9 = {e: ENHMOD.nine(c) for e, c in ENHMOD.ENTRIES.items()}
    saved = (engine.finish, engine.variant_enhanced)
    try:
        _inv = Z80Snapshot(str(z80))
        INV = inventory(lambda a: _inv.banks[{1: 5, 2: 2, 3: 0}[a >> 14]][a & 16383])
        def rgb8(v):
         lv=lambda n:(n*255+3)//7
         return (lv(v>>6&7),lv(v>>3&7),lv(v&7))
        original_finish=engine.finish
        def broken_finish(ink,w,h,*args,**kwargs):
         data,pix,n=original_finish(ink,w,h,*args,**kwargs);pix=dict(pix)
         want,seams=reference(tuple(sorted(ink.items())))
         if MODE=='seam':
          for p in seams:pix.pop(p,None)
         elif MODE=='hollow':
          for p in set(want)-set(ink):pix[p]=8
         elif MODE in ('outside','outline'):
          if MODE=='outside':pix[0,0]=15
          else:
           for x,y in want:
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
             p=(x+dx,y+dy)
             if p not in want and 0<=p[0]<w and 0<=p[1]<h:pix[p]=15
         packed=bytearray()
         for ty in range(h//16):
          for tx in range(w//16):
           for y in range(16):
            for x in range(0,16,2):packed.append((pix.get((tx*16+x,ty*16+y),0)&15)*16+(pix.get((tx*16+x+1,ty*16+y),0)&15))
         return bytes(packed),pix,n
        if MODE in ('seam','hollow','outside','outline'):engine.finish=broken_finish
        if MODE in ('enh_hollow','enh_outline'):
         # corrupt the Enhanced art after the build's own silhouette guard has passed it
         _good=engine.variant_enhanced
         def _bad(peek,addr,mirror,phase,family):
          data,pix,n=_good(peek,addr,mirror,phase,family);pix=dict(pix);w=64 if peek(addr)&15>=4 else 32
          ink=engine.variant(peek,addr,mirror,phase,raw=True)
          if MODE=='enh_hollow' and family=='robin':
           black=ENHMOD.INDEX['robin'][('hair','fill')]
           for p in pix:
            if p not in ink:pix[p]=black
          elif MODE=='enh_outline':
           ring={(x+dx,y+dy) for x,y in pix for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))}-set(pix)
           for p in ring:
            if 0<=p[0]<w and 0<=p[1]<48:pix[p]=1
          return engine.pack(pix,w,48),pix,n
         engine.variant_enhanced=_bad
        P=RobinPatch(enhanced=ENH);_snap=Z80Snapshot(str(z80));_peek=lambda a:_snap.banks[{1:5,2:2,3:0}[a>>14]][a&16383];FAMS=fig_families(_peek);P.apply(_snap)
        if MODE in ('enh_hollow','enh_outline'):engine.variant_enhanced=_good
        if MODE=='enh_palette':
         # Robin's face (skin) entry in the shipped setup palette becomes the tunic green: colour must be caught
         e=16*ENHMOD.BANK['robin']+ENHMOD.INDEX['robin'][('face','fill')];st=bytearray(P.stub_extra);st[0x43+2*e]=0x0C;st[0x43+2*e+1]=0;P.stub_extra=bytes(st)
        if MODE=='enh_default_art':
         # the Enhanced table and palette with the default build's figure images
         _d=RobinPatch();_d.apply(Z80Snapshot(str(z80)))
         for b in range(14,34):P.extra_banks[b]=_d.extra_banks[b]
        engine.finish=original_finish
        if MODE=='previous':raise ValueError('negative previous needs the pilot\'s 9304cc0e build and its profile: not imported')

        OBJECTS=[0xAAB8,0xAAC3,0xAACE,0xAAD9,0xAAE4,0xDDE5,0xDDF0,0xDDFB,0xDE06,0xCD77,0xB7BD,0xBA4F,0xBB1B]
        SITES={a:(old,sym) for a,old,sym in P.sites};WATCH=set(SITES)|{0xC090}; EXCLUDE={a+i for a,old,sym in P.sites for i in range(len(old))}|{a for a,_,_ in P.data_sites}|{0xD7AD}
        END={0xC7DD:0xC67E,0xC08D:0xC955,0xC16B:0xC16E,0xC05F:0xCE73,0xC056:0xCE67,0xBBB5:0xBBEC,0xBBCB:0xBBEC,0xD702:0xD705,0xD6F1:0xD6F4}
        class Event(Exception):pass
        class Ports:
         def __init__(self,sim):self.sim=sim;self.ins=[];self.i=0;self.bad=0;self.outs=[]
         def read_port(self,r,p):
          if self.i>=len(self.ins):self.bad+=1;return 255
          v=self.ins[self.i];self.i+=1;return v
         def write_port(self,r,p,v,offset=0):
          if p&0x8002==0 and not self.sim.memory.o7ffd&32:self.sim.memory.out7ffd(v)
          if p&0xC002 in (0x8000,0xC000) or p&1==0:self.outs.append((p,v))
        class Overlay:
         def __init__(self,m):
          self.base=m;self.pages={};self.s3=11;self.s4=4
          for b,data in P.extra_banks.items():self.pages[2*b]=bytearray(data[:8192]);self.pages[2*b+1]=bytearray(data[8192:])
         def __len__(self):return 65536
         def __getitem__(self,a):
          if isinstance(a,slice):return [self[i] for i in range(*a.indices(65536))]
          a&=65535
          if 0x386e<=a<P.regblock:return P.page[a-0x2000]
          if 0x6000<=a<0x8000 and self.s3!=11:return self.pages[self.s3][a-0x6000]
          if 0x8000<=a<0xa000 and self.s4!=4:return self.pages[self.s4][a-0x8000]
          return self.base[a]
         def __setitem__(self,a,v):
          a&=65535
          if 0x6000<=a<0x8000 and self.s3!=11:self.pages[self.s3][a-0x6000]=v
          elif 0x8000<=a<0xa000 and self.s4!=4:self.pages[self.s4][a-0x8000]=v
          else:self.base[a]=v
        # --- fix3: the sprite hardware modelled from the attribute bits, not from the engine's intent ---
        # Next sprite attributes (NextReg 0x35..0x39, 5-byte form):
        #  0: X7..0  1: Y7..0  2: PPPP XM YM R X8  3: V E N5..N0  4 (E=1): H N6 T XX YY Y8
        # A 4-bit anchor (H=1) pixel n of the 16-colour pattern shows sprite palette entry
        # (P<<4)|n unless n equals the low nibble of NextReg 0x4B. Mirror, rotate, scale and
        # the ninth coordinate bits are all honoured. 8-bit or relative sprites, and any
        # NextReg or port the hooks are not expected to touch, are recorded in hw.bad.
        # Colours are compared as the 9-bit RGB the palette RAM holds, so a palette offset,
        # a palette entry or a transparency change is visible.
        def _rgb9(r,g,b):return (r<<6)|(g<<3)|b
        ULA9={c:_rgb9(*(((7 if c&8 else 5) if c&m else 0) for m in (2,4,1))) for c in range(16)}
        ULA9[8]=0  # the engine's code for black ink (attribute ink 0, either brightness)
        # Independent statement of the approved fill shades: level 3 of the ink's own hue.
        FILL9={1:_rgb9(3,3,3),2:_rgb9(3,0,3),4:_rgb9(0,3,0),9:_rgb9(3,0,0),20:_rgb9(3,3,0),36:_rgb9(0,3,3)}
        def intended9(c,is_ink):
         """What the owner-approved policy says a figure pixel should look like."""
         if is_ink:return ULA9[c]          # original ink: the game's own ULA colour
         return FILL9[c] if c in FILL9 else ULA9[c]
        def intended_layer(pix,ink):
         return {p:intended9(c,p in ink) for p,c in pix.items()}
        HOOK_REGS={0x53,0x54,0x07,0x34,0x35,0x36,0x37,0x38,0x39}
        class Hardware:
         def __init__(self,m):
          self.mem=m;self.attr=[[0]*5 for _ in range(128)];self.pat=bytearray(16384);self.sel=0;self.ptr=0;self.speed=0;self.bad=[]
          # Reset state: sprite palettes hold the identity RRRGGGBB colour, B0=B1|B0.
          ident=[(i<<1)|(1 if i&3 else 0) for i in range(256)]
          self.spal=[ident[:],ident[:]];self.palctl=0;self.palidx=0;self.pal9=None
          self.trans=0xE3;self.reg15=0;self.clip=[0,255,0,191];self.clipi=0;self.setup=True
         def nextreg(self,n,v):
          if not self.setup and n not in HOOK_REGS:self.bad.append(('nextreg',n,v));return
          if n==0x53:self.mem.s3=v
          elif n==0x54:self.mem.s4=v
          elif n==7:self.speed=v
          elif n==0x34:self.sel=v&127
          elif 0x35<=n<=0x39:
           self.attr[self.sel][n-0x35]=v
           if n==0x39:self.sel=self.sel  # 0x75..0x79 auto-increment forms are not used
          elif n==0x43:self.palctl=v;self.pal9=None
          elif n==0x40:self.palidx=v;self.pal9=None
          elif n in (0x41,0x44):
           sub=(self.palctl>>4)&7
           if sub not in (2,6):self.bad.append(('palette not sprite',self.palctl,n,v));return
           pal=self.spal[1 if sub==6 else 0]
           if n==0x41:pal[self.palidx]=(v<<1)|(1 if v&3 else 0);done=True
           elif self.pal9 is None:self.pal9=v;done=False
           else:pal[self.palidx]=(self.pal9<<1)|(v&1);self.pal9=None;done=True
           if done and not self.palctl&128:self.palidx=(self.palidx+1)&255
          elif n==0x4B:self.trans=v
          elif n==0x15:self.reg15=v
          elif n==0x1C:
           if v&2:self.clipi=0
          elif n==0x19:self.clip[self.clipi]=v;self.clipi=(self.clipi+1)&3
          else:self.bad.append(('nextreg',n,v))
         def read_port(self,r,p):raise RuntimeError(f'hook input {p:04X}')
         def write_port(self,r,p,v,*args):
          if p==0x303b:self.ptr=(v&63)*256+(128 if v&128 else 0)
          elif p&255==0x5b:self.pat[self.ptr]=v;self.ptr=(self.ptr+1)&16383
          else:self.bad.append(('out',p,v))
         def global_state(self):
          return (tuple(self.spal[0][:256]),tuple(self.spal[1][:256]),self.palctl&8,self.trans,self.reg15,tuple(self.clip))
         def layer(self,first=0,end=128):
          """{(x,y): 9-bit RGB} of the visible sprites in [first,end), higher slots on top."""
          out={};pal=self.spal[1 if self.palctl&8 else 0];key=self.trans&15
          for slot in range(end-1,first-1,-1):
           a=self.attr[slot]
           if not a[3]&128:continue
           if not a[3]&64:self.bad.append(('4-byte (8-bit) sprite',slot,a[:]));continue
           if a[4]&0xC0==0x40:self.bad.append(('relative sprite',slot,a[:]));continue
           if not a[4]&128:self.bad.append(('8-bit sprite',slot,a[:]));continue
           P=a[2]>>4;xm=bool(a[2]&8);ym=bool(a[2]&4);rot=bool(a[2]&2)
           xs=1<<((a[4]>>3)&3);ys=1<<((a[4]>>1)&3)
           x0=a[0]+256*(a[2]&1)-32;y0=a[1]+256*(a[4]&1)-32
           off=(a[3]&63)*256+(128 if a[4]&64 else 0)
           for sy in range(16*ys):
            for sx in range(16*xs):
             ex=sx//xs;ey=sy//ys
             # Rotation transposes and inverts the X mirror (sprites.vhd: x_mirr xor rotate).
             if xm!=rot:ex=15-ex
             if ym:ey=15-ey
             px,py=(ey,ex) if rot else (ex,ey)
             b=self.pat[(off+py*8+px//2)&16383];c=b&15 if px&1 else b>>4
             if c==key:continue
             out[x0+sx,y0+sy]=pal[((P<<4)|c)&255]
          return out
        def run_setup(hw):
         """Execute the shipped setup routine (stub_extra, ORG 0xD000) against the hardware model."""
         mem=bytearray(65536);mem[0xD000:0xD000+len(P.stub_extra)]=P.stub_extra;mem[0xFFFE:0x10000]=b'\x00\x00'
         vm=Simulator(mem,config={'int_active':0});vm.set_tracer(hw);z80n.install(vm,hw.nextreg)
         r=vm.registers;r[24]=0xD000;r[12]=0xFFFE;hw.setup=True
         for _ in range(100000):
          vm.opcodes[mem[r[24]]]()
          if r[24]==0:break
         else:raise RuntimeError('setup did not return')
         hw.setup=False
         return hw.global_state()
        # The display state every hook must leave untouched; any later change is a failure.
        _probe=Hardware(Overlay.__new__(Overlay));SETUP_STATE=run_setup(_probe)
        assert _probe.clip==[16,239,0,143] and _probe.reg15&1 and _probe.trans&15==0 and not _probe.bad,(_probe.clip,_probe.reg15,_probe.trans,_probe.bad)
        def setup_hardware(m):
         hw=Hardware(m);run_setup(hw);return hw

        def run(path,mode='normal',limit=None,progress=None):
         counts=Counter();failures=[];refs={};ebank={};families={};negatives={};irq_cases={};rooms=set();late=[];started=time.monotonic();frame=0
         def fail(what,info=None):
          counts[what+'!']+=1
          if len(failures)<12:failures.append(dict(frame=frame,what=what,info=info))
         def ref(pc,sim):
          m=sim.memory;r=sim.registers;get=lambda a:m[a];rw=lambda a:m[a]+256*m[a+1]
          if pc in (0xc16b,0xc05f,0xc056):refs.clear();return
          if pc==0xc7dd:
           obj=r[8]*256+r[9];caller=rw(r[12]+2);g=r[6]*256+r[7];mirror=bool(r[0]&128);y=r[2];x=r[3]
           if obj not in OBJECTS:fail('unknown figure object',hex(obj));return
           n=OBJECTS.index(obj)
           if caller!=0xca52:refs.pop(n,None);return
           tiled=m[g]&15>=4
           _,pix,_=(variant_enhanced(get,g,mirror,y&7,FAMS[g]) if ENH else variant(get,g,mirror,y&7))
           ebank[n]=ENHMOD.BANK[FAMS[g]]
           ox=(8*(((x>>2)-3-int(mirror))&31) if tiled else 2*x-16)-1;oy=((y&248)-8 if tiled else y)-1
           families[n]=('robin' if n==9 else 'ent' if n==10 else 'bishop' if n==11 else 'witch' if n==12 else 'creature' if 5<=n<=8 else 'guard')
           refs[n]=(ox,oy,pix,variant(get,g,mirror,y&7,raw=True));counts[f'figure {obj:04X}']+=1;counts[f'graphic {g:04X}']+=1
          elif pc in (0xbbb5,0xbbcb):
           obj=r[4]*256+r[5];n=13+(obj-0xbe3f)//2
           if pc==0xbbb5:refs.pop(n,None)
           else:
            families[n]='arrow'
            refs[n]=(8*r[3]-1,8*r[2]-1,engine.finish({(x+1,1):14 for x in range(8)},16,16)[1],{(x+1,1):14 for x in range(8)});counts['arrows']+=1
          elif pc==0xd702:
           a=r[0]
           if a&32 or a&31>=8:return
           ox=8*(r[4]>>2)+15;oy=r[5]-1
           n=next((n for n,v in refs.items() if n>=17 and v[:2]==(ox,oy)),None)
           if a&128:
            if n is not None:del refs[n]
           else:
            if n is None:n=next(i for i in range(17,26) if i not in refs)
            families[n]='item_'+str(a&31)
            refs[n]=(ox,oy,item_variant(get,a&31)[2][1],item_variant(get,a&31,raw=True));counts[f'item {a&31}']+=1
         def colour9(n,c,is_ink):
          if ENH and n<13:return ENH9[16*ebank[n]+c]
          return intended9(c,is_ink)
         def expected():
          out={}
          for n,(ox,oy,pix,ink) in reversed(sorted(refs.items())):
           for (x,y),c in pix.items():out[ox+x,oy+y]=colour9(n,c,(x,y) in ink)
          return out
         if mode=='register':
          page=bytearray(P.page);i=page.index(bytes.fromhex('E1D1C1F1'),P.syms['e_gfx']-0x2000,P.syms['e_commit']-0x2000);page[i+2]=0xD1;P.page=bytes(page)
         for snap,record,_ in read_segments(path):
          so=from_snapshot(CSimulator,snap,config={'int_active':0});sp=from_snapshot(CSimulator,snap,config={'int_active':0})
          po=Ports(so);pp=Ports(sp);so.set_tracer(po);sp.set_tracer(pp)
          mo=so.memory;mp=sp.memory
          def put(a,v):mp.banks[{1:5,2:2,3:0}[a>>14]][a&16383]=v
          for a,old,sym in P.sites:
           for i,v in enumerate(b'\xcd'+P.syms[sym].to_bytes(2,'little')+bytes(len(old)-3)):put(a+i,v)
          for a,old,v in P.data_sites:put(a,v)
          overlay=Overlay(mp);hw=setup_hardware(overlay);vm=Simulator(overlay,config={'int_active':0});vm.set_tracer(hw);z80n.install(vm,hw.nextreg)
          if mode=='position':
           data=overlay.pages[26];i=data.index(bytes.fromhex('110F0019'));data[i+1]+=1
          elif mode=='colour':
           for pn in range(28,max(overlay.pages)+1):
            if pn in overlay.pages:
             overlay.pages[pn][:]=bytes(0xee if b else 0 for b in overlay.pages[pn])
          if mode.startswith('omit_'):
           inv=INV
           family=mode[5:]
           groups={'robin':lambda r:r['table']==0x8c25,'guard':lambda r:r['table']==0x8c69,
                   'ent':lambda r:r['table']==0x8c8f and r['index']<3,
                   'bishop':lambda r:r['table']==0x8c8f and 3<=r['index']<6,
                   'witch':lambda r:r['table']==0x8c8f and 6<=r['index']<16,
                   'creature':lambda r:r['table']==0x8c8f and r['index']>=16}
           data=overlay.pages[26];overlay.pages[95]=bytearray(8192)
           if family in groups:
            addrs={r['address'] for r in inv if groups[family](r)};q=P.syms['table']-0x6000
            for n in range(data[q]):
             a=q+1+n*51;g=data[a]+256*data[a+1]
             if g in addrs:
              for v in range(16):data[a+3+3*v:a+6+3*v]=bytes([95,0,128])
           elif family=='arrow':
            q=P.syms['arrow_pattern']-0x6000;data[q:q+3]=bytes([95,0,128])
           elif family=='item':
            q=P.syms['item_table']-0x6000
            for n in range(8):data[q+5*n+2:q+5*n+5]=bytes([95,0,128])
           else:raise ValueError(mode)
          if mode=='hide':
           d=overlay.pages[26];i=d.index(bytes.fromhex('B8D0ED9234ED9138003C18F4'));d[i+5:i+9]=bytes(4) # omit the actual sprite-tail hide write
          if mode=='reset':overlay.pages[26][P.syms['clear']-0x6000]=0xc9
          if mode in ('pal_guard0','pal_robin15'):
           # Change the figure-table palette nibble the engine copies into attribute 2.
           d=overlay.pages[26];q=P.syms['table']-0x6000;inv=INV
           want={r['address'] for r in inv if r['table']==(0x8c25 if mode=='pal_robin15' else 0x8c69)};hit=0;old=set()
           for k in range(d[q]):
            a=q+1+k*51;g=d[a]+256*d[a+1]
            if g in want:old.add(d[a+2]>>4);d[a+2]=(d[a+2]&15)|(0xF0 if mode=='pal_robin15' else 0);hit+=1
           counts['palette negative entries changed']+=hit
          def hook(pc):
           r=sp.registers;before=list(r)
           if mode=='normal':
            key=f'{pc:04X}'
            if pc==0xc7dd:
             obj=r[8]*256+r[9];g=r[6]*256+r[7];caller=mp[r[12]+2]+256*mp[r[12]+3]
             key+=f'_{obj:04X}_{int(mp[g]&15>=4)}_{caller:04X}'
            elif pc==0xc08d:key+=f'_{len(refs)}_{int(any(mp[0xcd7c]==a for a in (0x21,0xa1)))}'
            if key not in irq_cases:
             irq_cases[key]=dict(pc=pc,regs=before,banks=[bytes(b) for b in mp.banks],paging=mp.o7ffd,page26=bytes(overlay.pages[26]),attr=[a[:] for a in hw.attr],patterns=bytes(hw.pat),sel=hw.sel,ptr=hw.ptr)
           if pc==0xc08d and mode=='normal':
            # Fork the actual recorded pre-commit state. Corrupt just this family's
            # packed sprite asset, execute the assembled commit, then restore the fork.
            # The unmodified commit immediately below must still pass against the plot.
            for family in sorted({families[n] for n in refs}-set(negatives)):
             banks=[bytes(b) for b in mp.banks];pages={n:bytes(b) for n,b in overlay.pages.items()}
             attr=[a[:] for a in hw.attr];pat=bytes(hw.pat);sel=hw.sel;ptr=hw.ptr
             for n in refs:
              if families[n]!=family:continue
              a=P.syms['descriptors']-0x6000+n*16;d=overlay.pages[26];pn=d[a+6];off=d[a+7]+256*d[a+8]-0x8000;size=d[a+4]*d[a+5]*128
              overlay.pages[pn][off:off+size]=bytes(size)
              # A build with this corrupted asset has it corrupt on the first upload.
             vm.registers[:]=before
             for step in range(200000):
              vm.opcodes[overlay[vm.registers[24]]]()
              if vm.registers[24]==END[pc]:break
             got=hw.layer();want=expected();detected=got!=want
             negatives[family]=dict(result='DETECTED' if detected else 'UNDETECTED',frame=frame,different_pixels=sum(got.get(p)!=want.get(p) for p in set(got)|set(want)))
             if not detected:fail('asset negative escaped',family)
             for b,data in zip(mp.banks,banks):b[:]=data
             for n,data in pages.items():overlay.pages[n][:]=data
             hw.attr=attr;hw.pat[:]=pat;hw.sel=sel;hw.ptr=ptr;hw.speed=0;overlay.s3=11;overlay.s4=4
           vm.registers[:]=before
           for step in range(200000):
            vm.opcodes[overlay[vm.registers[24]]]()
            if vm.registers[24]==END[pc]:break
           else:raise RuntimeError(f'hook stuck {pc:04X} at {vm.registers[24]:04X}')
           rr=vm.registers;rr[15]=(before[15]&128)|((before[15]+1)&127)
           sp.registers[:]=type(r)(r.typecode,rr)
           counts[f'hook {pc:04X}']+=1
           if hw.bad:fail('unexpected hardware access',hw.bad[:4]);hw.bad.clear()
           if hw.global_state()!=SETUP_STATE:fail('sprite display state changed',pc)
           counts['hardware state checks']+=1
           if overlay.s3!=11 or overlay.s4!=4 or hw.speed:fail('mapping/speed', [pc,overlay.s3,overlay.s4,hw.speed])
           if overlay.pages[26][P.syms['error']-0x6000]:fail('engine error',overlay.pages[26][P.syms['error']-0x6000])
           if pc==0xc08d:
            if mode=='late':
             cur=[a[:] for a in hw.attr];shown=late[0] if late else cur;late[:]=[cur];saved_attr=hw.attr;hw.attr=[a[:] for a in shown]
            got=hw.layer();want=expected();counts['layer checks']+=1;counts['sprite pixels']+=len(want)
            dd=overlay.pages[26];base=P.syms['descriptors']-0x6000
            used=sum(dd[base+n*16+4]*dd[base+n*16+5] for n in range(26) if dd[base+n*16])
            tail=sum(bool(a[3]&128) for a in hw.attr[used:]);counts['hidden tail checks']+=1
            if tail:fail('visible sprite tail',dict(used=used,visible=tail))
            # Inspect each complete figure independently, even where another overlaps it.
            for n,(ox,oy,pix,ink) in refs.items():
             d=overlay.pages[26];a=P.syms['descriptors']-0x6000+n*16
             actual={(x-ox,y-oy):c for (x,y),c in hw.layer(d[a+12],d[a+12]+d[a+4]*d[a+5]).items()}
             policy,seams=reference(tuple(sorted(ink.items())))
             counts['closed figure checks']+=1;counts['seam pixels checked']+=len(seams)
             outside=set(actual)-set(policy);missing=set(policy)-set(actual);open_seams=set(seams)-set(actual)
             if ENH and n<13:
              if set(pix)!=set(policy):fail('Enhanced silhouette',dict(object=n,pixels=len(set(pix)^set(policy))))
              wrong=sum(actual.get(p)!=ENH9[16*ebank[n]+pix[p]] for p in policy if p in pix)
              if n==9:
               shown=set(actual.values());skin=ENH9[16*ebank[n]+ENHMOD.INDEX['robin'][('face','fill')]];hair=ENH9[16*ebank[n]+ENHMOD.INDEX['robin'][('hair','fill')]]
               counts['Robin plots']+=1;counts['Robin plots showing skin']+=skin in shown;counts['Robin plots showing black hair']+=hair in shown
             else:wrong=sum(actual.get(p)!=intended9(c,p in ink) for p,c in policy.items())
             if outside:fail('outside closed silhouette',dict(object=n,pixels=len(outside)))
             if open_seams:fail('open seam',dict(object=n,pixels=len(open_seams)))
             if missing:fail('hollow figure',dict(object=n,pixels=len(missing)))
             if wrong:fail('solid colour policy',dict(object=n,pixels=wrong))

            if got!=want:
             dif=[p for p in set(got)|set(want) if got.get(p)!=want.get(p)]
             fail('sprite layer',dict(count=len(dif),examples=[(p,got.get(p),want.get(p)) for p in sorted(dif)[:4]],objects=list(refs)))
            if mode=='late':hw.attr=saved_attr
          for f in record.frames:
           frame+=1
           if limit and frame>limit:frame-=1;break
           fc=f.fetch_counter;ins=list(record.data[f.start:f.end]);po.ins=ins;po.i=0;pp.ins=ins;pp.i=0
           events=[]
           def ot(left,pc):
            if (pc>=0xc000 and mo.o7ffd&7) or pc not in WATCH:return
            # Save exact original plot event state, not the patched descriptor.
            events.append((pc,list(so.registers),[bytes(b) for b in mo.banks] if pc in (0xc7dd,0xd702,0xc090) else None))
           so.exec_frame(fc,None,ot)
           ei=0;left=fc
           def pt(rem,pc):
            if pc in WATCH and not (pc>=0xc000 and mp.o7ffd&7):raise Event(rem,pc)
           while left>0:
            try:sp.exec_frame(left,None,pt);left=0
            except Event as e:
             left,pc=e.args
             if ei>=len(events) or events[ei][0]!=pc:
              fail('hook order',[pc,events[ei][0] if ei<len(events) else None]);return counts,failures
             _,er,eb=events[ei];ei+=1
             # Original-event view: immutable bytes captured at this plot, original regs.
             class RefMem:
              def __getitem__(self,a):
               if a<0x4000:return mo[a]
               return (eb or mo.banks)[{1:5,2:2,3:0}[a>>14]][a&16383]
             class RefSim:pass
             rs=RefSim();rs.memory=RefMem();rs.registers=er;ref(pc,rs)
             if pc==0xc090:
              # At the actual post-blit boundary, erase precisely the original figure
              # ink from the original ULA. Every remaining pixel must be scenery.
              want=bytearray(eb[5][:6144]);actual=bytes(mp.banks[5][:6144])
              for ox,oy,pix,ink in refs.values():
               for x,y in ink:
                xx=ox+x;yy=oy+y
                if 16<=xx<240 and 0<=yy<144:
                 off=((yy&0xC0)<<5)|((yy&7)<<8)|((yy&0x38)<<2)|(xx>>3)
                 want[off]^=128>>(xx&7)
              if bytes(want)!=actual:
               diff=[(i,want[i],actual[i]) for i in range(6144) if want[i]!=actual[i]]
               fail('ULA figure removal',dict(count=len(diff),examples=diff[:4]))
              counts['ULA checks']+=1
              sp.exec_frame(1,None,None)
             else:hook(pc)
             left-=1
           if ei!=len(events):fail('missing hooks',[ei,len(events)])
           ro=so.registers;rp=sp.registers;pc=ro[24]
           # XOR plot working registers legitimately carry different screen bytes until
           # the plot returns; compare all registers at every other frame boundary.
           inplot=(0xc67e<=pc<=0xc77a or 0xc7cf<=pc<0xc889 or 0xc955<=pc<=0xc9ef or 0xd75e<=pc<=0xd7e9 or 0xbbec<=pc<=0xbc0a)
           if not inplot:
            diff=[(i,ro[i],rp[i]) for i in range(30) if i not in (25,29) and ro[i]!=rp[i]]
            # The room-opening LDIR copies presentation bytes. Only its undocumented
            # F3/F5 depend on that byte; D003 ADD HL,BC replaces them before any test.
            if pc in (0xCFED,0xCFEE,0xCFEF,0xCFF0,0xD001,0xD002,0xD003):
             diff=[d for d in diff if not(d[0]==1 and (d[1]^d[2])&~0x28==0)]
            if diff:fail('registers',dict(pc=hex(pc),diff=diff))
            counts['register checks']+=1
           if ro[24]!=rp[24]:fail('PC',[ro[24],rp[24]])
           if po.i!=pp.i or po.i!=len(ins) or po.bad or pp.bad:fail('inputs',[po.i,pp.i,len(ins),po.bad,pp.bad])
           if po.outs!=pp.outs:fail('game ports',[len(po.outs),len(pp.outs)])
           po.outs.clear();pp.outs.clear()
           # All game RAM outside screen/bitmap buffer, code sites and dead stack.
           for bank in range(8):
            a=mo.banks[bank];b=mp.banks[bank]
            if a==b:continue
            base={5:0x4000,2:0x8000}.get(bank,0xc000);bad=[]
            for off,(x,y) in enumerate(zip(a,b)):
             if x==y:continue
             ad=base+off
             if bank==5 and (off<6912 or 0x5b00<=ad<min(ro[12],rp[12])):continue
             if bank==0 and 0xeb00<=ad<0xfd00:continue
             if bank in (0,2) and ad in EXCLUDE:continue
             bad.append((hex(ad),x,y))
             if len(bad)>=3:break
            if bad:fail('RAM',[bank,bad]);break
           counts['RAM checks']+=1
           if failures and mode!='normal':return counts,failures
           if counts['PC!'] or counts['hook order!'] or counts['inputs!']:return counts,failures
           for sim in (so,sp):
            r=sim.registers;r[25]=0
            if r[26]:
             if sim.memory[r[24]]==0x76:r[24]=(r[24]+1)&65535
             sim.accept_interrupt(r,sim.memory,0)
           if progress and frame%250==0:progress(frame)
          if limit and frame>=limit:break
         counts.update({'asset negative %s %s' % (k, v['result']): 1 for k, v in negatives.items()})
         counts['asset negatives detected']=sum(n['result']=='DETECTED' for n in negatives.values())
         counts['frames']=frame;counts['elapsed seconds']=round(time.monotonic()-started,2)
         return counts,failures

        return run(path, mode, limit, progress)
    finally:
        engine.finish, engine.variant_enhanced = saved


# ---------------------------------------------------------------------------------------------
# Detector, loading screen, auto (imported 2026-11-04: the pilot built with the module's build() and
# work/mkload.py (loading/work/stub.asm), and was not registered in nexclash/engines.py; the same bytes).
# ---------------------------------------------------------------------------------------------

LOADING = 'robin_of_the_wood.scr'     # the tape's loading screen (block 4), beside the snapshot (record input)
LOAD_BANK = 34
SITES_ORIG = {0xC7DD: 'CD7EC6', 0xC08D: 'CD55C9', 0xC16B: '21027C', 0xC05F: 'CD73CE', 0xBBB5: 'CDECBB',
              0xBBCB: 'CDECBB', 0xD702: '32C2D8', 0xD6F1: 'AF321DD8'}


def is_robin_of_the_wood(snap):
    """The 128K release: every patch site holds RobinPatch's original bytes (bank 0 at 0xC000, as the game runs)."""
    if getattr(snap, 'machine', '48K') == '48K':
        return False
    banks = getattr(getattr(snap, 'memory', None), 'banks', None)
    if not banks:
        return False
    peek = lambda a: banks[{1: 5, 2: 2, 3: 0}[a >> 14]][a & 0x3FFF]
    return all(bytes(peek(a + k) for k in range(len(o) // 2)) == bytes.fromhex(o) for a, o in SITES_ORIG.items())


def loading_nex(nex, scr):
    """A sprite build with the tape's loading screen: bank 5's screen area holds the picture, bank 34 (asm loading:
    the hold, then bank 5's own screen put back) is the entry bank, at the end of the file."""
    h = load_profile()['hooks']
    o = bytes(nex)
    if len(scr) != 6912:
        raise ValueError('loading screen: %d bytes, want 6912' % len(scr))
    hd = bytearray(o[:512])
    if hd[18 + LOAD_BANK] or hd[139] != 10 or any(o[18 + k] for k in range(LOAD_BANK + 1, 112)):
        raise ValueError('not a robin_of_the_wood sprite build: bank 34 in use, entry bank %d, or a bank above 34' % hd[139])
    code, end = bytes.fromhex(h['loading']), bytes.fromhex(h['loadend'])
    bank = code + o[512:512 + 6912]
    bank += bytes(0x4000 - len(end) - len(bank)) + end
    hd[9] += 1
    hd[18 + LOAD_BANK] = 1
    hd[139] = LOAD_BANK
    return bytes(hd) + scr + o[512 + 6912:] + bank


def build_all(z80, out, name, say=print):
    import os
    md5 = lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest()
    # No simulated boot: nextboot.check models the 48K paging only (this snapshot pages bank 4 at 0xC000, 7FFD 0x14),
    # and the pilot that built these ran none; the replay starts from the snapshot as the .nex does.
    scr = Path(z80).resolve().parent / LOADING
    plain = os.path.join(out, name + '.nex')
    convert(z80, plain, None, True, quiet=True)
    ok = True
    say('Plain     : %s  %s  (boot not simulated: 128K paging)' % (os.path.basename(plain), md5(plain)))
    for tag, enh in (('sprites', False), ('enhanced', True)):
        f = os.path.join(out, '%s_%s_raw.nex' % (name, tag))
        p = RobinPatch(enhanced=enh)
        convert(z80, f, None, True, quiet=True, patch=p)
        say('%-10s: %s  %s  (%s)' % (tag.capitalize(), os.path.basename(f), md5(f),
            ', '.join('%s %s' % kv for kv in sorted(p.stats.items()))[:200]))
        if scr.exists():
            ld = os.path.join(out, '%s_%s.nex' % (name, tag))
            Path(ld).write_bytes(loading_nex(Path(f).read_bytes(), scr.read_bytes()))
            say('Loading   : %s  %s  (the tape\'s screen held by bank 34 until a key or 5 s)' % (os.path.basename(ld), md5(ld)))
        else:
            say('Loading   : no %s beside the snapshot: no loading-screen build' % LOADING)
    return ok


def unit_tests(patch=None, states=(), neg=None, z80=None):
    """Static census the recordings do not cover: every graphic of the three figure tables, both facings, all eight
    vertical phases, against the independent closed-silhouette reference (same pixels, same colour codes, every seam
    closed). Negative control: the same figure with its closed seams dropped must differ. -> (Counter, failures)."""
    from .z80tonex import Z80Snapshot
    c = Counter()
    f = []
    snap = Z80Snapshot(str(z80))
    peek = lambda a: snap.banks[{1: 5, 2: 2, 3: 0}[a >> 14]][a & 16383]
    graphics = sorted({peek(a) + 256 * peek(a + 1) for a in range(0x8C25, 0x8CB7, 2)})
    for g in graphics:
        for mirror in (False, True):
            for phase in range(8):
                ink = variant(peek, g, mirror, phase, raw=True)
                _, pix, _ = variant(peek, g, mirror, phase)
                policy, seams = reference(tuple(sorted(ink.items())))
                c['census cases'] += 1
                c['seam pixels'] += len(seams)
                if set(pix) != set(policy) or any(pix[p] != policy[p] for p in policy):
                    c['figure differs from the closed-silhouette reference!'] += 1
                    if len(f) < 5:
                        f.append((hex(g), mirror, phase))
                if seams:
                    c['negative control cases'] += 1
                    broken = {p: v for p, v in pix.items() if p not in seams}
                    if set(broken) != set(policy):
                        c['negative control detected'] += 1
    if c['negative control detected'] != c['negative control cases']:
        c['negative control (seams dropped) NOT DETECTED!'] += 1
    return c, f


def auto(a, z80, name, out, say):
    import os, time
    say('Game      : %s' % name)
    say('Engine    : robin_of_the_wood (ULA figure ink removed after the blit; every figure a closed solid sprite)')
    ok = build_all(z80, out, name, say)
    rzxs = list(a.rzx or [])
    stop = getattr(a, 'quick', None)
    for r in rzxs:
        for enh in (False, True):
            t = time.time()
            c, f = verify(r, z80, 'normal', enh, stop)
            bad = {k: v for k, v in c.items() if k.endswith('!')}
            ok = ok and not f and not bad
            say('Verify    : %s%s  %d frames, %d hook calls, %d layer checks, %d closed figure checks, %d RAM checks, %s, '
                '%.0fs -> %s' % ('Enhanced ' if enh else '', os.path.basename(r), c['frames'],
                                sum(v for k, v in c.items() if k.startswith('hook ')), c['layer checks'],
                                c['closed figure checks'], c['RAM checks'],
                                ', '.join(k for k in sorted(c) if k.startswith('asset negative')) or 'no asset negatives',
                                time.time() - t, 'IDENTICAL' if not f and not bad else 'FAILED %s %s' % (bad, str(f[:2])[:300])))
            ok = ok and not any(k.startswith('asset negative') and k.endswith('UNDETECTED') for k in c)
    u, uf = unit_tests(None, (), None, z80)
    ub = {k: v for k, v in u.items() if k.endswith('!')}
    ok = ok and not ub
    say('Unit      : %d census cases (68 graphics x facing x phase), %d seam pixels, negative control %d/%d -> %s' % (
        u['census cases'], u['seam pixels'], u['negative control detected'], u['negative control cases'],
        'PASS' if not ub else 'FAIL %s %s' % (ub, uf)))
    if rzxs and not stop:
        r = next((x for x in rzxs if os.path.basename(x).startswith('lifecycle')), rzxs[0])
        det = tot = 0
        for enh, negs in ((False, NEGATIVES), (True, NEGATIVES_ENH)):
            for m in negs:
                tot += 1
                try:
                    c, f = verify(r, z80, m, enh, None)
                    res = 'DETECTED on %s %s (frame %d)' % (os.path.basename(r), f[0]['what'], f[0]['frame']) if f else 'NOT DETECTED'
                except ValueError as e:             # the build's own guard refuses the broken art
                    res = 'DETECTED (the build refuses it: %s)' % e
                det += res.startswith('DETECTED')
                say('Negative  : %-16s%s %s' % (m, ' Enhanced' if enh else '', res))
        ok = ok and det == tot
        say('Negatives : %d of %d DETECTED' % (det, tot))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('snapshot');ap.add_argument('output');ap.add_argument('--colours')
    ap.add_argument('--enhanced',action='store_true',help='the optional Enhanced colour set, painted by parts')
    a=ap.parse_args();build(a.snapshot,a.output,a.colours,a.enhanced)

