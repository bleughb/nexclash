"""The New Zealand Story colour build: the data (tilemap scenery, sprite figures and their palette), all made at build
time from the game's own tape blocks (maps, char sets, sprite sets) and its start state (the fixed frames), coloured by
rules (the owner's approved proposal and item corrections). Nothing of the game is stored here: the rules name frame
numbers and colours. Engine: nexclash/new_zealand_story.py.

Pages (Next 8K):
  LVBASE+level (21 pages): per level 0x0000 slot count, 0x0100 tilemap palette (256 x 2 bytes),
      0x0300 SLOT[code], 0x0400 ATTR[code], 0x0500 tiles (slot 1..n, 32 bytes each);
      0x1E00-0x1EFF hook scratch, 0x1F00-0x1FFF stack zone (mapped at 0x6000 during hooks).
  PRBASE.. : figure programs (MMU0 reads): per (set, frame, mirror) n parts of
      (dx lo, dx hi, dy, pid lo, pid hi, attr2 = palette offset << 4 | X mirror << 3, frame hy).
  PTBASE.. : 4-bit 16x16 patterns, 64 per page, pid = 64 * (page - PTBASE) + index.
Alt ROM tables (in the hook image): SETOF[256] (frame 20's height -> set), DIR (page, offset lo, hi, n).
Sprite palette: 16 x 16 entries; 1 black, 2 white, 4+2g / 5+2g body / second of group g (6 groups a
sub-palette).

Scenery colours: paper regions of each 8x8 char are coloured by the char's collision type (0 background, 1 solid,
2 water, 3/4 waterfall and cap, 7 spikes); enclosed paper gets the type's second colour. Figures: enclosed paper =
body, small enclosed parts = second colour, ink black, 1-pixel outline outside the ink. All colours quantised to the
Next's RGB333.
"""
import os

# The game's bytes for one build: set by use() before any function here runs (the engine's build does it).
_GAME = {'levels': None, 'mem': None}


def use(level_blocks, mem):
    """level_blocks: {name: data bytes without flag/checksum} of the 36 world-load blocks (from the tapes);
    mem: the start state's 64K (its fixed figure frames and descriptor table)."""
    global _PLAN
    _GAME['levels'], _GAME['mem'] = dict(level_blocks), bytes(mem)
    _PLAN = None


def blocks():
    return _GAME['levels']


# ---------------------------------------------------------------- colour rules
def q(c):  # RGB888 -> nearest RGB333 shown as RGB888
    return tuple(round(round(v*7/255)*255/7) for v in c)
def hexc(h): return q((int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)))
BLACK=(0,0,0); WHITE=(255,255,255)
# per world: type -> (outer paper, enclosed paper, ink for the sprite-stage look)
WORLD_PAL={
 1:{'name':'World 1 (Auckland)','sky':'8CCBFF',0:('8CCBFF','FFF0B0','000000'),1:('E06A1C','FFB24C','5A2000'),
    2:('2E6EE0','6EA8FF','001C6E'),3:('6EC8FF','FFFFFF','00246E'),4:('C060E0','FFB0FF','400060'),7:('8CCBFF','FFFFFF','B00000')},
 2:{'name':'World 2 (caves)','sky':'FFD49C',0:('FFD49C','FFFFFF','000000'),1:('8E5A34','D49460','3A1C00'),
    2:('24A0A0','80E0E0','004040'),3:('80E0FF','FFFFFF','004060'),4:('E05050','FFB0B0','600000'),7:('FFD49C','FFFFFF','C00000')},
 3:{'name':'World 3 (temple)','sky':'B4F0C8','0':0,0:('B4F0C8','FFFFFF','000000'),1:('6E7CA8','B4C0E8','1C2448'),
    2:('2E8A3C','70D070','003000'),3:('3C6EFF','A0C8FF','001C80'),4:('B04CD0','F0A0FF','400060'),7:('B4F0C8','FFFFFF','C00000')},
 4:{'name':'World 4 (sea)','sky':'A8E4FF',0:('A8E4FF','FFFFE0','000000'),1:('A8642C','E0A060','402000'),
    2:('2050C0','4C8CF0','00205C'),3:('A0D8FF','FFFFFF','004080'),4:('E0A040','FFE0A0','603000'),7:('A8E4FF','FFFFFF','C00000')},
 5:{'name':'World 5 (ice)','sky':'C8C0FF',0:('C8C0FF','FFFFFF','000000'),1:('70B8E8','E0F8FF','103C70'),
    2:('3050B0','7090E0','001050'),3:('A0E0FF','FFFFFF','004080'),4:('E080C0','FFC0E0','600030'),7:('C8C0FF','FFFFFF','C00000')},
}
WORLD_CSETS={1:['CA'],2:['CB'],3:['CC'],4:['CD'],5:['CE','CF']}
WORLD_BOSS={1:'CG',2:'CH',3:'CI',4:None,5:'CJ'}
def pal(world,t):
    p=WORLD_PAL[world]; e=p.get(t,p[0]); return tuple(hexc(x) for x in e)
