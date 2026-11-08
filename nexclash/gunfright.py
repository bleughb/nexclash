"""Gunfright (Ultimate, 1985, 48K): Filmation II hardware compositor, as published in .nxc 1.1.

The original loader, plots, game buffers, simulation and beeper are retained.
Default (v14): the original monochrome town and duel picture on a cached hardware sprite grid.
Enhanced (off by default; v18): the same original drawing recorded at its five producers and replayed into a
double-buffered Layer 2 in the owner's painted colours (asm/gunfright_l2.asm). Everything a build needs is here or
in the user's own copy of the game: the original graphics are read from the snapshot, and
docs/profiles/gunfright_colours.json holds the owner's painting (palette digits per source pixel, no game data).
With the original tape beside the snapshot the original loading screen is added, as in the published release.

    python -m nexclash.gunfright SNAPSHOT OUT.nex [--enhanced]

`nexclash.py auto` (nexclash/engines.py: is_gunfright) builds GAME.nex (default) and GAME_enhanced.nex and boots
both. games/gunfright.md has the design and results.
"""
import json
import os
import collections
from pathlib import Path
from .hooklib import CMP_R

CMP = CMP_R
RECORD = 'gunfright'
HERE = Path(__file__).resolve().parent
TAIL_ADDR = 0x5B00
ALT_PAGE = 26
ROM_ORG = 0x3900
SITES = {0xA3E2: ('cdbbc0', 's_in'), 0xA3F4: ('cda7ae', 's_out'),
         0xD6D4: ('210040', 's_clear')}
TARGETS = {0xA3E2: 0xC0BB, 0xA3F4: 0xAEA7, 0xD6D4: 0xD6D7}
INTERIORS = {a+i for a in SITES for i in (1, 2)}
COLOURS = str(HERE.parent/'docs/profiles/gunfright_colours.json')
SHEET_RGB = [(100,100,100),(0,0,0),(255,255,255),(255,182,146),
             (219,36,36),(36,73,219),(146,73,36),(255,219,36),
             (73,182,36),(36,109,36),(255,109,0),(146,36,182),
             (36,182,219),(146,146,146),(255,219,146),(73,36,0)]


def load_colours():
    """The town figures' colour map in coloursheet form (for sheets): $NEXCLASH_COLOURS when set, else the town map
    of docs/profiles/gunfright_colours.json."""
    from . import coloursheet, recolour
    path = recolour.build_colours_path(COLOURS)
    if path != COLOURS:
        return coloursheet.load(path)
    return {k: [0, 'mask-ink', v] for k, v in load_painting()['town'].items()}


def colour_identity(peek):
    """Stable original graphics plus their source-key interpretation."""
    import hashlib
    return dict(schema=1, game=RECORD, engine=RECORD,
                keys='gunfright-pixel-sources:2',
                inputs=hashlib.md5(bytes(peek(a) for a in range(0x67F4,0xA200))).hexdigest(),
                geometry=None)


def sheet_capture(rzx_paths, prof=None, progress=None):
    """Capture original multipart objects; preserve unobserved coverage gaps."""
    import tempfile
    from . import rzx as RZ
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    cap=dict(memory=None, compositions={}, recordings=[], plots=collections.Counter())
    def event(pc, sim):
        m=sim.memory; r=sim.registers
        if bytes(m[0xA3E2:0xA3E5])!=bytes.fromhex('cdbbc0'):return
        if cap['memory'] is None:cap['memory']=bytes(m)
        if pc==0xB28A:cap['plots']['duel:%02X'%r[0]]+=1;return
        if pc!=0xBD5E:return
        ix=r[8]*256+r[9]; ptr=m[ix+14]+256*m[ix+15]; parts=[]
        for k in range(12):
            x=m[ptr+3*k]
            if x==128:break
            y,g=m[ptr+3*k+1:ptr+3*k+3]
            parts.append((x-256 if x>=128 else x,y-256 if y>=128 else y,g))
            cap['plots']['masked:%02X'%g]+=1
        else:raise ValueError('unterminated original multipart object')
        key=(m[ix],tuple(parts))
        cap['compositions'].setdefault(key,dict(kind=m[ix],parts=parts,count=0))['count']+=1
    with tempfile.TemporaryDirectory(prefix='gunfright_sheets_')as tmp:
        for i,path in enumerate([rzx_paths]if isinstance(rzx_paths,str)else rzx_paths):
            source=path
            if sum(isinstance(b.obj,Snapshot)for b in parse_rzx(path))>1:
                source=str(Path(tmp)/('%d.rzx'%i));RZ.strip(path,source)
            frames,error=RZ.trace(source,{0x5E00,0xBD5E,0xB28A},event)
            cap['recordings'].append(dict(path=str(path),frames=frames,error=error))
            if progress:progress(path,frames,error)
            if error:raise ValueError('sheet recording desync: '+error)
    if cap['memory'] is None:raise ValueError('recordings never reached the original drawing code')
    return cap


