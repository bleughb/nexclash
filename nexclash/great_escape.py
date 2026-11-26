"""The Great Escape: original presentation and optional painted companion layer.

Native game logic and drawing remain intact. Game data and artwork stay external.
"""
from pathlib import Path
import hashlib,copy,json,os,collections
from functools import lru_cache
from skoolkit import CSimulator
from . import z80tonex as Z,hooklib
SOURCE_MD5='ff5eae3b61188cb5095a6177c3c34a06'
CMP=hooklib.CMP_R
LOADING_SHA256='7eff616121a684dd0c0e9e7642181129aadb2dc9951c8a4c804c86dd8c55803d'
TRAINERS={
    'Infinite morale':((0xA0E3,0x90,0xB7),),
    'No other people':((0xC52B,0xC0,0xC9),),
    'Pass through doors':((0xB368,0xC0,0x00),),
}

def _profile_path():
    return Path(__file__).resolve().parents[1]/'docs/profiles/great_escape.json'

def is_great_escape(snap):
    signature=load_profile()['signature'];at=signature['addr'];data=bytes.fromhex(signature['hex'])
    if getattr(snap,'is128',False) or getattr(snap,'machine','48K')!='48K' or snap.pc!=0x5BC5:return False
    banks=getattr(getattr(snap,'memory',None),'banks',None) or getattr(snap,'banks',None)
    if banks is not None:actual=bytes(banks[0][at&16383:(at&16383)+len(data)])
    else:actual=bytes(snap.ram(-1)[at-16384:at-16384+len(data)])
    return actual==data

def native(snap):
    regs={n.upper():getattr(snap,n) for n in ('a','f','bc','de','hl','ix','iy','sp','i','r','pc')}
    regs.update({'^'+n.upper():getattr(snap,n+'_') for n in ('a','f','bc','de','hl')})
    return CSimulator(list(Z.rom48()+snap.banks[5]+snap.banks[2]+snap.banks[0]),regs,{'iff':snap.iff1,'im':snap.im})

def normalize_source(snap):
    """Execute only the checked register restore and original relocation, to F068."""
    if snap.pc==0xF068:return
    if snap.pc!=0x5BC5 or snap.sp!=0x5BE8 or snap.iff1 or snap.is128:
        raise ValueError('Unsupported Great Escape loader state')
    snap._great_escape_raw={b:bytes(snap.banks[b]) for b in (5,2,0)}
    sim=native(snap);before=bytes(sim.memory)
    if bytes(sim.memory[0xFDE5:0xFDF3])!=bytes.fromhex('01E09F21005E11005BEDB0C368F0'):
        raise ValueError('Original relocation differs')
    for steps in range(50000):
        if sim.registers[24]==0xF068:break
        sim.run()
    else:raise ValueError('Original relocation did not finish')
    changes=[a for a in range(65536) if sim.memory[a]!=before[a]]
    if steps!=40833 or sim.registers[25]!=857190 or len(changes)!=39637 or min(changes)!=0x5B77 or max(changes)!=0xFADF:
        raise ValueError('Original relocation proof differs')
    r=sim.registers
    for n,i in (('a',0),('f',1),('sp',12),('i',14),('r',15),('a_',16),('f_',17),('pc',24),('iff1',26),('iff2',26),('im',27)):
        setattr(snap,n,r[i])
    for n,i in (('bc',2),('de',4),('hl',6),('ix',8),('iy',10),('bc_',18),('de_',20),('hl_',22)):
        setattr(snap,n,r[i]*256+r[i+1])
    for bank,at in ((5,0x4000),(2,0x8000),(0,0xC000)):snap.banks[bank]=bytes(sim.memory[at:at+16384])

class OriginalPatch:
    name='The Great Escape original presentation'
    tail_addr=0x5B00
    uses_printer_buffer=False
    setup_call=None
    stub_extra=b''
    hook_page_data=b''
    ram_slot1_after_alt=True
    def __init__(self,native_state=False):
        self.native_state=native_state
        self.slot1=(24,0x3B00);self.altrom=(0x3900,0x3B14)
        self.page=Z.rom48()[8192:]
        self.extra_banks={13:bytes(8192)+Z.rom48()[:8192]};self.sites=[]
    def apply(self,snap):
        if not self.native_state:normalize_source(snap)
        self.entry=snap.pc
        tail,_,restore,_=Z.build_tail(snap,self.tail_addr,self.slot1,True,True)
        if len(tail)>256:raise ValueError('Loader workspace exceeds saved buffer')
        page=bytearray(self.page);page[0x1900:0x1A00]=snap.banks[5][0x1B00:0x1C00]
        self.runtime_banks={b:bytes(snap.banks[b]) for b in (5,2,0)}
        relocation=b''
        if not self.native_state and hasattr(snap,'_great_escape_raw'):
            # Keep the archive's banks in the NEX. The startup copy reproduces
            # its native relocation, with hook sites translated into the source
            # range. This avoids shipping a near-complete relocated game in SIT1.
            raw=bytearray(bytes(16384)+b''.join(snap._great_escape_raw[b] for b in (5,2,0)))
            expected=b''.join(self.runtime_banks[b] for b in (5,2,0))
            for pc,old,new in self.sites:
                if raw[pc+0x300:pc+0x300+len(old)]!=old:
                    raise ValueError('Relocated hook source differs')
                raw[pc+0x300:pc+0x300+len(new)]=new
            copied=bytearray(raw);copied[0x5B00:0xFAE0]=raw[0x5E00:0xFDE0]
            if copied[16384:]!=expected:raise ValueError('Runtime relocation differs from native execution')
            for bank,at in ((5,0x4000),(2,0x8000),(0,0xC000)):
                snap.banks[bank]=bytes(raw[at:at+16384])
            relocation=bytes.fromhex('21005E11005B01E09FEDB0')
        resume=b'\xF3'+relocation+bytes.fromhex('21003911005B010001EDB0')+Z.nextreg(0x50,27)+tail[restore:]
        if 0x3A00+len(resume)>0x3A80:raise ValueError('Loader overlaps resident hooks')
        page[0x1A00:0x1A00+len(resume)]=resume;self.page=bytes(page)
        self.extra_banks[12]=self.page+bytes(8192);snap.pc=0x3A00

def build_original(source,out):
    if hashlib.md5(Path(source).read_bytes()).hexdigest()!=SOURCE_MD5:raise ValueError('Wrong Great Escape source')
    patch=OriginalPatch();Z.convert(str(source),str(out),patch=patch,quiet=True);return patch

def boot_problems(nex,source,patch):
    from . import nextboot
    expected=Z.Z80Snapshot(str(source));normalize_source(expected);sim=native(expected)
    q=copy.deepcopy(patch);q.apply(expected);bad=[]
    for loader in (False,True):
        state=nextboot.boot(str(nex),q.entry,nexload=loader,sysrom=nextboot.system_rom3()[0])
        bad.extend(('ROM',loader,v) for v in state['bad'])
        for i in CMP:
            a,b=sim.registers[i],state['R'][i]
            if (bool(a)!=bool(b)) if i==26 else (a!=b):bad.append(('register',loader,i,a,b))
        ram=b''.join(q.runtime_banks[b] for b in (5,2,0))
        diffs=[i for i in range(49152) if state['mem'][16384+i]!=ram[i]]
        if diffs:bad.append(('RAM',loader,len(diffs),diffs[:8]))
        # The view the game has at F068: the resume maps page 27 (Sinclair's lower ROM) at slot 0 whatever the
        # alt ROM fill, and slot 1 holds the build's page with its register block.
        image=bytearray(nextboot.alt_image(q,nextboot.system_rom3()[0]));image[:8192]=Z.rom48()[:8192];image[8192:]=q.page
        regs=Z.build_tail(expected,q.tail_addr,q.slot1,True,True)[3]
        image[q.slot1[1]:q.slot1[1]+len(regs)]=regs
        diffs=[i for i in range(16384) if state['mem'][i]!=image[i]]
        if diffs:bad.append(('hidden ROM',loader,len(diffs),diffs[:8]))
    return bad


def load_profile():
    import json
    return json.loads(_profile_path().read_text())