def components(paper,W,H):
    """4-connected components of paper pixels: list of (pixels, touches_edge)."""
    seen=set(); out=[]
    for p0 in paper:
        if p0 in seen: continue
        st=[p0]; seen.add(p0); comp=[]; edge=False
        while st:
            x,y=st.pop(); comp.append((x,y))
            if x==0 or y==0 or x==W-1 or y==H-1: edge=True
            for n in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                if n in paper and n not in seen: seen.add(n); st.append(n)
        out.append((comp,edge))
    return out
def paint_char(world,glyph,ctype,ink_mode='black'):
    """8x8 list of RGB. ink_mode 'black' = stage E (ULA lines on top), 'own' = sprite stage."""
    outer,inner,ink=pal(world,ctype)
    px=[[None]*8 for _ in range(8)]; paper=set()
    for y in range(8):
        for x in range(8):
            if glyph[y]&(0x80>>x): px[y][x]=None if ink_mode=='under' else (BLACK if ink_mode=='black' else ink)
            else: paper.add((x,y))
    for comp,edge in components(paper,8,8):
        c=outer if edge else inner
        for x,y in comp: px[y][x]=c
    if ink_mode=='under':   # stage E: ink lies under the ULA's black; give it the nearest paper colour, darker
        for y in range(8):
            for x in range(8):
                if px[y][x] is None:
                    n=[px[yy][xx] for xx,yy in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)) if 0<=xx<8 and 0<=yy<8 and px[yy][xx] is not None and (glyph[yy]&(0x80>>xx))==0]
                    base=n[0] if n else outer
                    px[y][x]=q(tuple(int(v*0.7) for v in base))
    return px
# ---- figures
FIG_RULES=[  # (first frame, last frame, body, second, label)  -- frame numbers of the descriptor table
 (1,17,'FFE020','FF8C00','Tiki (player)'),(18,18,'C8C8D8','FFE020','cage with kiwi'),(19,19,'FFE020','FF8C00','kiwi friend'),
 (20,25,'F08CC8','FFFFFF','cat-masks'),(26,31,'7C3CC8','E0C0FF','bats'),(32,33,'7C3CC8','E0C0FF','flyers'),
 (34,40,'3CA0D0','FFE0A0','spearmen'),(41,41,'FF8020','FFE040','burst'),(42,42,'FFE040','FFFFFF','star'),
 (43,44,'8C5028','E0A060','hedgehogs'),(45,48,'3C9C3C','8C5028','tree devils'),(49,50,'D0A060','FFFFFF','basket'),
 (51,51,'E03030','FFB0B0','devil'),(52,53,'B06830','F0C080','boar'),(54,58,'E04040','FFC0C0','crabs'),
 (59,60,'FF9030','FFFFFF','cats'),(61,64,'4C70E0','FFD0A0','men'),(65,66,'F0F0F0','FFB0C0','rabbits'),
 (67,72,'F078C8','FFD0F0','conch shells'),(73,74,'C0A040','FFFFFF','arch, door'),(75,79,'50C050','FFFFA0','frogs'),
 (80,81,'7C3CC8','E0C0FF','bow bats'),(82,82,'B0B0B0','FFC0C0','mouse'),(83,83,'FF3030','FFFFFF','balloon (ride)'),
 (84,85,'FF8020','FFE040','bursts'),(86,86,'F8F8F8','FFA000','duck (ride)'),(87,87,'3C8CFF','FFFFFF','balloon'),
 (88,90,'40C0C0','FFFFFF','masks'),(91,91,'D0A060','FFFFFF','sign'),(92,93,'FFFFFF','FFE040','sparkle'),
 (94,97,'E0E0FF','FFB0B0','ghosts'),(98,107,'D0A060','FF4040','arrows, bullets'),(108,114,'FF60C0','FFE040','items, flowers'),
 (115,124,'FFD020','E03030','fruit'),(125,139,'FF4040','FFE040','shots, misc'),
]
BOSS_RULES={'CG':{20:('A0C8E8','FFFFFF','whale')},'CH':{20:('B0B0B0','E0E0E0','dome'),21:('5CB040','D0F0A0','spiked body')},
            'CI':{20:('FFC8A0','FF8080','big face'),21:('B060E0','FFE0FF','part'),22:('B060E0','FFE0FF','part')},
            'CJ':{20:('A06838','F0C080','walrus face'),21:('6C8CB0','D0E0F0','Wally the seal')}}