def sheets(cap, prefix, colours=None):
    """Whole observed town figures and all twenty source-defined duel opponents.

    Unobserved masked fragments remain explicitly marked additional images;
    their existence is not presented as recording coverage.
    """
    from . import coloursheet as CS
    m=cap['memory']; ident=colour_identity(lambda a:m[a]); groups={'TOWN':[],'DUEL':[]}
    covered=set(); colourmap=load_colours()if colours is None else colours
    def masked(parts, group, count=1):
        records=[]
        for x,y,g in parts:
            if not 0<=g<56:raise ValueError('invalid masked graphic')
            a=m[0x67F4+2*g]+256*m[0x67F5+2*g];w,h=m[a]*8,m[a+1]
            if not w or not h:continue
            if w>64 or h>63:raise ValueError('unexpected original masked dimensions')
            records.append((x,y,g,a,w,h))
        if not records:return
        x0=min(x for x,y,g,a,w,h in records);y0=min(-y-h for x,y,g,a,w,h in records);out=[]
        for x,y,g,a,w,h in records:
            pixels=[];entries={}
            for yy in range(h):
                for b in range(w//8):
                    addr=a+2+2*((h-1-yy)*(w//8)+b);mask,ink=m[addr:addr+2];key='%04x'%addr
                    entries[key]=[mask*256+ink,'mask-ink']
                    for bit in range(8):
                        code=1 if ink&(128>>bit)else 2 if mask&(128>>bit)else 0
                        if code:pixels.append((8*b+bit,yy,key,bit,code,2 if code==1 else 1))
            out.append(dict(id=g,size=w*h,w=w,h=h,dx=x-x0,dy=-y-h-y0,dmir=0,vmir=0,pixels=pixels,entries=entries));covered.add(g)
        groups['TOWN'].append(dict(count=count,group=group,parts=out))
    for r in cap['compositions'].values():masked(r['parts'],'Town figure %02d'%r['kind'],r['count'])
    for g in range(56):
        if g not in covered:masked([(0,0,g)],'Additional original images')
    def duel(ids,group):
        out=[]
        for row,g in enumerate(ids):
            if not 0<=g<41:raise ValueError('invalid original duel strip')
            a=m[0x6AC6+2*g]+256*m[0x6AC7+2*g];pixels=[];entries={}
            for yy in range(8):
                for b in range(4):
                    addr=a+4*yy+b;key='duel:%04x'%addr;entries[key]=[m[addr],'ink-byte']
                    for bit in range(8):
                        if m[addr]&(128>>bit):pixels.append((8*b+bit,7-yy,key,bit,1,2))
            out.append(dict(id='duel-%d'%g,size=256,w=32,h=8,dx=0,dy=8*(len(ids)-1-row),dmir=0,vmir=0,pixels=pixels,entries=entries))
        groups['DUEL'].append(dict(count=1,group=group,parts=out))
    for guy in range(20):
        for pose in range(2):duel(list(m[46504+3*pose:46507+3*pose])+list(m[46510+5*guy:46515+5*guy]),'Opponent %02d'%(guy+1))
    for i in range(3):
        a=m[0xBBAB+2*i]+256*m[0xBBAC+2*i];duel(list(m[a:a+4-i]),'Duel collapse')
    outputs=[]
    for group,comps in groups.items():
        sizes={p['id']:p['size']for c in comps for p in c['parts']}
        for kind,selection in [('REFERENCE_ALL_SPRITES',comps),('PAINTING_SPRITES',CS.choose(comps,sizes))]:
            png='%s_%s_%s.png'%(prefix,group,kind);layout=str(Path(png).with_suffix(''))+'_layout.json'
            if Path(png).exists()or Path(layout).exists():raise ValueError('refusing to overwrite an editable sheet: '+png)
            n=CS.write(selection,png,layout,SHEET_RGB,colourmap,width=256,unique=False,identity=ident);outputs.append((png,n))
    return outputs


def _profile_path():
    return HERE.parent/'docs/profiles/gunfright.json'


def load_profile():
    return json.loads(_profile_path().read_text())


def is_gunfright(snap):
    if getattr(snap, 'machine', '48K') != '48K':
        return False
    sig = load_profile()['signature']
    a = sig['addr']; b = bytes.fromhex(sig['bytes'])
    return bytes(snap.memory[a:a+len(b)]) == b


def derive_start(z80, out, stop=0x5E00):
    """Execute the original PAUSE/USR path; stop before or after its relocation."""
    from .machine import Machine
    from skoolkit.simutils import PC, T, IFF
    m = Machine(str(z80)); r = m.sim.registers

    class Done(Exception): pass
    class FrameDone(Exception): pass

    def trace(fc, pc):
        if pc == stop: raise Done()
        if r[T] >= 69888: raise FrameDone()

    for _ in range(20): m.frame()
    m.held = frozenset({'SPACE'})
    try:
        for _ in range(60):
            try: m.sim.exec_frame(65535, None, trace)
            except FrameDone: pass
            r[T] = 0
            if r[IFF]:
                if m.sim.memory[r[PC]] == 0x76: r[PC] = (r[PC]+1)&65535
                m.sim.accept_interrupt(r, m.sim.memory, 0)
    except Done: pass
    if r[PC] != stop: raise ValueError('original loader did not reach %04X'%stop)
    Path(out).write_bytes(m.z80_bytes())
    return str(out)


class GunfrightPatch:
    name = 'Gunfright original-look town hardware compositor (development)'

    def __init__(self, prof=None, cpu_only=False):
        self.prof = prof or load_profile(); h = self.prof['hooks']
        self.syms = {k:int(v,16) for k,v in h['syms'].items()}
        page = bytearray.fromhex(h['page'])
        if cpu_only: page[self.syms['hlib_dma_policy']-8192] = 0
        for k in range(4):
            for v in range(256):
                page[0x1000+256*k+v] = (2 if v&(128>>(2*k)) else 1)*16+(2 if v&(64>>(2*k)) else 1)
        self.page = bytes(page)
        self.stub_extra = bytes.fromhex(h['setup']); self.setup_call = 0xD000
        self.slot1 = (ALT_PAGE, self.syms['regblock'])
        self.altrom = (0x3900, self.syms['regblock']+20)
        self.tail_addr = TAIL_ADDR; self.uses_printer_buffer = False
        self.keep_printer_buffer = True; self.hook_page_data = b''
        self.extra_banks = {13:self.page+bytes(8192), 14:bytes(16384), 15:bytes(16384)}
        self.sites = [(a, bytes.fromhex(old), b'\xCD'+self.syms[sym].to_bytes(2,'little'))
                      for a,(old,sym) in SITES.items()]

    def apply(self, snap):
        from . import z80tonex as Z
        from .build import rom48
        if snap.is128: raise ValueError('Gunfright expects the original 48K release')
        ram = bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        for a, old, new in self.sites:
            if ram[a-0x4000:a-0x4000+len(old)] != old:
                raise ValueError('unexpected original bytes at %04X' % a)
            ram[a-0x4000:a-0x4000+len(new)] = new
        for k,b in enumerate((5,2,0)): snap.banks[b] = bytes(ram[k*16384:(k+1)*16384])
        # Restore every temporary tail byte before the first game instruction.
        tail, _, restore, _ = Z.build_tail(snap, TAIL_ADDR, self.slot1, True)
        if len(tail)>64: raise ValueError('compact tail exceeds backup area')
        original = bytes(snap.read(TAIL_ADDR+i) for i in range(len(tail)))
        code = b'\xF3'+getattr(self,'boot_prefix',b'')+b'\x21\x00\x39\x11\x00\x5B\x01'+Z.w16(len(tail))+b'\xED\xB0'+tail[restore:]
        if 0x3940+len(code)>=0x3A00 or set(rom48()[0x3900:0x3940+len(code)])!={255}:
            raise ValueError('tail restoration overlaps live ROM')
        page = bytearray(self.page); page[0x1900:0x1900+len(original)] = original
        page[0x1940:0x1940+len(code)] = code
        self.page = bytes(page); self.extra_banks[13] = self.page+bytes(8192)
        self.original_pc = snap.pc; self.tail_restore_bytes = len(tail); snap.pc = 0x3940


def build(z80, out, start=None):
    from . import z80tonex as Z
    start = start or str(Path(out).with_suffix('.start.z80'))
    post=derive_start(z80, str(Path(start).with_suffix('.post.z80')))
    derive_start(z80, start, stop=0x5B96)
    patch = LoaderPatch(post)
    Z.convert(start, out, quiet=True, patch=patch)
    return patch, start


class Model:
    """Independent paged hardware state; executes the actual emitted hooks."""
    core_version = 0x33
    hardware_im2 = 0
    def __init__(self, patch, ram, regs, speed=0):
        from . import nextboot, z80n, simpool
        from .dizzy6 import _rw_simulator
        self.patch=patch; self.pages={}
        for b,raw in patch.extra_banks.items():
            self.pages[b*2]=bytearray(raw[:8192]); self.pages[b*2+1]=bytearray(raw[8192:])
        self.rom=nextboot.alt_image(patch); self.mmu=[255,255,10,11,4,5,0,1]
        self.nr={7:speed, 1:self.core_version, 0xC0:self.hardware_im2}; self.sel=0; self.line=0
        # Setup initializes the used pattern range to opaque black.
        self.pat=bytearray(bytes([0x11])*(77*128)+bytes(16384-77*128)); self.ptr=0; self.attr=[[0]*5 for _ in range(128)]; self.sprite=0
        self.writes=set(); self.trace_writes=False
        outer=self
        class Mem:
            def __len__(s):return 65536
            def __getitem__(s,a):
                if isinstance(a,slice):return [s[i] for i in range(*a.indices(65536))]
                p=outer.mmu[a>>13]
                return outer.rom[a] if p==255 else outer.pages.setdefault(p,bytearray(8192))[a&8191]
            def __setitem__(s,a,v):
                if isinstance(a,slice):
                    for i,n in zip(range(*a.indices(65536)),v):s[i]=n
                    return
                p=outer.mmu[a>>13]
                if p!=255:
                    outer.pages.setdefault(p,bytearray(8192))[a&8191]=v
                    if outer.trace_writes:outer.writes.add(a)
        self.mem=Mem(); self.mem[0x4000:]=ram[0x4000:]
        for a,old,new in patch.sites:self.mem[a:a+len(new)]=new
        self.sim=simpool.machine(_rw_simulator(),self.mem,regs,('gunfright','patched'))
        from .dma import DMA
        self.dma=DMA(lambda a:self.mem[a], lambda a,v:self.mem.__setitem__(a,v),
                     lambda p,v:self.write_port(self.sim.registers,p,v),
                     blitter=self.core_version>=0x33)
        self.sim.int_active=0
        self.sim.set_tracer(self); z80n.install(self.sim,self.nextreg,strict=False)
        self.trace_writes=True

    def nextreg(self, reg, value):
        self.nr[reg]=value
        if 0x50<=reg<=0x57:self.mmu[reg-0x50]=value
        elif reg==0x34:self.sprite=value&127
        elif 0x35<=reg<=0x39:self.attr[self.sprite][reg-0x35]=value

    def read_port(self, regs, port):
        if port==0x253B:
            if 0x50<=self.sel<=0x57:return self.mmu[self.sel-0x50]
            if self.sel==7:return self.nr[7]*17
            if self.sel==0x1E:return self.line>>8
            if self.sel==0x1F:
                n=self.line&255;self.line=(self.line+1)%312;return n
            return self.nr.get(self.sel,0)
        return 255

    def write_port(self, regs, port, value, *ignored):
        if port==0x243B:self.sel=value
        elif port==0x303B:self.ptr=(value&63)*256+(128 if value&128 else 0)
        elif port&255==0x5B:self.pat[self.ptr&16383]=value;self.ptr+=1
        elif port&255==0x6B:self.dma.feed(value)

    def run_to(self, pc, limit=2000000):
        r=self.sim.registers; n=0
        while n==0 or r[24]!=pc:
            self.sim.opcodes[self.mem[r[24]]]()
            n+=1
            if n>=limit:raise AssertionError(('hook did not return',hex(r[24]),hex(pc),n))
        return n


def event_check(patch, pc, mem, regs, carry=None, speed=0):
    """One emitted-hook induction step; original game RAM is refreshed exactly.

    Only extra runtime pages, cached patterns and attributes persist between
    events. Dead stack differences are reported byte by byte, never confused
    with live game state. Native complete-update RAM proof is a separate gate.
    """
    from skoolkit.simulator import Simulator
    from . import simpool
    o = simpool.machine(Simulator, list(mem), list(regs), ('gunfright', 'original'),copy=True)
    o.int_active=0
    o.opcodes[o.memory[pc]]()
    m = Model(patch, mem, regs, speed=speed)
    if carry:
        m.pages.update({p:bytearray(v) for p,v in carry['pages'].items()})
        m.pat[:] = carry['patterns']; m.attr = [list(a) for a in carry['attributes']]
        m.nr.update(carry['nr']); m.line=carry['line']
    if pc==0xA3E2:expected_speed=3
    elif pc==0xA3F4 or (pc==0xD6D4 and m.pages[26][patch.syms['active']-8192]):
        expected_speed=m.pages[26][patch.syms['speed']-8192]
    else:expected_speed=m.nr[7]
    m.run_to(TARGETS[pc])
    bad = {}
    rd = {i:(o.registers[i],m.sim.registers[i]) for i in CMP if o.registers[i]!=m.sim.registers[i]}
    if rd: bad['registers'] = rd
    masks = {a+i for a,old,new in patch.sites for i in range(len(new))}
    diff = [a for a in range(0x4000,0x10000) if a not in masks and o.memory[a]!=m.mem[a]]
    dead = [a for a in diff if regs[12]-64<=a<regs[12] and a in m.writes]
    live = [a for a in diff if a not in dead]
    if live: bad['memory'] = live[:20]
    if m.mmu != [255,255,10,11,4,5,0,1]: bad['mapping'] = m.mmu
    if m.nr[7]!=expected_speed:bad['speed']=(expected_speed,m.nr[7])
    if pc==0xD6D4 and m.nr.get(0x15)!=0: bad['clear'] = 'sprites still visible'
    pixels=0
    if pc==0xA3F4:
        original_attr=mem[0x5825+mem[41577]]
        attrs={mem[0x5800+32*y+x]for y in range(1,15)
               for x in range(5+mem[41577],27+mem[41577])}
        if attrs!={original_attr} or original_attr&0xF8!=0x40:
            bad['original attribute coverage'] = sorted(attrs)
        for i,a in enumerate(m.attr[:77]):
            x=a[0]+((a[2]&1)<<8)-32; y=a[1]-32
            wx=40+8*mem[41577]+16*(i%11); wy=8+16*(i//11)
            if (x,y)!=(wx,wy): bad.setdefault('positions',[]).append((i,x,y,wx,wy))
            if a[2]>>4 != original_attr&7:
                bad.setdefault('colours',[]).append((i,a[2]>>4,original_attr&7))
            for dy in range(16):
                for dx in range(16):
                    sx,sy=wx+dx,wy+dy
                    at=0x4000+((sy&192)<<5)+((sy&7)<<8)+((sy&56)<<2)+(sx>>3)
                    want=2 if mem[at]&(128>>(sx&7)) else 1
                    b=m.pat[i*128+dy*8+dx//2];got=(b>>4) if dx%2==0 else b&15
                    pixels+=1
                    if want!=got and len(bad.setdefault('pixels',[]))<10:bad['pixels'].append((i,dx,dy,want,got))
        if not bad.get('pixels'):bad.pop('pixels',None)
        oldpat=carry['patterns']if carry else bytes([0x11])*(77*128)+bytes(16384-77*128)
        oldattrs=carry['attributes']if carry else [[0]*5 for _ in range(128)]
        oldvisible=bool(carry and carry['nr'].get(0x15,0)&1)
        changed=[i for i in range(77)if bytes(oldpat[i*128:i*128+128])!=bytes(m.pat[i*128:i*128+128])
                 or oldattrs[i]!=m.attr[i]or not oldvisible]
        if changed:
            ys=[]
            for i in changed:
                ys.extend((m.attr[i][1]-32,m.attr[i][1]-16))
                if oldvisible:ys.extend((oldattrs[i][1]-32,oldattrs[i][1]-16))
            lo=m.pages[26][patch.syms['dirty_min']-8192];hi=m.pages[26][patch.syms['dirty_max']-8192]
            if lo>min(ys)or hi<max(ys):bad['publication bounds']=(lo,hi,min(ys),max(ys))
    newcarry=dict(pages={p:bytes(v) for p,v in m.pages.items() if p not in (10,11,4,5,0,1)},
                  patterns=bytes(m.pat),attributes=m.attr,nr=m.nr,line=m.line)
    return bad,newcarry,dead,pixels


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    from .rzx import trace
    c=collections.Counter();examples={};states=[];carry=None;seen=collections.Counter();ready=False
    def fail(k,value):
        c[k+'!']+=1
        if len(examples.setdefault(k,[]))<5:examples[k].append(value)
    def at(pc,s):
        nonlocal carry,ready
        if pc==0x5E00:ready=True;return
        if not ready and pc in SITES:
            # A separately labelled mode fixture may start after the loader.
            # Require every exact decompressed patch site before accepting it.
            ready=all(bytes(s.memory[a:a+3])==bytes.fromhex(old)
                      for a,(old,_) in SITES.items())
        if not ready:return
        if pc in INTERIORS:fail('patched instruction interior',pc);return
        mem,regs=bytes(s.memory),list(s.registers)
        if collect and seen[pc]<collect:states.append((pc,mem,regs));seen[pc]+=1
        bad,carry,dead,pixels=event_check(patch,pc,mem,regs,carry)
        c[f'site {pc:04X}']+=1;c['sprite pixels compared']+=pixels;c['dead stack bytes observed']+=len(dead)
        for k,v in bad.items():fail(k,(pc,v))
        if progress and sum(c[f'site {x:04X}']for x in SITES)%100==0:progress(dict(c))
    n,error=trace(rzx_path,set(SITES)|INTERIORS|{0x5E00},at,stop=stop)
    c['frames']=n
    if error:fail('recording desync',error)
    return (c,examples,states) if collect else (c,examples)



def negative_patches(patch):
    """Broken builds retain their own emitted bytes, LUTs and addresses."""
    import copy
    def changed(name, pc, kind, addr, expected, replacement):
        q=copy.deepcopy(patch); page=bytearray(q.page); off=addr-8192
        if page[off:off+len(expected)]!=expected:
            raise AssertionError(('negative source bytes changed', name, hex(addr)))
        page[off:off+len(replacement)]=replacement
        q.page=bytes(page); q.extra_banks[13]=q.page+bytes(8192)
        return name,pc,kind,q
    sy=patch.syms; page=patch.page
    rin=page.index(b'\x3e\x72',sy['h_in']-8192,sy['h_out']-8192)+8192
    xpos=page.index(b'\xc6\x09',sy['attributes']-8192,sy['speed']-8192)+8192
    clear=page.index(b'\xed\x91\x15\x00',sy['h_clear']-8192,sy['grid']-8192)+8192
    ink=page.index(b'\xe6\x07\x07\x07\x07\x07',sy['grid']-8192,sy['grid']-8192+80)+8192
    return [changed('R off by one',0xA3E2,'registers',rin,b'\x3e\x72',b'\x3e\x71'),
            changed('wrong figure position',0xA3F4,'positions',xpos,b'\xc6\x09',b'\xc6\x0a'),
            changed('wrong pattern pixels',0xA3F4,'pixels',0x3000,page[0x1000:0x1100],bytes(v^0x33 for v in page[0x1000:0x1100])),
            changed('stale grid after clear',0xD6D4,'clear',clear,b'\xed\x91\x15\x00',b'\xed\x91\x15\x01'),
            changed('wrong original ink',0xA3F4,'colours',ink,b'\xe6\x07',b'\xe6\x00')]


def unit_tests(patch, states, neg=None):
    c=collections.Counter()
    for pc,mem,regs in states:
        for iff in (0,1):
            for speed in range(4):
                r=list(regs);r[26]=iff
                carry=None
                if pc==0xA3F4:
                    page=bytearray(patch.page);page[patch.syms['speed']-8192]=speed
                    carry=dict(pages={26:page},patterns=bytes([0x11])*(77*128)+bytes(16384-77*128),attributes=[[0]*5 for _ in range(128)],nr={7:3},line=0)
                bad,_,_,_=event_check(patch,pc,mem,r,carry,speed=speed)
                c['unit failures!' if bad else 'unit cases passed']+=1
    if not states:c['no captured unit states!']+=1
    for name,pc,kind,broken in negative_patches(patch):
        samples=[(m,r)for a,m,r in states if a==pc]
        caught=False
        for mem,regs in samples:
            bad,_,_,_=event_check(broken,pc,mem,regs)
            if kind in bad:caught=True;break
        c['negative '+name+(' caught' if caught else ' escaped!')]+=1
    return c


class LoaderPatch(GunfrightPatch):
    """Archive-sized package: relocate at boot, then restore the original state.

    Source hooks sit +0x200 before the original 6000->5E00 copy. The copy runs
    once while the boot stub is DI; post-loader registers/R and outside-copy
    RAM come from the unchanged original loader. Gameplay remains identical.
    """
    def __init__(self, post_source, prof=None, cpu_only=False):
        from . import z80tonex as Z
        super().__init__(prof, cpu_only)
        self.post_source=Z.Z80Snapshot(str(post_source))
        if self.post_source.pc!=0x5E00:raise ValueError('expected original post-relocation state')
        self.live_sites=list(self.sites)
        self.sites=[(a+0x200,old,new)for a,old,new in self.sites]
        self.boot_prefix=bytes.fromhex('21006011005e010080edb0')

    def apply(self,snap):
        if snap.pc!=0x5B96 or bytes(snap.read(a)for a in range(0x5B96,0x5BA4))!=bytes.fromhex('21006011005e010080edb0c3005e'):
            raise ValueError('expected exact original pre-relocation USR entry')
        post=self.post_source
        before=bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        after=bytearray(post.banks[5]+post.banks[2]+post.banks[0])
        if before[0x2000:0xA000]!=after[0x1E00:0x9E00]:
            raise ValueError('original loader did more than the verified relocation')
        self.loader_outside_changes=[]
        for i in range(49152):
            if not 0x1E00<=i<0x9E00 and before[i]!=after[i]:
                self.loader_outside_changes.append(i+0x4000);before[i]=after[i]
        for k,bank in enumerate((5,2,0)):snap.banks[bank]=bytes(before[16384*k:16384*(k+1)])
        for key in ('a','f','bc','de','hl','ix','iy','a_','f_','bc_','de_','hl_','sp','i','r','iff1','iff2','im','border','pc'):
            setattr(snap,key,getattr(post,key))
        for addr,old,new in self.live_sites:
            if after[addr-0x4000:addr-0x4000+len(old)]!=old:raise ValueError('original post-loader hook mismatch')
            after[addr-0x4000:addr-0x4000+len(new)]=new
        self.expected_game_ram=bytes(after)
        super().apply(snap)


class PlainPatch(GunfrightPatch):
    """Same full-ROM and exact-state boot, with no changed game instructions."""
    name = 'Gunfright unchanged original reference'
    def __init__(self):
        from .build import rom48
        super().__init__()
        self.page=rom48()[8192:]; self.extra_banks={13:self.page+bytes(8192)}
        self.sites=[]; self.stub_extra=b'\xc9'


def boot_check(nex, source, patch, nexload=False, sysrom=None):
    """Boot through self-erasure: every original RAM byte, all registers and R."""
    import copy
    from . import z80tonex as Z, nextboot
    q=copy.deepcopy(patch); expected=Z.Z80Snapshot(str(source)); q.apply(expected)
    st=nextboot.boot(str(nex),q.original_pc,nexload=nexload,sysrom=sysrom); r=st['R']
    want={0:expected.a,1:expected.f,12:expected.sp,14:expected.i,15:expected.r,26:expected.iff1,27:expected.im}
    bad=[('register',k,r[k],v)for k,v in want.items()if r[k]!=v]
    for k,v in ((2,expected.bc),(4,expected.de),(6,expected.hl),(8,expected.ix),(10,expected.iy),
                (16,expected.a_*256+expected.f_),(18,expected.bc_),(20,expected.de_),(22,expected.hl_)):
        if r[k]*256+r[k+1]!=v:bad.append(('pair',k,r[k]*256+r[k+1],v))
    ram=getattr(q,'expected_game_ram',expected.banks[5]+expected.banks[2]+expected.banks[0])
    diff=[a for a in range(16384,65536)if st['mem'][a]!=ram[a-16384]]
    if diff:bad.append(('RAM',len(diff),diff[:10]))
    image=nextboot.rom_view(q,sysrom)
    regs=Z.build_tail(expected,TAIL_ADDR,q.slot1,True)[3]
    image=bytearray(image); image[q.slot1[1]:q.slot1[1]+len(regs)]=regs
    if bytes(st['mem'][i] for i in range(16384))!=bytes(image):bad.append(('complete hidden ROM differs',))
    if st['mmu']!=[255,255,10,11,4,5,0,1]:bad.append(('MMU',st['mmu']))
    if st['nr'].get(0x8c)!=0x80:bad.append(('hidden ROM disabled',))
    return bad+st['bad']


SCREEN_MD5='de2ebbf6d54e4c8d2842ab8a5063de78'
SOURCE_MD5='0cd9e86a2c6c7afa22025f8d593af093'
ARCHIVE_POK_SHA256='70bc3652c5eb865c10d2988b05696cb62a4eb9792f6d28a875805dc0e7085ec5'
# Live addresses, original bytes, replacements. The original loader moves these
# from live+0200. The ammo/money substitutions preserve HUD and BCD arithmetic.
TRAINERS=(
    ('Infinite lives', ((0xC051,0x35,0),)),
    ('Infinite ammo', ((0xCA00,0x32,0),(0xCA01,0x64,0),(0xCA02,0xA2,0),(0xCA06,0x28,0x18))),
    ('Infinite money', ((0xD36A,0x77,0),(0xD36F,0x77,0),(0xD375,0x77,0))),
    ('Bandit cannot move', ((0xB9F4,0x20,0x18),)),
    ('Bandit cannot shoot', ((0xB9F9,0xCA,0x3A),)),
    ('No horses', ((0xA97F,0x3A,0xC9),)),
    ('No jumping boys', ((0xB316,0x11,0xC9),)),
    ('No townsfolk', ((0xB68F,0xFD,0xC9),)),
)


def verified_trainers(z80, output, requested=None):
    """Emit only behaviour-tested trainers at the archive's pre-relocation addresses.

    nxcout's ordinary import-pok path can consume this without engine-specific
    packager changes. Never import the archive's live addresses into its loader
    snapshot, or silently accept an unreviewed replacement .pok.
    """
    import hashlib
    from . import z80tonex as Z, nxc
    source=Path(z80).read_bytes()
    if hashlib.md5(source).hexdigest()!=SOURCE_MD5:
        raise ValueError('Gunfright trainers require the exact verified 48K archive')
    snap=Z.Z80Snapshot(str(z80)); lines=[]
    for name,pokes in TRAINERS:
        lines.append('N'+name)
        for i,(live,original,value)in enumerate(pokes):
            address=live+0x200; bank=5 if address<0x8000 else 2 if address<0xC000 else 0
            if snap.banks[bank][address&0x3FFF]!=original:
                raise ValueError('Gunfright trainer source mismatch at %04X'%address)
            lines.append('%s 8 %d %d %d'%('Z'if i==len(pokes)-1 else'M',address,value,original))
    text='\n'.join(lines+['Y'])+'\n'
    if requested:
        data=Path(requested).read_bytes()
        if hashlib.sha256(data).hexdigest()!=ARCHIVE_POK_SHA256:
            if nxc.parse_pok(data.decode('ascii'))!=nxc.parse_pok(text):
                raise ValueError('Gunfright --pok must be the verified archive or the engine translation')
    Path(output).write_text(text)
    return str(Path(output).resolve())


def find_screen(folder):
    """The original SP tape block has a twelve-byte copier before its picture."""
    import hashlib, functools, operator
    for path in sorted(Path(folder).glob('*')):
        if path.suffix.lower() not in ('.tap','.scr'):continue
        data=path.read_bytes(); candidates=[data]if len(data)==6912 else []
        at=0
        while path.suffix.lower()=='.tap' and at+2<=len(data):
            n=int.from_bytes(data[at:at+2],'little'); block=data[at+2:at+2+n];at+=n+2
            if len(block)!=n:raise ValueError('truncated original tape block')
            if n==6926 and block[:13]==bytes.fromhex('ff210c6011004001001bedb0c9'):
                if functools.reduce(operator.xor,block,0):raise ValueError('original screen block checksum')
                candidates.append(block[13:-1])
        for scr in candidates:
            if hashlib.md5(scr).hexdigest()==SCREEN_MD5:return str(path),scr
    return None,None


def loading_nex(nex, screen):
    if len(screen)!=6912 or nex[10]!=0:raise ValueError('expected bare NEX and original ULA screen')
    data=bytearray(nex);data[10]=2
    return bytes(data[:512])+screen+bytes(data[512:])


# ---------------------------------------------------------------------------------------------------------------
# Enhanced: the ordered Layer 2 renderer (asm/gunfright_enhanced.asm + asm/gunfright_l2.asm, profile
# docs/profiles/gunfright_enhanced.json) and its pre-coloured assets, compiled from the owner's painting and the
# original graphics in the user's snapshot.
# ---------------------------------------------------------------------------------------------------------------
ENHANCED_PROFILE = HERE.parent/'docs/profiles/gunfright_enhanced.json'
L2_SITES = [(0xBE0D, 'ed731d', 's_l2_mask'), (0xBF51, 'ed731d', 's_l2_mirror'), (0xC4AB, 'ed731d', 's_l2_scenery'),
            (0xC622, 'ed731d', 's_l2_ground'), (0xB28A, 'eb01c6', 's_l2_strip')]
L2_REMAP = {1: 0, 2: 15, 15: 2}      # sheet palette digit -> Layer 2 index (black 0, white 15)
L2_T = 255                           # transparent in the masked colour pages


def load_painting(path=COLOURS):
    """docs/profiles/gunfright_colours.json -> {'palette', 'town', 'bandit', 'scenery', 'opponents' (20 maps),
    'add', 'remove'}; each map {source key: 8 digits, leftmost pixel first}."""
    d = json.loads(Path(path).read_text())
    def expand(runs, step=1, prefix=''):
        out = {}
        for k, digits in runs.items():
            if len(digits) % 8: raise ValueError('colour run %s is not whole bytes' % k)
            for i in range(len(digits)//8):
                out['%s%04x' % (prefix, int(k, 16)+step*i)] = [int(c, 16) for c in digits[8*i:8*i+8]]
        return out
    duel = expand(d['duel'], 1, 'duel:')
    return dict(palette=[tuple(c) for c in d['palette']], town=expand(d['town'], 2), bandit=expand(d['bandit'], 2),
                scenery=expand(d['scenery']), opponents=[dict(duel, **expand(o, 1, 'duel:')) for o in d['opponents']],
                add={(k, b) for k, b in d['geometry']['add']}, remove={(k, b) for k, b in d['geometry']['remove']})


def masked_records(mem):
    """(address, width, height) of every nonempty original masked graphic (table 67F4)."""
    out = []
    for g in range(56):
        a = mem[0x67F4+2*g] | mem[0x67F5+2*g] << 8; w, h = mem[a]*8, mem[a+1]
        if w and h: out.append((a, w, h))
    return out


def identity_of(mem):
    """The mapped bounty identity the duel draws (A262 through B492), as the original does."""
    b = mem[0xA262]
    i = mem[0xB492+b] if b < 20 else 0
    return i if i < 20 else 0


class Painting:
    """Per-pixel Layer 2 colour of the original graphics: masked = replace on cover (town or street-bandit role),
    plain = scenery, ground and duel strips (per opponent identity)."""
    def __init__(self, mem, paint=None):
        p = paint or load_painting()
        self.mem = bytes(mem[0:65536]); self.town, self.bandit, self.scenery = p['town'], p['bandit'], p['scenery']
        self.owner, self.removed, self.added = p['opponents'], p['remove'], p['add']
        self.records = masked_records(self.mem)
        self.mask_addr = {a+2+2*k for a, w, h in self.records for k in range(w//8*h)}

    def masked(self, a, x, bandit_role):
        m = self.mem; mask, ink = m[a], m[a+1]; key = '%04x' % a; bit = 128 >> x
        cover = mask | ink
        if a in self.mask_addr:
            if (key, x) in self.removed: cover &= ~bit
            if (key, x) in self.added: cover |= bit
        if not cover & bit:
            return L2_T
        if a in self.mask_addr:
            if bandit_role and key in self.bandit:
                n = self.bandit[key][x] or (2 if ink & bit else 1)
                if not (mask | ink) & bit:
                    return 0
                return L2_REMAP.get(n, n)
            n = self.town.get(key, [0]*8)[x] or (2 if ink & bit else 1)
            return L2_REMAP.get(n, n)
        return 15 if ink & bit else 0

    def plain(self, a, x, identity=None):
        old = self.mem[a]; bit = 128 >> x
        if identity is not None:
            e = self.owner[identity].get('duel:%04x' % a)
            if e:
                n = e[x] or (2 if old & bit else 1)
                return L2_REMAP.get(n, n)
        e = self.scenery.get('%04x' % a)
        if e:
            n = e[x] or (2 if old & bit else 1)
            return L2_REMAP.get(n, n)
        return 15 if old & bit else 0


_ASSETS = {}


def enhanced_assets(mem):
    """Layer 2 asset pages 44..61 from the original graphics in mem: masked town role (44..48), bandit role
    (49..53), plain scenery and ground (54..59), duel strips with the identity table (60..61). -> (pages, manifest)."""
    import hashlib
    key = hashlib.sha256(bytes(mem[0x4000:0x10000])).hexdigest()
    if key in _ASSETS: return _ASSETS[key]
    col = Painting(mem)
    def masked(bandit):
        arr = bytearray([L2_T])*(5*8192)
        for a0, w, h in col.records:
            for k in range(w//8*h):
                a = a0+2+2*k; o = (a-0x68EC)*4
                for x in range(8): arr[o+x] = col.masked(a, x, bandit)
        return arr
    mt, mb = masked(False), masked(True)
    pl = bytearray(6*8192)
    for a in range(0x8A3B, 0xA207):
        for x in range(8): pl[(a-0x8A3B)*8+x] = col.plain(a, x)
    for a in range(0x6873, 0x688D):
        for x in range(8): pl[0xBE60+(a-0x6873)*8+x] = col.plain(a, x)
    du = bytearray(2*8192); uniq = {}; table = bytearray(20*41)
    for ident in range(20):
        for sid in range(41):
            data = col.mem[0x6AC6+2*sid] | col.mem[0x6AC7+2*sid] << 8
            px = bytes(col.plain(data+4*r+j//8, j % 8, ident) for r in range(8) for j in range(32))
            if px not in uniq: uniq[px] = len(uniq); du[256*uniq[px]:256*uniq[px]+256] = px
            table[ident*41+sid] = uniq[px]
    if len(uniq)*256 > 0x3500: raise ValueError('duel strips exceed their pages')
    du[0x3500:0x3500+len(table)] = table
    pages = {}
    for base, arr in ((44, mt), (49, mb), (54, pl), (60, du)):
        for i in range(len(arr)//8192): pages[base+i] = bytes(arr[i*8192:(i+1)*8192])
    man = dict(duel_unique_strips=len(uniq), pages=sorted(pages),
               sha256={str(p): hashlib.sha256(v).hexdigest() for p, v in pages.items()})
    _ASSETS[key] = (pages, man)
    return pages, man


def layer2_palette(paint=None):
    """The 16 Layer 2 palette entries (NR 0x44 byte pairs) the Enhanced setup loads, from the painting's palette."""
    pal = [(0, 0, 0)]*16
    for i, c in enumerate((paint or load_painting())['palette']): pal[L2_REMAP.get(i, i)] = c
    vals = []
    for r, g, b in pal:
        rr, gg, bb = round(r*7/255), round(g*7/255), round(b*7/255)
        v = rr*32+gg*4+(bb >> 1)
        if v == 0xE3: raise ValueError('colour equals the global transparency')
        vals += [v, bb & 1]
    return bytes(vals)


class EnhancedPatch(GunfrightPatch):
    """The default runtime with the sprite grid replaced by the ordered Layer 2 renderer: five producer hooks
    (L2_SITES), Layer 2 buffers in banks 16..21, painted assets in banks 22..30. Banks 14/15 (the default's grid
    workspace, never mapped by Enhanced) are kept as zeros so the Enhanced build is the default's banks plus its own
    (the .nxc colour-set rule), as published."""
    name = 'Gunfright Enhanced: owner painting on an ordered Layer 2 renderer'

    def __init__(self, mem, prof=None, cpu_only=False):
        super().__init__(prof or json.loads(ENHANCED_PROFILE.read_text()), cpu_only)
        page = bytearray.fromhex(self.prof['hooks']['page'])
        if cpu_only: page[self.syms['hlib_dma_policy']-8192] = 0
        if not self.stub_extra.endswith(layer2_palette()):
            raise ValueError('Enhanced setup palette differs from docs/profiles/gunfright_colours.json')
        self.page = bytes(page); self.extra_banks = {13: self.page+bytes(8192)}
        for a, old, sym in L2_SITES:
            self.sites.append((a, bytes.fromhex(old), b'\xC3'+self.syms[sym].to_bytes(2, 'little')))
        pages, self.asset_manifest = enhanced_assets(mem)
        for b in range(16, 22): self.extra_banks[b] = bytes(16384)
        for b in range(22, 31): self.extra_banks[b] = pages.get(2*b, bytes(8192))+pages.get(2*b+1, bytes(8192))
        self.extra_banks[14] = bytes(16384); self.extra_banks[15] = bytes(16384)


class EnhancedLoaderPatch(LoaderPatch, EnhancedPatch):
    """Enhanced through the same archive-sized boot relocation as LoaderPatch; assets from the post-loader state."""
    def __init__(self, post_source, cpu_only=False):
        from . import z80tonex as Z
        from .machine import Machine
        EnhancedPatch.__init__(self, Machine(str(post_source)).sim.memory, cpu_only=cpu_only)
        self.post_source = Z.Z80Snapshot(str(post_source))
        if self.post_source.pc != 0x5E00: raise ValueError('expected original post-relocation state')
        self.live_sites = list(self.sites)
        self.sites = [(a+0x200, old, new) for a, old, new in self.sites]
        self.boot_prefix = bytes.fromhex('21006011005e010080edb0')


def release(z80, out, enhanced=False, screen=None, temp=None):
    """One published build: the loader-bridged patch on the original pre-relocation state, then (when the original
    loading screen is given) that screen in the NEX header with a start delay of 50, as in .nxc 1.0/1.1.
    -> (patch class factory, pre-relocation source, bare NEX path)."""
    import tempfile
    from . import z80tonex as Z
    temp = Path(temp or tempfile.mkdtemp(prefix='gunfright_'))
    temp.mkdir(parents=True, exist_ok=True)
    post = derive_start(z80, temp/'post.z80'); pre = derive_start(z80, temp/'pre.z80', stop=0x5B96)
    make = (lambda: EnhancedLoaderPatch(post)) if enhanced else (lambda: LoaderPatch(post))
    bare = temp/('enhanced.nex' if enhanced else 'default.nex')
    Z.convert(pre, str(bare), quiet=True, patch=make())
    data = bare.read_bytes()
    if screen is not None:
        data = bytearray(loading_nex(data, screen)); data[133] = 50; data = bytes(data)
    Path(out).write_bytes(data)
    return make, pre, bare


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default and Enhanced builds as published (loader bridge, original loading screen when
    the tape is beside the snapshot), each boot-checked; with --rzx the default runtime's replay proof and unit
    tests. Enhanced's replay proof is the pilot run's (games/gunfright.md "Evidence")."""
    import hashlib, tempfile
    from . import rzx as RZ
    from skoolkit.rzxplay import parse_rzx
    from skoolkit.snapshot import Snapshot
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    a.pok=verified_trainers(z80,out/(name+'_verified_trainers.pok'),getattr(a,'pok',None))
    say('Game      : Gunfright (Ultimate Play The Game, 1985, 48K)')
    say('Engine    : gunfright; default: exact original renderer on a cached hardware grid; Enhanced: painted ordered Layer 2; original pace')
    say('Trainers  : eight behaviour-tested choices; translated to the original loader source addresses')
    ok=True; states=[];screen_file,screen=find_screen(Path(z80).parent)
    with tempfile.TemporaryDirectory(prefix='gunfright_')as temp:
        for label,enhanced,suffix in (('Default',False,''),('Enhanced',True,'_enhanced')):
            dst=out/(name+suffix+'.nex')
            make,pre,bare=release(z80,dst,enhanced,screen,Path(temp)/label)
            bad=boot_check(bare,pre,make())+boot_check(bare,pre,make(),nexload=True)
            if screen:bad+=boot_check(dst,pre,make(),nexload=True)
            ok=ok and not bad
            say('%-10s: %s  %s  loading screen %s'%(label,dst.name,hashlib.md5(dst.read_bytes()).hexdigest(),
                'from the original tape (%s)'%SCREEN_MD5 if screen else 'none (no original .tap beside the snapshot)'))
            say('Boot      : %s'%('OK (all RAM, registers with R, complete hidden ROM; converter loader and NEXLOAD)'if not bad else 'MISMATCH %s'%str(bad[:3])[:300]))
        for path in getattr(a,'rzx',None)or []:
            if sum(isinstance(b.obj,Snapshot)for b in parse_rzx(path))>1:
                stripped=str(Path(temp)/Path(path).name);RZ.strip(path,stripped);path=stripped
            c,ex,got=verify(GunfrightPatch(),path,stop=getattr(a,'quick',None),collect=4)
            states+=got;fail={k:v for k,v in c.items()if k.endswith('!')};ok=ok and not fail
            say('Verify    : %s %d frames, %s'%(Path(path).name,c['frames'],'IDENTICAL'if not fail else str(fail)))
            for k,v in ex.items():say('            %s: %s'%(k,v))
        if states:
            counts=unit_tests(GunfrightPatch(),states);fail={k:v for k,v in counts.items()if k.endswith('!')};ok=ok and not fail
            say('Unit      : %s'%dict(counts))
        else:say('Verify    : not requested; boot evidence only')
    say('Coverage  : default replay/unit proof here (--rzx); Enhanced oracle, pace and loader proofs in games/gunfright.md "Evidence"')
    say('Result    : %s'%('PASSED' if ok else 'FAILED'))
    return bool(ok)


def main(argv=None):
    import sys
    args=list(sys.argv[1:] if argv is None else argv)
    enhanced='--enhanced' in args; args=[x for x in args if x!='--enhanced']
    if len(args)!=2:raise SystemExit(__doc__)
    snapshot,out=args
    release(snapshot,out,enhanced,find_screen(Path(snapshot).parent)[1])


if __name__=='__main__':
    main()