@lru_cache(maxsize=4)
def searchlight_table(code):
    """Native painter costs for its clipped screen address and mirror flag.

    AE1E..AE3C bounds its caller to DE=5636..5A3D. This painter only writes
    attributes; its fixed mask and code are taken from the owner's snapshot.
    """
    memory=[0]*65536;memory[0xAEB8:0xAF5E]=code
    memory[0xF200:0xF202]=[255,255]
    result=bytearray(8192)
    sim=CSimulator(memory,{'PC':0xAEB8,'SP':0xF200},{'iff':0,'im':1})
    original=sim.registers[:]
    for flag in (0,255):
        sim.memory[0xAE75]=flag
        for offset in range(2048):
            sim.registers[:]=original[:]
            sim.registers[4]=(0x5600+offset)>>8;sim.registers[5]=offset&255
            sim.run(stop=0xFFFF)
            index=(offset+(2048 if flag else 0))*2
            result[index:index+2]=hooklib.lines16(sim.registers[25]).to_bytes(2,'little')
    return bytes(result)


class EnhancedPatch(OriginalPatch):
    """External pixel-cache companion; the native drawing and game RAM are retained."""
    name='The Great Escape Enhanced'
    entries=((0xA9D0,'011800','h_tile_out'),(0x6B5A,'011808','h_tile_in'),(0xBC62,'E51AD9','h_tile_dirty'),
             (0xA9FC,'01BF0CEDB0','h_scroll_r'),(0xAA1D,'01C00CEDB8','h_scroll_l'),
             (0xAA3F,'01000CEDB0','h_scroll_dr'),(0xAA63,'01000CEDB0','h_scroll_d'),
             (0xAA84,'01000CEDB8','h_scroll_u'),(0xAAA6,'01FF0BEDB8','h_scroll_ul'),
             (0xE2A2,'FD7E18E607','h_figure16'),(0xE102,'FD7E18E607','h_figure24'),
             (0xE29F,'AF180A','h_item'),(0xEED3,'ED73D1ED','h_publish'),
             (0x9DC2,'CD35A0','h_frame_end'),(0xAEB8,'D9113EAF','h_searchlight'),
             (0xA50B,'CD276A','h_dialog'))
    def __init__(self,enabled=True,colours=None,palette=None,world=None,palette_dusk=None,mcqueen=False,native_state=False,dma=True):
        super().__init__(native_state);self.enabled=enabled
        self.hooks=copy.deepcopy(load_profile()['hooks']);self.syms={k:int(v,16) for k,v in self.hooks['syms'].items()}
        self.slot1=(24,0x3E40);self.altrom=(0x3900,0x3E70)
        page=bytearray(self.page);blob=bytes.fromhex(self.hooks['resident']);page[0x1A80:0x1A80+len(blob)]=blob
        page[0x1E00:0x2000]=bytes(512);page[0x1E18]=int(mcqueen);page[0x1E19]=int(colours is not None);self.page=bytes(page)
        private=bytearray(16384);private[8192:]=Z.rom48()[:8192]
        for key,at in (('code',0),('library',0x1800),('extra',0x1A00)):
            blob=bytes.fromhex(self.hooks[key]);private[at:at+len(blob)]=blob
        private[0x1DC0:0x1E00]=bytes(n//3 for n in range(64))
        private[self.syms['hlib_dma_policy']]=2 if dma else 0
        self.extra_banks[13]=bytes(private)
        self.colours=colours;self.palette=palette;self.world=world
        for bank in range(14,17):self.extra_banks[bank]=bytes([255])*16384
        for bank in range(17,21):self.extra_banks[bank]=bytes(16384)
        for bank in (45,46):self.extra_banks[bank]=bytes(16384)
        palette=palette or [0 if n%128==0 else 0x049 if n>=128 else 511 for n in range(256)]
        palette[255]=0x1C7
        setup=bytearray()
        def nr(n,v):setup.extend((0xED,0x91,n,v))
        for n,v in ((0x69,0),(0x12,14),(0x70,0),(0x16,0),(0x17,0),(0x15,0),
                    (0x1C,1),(0x18,56),(0x18,239),(0x18,16),(0x18,143),(0x43,0x10),(0x40,0)):
            nr(n,v)
        def upload(values):
            # A loop plus the 512-byte palette leaves the DFFE stub stack clear.
            at=0xD000+len(setup);data=at+20;end=data+512
            setup.extend(bytes((0x21,data&255,data>>8,0x06,0,0x7E,0xED,0x92,0x44,0x23,
                                0x7E,0xED,0x92,0x44,0x23,0x10,0xF4,0xC3,end&255,end>>8)))
            for value in values:setup.extend((value>>1,value&1))
        upload(palette)
        nr(0x43,0x50);nr(0x40,0);upload(palette_dusk or palette)
        nr(0x43,0x10);nr(0x14,0xE3);nr(0x69,0x80 if enabled else 0);setup.append(0xC9)
        assert len(setup)<0xFF0, "Setup collides with the stub stack"
        self.setup_call,self.stub_extra=0xD000,bytes(setup)
    def apply(self,snap):
        if not self.native_state:normalize_source(snap)
        memory=Z.rom48()+snap.banks[5]+snap.banks[2]+snap.banks[0]
        self.native_memory=bytes(memory)
        colours=self.colours or bytes(7 if memory[a]&(128>>x) else 0 for a in range(16384,65536) for x in range(8))
        self.colour_data=colours
        if len(colours)!=393216:raise ValueError('Pixel cache must cover exactly 48K x 8')
        # Compact native source pages plus contextual 8x8 world tiles. Bright and
        # dark pools are identical in layout, 22 pages apart, and fit below ROM47.
        pages=tuple(range(0x21,0x28))+tuple(range(0x34,0x39))
        lookup=bytearray(64);pool=bytearray()
        for page in pages:
            lookup[page]=42+len(pool)//8192
            at=(page*1024-16384)*8;pool.extend(colours[at:at+8192])
        tiles={bytes(pool[a:a+64]):a//64 for a in range(0,len(pool),64)}
        world=self.world
        if world is not None and len(world)!=256*1024:raise ValueError('World art must cover 256 x 32x32 pixels')
        table=bytearray()
        for block in range(256):
            base=0x8590 if block<45 else 0x90F8 if 139<=block<204 else 0x8A18
            for cell in range(16):
                if world is None:
                    at=base+memory[0x5B00+block*16+cell]*8
                    tile=colours[(at-16384)*8:(at-16384)*8+64]
                else:
                    x,y=(cell%4)*8,(cell//4)*8
                    tile=b''.join(world[block*1024+(y+yy)*32+x:block*1024+(y+yy)*32+x+8] for yy in range(8))
                if tile not in tiles:tiles[tile]=len(pool)//64;pool.extend(tile)
                table.extend(tiles[tile].to_bytes(2,'little'))
        if len(pool)>22*8192:raise ValueError('Enhanced tile pool exceeds the 1MB budget')
        self.cache_bytes=len(pool);pool.extend(bytes(22*8192-len(pool)))
        for n in range(11):self.extra_banks[21+n]=bytes(pool[n*16384:(n+1)*16384])
        dark_pool=bytes(v|128 for v in pool)
        for n in range(11):self.extra_banks[32+n]=dark_pool[n*16384:(n+1)*16384]
        self.extra_banks[43]=bytes(table)+searchlight_table(bytes(memory[0xAEB8:0xAF5E]))
        timing=bytearray(16384)
        for wide in (0,1):
            for mirror in (0,1):
                for phase in range(8):
                    row=((627+64*phase if phase<4 else 883-64*(phase-4))+113*mirror) if wide else ((509+48*phase if phase<4 else 698-48*(phase-4))+91*mirror)
                    constant=(149 if phase<4 else 145) if wide else (153 if phase<4 else 149)
                    for count in range(5):
                        for height in range(1,33):
                            index=(wide*16+mirror*8+phase)*256+count*32+height-1
                            t=(row+3*min(count,wide+3))*height+constant
                            timing[index*2:index*2+2]=hooklib.lines16(t).to_bytes(2,'little')
        self.extra_banks[44]=bytes(timing)
        private=bytearray(self.extra_banks[13]);private[0x1D80:0x1DC0]=lookup;self.extra_banks[13]=bytes(private)
        canvas=bytes(7 if memory[a]&(128>>x) else 0 for a in range(0xF290,0xFF51) for x in range(8))+bytes(6648)
        assert len(canvas)==32768
        self.extra_banks[17],self.extra_banks[18]=canvas[:16384],canvas[16384:]
        dark=bytes(v|128 for v in canvas);self.extra_banks[19],self.extra_banks[20]=dark[:16384],dark[16384:]
        self.sites=[]
        if self.enabled:
            for pc,old,label in self.entries:
                old=bytes.fromhex(old);at=self.syms[label];new=bytes((0xC3,at&255,at>>8))+bytes(len(old)-3)
                bank=5 if pc<0x8000 else 2 if pc<0xC000 else 0;off=pc&16383;data=bytearray(snap.banks[bank])
                if data[off:off+len(old)]!=old:raise ValueError(f'Unexpected Great Escape hook bytes at {pc:04X}')
                data[off:off+len(old)]=new;snap.banks[bank]=bytes(data);self.sites.append((pc,old,new))
        super().apply(snap)


# Memory no hook may write: page 27 (Sinclair's lower ROM, the game's slot 0 view), page 25, the colour pools,
# world, timing and table pages (banks 21-44), and the alt ROM view below the resident hooks (0x2000-0x3A7F).
IMMUTABLE_PAGES=frozenset([25,27]+list(range(42,90)))

class DrawingMemory:
    """Scoped hook model: three mapped slots, source/canvas pages and line time.
    policy None = the build's own DMA policy byte. DDMA only on core 3.03 (0x33) or later; no DMA port write at all
    in the CPU fallbacks (policy 0, hardware IM2). Writes to immutable memory are collected in .violations."""
    def __init__(self,memory,patch,clock=0,core=0x33,policy=None,hwim2=0):
        from .dma import DMA
        self.core=core;self.hwim2=hwim2;self.violations=[]
        self.data=list(memory);self.nr={7:clock,0x50:27,0x52:10,0x53:11,0x54:4,0x69:128};self.selected=0;self.elapsed=0
        self.pages={}
        for bank,data in patch.extra_banks.items():
            for half in (0,1):self.pages[bank*2+half]=list(data[half*8192:(half+1)*8192])
        if policy is not None:self.pages[26][patch.syms["hlib_dma_policy"]]=policy
        self.dma_allowed=bool(self.pages[26][patch.syms["hlib_dma_policy"]]) and not hwim2
        blob=bytes.fromhex(patch.hooks['resident']);self.data[0x3A80:0x3A80+len(blob)]=blob
        self.data[0x3E00:0x4000]=list(patch.page[0x1E00:0x2000])
        canvas=[7 if memory[a]&(128>>x) else 0 for a in range(0xF290,0xFF51) for x in range(8)]+[0]*6648
        for n in range(4):
            self.pages[34+n]=canvas[n*8192:(n+1)*8192]
            self.pages[38+n]=[v|128 for v in self.pages[34+n]]
        class Physical:
            def __len__(s):return 1024*1024
            def __getitem__(s,a):return self.pages[a>>13][a&8191]
            def __setitem__(s,a,v):self.guard(a>>13,a&8191);self.pages[a>>13][a&8191]=v
        self.dma=DMA(self.__getitem__,self.__setitem__,self.dma_io,blitter=core>=0x33,physical=Physical(),stall=self.dma_stall)
    def guard(self,page,offset):
        if page in IMMUTABLE_PAGES or (page==24 and offset<0x1A80):self.violations.append(('page',page,f'{offset:04X}'))
    def dma_io(self,p,v):raise AssertionError(('Unexpected DMA I/O',p,v))
    def dma_stall(self,n):self.elapsed+=n/2  # Injected timing only; JNext/hardware measured separately.
    def __len__(self):return 65536
    def __getitem__(self,a):
        if isinstance(a,slice):return [self[i] for i in range(*a.indices(65536))]
        slot=a>>13
        if slot in (0,2,3,4) and self.nr[0x50+slot] in self.pages:return self.pages[self.nr[0x50+slot]][a&8191]
        return self.data[a]
    def __setitem__(self,a,v):
        slot=a>>13
        if slot in (0,2,3,4) and self.nr[0x50+slot] in self.pages:
            self.guard(self.nr[0x50+slot],a&8191);self.pages[self.nr[0x50+slot]][a&8191]=v
        else:
            if a<0x3A80:self.violations.append(('ROM view',f'{a:04X}'))
            self.data[a]=v
    def nextreg(self,n,v):self.nr[n]=v
    def write_port(self,r,p,v,*args):
        if p==0x243B:self.selected=v
        elif p==0x253B:self.nextreg(self.selected,v)
        elif p&255==0x6B:
            if not self.dma_allowed:raise AssertionError(('DMA port write in a CPU fallback',p,v))
            self.dma.feed(v)
        else:raise AssertionError(('Unexpected hook output',p,v))
    def read_port(self,r,p):
        if p!=0x253B:raise AssertionError(('Unexpected hook input',p))
        line=int(self.elapsed//224)%312
        if self.selected==0x1E:return line>>8
        if self.selected==0x1F:return line&255
        if self.selected==1:return self.core
        if self.selected==0xC0:return self.hwim2
        return self.nr.get(self.selected,0)


def state_trial(patch,memory,registers,clock=0,iff=0,core=0x33,policy=None,hwim2=0,reuse=None,display=None):
    from .dizzy6 import _rw_simulator
    from . import simpool,z80n
    pc=registers[24];kind=next(i for i,x in enumerate(patch.entries) if x[0]==pc)
    end=(0xA9DF,0x6B68,0xBC7F)[kind] if kind<3 else 0xA035 if kind==13 else 0x6A27 if kind==15 else pc+len(bytes.fromhex(patch.entries[kind][1])) if kind<9 else memory[registers[12]]+256*memory[registers[12]+1]
    r=list(registers);r[25]=0;r[26]=iff
    original=simpool.machine(CSimulator,list(memory),slot='great-escape-native')
    for i,v in enumerate(r):original.registers[i]=v
    original.run(stop=end)
    mem=reuse or DrawingMemory(memory,patch,clock,core,policy,hwim2)
    if display is not None:mem.nr[0x69]=display
    mem.violations.clear()
    hook_at=patch.syms[patch.entries[kind][2]];entered=False
    elapsed=mem.elapsed
    palette_in=mem.nr.get(0x43,0x10)
    display_in=mem.nr[0x69]
    if reuse is not None:mem.data[16384:]=list(memory[16384:])
    ignore=set()
    for at,old,new in patch.sites:mem.data[at:at+len(new)]=new;ignore.update(range(at,at+len(new)))
    sim=simpool.machine(_rw_simulator(),mem,slot='great-escape-hook');sim.low_writes=True;sim.registers[:]=r
    sim.set_tracer(mem);z80n.install(sim,mem.nextreg)
    for steps in range(1000000):
        if sim.registers[24]==end:break
        if sim.registers[24]==hook_at:entered=True
        t=sim.registers[25];speed=mem.nr[7];sim.opcodes[mem[sim.registers[24]]]()
        mem.elapsed+=(sim.registers[25]-t)/(1<<speed)
    else:raise AssertionError(('Hook did not return',kind,f'{sim.registers[24]:04X}'))
    bad=[('register',i,original.registers[i],sim.registers[i]) for i in CMP if original.registers[i]!=sim.registers[i]]
    if not entered:bad.append(('hook not entered',f'{pc:04X}',f'{hook_at:04X}'))
    if mem.violations:bad.append(('write to immutable memory',len(mem.violations),mem.violations[:6]))
    expected=bytearray(original.memory[16384:])
    for at,old,new in patch.sites:expected[at-16384:at-16384+len(new)]=new
    got=bytes(mem.data[16384:])
    if expected!=got:
        diffs=[a+16384 for a,(x,y) in enumerate(zip(expected,got)) if x!=y]
        bad.append(('RAM',len(diffs),[(f'{a:04X}',original.memory[a],mem.data[a]) for a in diffs[:12]]))
    actual=dict(mem.nr)
    display=0 if kind==15 else 128 if kind==13 else display_in
    if actual.pop(0x69)!=display:bad.append(('Layer2 visibility',mem.nr.get(0x69),display))
    if kind==13:
        shade=0x14 if memory[0x5847] in (1,5) else 0x10
        if actual.pop(0x43,0x10)!=shade:bad.append(('L2 palette',mem.nr.get(0x43),shade))
    if kind!=13 and actual.pop(0x43,palette_in)!=palette_in:bad.append(('Unexpected palette write',mem.nr))
    if actual!={7:clock,0x50:27,0x52:10,0x53:11,0x54:4}:bad.append(('NextREG',mem.nr))
    return bad,dict(kind=kind,steps=steps,original_t=original.registers[25]/(1<<clock),hook_t=mem.elapsed-elapsed),mem


def load_art(assets):
    assets=Path(assets)
    def palette(name):
        data=(assets/name).read_bytes()
        if len(data)!=512:raise ValueError('Great Escape palette must contain 256 RGB9 words')
        result=[int.from_bytes(data[i:i+2],'little') for i in range(0,512,2)]
        if any(n>511 for n in result):raise ValueError('Great Escape palette is not RGB9')
        return result
    return dict(colours=(assets/'colours.bin').read_bytes(),world=(assets/'world.bin').read_bytes(),
                palette=palette('palette.bin'),palette_dusk=palette('palette-dusk.bin'))


def build(source,destination,assets=None,enhanced=True,loading=None,mcqueen=False,dma=True):
    if hashlib.md5(Path(source).read_bytes()).hexdigest()!=SOURCE_MD5:
        raise ValueError('Unsupported Great Escape source; use the verified archive release')
    patch=EnhancedPatch(enabled=enhanced,mcqueen=mcqueen,dma=dma,**load_art(assets)) if assets else OriginalPatch()
    Z.convert(str(source),str(destination),patch=patch,quiet=True)
    if loading is not None:
        scr=Path(loading).read_bytes()
        if len(scr)!=6912 or hashlib.sha256(scr).hexdigest()!=LOADING_SHA256:
            raise ValueError('The verified original Great Escape loading screen is required')
        data=Path(destination).read_bytes();head=bytearray(data[:512]);head[10],head[133]=2,50
        Path(destination).write_bytes(bytes(head)+scr+data[512:])
    return patch


SCROLL_COUNT={0xA9FC:3263,0xAA1D:3264,0xAA3F:3072,0xAA63:3072,0xAA84:3072,0xAAA6:3071}
CANVAS_START=0xF290
CANVAS_BYTES=3265
DARK=bytes(n|128 for n in range(256))

def _word(m,a):return m[a]+256*m[a+1]
def _pair(r,i):return r[i]*256+r[i+1]


class CanvasOracle:
    """Pixel geometry from the original blitter, independently of hook tables.

    Native one-bit coverage, per-pixel colour, source world context and final
    viewport are checked separately. This retains state between actual hooks.
    """
    def __init__(self,patch,memory):
        self.patch=patch
        self.bits=bytearray((memory[a]>>(7-x))&1 for a in range(CANVAS_START,CANVAS_START+CANVAS_BYTES) for x in range(8))
        self.colours=bytearray(7 if b else 0 for b in self.bits)

    def event(self,pc,m,r):
        p=self.patch
        if pc==0xBC62:
            from . import simpool
            s=simpool.machine(CSimulator,list(m),slot='great-escape-prefix-oracle')
            for i,v in enumerate(r):s.registers[i]=v
            s.run(stop=0xBC71);m=bytes(s.memory);r=list(s.registers);pc=0xBC71
        if pc in (0xA9D0,0x6B5A,0xBC71):
            src,dest=(_pair(r,4),_pair(r,6)) if pc==0xA9D0 else (_pair(r,6),_pair(r,4))
            context=None
            if pc==0xA9D0:
                ptr=_pair(r,20)
                if not 0x5B00<=ptr<0x6B00:ptr=_pair(r,22)
                if not 0x5B00<=ptr<0x6B00:raise AssertionError('World tile pointer outside the native block table')
                context=divmod(ptr-0x5B00,16)
            elif pc==0xBC71 and not m[0x68A0]:
                sp=r[12];context=(r[16],((m[0x81BC]+m[sp])&3)*4+((m[0x81BB]+m[sp+1])&3))
            for y in range(8):
                a=(src&0xFF00)|((src+y)&255);n=(dest+y*24-CANVAS_START)*8
                if not 0<=n<len(self.bits)-7:raise AssertionError('Native tile outside canvas')
                for x in range(8):
                    bit=(m[a]>>(7-x))&1;self.bits[n+x]=bit
                    if context is None or p.world is None:value=p.colour_data[(a-16384)*8+x]
                    else:
                        block,cell=context;value=p.world[block*1024+(cell//4*8+y)*32+cell%4*8+x]
                    self.colours[n+x]=value
        elif pc in SCROLL_COUNT:
            count=SCROLL_COUNT[pc];src,dest=_pair(r,6),_pair(r,4)
            if pc in (0xAA1D,0xAA84,0xAAA6):src-=count-1;dest-=count-1
            a,b,n=(src-CANVAS_START)*8,(dest-CANVAS_START)*8,count*8
            if min(a,b)<0 or max(a,b)+n>len(self.bits):raise AssertionError('Native scroll outside canvas')
            self.bits[b:b+n]=self.bits[a:a+n];self.colours[b:b+n]=self.colours[a:a+n]
        elif pc in (0xE2A2,0xE102,0xE29F):
            iy=_pair(r,10);width=3 if pc==0xE102 else 2;phase=0 if pc==0xE29F else m[iy+24]&7
            height=m[(0xE121 if phase<4 else 0xE1E2) if width==3 else (0xE2C2 if phase<4 else 0xE363)]
            bitmap,mask,fg,dest=[_word(m,a) for a in (0x81AC,0x81AE,0x81B0,0x81A2)]
            mirrored=bool(m[0x81B7]&128)
            stores=((0xE188,0xE199,0xE1AA,0xE1BF) if phase<4 else (0xE259,0xE26A,0xE27B,0xE290)) if width==3 else ((0xE319,0xE32A,0xE340) if phase<4 else (0xE3C5,0xE3D6,0xE3EC))
            enabled=[m[a]==0x77 for a in stores];role=m[iy]
            base=0
            if p.page[0x1E19] and pc==0xE29F and 9<=role<=11:base=104+8*(role-9)
            if p.page[0x1E19] and pc!=0xE29F and 0xD1EA<=bitmap<0xD455:
                if 20<=role<=25:base=(role-19)*8
                elif role==0 and p.page[0x1E18]:base=56
            for y in range(height):
                for x in range(width*8):
                    xx=width*8-1-x if mirrored else x;a=bitmap+y*width+xx//8
                    bit=(m[a]>>(7-(xx&7)))&1
                    opaque=bit or not ((m[mask+y*width+xx//8]>>(7-(xx&7)))&1)
                    dx=x+phase;col=dx//8;fga=(fg&0xFF00)|((fg+y*4+col)&255)
                    if not enabled[col] or not opaque or not (m[fga]&(128>>(dx&7))):continue
                    n=(dest+y*24-CANVAS_START)*8+dx
                    if not 0<=n<len(self.bits):raise AssertionError('Visible native figure outside canvas')
                    self.bits[n]=bit;self.colours[n]=p.colour_data[(a-16384)*8+(xx&7)]|base
        elif pc==0xEED3:
            for n in range(24*128):
                value=sum(self.bits[n*8+x]<<(7-x) for x in range(8))
                if value!=m[CANVAS_START+n]:raise AssertionError(('Native bitmap',n,value,m[CANVAS_START+n]))
        elif pc==0xAEB8:
            if not 0x5600<=_pair(r,4)<0x5E00 or m[0xAE75] not in (0,255):
                raise AssertionError('Searchlight painter escaped its native caller bounds')
        elif pc in (0x9DC2,0xA50B):pass        # frame end / dialog: no canvas geometry; compare() and state_trial check them
        else:raise AssertionError(('No oracle case for this event',f'{pc:04X}'))

    def compare(self,pc,m,mem):
        bad=[]
        if pc!=0xEED3:
            bright=bytes(sum((mem.pages[j] for j in range(34,38)),[]))[:len(self.colours)]
            dark=bytes(sum((mem.pages[j] for j in range(38,42)),[]))[:len(self.colours)]
            for label,want,got in (('canvas',self.colours,bright),('dark canvas',bytes(self.colours).translate(DARK),dark)):
                if want!=got:
                    examples=[(i,a,b) for i,(a,b) in enumerate(zip(want,got)) if a!=b][:12]
                    bad.append((label,examples))
        if pc==0x9DC2:
            layer=bytes(sum((mem.pages[j] for j in range(28,34)),[]));offset=m[0xA7C7]*8+(8 if m[0xA7C8]==0 else 4)
            for y in range(128):
                row=bytearray()
                for cell in range(23):
                    at=y*192+offset+cell*8;part=bytes(self.colours[at:at+8]);shade=m[0x5847+(y//8)*32+cell]&7
                    row.extend(part.translate(DARK) if shade<2 else part)
                got=layer[(y+16)*256+56:(y+16)*256+240]
                if row!=got:
                    bad.append(('Layer2 position/pixels',y,[(x,a,b) for x,(a,b) in enumerate(zip(row,got)) if a!=b][:12]));break
        return bad


def verify(patch,rzx_path,stop=None,collect=0,progress=None):
    from . import rzx,simrun
    counts=collections.Counter();examples={};states=[];collected=collections.Counter()
    mem=DrawingMemory(patch.native_memory,patch,core=0x32);oracle=CanvasOracle(patch,patch.native_memory)
    sites={pc for pc,_,_ in patch.entries};interiors=set();valid=set()
    loops={pc+3:pc for pc in SCROLL_COUNT};remaining=collections.Counter()
    for pc,old,_ in patch.entries:
        end=pc+len(bytes.fromhex(old));interiors.update(range(pc+1,end));at=pc
        while at<end:
            if at!=pc:valid.add(at)
            at+=simrun.disasm(list(patch.native_memory),at)[1]
    def failure(key,value):
        counts[key+'!']+=1
        if len(examples.setdefault(key,[]))<5:examples[key].append(value)
    def hit(pc,s):
        if pc not in sites:
            counts[f'interior {pc:04X}']+=1
            if pc not in valid:failure('jump into instruction',f'{pc:04X}')
            if pc in loops:
                # LDIR/LDDR fetch their own ED prefix once per copied byte.
                # Check the countdown, rather than mistaking those repeats for
                # jumps from elsewhere into the replaced instruction sequence.
                expected=remaining[pc];actual=_pair(s.registers,2)
                if expected<=0 or actual!=expected:failure('block repeat entry',(f'{pc:04X}',expected,actual))
                remaining[pc]-=1
            return
        r=list(s.registers);m=bytes(s.memory);counts['hooks']+=1;counts[f'site {pc:04X}']+=1
        if pc in SCROLL_COUNT:
            if remaining[pc+3]:failure('unfinished block repeat',f'{pc:04X}')
            remaining[pc+3]=SCROLL_COUNT[pc]
        for a,old,_ in patch.entries:
            if m[a:a+len(bytes.fromhex(old))]!=bytes.fromhex(old):failure('native patch-site write',f'{a:04X}')
        try:oracle.event(pc,m,r)
        except AssertionError as exc:failure('native geometry',(f'{pc:04X}',str(exc)));raise
        bad,_,_=state_trial(patch,m,r,core=0x32,reuse=mem)
        for value in bad:failure('ABI',(f'{pc:04X}',value))
        for value in oracle.compare(pc,m,mem):failure('pixels',(f'{pc:04X}',value))
        if collected[pc]<collect:
            states.append(dict(pc=pc,memory=m,registers=r));collected[pc]+=1
        if counts['hooks']%10000==0 and progress:progress(dict(counts))
        if sum(v for k,v in counts.items() if k.endswith('!'))>=20:raise AssertionError(examples)
    import tempfile
    fd,stripped=tempfile.mkstemp(suffix='.rzx',dir=os.environ.get('TMPDIR'));os.close(fd)
    try:
        # One execution per recording: later snapshot blocks (autosaves) would reset the native machine but not
        # the oracle, the cache model or the repeat counters (ENGINE_CONTRACT: autosaves stripped).
        counts['autosaves stripped']=rzx.strip(str(rzx_path),stripped)
        frames,error=rzx.trace(stripped,sites|interiors,hit,stop=stop or 0)
    finally:os.remove(stripped)
    counts['frames']=frames
    if error:failure('recording',error)
    if not counts['hooks']:failure('no hook reached',Path(rzx_path).name)
    for pc,old,_ in patch.entries:
        for a in valid&set(range(pc+1,pc+len(bytes.fromhex(old)))):
            if a in loops:continue
            if not 0<=counts[f'site {pc:04X}']-counts[f'interior {a:04X}']<=1:failure('interior entry count',f'{a:04X}')
    return counts,examples,states


def _case(patch,state,clock=0,iff=0,core=0x32,policy=None,hwim2=0,display=None):
    m,r=state['memory'],state['registers'];oracle=CanvasOracle(patch,m)
    oracle.event(state['pc'],m,r)
    bad,_,mem=state_trial(patch,m,r,clock=clock,iff=iff,core=core,policy=policy,hwim2=hwim2,display=display)
    return bad+oracle.compare(state['pc'],m,mem)


PIXEL_FAILURES=('canvas','dark canvas','Layer2 position/pixels')
# Each control is detected only by its own failure (a crash or another mismatch does not count).
NEG_EXPECT={
    'position':lambda bad,clock:any(isinstance(b,tuple) and b[0] in PIXEL_FAILURES for b in bad),
    'transparency':lambda bad,clock:any(isinstance(b,tuple) and b[0] in PIXEL_FAILURES for b in bad),
    'R':lambda bad,clock:any(isinstance(b,tuple) and b[0]=='register' and b[1]==15 for b in bad),
    'speed':lambda bad,clock:any(isinstance(b,tuple) and b[0]=='NextREG' and b[1].get(7)!=clock for b in bad),
    'missing publication site':lambda bad,clock:any(isinstance(b,tuple) and b[0]=='hook not entered' for b in bad),
    'frame end leaves Layer 2 hidden':lambda bad,clock:any(isinstance(b,tuple) and b[0]=='Layer2 visibility' for b in bad),
    'dialog leaves Layer 2 shown':lambda bad,clock:any(isinstance(b,tuple) and b[0]=='Layer2 visibility' for b in bad),
}
NEG_DISPLAY={'frame end leaves Layer 2 hidden':0,'dialog leaves Layer 2 shown':128}

def negative_patches(patch):
    """Mutate the broken build's own code and banks, never its captured tables."""
    cases=[]
    broken=copy.deepcopy(patch);broken.sites=[x for x in broken.sites if x[0]!=0xEED3]
    if len(broken.sites)!=len(patch.sites)-1:raise AssertionError('Missing negative-control site: publication')
    cases.append(('missing publication site',broken))
    for name,block,offset,before,after in (
        ('position','code',patch.syms['buffer_offset'],bytes.fromhex('1190F2'),bytes.fromhex('1191F2')),
        ('transparency','code',None,bytes.fromhex('CB00300A'),bytes.fromhex('CB00180A')),
        ('R','resident',None,bytes.fromhex('ED4F'),bytes.fromhex('0000')),
        ('speed','resident',None,bytes.fromhex('ED9207'),bytes.fromhex('000000')),
        ('frame end leaves Layer 2 hidden','code',None,bytes.fromhex('ED916980'),bytes.fromhex('00000000')),
        ('dialog leaves Layer 2 shown','extra',None,bytes.fromhex('ED916900'),bytes.fromhex('00000000'))):
        broken=copy.deepcopy(patch);blob=bytearray.fromhex(broken.hooks[block])
        at=blob.find(before) if offset is None else offset
        if at<0 or blob[at:at+len(before)]!=before:raise AssertionError('Missing negative-control site: '+name)
        blob[at:at+len(before)]=after;broken.hooks[block]=blob.hex()
        if block in ('code','extra'):
            at0=0 if block=='code' else 0x1A00
            bank=bytearray(broken.extra_banks[13]);bank[at0:at0+len(blob)]=blob;broken.extra_banks[13]=bytes(bank)
        else:
            page=bytearray(broken.page);page[0x1A80:0x1A80+len(blob)]=blob;broken.page=bytes(page)
            bank=bytearray(broken.extra_banks[12]);bank[:8192]=page;broken.extra_banks[12]=bytes(bank)
        cases.append((name,broken))
    return cases


def unit_tests(patch,states):
    counts=collections.Counter();first={s['pc']:s for s in reversed(states)}
    def check(label,p,s,**kw):
        try:bad=_case(p,s,**kw)
        except (AssertionError,ValueError,KeyError,IndexError) as exc:bad=[str(exc)]
        counts[label+'!' if bad else label]+=1
        if bad and counts[label+'!']<=2:print('Great Escape unit failure',label,hex(s['pc']),bad[:2],flush=True)
    for s in first.values():
        for clock in range(4):
            for iff in (0,1):
                for core in (0x32,0x33):
                    state=dict(s);state['registers']=s['registers'][:];state['registers'][15]=(0x7F,0x80,0x00,0xFF)[clock]
                    check('ABI clock/IFF/core',patch,state,clock=clock,iff=iff,core=core)
        check('CPU fallback',patch,s,policy=0)
        check('HW IM2 fallback',patch,s,core=0x33,hwim2=1)
    for pc in (0xE2A2,0xE102):
        if pc not in first:continue
        s=first[pc];wide=pc==0xE102;iy=_pair(s['registers'],10)
        stores=((0xE188,0xE199,0xE1AA,0xE1BF),(0xE259,0xE26A,0xE27B,0xE290)) if wide else ((0xE319,0xE32A,0xE340),(0xE3C5,0xE3D6,0xE3EC))
        heights=(0xE121,0xE1E2) if wide else (0xE2C2,0xE363)
        for phase in range(8):
            for mirror in (0,128):
                for height in (1,32):
                    for clip in (0,1,2):
                        m=bytearray(s['memory']);m[0x81A2:0x81A4]=(0xF352).to_bytes(2,'little')
                        m[0x81B0:0x81B2]=(0x8100).to_bytes(2,'little');m[0x8100:0x8180]=bytes([255])*128
                        m[iy+24]=(m[iy+24]&248)|phase;m[0x81B7]=mirror
                        for a in heights:m[a]=height
                        for branch in stores:
                            for j,a in enumerate(branch):m[a]=0x77 if clip==1 or (clip==2 and j!=0) else 0
                        check('figure phase/mirror/clip/height',patch,dict(s,memory=bytes(m)))
        for start in (0xF28F,0xF2A7):
            m=bytearray(s['memory']);m[0x81A2:0x81A4]=start.to_bytes(2,'little');m[0x81B0:0x81B2]=(0x8100).to_bytes(2,'little');m[0x8100:0x8180]=bytes([255])*128
            m[iy+24]&=248
            for a in heights:m[a]=27
            for branch in stores:
                for j,a in enumerate(branch):m[a]=0 if j==0 else 0x77
            check('clipped canvas edge',patch,dict(s,memory=bytes(m)))
    for s in first.values():
        if s['pc'] in (0x9DC2,0xA50B):
            for start in (0,128):       # frame end must show Layer 2 from hidden, the dialog hide it from shown
                check('Layer 2 transition from %s'%('hidden' if not start else 'shown'),patch,s,display=start)
    for name,broken in negative_patches(patch):
        detected=False
        for s in states:
            try:bad=_case(broken,s,display=NEG_DISPLAY.get(name))
            except (AssertionError,ValueError,KeyError,IndexError):bad=[]
            if bad and NEG_EXPECT[name](bad,0):detected=True;break
        counts[name+' negative detected' if detected else name+' negative missed!']+=1
    if 0xE29F in first:
        s=first[0xE29F];iy=_pair(s['registers'],10)
        for item in range(16):
            m=bytearray(s['memory']);a=0xDD7D+item*6;m[iy]=item
            m[0x81AC:0x81B0]=m[a+2:a+6]
            m[0xE2C2]=m[0xE363]=m[a+1]
            check('item descriptor and key colour',patch,dict(s,memory=bytes(m)))
    if 0xE2A2 in first:
        s=first[0xE2A2];iy=_pair(s['registers'],10)
        for cosmetic in (False,True):
            p=copy.deepcopy(patch);page=bytearray(p.page);page[0x1E18]=int(cosmetic);p.page=bytes(page)
            bank=bytearray(p.extra_banks[12]);bank[:8192]=p.page;p.extra_banks[12]=bytes(bank)
            for figure in (2,30):
                for role in (0,1,20,21,22,23,24,25):
                    m=bytearray(s['memory']);a=0xCE22+figure*6;m[iy]=role
                    m[0x81AC:0x81B0]=m[a+2:a+6];m[0xE2C2]=m[0xE363]=m[a+1]
                    check('outfit and disguise',p,dict(s,memory=bytes(m)))
    return counts


def sheets(source,assets,out):
    """Export exact nearest-neighbour editable figures, outfit palettes and world tiles."""
    from PIL import Image,ImageDraw
    assets=Path(assets);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    snap=Z.Z80Snapshot(str(source));normalize_source(snap)
    memory=Z.rom48()+snap.banks[5]+snap.banks[2]+snap.banks[0]
    art=load_art(assets);colours=art['colours'];world=art['world']
    def rgb(n):return tuple(v*255//7 for v in ((n>>6)&7,(n>>3)&7,n&7))
    palette=[rgb(n) for n in art['palette']]
    variants=('Player RAF','Prisoner brown','Prisoner blue brown','Prisoner cream','Prisoner olive',
              'Prisoner RAF','Prisoner rust knit','McQueen player','Guard or disguise')
    image=Image.new('RGB',(1280,1140),'#30343a');draw=ImageDraw.Draw(image);figures=[]
    for i in range(38):
        a=0xCE22+i*6;width=(memory[a]-1)*8;height=memory[a+1];bitmap=_word(memory,a+2);mask=_word(memory,a+4)
        x0=(i%8)*160+8;y0=(i//8)*190+25;tile=Image.new('RGB',(width,height),'#30343a')
        for y in range(height):
            for x in range(width):
                addr=bitmap+y*(width//8)+x//8;bit=128>>(x&7)
                if memory[addr]&bit or not memory[mask+y*(width//8)+x//8]&bit:
                    tile.putpixel((x,y),palette[colours[(addr-16384)*8+(x&7)]])
        image.paste(tile.resize((width*5,height*5),Image.Resampling.NEAREST),(x0,y0))
        name='Stove' if i==0 else 'Crate' if i==1 else 'Person walk' if i<10 else 'Person crawling' if i<14 else 'Dog' if i<22 else 'Guard' if i<30 else 'Disguise'
        draw.text((x0,y0-18),f'{name} {i:02}',fill='white')
        figures.append(dict(index=i,name=name,width=width,height=height,bitmap=bitmap,mask=mask,x=x0,y=y0,scale=5))
    for i,name in enumerate(variants):
        x0=(i%3)*420+8;y0=955+(i//3)*60;draw.text((x0,y0),name,fill='white')
        for n in range(8):draw.rectangle((x0+n*28,y0+18,x0+n*28+23,y0+40),fill=palette[i*8+n])
    image.save(out/'GREAT_ESCAPE_PAINTING_SPRITES.png')
    image=Image.new('RGB',(1280,400),'#30343a');draw=ImageDraw.Draw(image);items=[]
    names={0:'Cutters',1:'Spade',3:'Uniform',5:'Chocolate',8:'Poison',9:'Red key',10:'Yellow key',11:'Green key',12:'Parcel'}
    for i in range(16):
        a=0xDD7D+i*6;width=memory[a]*8;height=memory[a+1];bitmap=_word(memory,a+2);mask=_word(memory,a+4)
        x0=i%8*160+8;y0=i//8*140+25;base=104+(i-9)*8 if 9<=i<=11 else 0
        tile=Image.new('RGB',(width,height),'#30343a')
        for y in range(height):
            for x in range(width):
                addr=bitmap+y*(width//8)+x//8;bit=128>>(x&7)
                if memory[addr]&bit or not memory[mask+y*(width//8)+x//8]&bit:
                    tile.putpixel((x,y),palette[colours[(addr-16384)*8+(x&7)]|base])
        image.paste(tile.resize((width*5,height*5),Image.Resampling.NEAREST),(x0,y0))
        name=names.get(i,'Item');draw.text((x0,y0-18),f'{name} {i:02}',fill='white')
        items.append(dict(index=i,name=name,width=width,height=height,bitmap=bitmap,mask=mask,x=x0,y=y0,scale=5,base=base))
    for i,name in enumerate(('Red key','Yellow key','Green key')):
        x0=i*420+8;draw.text((x0,300),name,fill='white')
        for n in range(8):draw.rectangle((x0+n*28,318,x0+n*28+23,340),fill=palette[104+i*8+n])
    draw.text((8,365),'The three keys share one drawing; their swatches select the three original key colours.',fill='white')
    image.save(out/'GREAT_ESCAPE_PAINTING_ITEMS.png')
    image=Image.new('RGB',(1280,1040),'#30343a');draw=ImageDraw.Draw(image)
    for i in range(194):
        a=0x9768+i*8;tile=Image.new('RGB',(8,8));tile.putdata([palette[v] for v in colours[(a-16384)*8:(a-16384)*8+64]])
        x0=i%16*80+4;y0=i//16*80+14
        image.paste(tile.resize((64,64),Image.Resampling.NEAREST),(x0,y0));draw.text((x0,y0-12),f'Inside {i:02X}',fill='white')
    image.save(out/'GREAT_ESCAPE_PAINTING_INTERIORS.png')
    for group in range(4):
        image=Image.new('RGB',(1200,1200),'#30343a');draw=ImageDraw.Draw(image)
        for j in range(64):
            block=group*64+j;tile=Image.new('RGB',(32,32));tile.putdata([palette[v] for v in world[block*1024:(block+1)*1024]])
            x0=j%8*150+4;y0=j//8*150+18
            image.paste(tile.resize((128,128),Image.Resampling.NEAREST),(x0,y0));draw.text((x0,y0-14),f'World {block:02X}',fill='white')
        image.save(out/f'GREAT_ESCAPE_PAINTING_WORLD_{group+1}.png')
    metadata=dict(source_md5=SOURCE_MD5,figures=figures,items=items,variants=variants,palette=palette,
                  colour_sha256=hashlib.sha256(colours).hexdigest(),world_sha256=hashlib.sha256(world).hexdigest())
    (out/'GREAT_ESCAPE_PAINTING_LAYOUT.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def import_sheets(source,assets,sheet_dir,destination):
    """Read flat RGB9 edits; reject interpolation and painting outside native figures.

    Common-person pixels are semantic colours 0..7. Their named outfit swatches
    control the nine costumes without changing the game's shared animation data.
    Other figures/world use the existing 128-colour palette. No nearest-colour
    blending: an unavailable colour is reported rather than silently substituted.
    """
    from PIL import Image
    assets=Path(assets);folder=Path(sheet_dir);destination=Path(destination)
    meta=json.loads((folder/'GREAT_ESCAPE_PAINTING_LAYOUT.json').read_text())
    if hashlib.md5(Path(source).read_bytes()).hexdigest()!=meta['source_md5']:raise ValueError('Painting source differs')
    art=load_art(assets);colours=bytearray(art['colours']);world=bytearray(art['world']);palette=art['palette'][:]
    if hashlib.sha256(colours).hexdigest()!=meta['colour_sha256'] or hashlib.sha256(world).hexdigest()!=meta['world_sha256']:
        raise ValueError('Painting layout belongs to different assets; export a new sheet first')
    snap=Z.Z80Snapshot(str(source));normalize_source(snap);m=Z.rom48()+snap.banks[5]+snap.banks[2]+snap.banks[0]
    def packed(rgb):return (round(rgb[0]*7/255)<<6)|(round(rgb[1]*7/255)<<3)|round(rgb[2]*7/255)
    def pixel(image,x,y,scale):
        samples={image.getpixel((x+dx,y+dy)) for dy in range(scale) for dx in range(scale)}
        if len(samples)!=1:raise ValueError(f'Non-flat enlarged pixel at {x},{y}; use nearest-neighbour pixels')
        return samples.pop()
    image=Image.open(folder/'GREAT_ESCAPE_PAINTING_SPRITES.png').convert('RGB')
    if image.size!=(1280,1140):raise ValueError('Sprite sheet dimensions changed')
    old=palette[:]
    for variant in range(9):
        x0=variant%3*420+8;y0=955+variant//3*60
        for n in range(8):
            value=packed(image.getpixel((x0+n*28+12,y0+28)))
            if n==0 and value:raise ValueError('Keep each outfit black swatch black')
            palette[variant*8+n]=value
    def index(rgb,previous,allowed):
        value=packed(rgb)
        if value==old[previous] or value==palette[previous]:return previous
        found=[i for i in allowed if value in (old[i],palette[i])]
        if not found:raise ValueError(f'Colour {rgb} is outside this sheet palette; edit the named outfit swatch to change its colour')
        return found[0]
    for f in meta['figures']:
        i=f['index'];w=f['width'];h=f['height'];allowed=range(8) if 2<=i<14 else range(128)
        for y in range(h):
            for x in range(w):
                rgb=pixel(image,f['x']+x*5,f['y']+y*5,5);a=f['bitmap']+y*(w//8)+x//8;bit=128>>(x&7)
                if not (m[a]&bit or not m[f['mask']+y*(w//8)+x//8]&bit):
                    if rgb!=(48,52,58):raise ValueError(f'Paint outside native figure {i} at {x},{y}')
                    continue
                n=(a-16384)*8+(x&7);colours[n]=index(rgb,colours[n],allowed)
    image=Image.open(folder/'GREAT_ESCAPE_PAINTING_ITEMS.png').convert('RGB')
    if image.size!=(1280,400):raise ValueError('Item sheet dimensions changed')
    for variant in range(3):
        for n in range(8):
            value=packed(image.getpixel((variant*420+8+n*28+12,328)))
            if n==0 and value:raise ValueError('Keep each key black swatch black')
            palette[104+variant*8+n]=value
    edits={}
    for f in meta['items']:
        w=f['width'];base=f['base']
        for y in range(f['height']):
            for x in range(w):
                rgb=pixel(image,f['x']+x*5,f['y']+y*5,5);a=f['bitmap']+y*(w//8)+x//8;bit=128>>(x&7)
                if not (m[a]&bit or not m[f['mask']+y*(w//8)+x//8]&bit):
                    if rgb!=(48,52,58):raise ValueError(f"Paint outside native item {f['index']} at {x},{y}")
                    continue
                n=(a-16384)*8+(x&7);previous=colours[n]
                value=index(rgb,previous|base,range(base,base+8) if base else range(128))
                if base:value&=7
                if value==previous:continue
                if n in edits and edits[n]!=value:raise ValueError('Conflicting edits to the shared key drawing')
                edits[n]=value
    for n,v in edits.items():colours[n]=v
    image=Image.open(folder/'GREAT_ESCAPE_PAINTING_INTERIORS.png').convert('RGB')
    if image.size!=(1280,1040):raise ValueError('Interior sheet dimensions changed')
    for i in range(194):
        x0=i%16*80+4;y0=i//16*80+14;start=(0x9768+i*8-16384)*8
        for y in range(8):
            for x in range(8):
                n=start+y*8+x;colours[n]=index(pixel(image,x0+x*8,y0+y*8,8),colours[n],range(128))
    for group in range(4):
        image=Image.open(folder/f'GREAT_ESCAPE_PAINTING_WORLD_{group+1}.png').convert('RGB')
        if image.size!=(1200,1200):raise ValueError('World sheet dimensions changed')
        for j in range(64):
            x0=j%8*150+4;y0=j//8*150+18;block=group*64+j
            for y in range(32):
                for x in range(32):
                    n=block*1024+y*32+x;world[n]=index(pixel(image,x0+x*4,y0+y*4,4),world[n],range(128))
    for n in range(128):
        value=palette[n];r,g,b=[v*255/7 for v in ((value>>6)&7,(value>>3)&7,value&7)]
        palette[n+128]=packed((r*.28,g*.33,b*.45+10 if r+g+b else 0))
    palette[255]=0x1C7
    dusk=[]
    for value in palette:
        channels=[v*255/7*.65 for v in ((value>>6)&7,(value>>3)&7,value&7)];dusk.append(packed(channels))
    dusk[255]=palette[255]
    destination.mkdir(parents=True,exist_ok=True)
    for name,data in (('colours.bin',colours),('world.bin',world),('palette.bin',b''.join(v.to_bytes(2,'little') for v in palette)),('palette-dusk.bin',b''.join(v.to_bytes(2,'little') for v in dusk))):
        (destination/name).write_bytes(data)
    return dict(changed_pixels=sum(a!=b for a,b in zip(colours,art['colours'])),changed_world_pixels=sum(a!=b for a,b in zip(world,art['world'])),changed_palette=sum(a!=b for a,b in zip(palette,art['palette'])))


def auto(a,z80,name,out,say):
    """Build both presentations from checked local source/art and prove every hook."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True);beside=Path(z80).resolve().parent
    default_art=beside/'great_escape_art' if (beside/'great_escape_art').is_dir() else beside
    assets=Path(os.environ.get('NEXCLASH_GREAT_ESCAPE_ART',str(default_art)))
    loading=beside/'great_escape-loading.scr'
    if not (assets/'colours.bin').is_file():raise ValueError('Set NEXCLASH_GREAT_ESCAPE_ART to the external painting assets')
    if not loading.is_file():raise ValueError('The original great_escape-loading.scr is required beside the source')
    if Z.ALLOW_60HZ:raise ValueError('Great Escape pacing counts 312-line (50 Hz) frames: --allow-60hz is not supported')
    if not getattr(a,'publisher',None):a.publisher='Ocean, 1986'
    if not getattr(a,'fix_label',None):a.fix_label='Presentation'
    trainers=out/(name+'_verified.pok')
    trainers.write_text(''.join('N'+title+'\n'+''.join(
        ('Z' if i==len(items)-1 else 'M')+f' 8 {addr+0x300} {value} {old}\n'
        for i,(addr,old,value) in enumerate(items)) for title,items in TRAINERS.items())+'Y\n')
    supplied=getattr(a,'pok',None)
    if supplied and Path(supplied).read_bytes()!=trainers.read_bytes():
        if hashlib.md5(Path(supplied).read_bytes()).hexdigest()!='7f61c780cc1d94e0fc2407c4e34206a4':
            raise ValueError('Unverified trainers; use the archive POK or the generated verified POK')
        say('Trainers  : morale carry fixed; invalid duplicate legacy addresses consolidated')
    a.pok=str(trainers);say('Game      : '+name)
    say('Engine    : great_escape; original monochrome default, optional painted Layer 2')
    ok=True;painted=None;built=[]
    for label,enabled,suffix in (('Plain',None,''),('Sprites',False,'_sprites'),('Enhanced',True,'_enhanced')):
        path=out/(name+suffix+'.nex');p=build(z80,path,assets if enabled is not None else None,enhanced=bool(enabled))
        bad=boot_problems(path,z80,p);ok &= not bad;built.append(str(path))
        say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK' if not bad else bad))
        if enabled is not None:
            path=out/(name+suffix+'_loading.nex');build(z80,path,assets,enhanced=enabled,loading=loading)
            bad=boot_problems(path,z80,p);ok &= not bad;built.append(str(path))
            if bad:say('Loading   : '+str(bad))
        if enabled:painted=p
    toggles={}
    # McQueen is a menu toggle that needs Enhanced (OPR1 "needs"); the CPU-copy builds are diagnostics only, kept
    # beside the package (nxcout "other"), never a menu choice.
    for title,suffix,kw in (('McQueen player','mcqueen',{'mcqueen':True}),('Disable DMA','cpu',{'dma':False})):
        row=dict(logic=False,what='Cosmetic outfit, requires Enhanced' if suffix=='mcqueen' else 'CPU copy compatibility fallback',colours={})
        for enabled in (False,True):
            entry={}
            for loaded in (False,True):
                path=out/(name+'_'+suffix+('_enhanced' if enabled else '')+('_loading' if loaded else '')+'.nex')
                p=build(z80,path,assets,enhanced=enabled,loading=loading if loaded else None,**kw)
                bad=boot_problems(path,z80,p);ok &= not bad;built.append(str(path))
                if bad:say('Toggle    : '+str(bad))
                entry['loading' if loaded else 'default']=path.name
            if enabled:row['colours']['Enhanced']=entry
            else:row.update(entry)
        if suffix=='mcqueen':toggles[title]=row
    manifest=dict(default=name+'_sprites.nex',loading=name+'_sprites_loading.nex',plain=name+'.nex',
                  colours={'Enhanced':dict(default=name+'_enhanced.nex',loading=name+'_enhanced_loading.nex')},toggles=toggles,
                  needs=[['McQueen player','Enhanced']])
    (out/(name+'_outputs.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    recordings=list(getattr(a,'rzx',None) or []);all_states=[]
    for recording in recordings:
        counts,examples,states=verify(painted,recording,stop=getattr(a,'quick',None),collect=4)
        all_states.extend(states);bad={k:v for k,v in counts.items() if k.endswith('!')};ok &= not bad
        say('Verify    : %s %d frames; %d hooks, registers/R/RAM/native pixels/colour pixels: %s'%(
            Path(recording).name,counts['frames'],counts['hooks'],'IDENTICAL' if not bad else bad))
        (out/(name+'_'+Path(recording).stem+'_verification.json')).write_text(json.dumps(dict(
            recording=Path(recording).name,counts=dict(counts),examples=examples),indent=2)+'\n')
    if recordings:
        units=unit_tests(painted,all_states);bad={k:v for k,v in units.items() if k.endswith('!')};ok &= not bad
        covered={s['pc'] for s in all_states};missing=[f'{pc:04X}' for pc,_,_ in painted.entries if pc not in covered]
        if missing and not getattr(a,'quick',None):ok=False;say('Coverage  : missing hooks '+str(missing))
        say('Unit      : '+str(dict(units)))
        (out/(name+'_units.json')).write_text(json.dumps(dict(counts=dict(units),missing=missing),indent=2)+'\n')
        from . import nextboot,runchecks,rzx
        from .machine import Machine
        runtime=Z.Z80Snapshot(str(z80));normalize_source(runtime)
        machine=Machine(str(z80));machine.sim=native(runtime);machine.sim.set_tracer(machine)
        runtime_path=out/(name+'_runtime.z80');runtime_path.write_bytes(machine.z80_bytes())
        # Raw-loader recordings start observation at the separately proven F068.
        # Already decoded test fixtures receive the full audit from frame zero.
        groups={True:[],False:[]}
        for recording in recordings:groups[rzx.read_segments(str(recording))[0][0].pc==0x5BC5].append(recording)
        report={}
        for loader,subset in groups.items():
            if not subset:continue
            part=nextboot.rom_paths(built,subset,stop=getattr(a,'quick',None),z80=str(runtime_path),start_pc=runtime.pc if loader else None)
            for nex,result in part.items():
                if nex not in report:report[nex]=result
                else:
                    old=report[nex];report[nex]=(old[0],old[1]+result[1],dict(old[2],**result[2]),dict(old[3],**result[3]))
        status,why,coverage=runchecks.rom_paths(report,recordings,built)
        for result in report.values():
            for line in result[1]:say('ROM paths : '+line)
        runchecks.add(runchecks.RUN,'rom_paths',status,why,coverage=coverage);ok &= status=='pass'
    if not (out/'GREAT_ESCAPE_PAINTING_LAYOUT.json').exists():sheets(z80,assets,out)
    if not recordings:say('Verify    : none (no recording given): builds and boot checks only')
    say('Result    : '+('PASSED' if ok else 'FAILED')+('' if recordings else ' (builds and boot checks only)'))
    return bool(ok)