def fig_rule(n,setname=None):
    if setname in BOSS_RULES and n in BOSS_RULES[setname]:
        b,s,l=BOSS_RULES[setname][n]; return hexc(b),hexc(s),l
    for a,z,b,s,l in FIG_RULES:
        if a<=n<=z: return hexc(b),hexc(s),l
    return hexc('C0C0C0'),hexc('FFFFFF'),'?'
def paint_figure(inkset,W,H,body,second,outline=True):
    """dict (x,y)->RGB over a box padded by 1 on all sides (coords may be -1..W)."""
    out={}
    paper=set((x,y) for y in range(-1,H+1) for x in range(-1,W+1) if (x,y) not in inkset)
    comps=components(set((x+1,y+1) for x,y in paper),W+2,H+2)
    inside=[c for c,e in comps if not e]
    big=max((len(c) for c in inside),default=0)
    for c in inside:
        col=body if (len(c)>=max(6,big//4) or len(c)<=2) else second
        for x,y in c: out[(x-1,y-1)]=col
    for p in inkset: out[p]=BLACK
    if outline and W*H>=48 and H>=8:
        oc=WHITE if sum(body)<600 else BLACK
        for (x,y) in list(inkset):
            for n in ((x+1,y),(x-1,y),(x,y+1),(x,y-1),(x+1,y+1),(x-1,y-1),(x+1,y-1),(x-1,y+1)):
                if n not in out: out[n]=oc
    return out

# ---------------------------------------------------------------- scenery data from the tape blocks
# level index (A402) -> (map name, char set name); char set table 0xD3DD (levels 0,4,8,12,17,19)
CSET={0:'CA',4:'CB',8:'CC',12:'CD',17:'CE',19:'CF'}
NAMES=['1-1','1-2','1-3','1-4','2-1','2-2','2-3','2-4','3-1','3-2','3-3','3-4',
       '4-1','4-2','4-3','4-4a','4-4b','5-1','5-2','5-3','5-4']
WORLD=[0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,3,4,4,4,4]
def cset_of(level):
    c=None
    for k in sorted(CSET):
        if level>=k: c=CSET[k]
    return c
class Charset:
    def __init__(self,name):
        d=blocks()[name]; self.name=name; self.raw=d
        self.gfx=d[0:0x800]; self.types=d[0x800:0x900]; self.meta=d[0x900:0xC00]
    def glyph(self,code):   # 8 bytes, top row first
        return bytes(self.gfx[r*256+code] for r in range(8))
    def type(self,code): return self.types[code]&7
    def mt(self,m):  # TL TR BL BR
        return self.meta[4*m:4*m+4]
class Map:
    def __init__(self,level):
        self.level=level; self.name='M'+chr(65+level); d=blocks()[self.name]; self.raw=d
        self.W=d[0]; self.H=d[1]; self.cells=d[2:2+64*64]; self.tail=d[2+self.W*self.H:]
        self.cs=Charset(cset_of(level))
    def metatile(self,col,row): return self.cells[(row%self.H)*self.W+(col%self.W)]
    def chargrid(self):
        """2W x 2H char codes."""
        g=[[0]*(2*self.W) for _ in range(2*self.H)]
        for r in range(self.H):
            for c in range(self.W):
                t=self.cs.mt(self.metatile(c,r))
                g[2*r][2*c]=t[0]; g[2*r][2*c+1]=t[1]; g[2*r+1][2*c]=t[2]; g[2*r+1][2*c+1]=t[3]
        return g

# ---------------------------------------------------------------- figure records and frames
def frame_of(m,ix):
    p=(m[ix+6]|m[ix+7]<<8)+m[ix+8]; return m[p&0xFFFF]
def desc(m,n):
    a=0x9AFA+(n-1)*6; off=m[a]|m[a+1]<<8
    return dict(n=n,addr=(0x7E92+off)&0xFFFF,w=m[a+2],h=m[a+3],hx=m[a+4],hy=m[a+5])
def bits(m,d,mirror):
    """set of (x,y) ink pixels of frame d, mirrored if asked."""
    s=set(); W=d['w']*8
    for y in range(d['h']):
        for xb in range(d['w']):
            b=m[d['addr']+y*d['w']+xb]
            for i in range(8):
                if b&(0x80>>i):
                    x=xb*8+i; s.add((W-1-x if mirror else x,y))
    return s
def records(m):
    out=[]
    for k in range(36):
        ix=0x5CB2+32*k
        if m[ix+0x0C]==0: continue
        out.append(dict(slot=k,ix=ix,type=m[ix+0x0C],drawn=m[ix+0x0D],x4=m[ix+4],y5=m[ix+5],
                        mir=m[ix+0x0B]&1,frame=frame_of(m,ix),raw=bytes(m[ix:ix+32])))
    return out
def buf_pixel(m,x,y,base=0xE700):
    return (m[base+y*32+(x>>3)]>>(7-(x&7)))&1
def screen_pos(m,ix_or_rec,d,mir):
    """Top-left pixel of a plotted frame: the clipper 0xDCB8 halves the hot spot with SRA (floor of
    -h/2), so x = 2*(+4) - 2*ceil(h/2), h = hx (mirrored: 8w - hx); y = (+5) - hy."""
    x4,y5=(m[ix_or_rec+4],m[ix_or_rec+5]) if isinstance(ix_or_rec,int) else (ix_or_rec['x4'],ix_or_rec['y5'])
    h=(d['w']*8-d['hx']) if mir else d['hx']
    y=(y5-d['hy'])&255                  # the clipper's 8-bit arithmetic: 144..255 = above the top
    if y>=144: y-=256
    return 2*x4-2*((h+1)//2), y

def memory(setname=None):
    m=bytearray(_GAME['mem'])
    if setname:
        d=blocks()[setname]; m[0x7E92:0x7E92+0xD00]=d[:0xD00]; m[0x9AFA:0x9AFA+0x100]=d[0xD00:0xE00]
    return m
def frame(m,n):
    a=0x9AFA+(n-1)*6; off=m[a]|m[a+1]<<8; w=m[a+2]; h=m[a+3]; hx=m[a+4]; hy=m[a+5]
    g=0x7E92+off
    return dict(n=n,addr=g,off=off,w=w,h=h,hx=hx,hy=hy,data=bytes(m[g:g+w*h]))

# ---------------------------------------------------------------- the build data
ALTPG=82; LVBASE=46; PRBASE=68; PTBASE=70   # stage 1 uses pages 20-44 (block 37 from side B fills 44, bank 22): the alt ROM image goes to page 82 (bank 41); all below 96 (768K)
SETS=['CK0','CG','CH','CI','CJ']
BOSSLEVEL={3:'CG',7:'CH',11:'CI',20:'CJ'}
def rgb9(c):
    r,g,b=(round(v*7/255) for v in c); return (r<<6)|(g<<3)|b
def world_of(level): return WORLD[level]+1
# ---------------- tiles
def level_page(level,mode,bd=False):
    """mode 'under' (stage E: ULA lines on top) or 'own' (stage F: tiles over the ULA)."""
    mp=Map(level); cs=mp.cs; w=world_of(level)
    codes=sorted(set(x for row in mp.chargrid() for x in row))
    assert len(codes)<=175, (level,len(codes))
    pal={t:[None] for t in range(8)}; tiles={}; slot=bytearray(256); attr=bytearray(256)
    for n,code in enumerate(codes,1):
        t=cs.type(code); gl=cs.glyph(code); px=paint_char(w,gl,t,mode); idx=[]
        for y in range(8):
            for x in range(8):
                if bd and t==0 and not gl[y]&(0x80>>x):
                    idx.append(0); continue     # v1.2 Backdrops: background paper is tile pixel 0, transparent ($4C=0)
                c=px[y][x]
                if c not in pal[t]: pal[t].append(c)
                idx.append(pal[t].index(c))
        assert len(pal[t])<=16
        tiles[n]=bytes((idx[i]<<4)|idx[i+1] for i in range(0,64,2))
        slot[code]=n; attr[code]=(t<<4)|(1 if mode=='under' else 0)
    palette=[0]*256
    for t,cols in pal.items():
        for i,c in enumerate(cols):
            if c is not None: palette[t*16+i]=rgb9(c)
    pg=bytearray(8192); pg[0]=len(codes)
    pg[0x100:0x300]=b''.join(bytes([v>>1,v&1]) for v in palette)
    pg[0x300:0x400]=slot; pg[0x400:0x500]=attr
    for n,tb in tiles.items(): pg[0x500+32*(n-1):0x500+32*n]=tb
    return bytes(pg),{'codes':codes,'slot':bytes(slot),'attr':bytes(attr),'tiles':tiles,'palette':palette}
# ---------------- figures
GROUPS=[(a,z) for a,z,b,s,l in FIG_RULES]
def group_of(n,setname):
    if setname in BOSS_RULES and n in BOSS_RULES[setname]:
        return len(GROUPS)+sum(len(BOSS_RULES[k]) for k in ['CG','CH','CI','CJ'][:['CG','CH','CI','CJ'].index(setname)])+sorted(BOSS_RULES[setname]).index(n)
    for i,(a,z) in enumerate(GROUPS):
        if a<=n<=z: return i
    return 0
def group_colours():
    cols=[]
    for a,z,b,s,l in FIG_RULES: cols.append((hexc(b),hexc(s)))
    for k in ['CG','CH','CI','CJ']:
        for n in sorted(BOSS_RULES[k]): b,s,l=BOSS_RULES[k][n]; cols.append((hexc(b),hexc(s)))
    return cols
def is_boss(n,setname): return setname in BOSS_RULES and 20<=n<=42 and setname!='CK0'
# Items are drawn by the game as SOLID ink pictures (the ink is the body, the paper gaps are the line
# art), so the see-through fill rule makes them black blobs. The owner's rule (2026-11-04): fruit and
# pickups solid in their own colours, the game's line art kept as darker detail. Identified from the
# game's item tables: an enemy that dies drops one of the fruit at 0xD15C (frames 115, 116, 117, 116,
# random); every eighth drops a special item, codes 0x2A-0x33 (table 0xCAE8) -> frames via 0xD013.
#        frame: (what, ink = body, paper inside = detail, rim (ink touching the outside), [(x0,y0,x1,y1, ink colour)])
ITEMS={
 115:('banana (fruit)',          'FFE040','B07800','C89000',[(0,0,15,2,'8C5028')]),
 116:('grapes (fruit)',          '9C48DC','401860','6C2CA0',[(9,0,15,4,'3CA03C')]),
 117:('apple (fruit)',           'E02828','FFA8A8','A01010',[(0,0,15,2,'3CA03C')]),
 118:('book (special item 0x32)','3C5CD0','FFF0C0','203890',[]),
 119:('fireball swirl (special item 0x2D/0x2C)','FF6420','FFE040',None,[]),
 120:('plunger (special item 0x30)','B0B0B0','505050','707070',[(0,0,15,6,'E03030')]),
 121:('clock (special item 0x31)','E8B830','4C3010','A07818',[]),
 122:('bow and arrows (special item 0x2B)','B06830','FFE0A0','704018',[(10,0,15,5,'C8C8C8')]),
 123:('bomb (special item 0x2A)', '3C4C90','A0C0FF','202C60',[(7,0,15,4,'FF8C20')]),
 126:('laser gun (special item 0x2C)','2C5C90','C8F0FF',None,[]),
 129:('potion (special item 0x33)','3C5CA0','FF60C0',None,[]),
 130:('picture (special item 0x2E)','D0A040','A0D8FF',None,[]),
}
SOLID_AUTO=0.75          # other figures whose silhouette is at least this much ink are painted solid too
BEAMS={('CI',23),('CI',24),('CJ',23),('CJ',24)}                 # boss beams
DROPS={('CG',21),('CG',22)}                                       # the whale's spout
LINEART={25}                                                      # thin line art that only measures as ink: keep the fill rule
def dark(c,f=0.55): return hexc('%02X%02X%02X'%tuple(int(v*f) for v in c))
# Owner fix (2026-11-04): a mouth or other opening that is part of a figure, even open to the outside on
# one side, showed the sky through it (the pink shell's open mouth). Background pixels inside the
# figure's closed silhouette (the ink closed with a radius of CLOSE_R: dilated, then eroded) are filled
# with MOUTH, the teeth and the game's ink kept, when they lie between ink above and below (the jaws) and
# beside (the back of the mouth): gaps the game means as background, between legs or under an arm, are
# open below and keep the sky. As Ikari Warriors' seam closing.
CLOSE_R=2
MOUTH='6C1010'
FILL_FIX=True
def closed_fill(ink,W,H,r=CLOSE_R):
    """Background pixels of the frame box the closing of the ink with a (2r+1) square covers, and those
    it encloses: what the figure's own shape holds, as against the background around it."""
    box=[(x,y) for y in range(-r-1,H+r+1) for x in range(-r-1,W+r+1)]
    dil=set(p for p in box if any((p[0]+dx,p[1]+dy) in ink for dx in range(-r,r+1) for dy in range(-r,r+1)))
    clo=set(p for p in dil if all((p[0]+dx,p[1]+dy) in dil for dx in range(-r,r+1) for dy in range(-r,r+1)))
    clo|=set(ink)
    paper=set(p for p in box if p not in clo)
    comps=components(set((x+r+1,y+r+1) for x,y in paper),W+2*r+2,H+2*r+2)
    enclosed=set((x-r-1,y-r-1) for c,e in comps if not e for x,y in c)
    cand=set(p for p in (clo|enclosed) if p not in ink and 0<=p[0]<W and 0<=p[1]<H)
    # a mouth, not a gap: ink above and below it in its column (the jaws), and on one side in its row
    # (the back of the mouth). Gaps between legs or under arms are open below, so they stay sky.
    def near(p,dx,dy):
        return any((p[0]+dx*k,p[1]+dy*k) in ink for k in range(1,REACH+1))
    held=set(p for p in cand if near(p,0,-1) and near(p,0,1) and (near(p,-1,0) or near(p,1,0)))
    # the rest of a mouth open on one side: paper held the same way (ink above, below and to one
    # side) that joins the part the closed outline holds
    jaw=set((x,y) for y in range(H) for x in range(W) if (x,y) not in ink
            and near((x,y),0,-1) and near((x,y),0,1) and (near((x,y),-1,0) or near((x,y),1,0)))
    todo=list(held)
    while todo:
        p=todo.pop()
        for q in ((p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)):
            if q in jaw and q not in held: held.add(q); todo.append(q)
    # and big enough to be an opening, not a notch in the outline
    keep=set()
    for c,e in components(set((x+1,y+1) for x,y in held),W+2,H+2):
        if len(c)>=MOUTH_MIN: keep|=set((x-1,y-1) for x,y in c)
    keep-=set(p for p in keep if (p[0]-1,p[1]) in ink and (p[0]+1,p[1]) in ink)   # gaps between teeth stay white
    return keep
REACH=6
MOUTH_MIN=20
# Found by the rule and looked at: not mouths, so left as they were (sheets/fill_fix.png, second row).
NOT_MOUTH={('CK0',18),('CK0',25),('CK0',85),('CK0',96)}   # sky under a caged kiwi's wings; thin line art's body; an explosion's sparks; the sky through a hood's arch
def silhouette(ink,W,H):
    paper=set((x,y) for y in range(-1,H+1) for x in range(-1,W+1) if (x,y) not in ink)
    comps=components(set((x+1,y+1) for x,y in paper),W+2,H+2)
    inside=[[(x-1,y-1) for x,y in c] for c,e in comps if not e]
    outside=set((x-1,y-1) for c,e in comps if e for x,y in c)
    return inside,outside
def solid_kind(m,n,setname):
    if setname=='CK0' and n in ITEMS: return 'item'
    if (setname,n) in BEAMS: return 'beam'
    if (setname,n) in DROPS: return 'drop'
    if setname=='CK0' and n in LINEART: return None
    d=desc(m,n); W=d['w']*8; H=d['h']
    if not W or not H: return None
    ink=bits(m,d,0); inside,_=silhouette(ink,W,H); s=sum(len(c) for c in inside)
    return 'auto' if ink and len(ink)/(len(ink)+s)>=SOLID_AUTO else None
def figure_colours(m,n,setname,mirror,outline=True,clip_outline=False):
    """{(x,y): RGB} over the frame box plus a 1-pixel margin: the colour rules (approved proposal,
    with the owner's item correction)."""
    d=desc(m,n); W=d['w']*8; H=d['h']
    if not W or not H: return None,d
    ink=bits(m,d,mirror); g=group_of(n,setname); body,second=group_colours()[g]
    inside,outside=silhouette(ink,W,H); kind=solid_kind(m,n,setname); out={}
    if kind is None:                              # line art with see-through body: fill it
        big=max((len(c) for c in inside),default=0)
        for c in inside:
            col=body if (len(c)>=max(6,big//4) or len(c)<=2) else second
            for p in c: out[p]=col
        if FILL_FIX and not is_boss(n,setname) and (setname,n) not in NOT_MOUTH:   # an opening the figure holds: a dark mouth
            for p in closed_fill(ink,W,H):
                if p not in out: out[p]=hexc(MOUTH)
        for p in ink: out[p]=BLACK
    else:                                         # solid picture: the ink is the body
        if kind=='item':
            lab,b,dt,rim,regions=ITEMS[n]; b=hexc(b); dt=hexc(dt); rim=hexc(rim) if rim else None
            regions=[(x0,y0,x1,y1,hexc(c)) for x0,y0,x1,y1,c in regions]
        elif kind=='beam':
            b,dt,rim,regions=hexc('A0F0FF'),hexc('FFFFFF'),hexc('3C8CC8'),[]
        elif kind=='drop':
            b,dt,rim,regions=hexc('80C0FF'),hexc('FFFFFF'),hexc('2C64C8'),[]
        else:
            b,dt,rim,regions=body,second,dark(body),[]
        for c in inside:
            for p in c: out[p]=dt
        for (x,y) in ink:
            ux=(W-1-x) if mirror else x           # regions are given on the unmirrored picture
            col=b
            for x0,y0,x1,y1,rc in regions:
                if x0<=ux<=x1 and y0<=y<=y1: col=rc
            if rim and col==b and any(q in outside for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1))): col=rim
            out[(x,y)]=col
        body=b
    if outline and not is_boss(n,setname) and W*H>=48 and H>=8:
        oc=WHITE if sum(body)<600 else BLACK
        for (x,y) in list(ink):
            for q in ((x+1,y),(x-1,y),(x,y+1),(x,y-1),(x+1,y+1),(x-1,y-1),(x+1,y-1),(x-1,y+1)):
                if q not in out:
                    if clip_outline and not (0<=q[0]<W and 0<=q[1]<H): continue
                    out[q]=oc
    return out,d
def rgb9c(c): return rgb9(c)
_PLAN=None
def palette_plan():
    """Pack every frame's colours into the 16 sprite sub-palettes (1 black, 2 white in each):
    {(setname, frame): palette offset}, [256 x 9-bit]."""
    global _PLAN
    if _PLAN: return _PLAN
    need={}
    for si,s,n in frame_list():
        m=memory(s); cols=set()
        for mir in (0,1):
            c,d=figure_colours(m,n,s,mir)
            if c: cols|=set(rgb9(v) for v in c.values())
        need[(s,n)]=cols-{rgb9(BLACK),rgb9(WHITE)}
    subs=[set() for _ in range(16)]; po={}
    for key in sorted(need,key=lambda k:-len(need[k])):
        cs=need[key]
        best=None
        for i,sp in enumerate(subs):
            if len(sp|cs)<=13 and (best is None or len(sp|cs)<len(subs[best]|cs)): best=i
        assert best is not None,'sprite palette full'
        subs[best]|=cs; po[key]=best
    pal=[0]*256; index={}
    for i,sp in enumerate(subs):
        pal[16*i+1]=rgb9(BLACK); pal[16*i+2]=rgb9(WHITE); index[(i,rgb9(BLACK))]=1; index[(i,rgb9(WHITE))]=2
        for k,v in enumerate(sorted(sp)): pal[16*i+3+k]=v; index[(i,v)]=3+k
    _PLAN=(po,pal,index)
    return _PLAN
def figure_indices(m,n,setname,mirror,outline=True,clip_outline=False):
    """{(x,y): palette index} for the build's patterns, and the frame descriptor."""
    c,d=figure_colours(m,n,setname,mirror,outline,clip_outline)
    if not c: return None,d
    po,pal,index=palette_plan(); p=po[(setname,n)]
    return {k:index[(p,rgb9(v))] for k,v in c.items()},d
def frame_list():
    """(set index, setname, frame) for every directory entry, in DIR order."""
    L=[(0,'CK0',n) for n in range(1,140)]
    for si,s in enumerate(SETS[1:],1): L+= [(si,s,n) for n in range(20,43)]
    return L
def dir_index(si,n,mir):
    if si>0 and 20<=n<=42: return 139*2+((si-1)*23+n-20)*2+mir
    return (n-1)*2+mir
def figures(neg=None):
    mems={s:memory(s) for s in SETS}
    pats={}; plist=[]; progs={}
    for si,s,n in frame_list():
        m=mems[s]
        idx,d=figure_indices(m,n,s,0,clip_outline=(neg=='NEG_OUTLINE'))   # unmirrored; mirror by the sprite's X mirror bit
        for mir in (0,1):
            parts=[]
            if idx:
                W=d['w']*8; H=d['h']; h=(W-d['hx']) if mir else d['hx']; k=2*((h+1)//2)
                g=group_of(n,s)
                bw=(W+2+15)//16; bh=(H+2+15)//16
                for by in range(bh):
                    for bx in range(bw):
                        blk=bytearray(128); any_=False
                        for yy in range(16):
                            for xx in range(16):
                                v=idx.get((-1+16*bx+xx,-1+16*by+yy),0)
                                if v: any_=True
                                if xx&1: blk[yy*8+xx//2]|=v
                                else: blk[yy*8+xx//2]|=v<<4
                        if not any_: continue
                        key=bytes(blk)
                        if key not in pats: pats[key]=len(plist); plist.append(key)
                        left=(W-15-16*bx) if mir else (-1+16*bx)   # the block's left edge in the (mirrored) image
                        dx=left-k; dy=-1+16*by
                        if neg=='NEG_ROW': dy+=1
                        parts.append((dx,dy,pats[key],palette_plan()[0][(s,n)],d['hy']))
                if is_boss(n,s) and neg=='NEG_BOSSPART' and len(parts)>1: parts=parts[:-1]
            progs[dir_index(si,n,mir)]=parts
    return progs,plist
def sprite_palette(neg=None):
    pal=list(palette_plan()[1])
    if neg=='NEG_PALETTE': pal=pal[16:]+pal[:16]
    return pal
def pack_programs(progs):
    pages=[bytearray(8192)]; dirb=bytearray(); pos=0
    n=max(progs)+1
    for i in range(n):
        parts=progs.get(i,[])
        blob=b''.join(bytes([dx&255,(dx>>8)&255,dy&255,pid&255,pid>>8,(po<<4)|(8 if i&1 else 0),hy]) for dx,dy,pid,po,hy in parts)
        if pos+len(blob)>8192: pages.append(bytearray(8192)); pos=0
        pages[-1][pos:pos+len(blob)]=blob
        dirb+=bytes([PRBASE+len(pages)-1,pos&255,pos>>8,len(parts)]); pos+=len(blob)
    return pages,bytes(dirb)
def pack_patterns(plist):
    pages=[]
    for i in range(0,len(plist),64):
        pg=bytearray(8192)
        for j,p in enumerate(plist[i:i+64]): pg[128*j:128*j+128]=p
        pages.append(pg)
    return pages
def setof():
    t=bytearray([0xFF]*256)
    for si,s in enumerate(SETS):
        d=desc(memory(s),20); assert t[d['h']]==0xFF; t[d['h']]=si
    return bytes(t)
def build_all(out, mode='own', neg=None, bd=False):
    """Write setof.bin, dir.bin, sprite palette; return {page: bytes} for every page of the build."""
    os.makedirs(out,exist_ok=True)
    pages={}
    lvinfo={}
    for lv in range(21):
        pg,info=level_page(lv,mode,bd and neg!='NEG_OPAQUE')
        if neg=='NEG_TILEPAL' and lv==0: pass
        pages[LVBASE+lv]=pg; lvinfo[lv]=info
    progs,plist=figures(neg)
    pp,dirb=pack_programs(progs); pt=pack_patterns(plist)
    for i,p in enumerate(pp): pages[PRBASE+i]=bytes(p)
    for i,p in enumerate(pt): pages[PTBASE+i]=bytes(p)
    assert PRBASE+len(pp)<=PTBASE and PTBASE+len(pt)<=96
    open(os.path.join(out,'setof.bin'),'wb').write(setof())
    open(os.path.join(out,'dir.bin'),'wb').write(dirb)
    spal=sprite_palette(neg)
    open(os.path.join(out,'spal.bin'),'wb').write(b''.join(bytes([v>>1,v&1]) for v in spal))
    p14=bytearray(8192)
    p15=bytearray(8192); p15[0x0400:0x0C00]=b'\xff'*2048; p15[0x0E00:0x0E80]=b'\xff'*128
    pages[14]=bytes(p14); pages[15]=bytes(p15)
    return pages,{'lvinfo':lvinfo,'progs':progs,'plist':plist,'spal':spal}
