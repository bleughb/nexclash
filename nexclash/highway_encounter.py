"""Highway Encounter: exact archive entry and owned hidden ROM.

Original ordered mask/OR drawing, optional approved colours, original-pace windows.
"""
from pathlib import Path
from functools import lru_cache
import hashlib
import json
import os
import tempfile
from collections import Counter
from . import hooklib, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MD5 = 'ecfe7da10ba9aa395ae54c44301be1af'
COLOUR_MD5 = 'f2fb116ed79269c2412f210edc45675f'
LOADING_MD5 = 'be406c30814d5149a1b9053be25a8d58'
TRAINERS = {
    'Infinite time': {37268: 43},
    'Immunity': {40905: 8, 40918: 190, 40923: 182, 40763: 81, 40767: 195, 40768: 81},
    'Objects: shots only': {40890: 195},
}
GRAPHIC_RANGES = ((0x5b01,0x5bd7),(0x5e60,0x6420),(0x7100,0x7900),(0x9544,0x95e2),
                  (0xa490,0xa4ed),(0xab00,0xb0a0),(0xb8f0,0xd900))

CACHE_PAGES = tuple(range(25,46))
ENTRY = 0xB0E0
TAIL_ADDR = 0x5C80
CMP = tuple(hooklib.CMP_R)
SITES = {0x95EF: (bytes.fromhex("2100fd"), "h_scene_open", 0x95F2),
         0x9765: (bytes.fromhex("3a1c8f"), "h_scene_close", 0x9768),
         0x976D: (bytes.fromhex('2105d9'), 'h_post_open', 0x9770),
         0x981F: (bytes.fromhex('c346a5'), 'h_post_close', 0xA546),
         0x985A: (bytes.fromhex('dd2a018f'), 'h_open', 0x985E),
         0x9AD8: (bytes.fromhex('3a0b8f'), 'h_close', 0x9ADB),
         0x9822: (bytes.fromhex('21528d'), 'h_erase_open', 0x9825),
         0x9827: (bytes.fromhex('ca5998'), 'h_erase_test', (0x982A,0x9859)),
         0x9856: (bytes.fromhex('c22a98'), 'h_erase_test', (0x982A,0x9859))}
COLOUR_SITES = {0x9933:(bytes.fromhex('69603e18'),'c_9933',0x9937),
                0x99D1:(bytes.fromhex('60693e18'),'c_99d1',0x99D5),
                0x9A26:(bytes.fromhex('60693e18'),'c_9a26',0x9A2A),
                0x9A70:(bytes.fromhex('60690618'),'c_9a70',0x9A74),
                0x9615:(bytes.fromhex('edb0dd23'),'c_9615',0x9619),
                0x9622:(bytes.fromhex('edb0211bda'),'c_9622',0x9627),
                0x9778:(bytes.fromhex('edb02105d9'),'c_9778',0x977D),
                0x9783:(bytes.fromhex('edb02125d9'),'c_9783',0x9788),
                0x97B6:(bytes.fromhex('edb0d1'),'c_97b6',0x97B9),
                0x97E8:(bytes.fromhex('edb00e0f'),'c_97e8',0x97EC),
                0x97FB:(bytes.fromhex('edb0d1'),'c_97fb',0x97FE),
                0x983D:(bytes.fromhex('0105f0'),'c_983d',0x9840),
                0xA3DE:(bytes.fromhex('edb8212060'),'c_a3de',0xA3E3),
                0xA5F0:(bytes.fromhex('edb00e0c'),'c_a5f0',0xA5F4),
                0xA603:(bytes.fromhex('edb0d1'),'c_a603',0xA606),
                0xA9EB:(bytes.fromhex('edb8c9'),'c_a9eb',None),
                0xAA4C:(bytes.fromhex('edb02100fd'),'c_aa4c',0xAA51),
                0xAA79:(bytes.fromhex('edb0d1'),'c_aa79',0xAA7C),
                0x960B:(bytes.fromhex('1213dd7e00'),'c_960b',0x9610),
                0x9610:(bytes.fromhex('1213011e00'),'c_9610',0x9615),
                0x9641:(bytes.fromhex('77dd23'),'c_9641',0x9644),
                0x964D:(bytes.fromhex('77dd23'),'c_964d',0x9650),
                0x96B8:(bytes.fromhex('3e08112000087edd770023dd19083d20f4'),'c_96b8',0x96C9),
                0x972D:(bytes.fromhex('3e08112000087edd770023dd19083d20f4'),'c_972d',0x973E),
                0xA911:(bytes.fromhex('7723dd7e08'),'c_a911',0xA916),
                0xA916:(bytes.fromhex('7719dd23'),'c_a916',0xA91A),
                0x9A9B:(bytes.fromhex('21fc9b'),'c_9a9b',0x9A9E),
                0x9773:(bytes.fromhex('36ff011f00'),'c_9773',0x9778),
                0xA3D9:(bytes.fromhex('360001001b'),'c_a3d9',0xA3DE),
                0x979F:(bytes.fromhex('3600013f02'),'c_979f',0x97A4),
                0x97A4:(bytes.fromhex('edb82105d9'),'c_97a4',0x97A9),
                0x99A0:(bytes.fromhex('77237723771910f8'),'c_99a0',0x99A8),
                0xA5CD:(bytes.fromhex('7723772377'),'c_a5cd',0xA5D2),
                0x978D:(bytes.fromhex('7ef68077197ef601772310f4'),'c_978d',0x9799),
                0xB8B6:(bytes.fromhex('121318dc'),'c_b8b6',0xB896),
                0xB8DA:(bytes.fromhex('123e7f'),'c_b8da',0xB8DD),
                0xB8DE:(bytes.fromhex('12140605'),'c_b8de',0xB8E2),
                0xB8E3:(bytes.fromhex('121423'),'c_b8e3',0xB8E6),
                0xB8EA:(bytes.fromhex('12d113'),'c_b8ea',0xB8ED),
                0xA3AF:(bytes.fromhex('365223'),'c_a3af',0xA3B2),
                0x97DD:(bytes.fromhex('edb82105db'),'c_97dd',0x97E2),
                0xB3A4:(bytes.fromhex('010003'),'c_b3a4',0xB3A7),
                }
INTERIORS = tuple(a+k for a,(old,_,_) in SITES.items() for k in range(1,len(old)))

def load_profile():
    return json.loads((ROOT/'docs/profiles/highway_encounter.json').read_text())

def is_highway_encounter(snap):
    banks = getattr(getattr(snap, 'memory', None), 'banks', None) or getattr(snap, 'banks', None)
    if not banks or getattr(snap, 'is128', False) or getattr(snap, 'machine', '48K') != '48K':
        return False
    return bytes(banks[0][0x3260:0x3276]) == bytes.fromhex(
        'f33100002160f111005b010001edb03ef9ed4fc3e0b0')

@lru_cache(maxsize=2)
def entry_snapshot(source):
    """Run the original BASIC/USR prefix, stopping before the first B0E0 instruction."""
    from .machine import Machine, parse_inputs
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Use the supported Highway Encounter archive, MD5 '+SOURCE_MD5)
    machine = Machine(str(source))
    r = machine.sim.registers
    last = [r[24]]
    class Reached(Exception): pass
    class FrameEnd(Exception): pass
    def trace(fc, pc):
        if pc == ENTRY:
            raise Reached()
        if r[25] >= 69888:
            raise FrameEnd()
        last[0] = pc
    for frame in range(100):
        machine.held = parse_inputs('ENTER' if 10 <= frame < 16 else '')
        try:
            machine.sim.exec_frame(65535, None, trace)
        except Reached:
            return machine.z80_bytes()
        except FrameEnd:
            pass
        r[25] = 0
        if r[26]:
            if machine.sim.memory[last[0]] == 0x76:
                r[24] = (r[24]+1) & 65535
            machine.sim.accept_interrupt(r, machine.sim.memory, 0)
    raise ValueError('Original loader did not reach B0E0')

def prepared(source):
    fd, name = tempfile.mkstemp(suffix='.z80')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(entry_snapshot(str(source)))
        return zt.Z80Snapshot(name)
    finally:
        os.unlink(name)

class Patch:
    name = 'Highway Encounter: original entry'
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    max_tail = 128
    hook_page_data = b''
    setup_call = 0xD000
    altrom_whole = True

    def __init__(self, source, enabled=True, resume=False, colour_source=None, palette_source=None, dma=True, painting=None, trainers=()):
        self.source = str(source)
        self.enabled = enabled
        self.resume = resume
        self.colour_source = colour_source
        self.painting = painting
        self.trainers = tuple(trainers)
        if set(self.trainers)-TRAINERS.keys():raise ValueError('Unknown trainer')
        self.paint_changes = 0
        self.paint_overrides = {}
        self.site_map = SITES | (COLOUR_SITES if colour_source else {})
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        if colour_source:
            palette_path = Path(palette_source or Path(colour_source).with_name('source-palette.pal'))
            values = list(map(int,palette_path.read_text().split()))
            if len(values)!=768 or any(not 0<=v<=255 for v in values):
                raise ValueError('Expected 256 RGB palette entries')
            self.source_rgb = [tuple(values[i:i+3]) for i in range(0,768,3)]
            self.palette = [tuple(round(v*7/255) for v in rgb) for rgb in self.source_rgb]
            palette = bytearray()
            for i in range(256):
                r,g,b = (round(v*7/255) for v in values[i*3:i*3+3])
                palette += bytes([(r<<5)|(g<<2)|(b>>1),b&1]) if i!=227 else bytes([0xE3,0])
            self.stub_extra += bytes(256-len(self.stub_extra))+bytes.fromhex(h['colour_setup'])+palette
            self.setup_call = 0xD100
        self.slot1 = (24, self.syms['regblock'])
        self.altrom = self.altrom0 = (self.syms["rom_start"], 0x3E00)
        self.page = bytearray(zt.rom48()[0x2000:0x4000])
        self.page[self.syms["rom_start"]-0x2000:self.syms["rom_start"]-0x2000+len(self.code)] = self.code
        self.page[self.syms['hlib_dma_policy']-0x2000] = int(dma)
        self.page[0x1E00:0x1F00] = bytes(256)
        self.sites = [(a,old,b'\xc3'+zt.w16(self.syms[name])+bytes(len(old)-3))
                      for a,(old,name,_) in self.site_map.items()] if enabled else []
        # SET3 options may add only banks8+. Reserve Layer2 banks6/7 in the
        # base too;48K gameplay never maps them, and their zero payload is tiny.
        self.extra_banks = {6:bytearray(16384),7:bytearray(16384)}

    def apply(self, snap):
        if self.resume:
            # Private paired measurements start at the same original gameplay
            # checkpoint; the supported archive still gates release identity.
            entry_snapshot(self.source)
        else:
            if not is_highway_encounter(snap):
                raise ValueError('Unsupported Highway Encounter snapshot')
            snap.__dict__.update(prepared(self.source).__dict__)
        # NEXLOAD uses the printer buffer; the original loader's font and the
        # temporary startup tail must both be restored before game entry.
        self.page[0:0x200] = snap.banks[5][0x1B00:0x1D00]
        for name, value, width in (('boot_r', ((snap.r-5)&127)|(snap.r&128), 1),
                                   ('boot_sp', snap.sp, 2), ('boot_jump', snap.pc, 2)):
            o = self.syms[name]-0x2000+1
            self.page[o:o+width] = value.to_bytes(width, 'little')
        ram = bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        if self.colour_source:
            self.colours = colour_assets(self.colour_source,bytes(16384)+ram,self)
            # Palette edits are part of the same immutable setup tail.
            palette = b''.join(bytes([(r<<5)|(g<<2)|(b>>1), b&1]) if i!=227
                               else b'\xe3\0' for i,(r,g,b) in enumerate(self.palette))
            self.stub_extra = self.stub_extra[:-512] + palette
            for page,data in self.colours.items():
                bank=self.extra_banks.setdefault(page//2,bytearray(16384))
                bank[(page&1)*8192:(page&1)*8192+8192]=data
        self.extra_banks[12] = bytes(self.page)+bytes(
            self.colours[25] if self.colour_source else bytes(8192))
        for a,(old,_,_) in self.site_map.items():
            if ram[a-0x4000:a-0x4000+len(old)] != old:
                raise ValueError('Original patch bytes differ at '+hex(a))
        for a,old,new in self.sites:
            ram[a-0x4000:a-0x4000+len(new)] = new
        for trainer in self.trainers:
            for address,value in TRAINERS[trainer].items():ram[address-0x4000]=value
        snap.banks[5],snap.banks[2],snap.banks[0] = bytes(ram[:16384]),bytes(ram[16384:32768]),bytes(ram[32768:])
        snap.pc = self.syms['boot_resume']

def build(source, destination, enabled=True, checkpoint=None, colour_source=None, palette_source=None, dma=True, painting=None, trainers=(), loading=None):
    patch = Patch(source, enabled, resume=checkpoint is not None,colour_source=colour_source,palette_source=palette_source,dma=dma,painting=painting,trainers=trainers)
    zt.convert(str(checkpoint or source), str(destination), patch=patch, quiet=True)
    if loading is not None:
        screen=Path(loading).read_bytes()
        if hashlib.md5(screen).hexdigest()!=LOADING_MD5:raise ValueError('Use the verified original HIGHWAY.scr')
        data=Path(destination).read_bytes();head=bytearray(data[:512]);head[10],head[133]=2,50
        Path(destination).write_bytes(bytes(head)+screen+data[512:])
    return patch

def boot_check(nex, source, patch):
    from . import nextboot
    from .machine import Machine
    fd, name = tempfile.mkstemp(suffix='.z80')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(entry_snapshot(str(source)))
        original = Machine(name)
    finally:
        os.unlink(name)
    expected = list(original.sim.memory)
    for a,old,new in patch.sites:
        if bytes(expected[a:a+len(old)]) != old:
            raise ValueError('Original patch bytes differ at '+hex(a))
        expected[a:a+len(new)] = new
    for trainer in patch.trainers:
        for address,value in TRAINERS[trainer].items():expected[address]=value
    bad = []
    for nexload in (False, True):
        state = nextboot.boot(str(nex), ENTRY, nexload=nexload, sysrom=nextboot.system_rom3()[0])
        bad += [('register', nexload, i, original.sim.registers[i], state['R'][i]) for i in CMP
                if (bool(original.sim.registers[i]) != bool(state['R'][i]) if i == 26
                    else original.sim.registers[i] != state['R'][i])]
        bad += [('RAM', nexload, hex(a), expected[a], state['mem'][a])
                for a in range(0x4000, 65536) if expected[a] != state['mem'][a]]
        bad += [('ROM', nexload, v) for v in state['bad']]
        if state['mmu'] != [255,255,10,11,4,5,0,1]:
            bad.append(('MMU', nexload, state['mmu']))
        if state['nr'].get(0x8C) != 0x80:
            bad.append(('hidden ROM disabled', nexload))
        # Both complete hidden ROM images must survive NextZXOS 26.11.
        snap = prepared(source)
        snap.pc = patch.syms['boot_resume']
        regs = zt.build_tail(snap,TAIL_ADDR,patch.slot1,True,False)[3]
        for slot,wanted in enumerate((nextboot.alt_image0(patch),nextboot.alt_image(patch))):
            wanted[patch.syms['regblock']:patch.syms['regblock']+len(regs)] = regs
            if bytes(state['alt'][slot]) != bytes(wanted):
                bad.append(('full hidden ROM differs',nexload,slot))
    return bad

class HookMemory:
    def __init__(self, memory, patch, page=None):
        self.ram = bytearray(memory)
        self.patch = patch
        self.page = bytearray(patch.page if page is None else page)
        self.model = None
        for a,old,new in patch.sites:
            self.ram[a:a+len(new)] = new
    def __len__(self): return 65536
    def __getitem__(self,a):
        if isinstance(a,slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if 0x2000 <= a < 0x4000:
            if self.model and self.model.nr.get(0x51,255) == 24:
                return self.page[a-0x2000]
            return self.patch.page[a-0x2000]
        return self.ram[a]
    def __setitem__(self,a,v):
        if 0x2000 <= a < 0x4000 and self.model and self.model.nr.get(0x51,255) == 24:
            self.page[a-0x2000] = v
        elif a >= 0x4000:
            self.ram[a] = v

class HookModel(hooklib.NextModel):
    def __init__(self,sim,speed):
        super().__init__(sim,speed)
        self.nr[0x51] = 255
        self.nr[1], self.nr[0xC0] = 0x32, 0
        self.dma.stall = self.dma_stall
        self.game_io = []
    def dma_stall(self,count):
        self.real += count/4  # Explicit injected model time, not hardware timing.
    def write_port(self,regs,port,value,*args):
        if port in (0x243B,0x253B) or port&255==0x6B:
            return super().write_port(regs,port,value,*args)
        self.game_io.append((port,value))

def colour_location(address):
    """Independent logical-byte map for the eight-pixel colour mirror."""
    if not 0x4000 <= address <= 0xFFFF:
        raise ValueError('Colour source outside original RAM')
    if address >= 0x5800:
        offset = (address-0x5800)*8
        return 50+offset//8192,offset%8192
    y = ((address>>8)&7)|((address>>2)&0x38)|((address>>5)&0xC0)
    offset = y*256+(address&31)*8
    return 12+offset//8192,offset%8192

def painting_frames():
    for i in range(57):yield i,0xB8F0+144*i,(i%8)*32,(i//8)*32

def import_painting(patch,memory,decode):
    """Exact source indices survive an unedited PNG; changed RGB uses solid Next RGB333."""
    from PIL import Image
    path=Path(patch.painting)
    if path.is_dir():path=path/'HIGHWAY_PAINTING_SPRITES.png'
    im=Image.open(path).convert('RGBA')
    if im.size!=(256,256):raise ValueError('Highway sheet must remain native256x256')
    used={0,255,227}
    for lo,hi in GRAPHIC_RANGES:
        for a in range(lo,hi):used.update(decode(a))
    overrides={};changed=0;occupied=set()
    for i,source,x0,y0 in painting_frames():
        for y in range(24):
            for x in range(24):
                at=source+(23-y)*6+x//8;bit=128>>(x&7)
                opaque=not(memory[at]&bit) or bool(memory[at+3]&bit)
                pixel=im.getpixel((x0+x,y0+y));occupied.add((x0+x,y0+y))
                if pixel[3] not in (0,255):raise ValueError('Partial alpha in frame '+str(i))
                if bool(pixel[3])!=opaque:raise ValueError('Keep the original pixel border in frame '+str(i))
                if not opaque:continue
                at+=3;old=decode(at)[x&7]
                if pixel[:3]==patch.source_rgb[old]:continue
                rgb=tuple(round(v*7/255) for v in pixel[:3])
                n=next((j for j,c in enumerate(patch.palette) if j!=227 and c==rgb),None)
                if n is None:
                    n=next((j for j in range(256) if j not in used),None)
                    if n is None:raise ValueError('No free opaque palette index')
                    patch.palette[n]=rgb
                used.add(n)
                row=overrides.setdefault(at,bytearray(decode(at)));row[x&7]=n;changed+=1
    if any(im.getpixel((x,y))[3] for y in range(256) for x in range(256) if (x,y) not in occupied):
        raise ValueError('Paint outside the native figure cells')
    return {a:bytes(v) for a,v in overrides.items()},changed

def painting_sheets(patch,destination):
    """Never overwrite an editable master. Geometry comes from original mask/ink borders."""
    from PIL import Image
    folder=Path(destination);folder.mkdir(parents=True,exist_ok=True)
    path=folder/'HIGHWAY_PAINTING_SPRITES.png'
    if path.exists():return
    snap=prepared(patch.source);memory=bytes(16384)+snap.banks[5]+snap.banks[2]+snap.banks[0]
    raw=Path(patch.colour_source).read_bytes();im=Image.new('RGBA',(256,256),(0,0,0,0));frames=[]
    for i,base,x0,y0 in painting_frames():
        for y in range(24):
            for x in range(24):
                a=base+y*6+x//8;bit=128>>(x&7)
                if memory[a]&bit and not memory[a+3]&bit:continue
                a+=3;p=(5,2,0)[(a>>14)-1]*16384*9+(a&16383)*9
                n=sum(((raw[p+k]>>(7-(x&7)))&1)<<k for k in range(8))
                im.putpixel((x0+x,y0+23-y),(*patch.source_rgb[n],255))
        frames.append(dict(id=i,source=base,x=x0,y=y0,width=24,height=24))
    im.save(path)
    path.with_suffix('.layout.json').write_text(json.dumps(dict(schema=1,palette=patch.source_rgb,
        frames=frames,source_sha256=hashlib.sha256(memory[0xb8f0:0xd900]).hexdigest()),indent=2)+'\n')

def colour_assets(path,memory,patch):
    """Private owner-supplied colour planes; no painter code is imported."""
    data=Path(path).read_bytes()
    if hashlib.md5(data).hexdigest()!=COLOUR_MD5:
        raise ValueError('Unsupported colour master')
    def decode(a):
        p=(5,2,0)[(a>>14)-1]*16384*9+(a&16383)*9
        if data[p+8]!=memory[a]:
            raise ValueError('Colour graphics differ at '+hex(a))
        return bytes(sum(((data[p+k]>>(7-b))&1)<<k for k in range(8)) for b in range(8))
    colours={n:bytearray(8192) for n in (*range(12,18),*range(50,92),*CACHE_PAGES)}
    for n in range(12,18):colours[n][:]=bytes([227])*8192
    # F260 changes 5B00 from 68 to 65 before B0E0. That loader byte is not
    # source-matched artwork; leave its mirror monochrome. Text uses the ULA.
    if patch.painting:
        patch.paint_overrides, patch.paint_changes = import_painting(patch,memory,decode)
    original_decode=decode
    def decode(a):return patch.paint_overrides.get(a,original_decode(a))
    for a in range(0x4000,65536):
        page,offset=colour_location(a)
        colours[page][offset:offset+8]=bytes(255 if memory[a]&(128>>b) else 0 for b in range(8))
    for lo,hi in GRAPHIC_RANGES:
        for a in range(lo,hi):
            page,offset=colour_location(a);colours[page][offset:offset+8]=decode(a)
    cache=bytearray();table=bytearray()
    for frame in range(57):
        src=0xb8f0+144*frame
        for shift in (2,-4,-2,0):
            offset=len(cache);page=CACHE_PAGES[offset//8192]
            rows=[]
            for y in range(24):
                masks=[int(bool(memory[src+y*6+x//8]&(128>>(x&7)))) for x in range(24)]
                ink=list(b''.join(decode(src+y*6+3+x) for x in range(3)))
                if shift==2:masks=[masks[0]]*2+masks[:22];ink=[0,0]+ink[:22]
                elif shift==-2:masks=masks[2:]+[1,masks[0]];ink=ink[2:]+[0,0]
                elif shift==-4:masks=masks[4:20]+[1]*8;ink=ink[4:20]+[0]*8
                rows.append((masks,ink))
            fast=False
            table+=bytes([page])+(0xc000+(offset&8191)).to_bytes(2,'little')+bytes([fast])
            for masks,ink in rows:
                cache+=bytes(sum(masks[k*8+b]<<(7-b) for b in range(8)) for k in range(3))
                flags=[not any(masks[k*8+b] and ink[k*8+b] for b in range(8)) for k in range(3)]
                cache+=bytes(flags)
                cache+=bytes(227 if flags[i//8] and mask else colour for i,(mask,colour) in enumerate(zip(masks,ink)))
    for i,page in enumerate(CACHE_PAGES):
        block=cache[i*8192:(i+1)*8192];colours[page][:len(block)]=block
    offset=patch.syms['colour_cache_table']-0xC000
    colours[45][offset:offset+len(table)]=table
    if len(cache)>20*8192+2048 or offset+len(table)>2048:
        raise ValueError('Monochrome lookup overlaps figure cache')
    colours[45][2048:4096]=bytes(255 if value&(128>>bit) else 0
                               for value in range(256) for bit in range(8))
    return colours

class ColourMemory(HookMemory):
    def __init__(self,memory,patch,page=None,colours=None):
        super().__init__(memory,patch,page)
        self.colour_writes = set()
        self.colours = colours if colours is not None else {
            n:bytearray(8192) for n in (*range(12,18),*range(50,92))}
    def __getitem__(self,a):
        if not isinstance(a,slice) and a>=0xA000 and self.model:
            bank=self.model.nr.get(0x50+(a>>13),(a>>13)-6)
            if bank in self.colours:return self.colours[bank][a&8191]
        return super().__getitem__(a)
    def __setitem__(self,a,v):
        if a>=0xA000 and self.model:
            bank=self.model.nr.get(0x50+(a>>13),(a>>13)-6)
            if bank in self.colours:
                self.colours[bank][a&8191]=v;self.colour_writes.add((bank,(a&8191)//8));return
        super().__setitem__(a,v)

def compare_hook(memory,registers,patch,page=None,speed=0,colours=None):
    from skoolkit.simulator import Simulator
    from . import simpool
    from .dizzy6 import _rw_simulator
    ref = simpool.machine(Simulator,list(memory),list(registers),'highway-original',copy=True)
    target = patch.site_map[registers[24]][2]
    if target is None:
        sp=registers[12];target=memory[sp]+256*memory[(sp+1)&65535]
    targets=target if isinstance(target,tuple) else (target,)
    for step in range(1000000):
        if step and ref.registers[24] in targets:break
        ref.opcodes[ref.memory[ref.registers[24]]]()
    else:raise AssertionError('Original hook scope failed to return')
    target=ref.registers[24]
    view = (ColourMemory(memory,patch,page,colours if colours is not None else {
                n:bytearray(v) for n,v in patch.colours.items()})
            if patch.colour_source else HookMemory(memory,patch,page))
    sim = simpool.machine(_rw_simulator(),view,list(registers),'highway-hook')
    model = HookModel(sim,speed);view.model = model
    model.nr[1],model.nr[0xC0]=getattr(patch,'test_backend',(0x32,0))
    if registers[24] in (0x9AD8,0x9765,0x981F) or (registers[24] in (0x9827,0x9856) and registers[1]&64):
        model.real = 2000
    for step in range(5000000):
        if step and sim.registers[24] == target:break
        sim.opcodes[view[sim.registers[24]]]()
    else:raise AssertionError('Highway hook failed to return at '+hex(sim.registers[24]))
    bad = [('register',i,ref.registers[i],sim.registers[i]) for i in CMP
           if (bool(ref.registers[i]) != bool(sim.registers[i]) if i == 26
               else ref.registers[i] != sim.registers[i])]
    expected = bytearray(ref.memory[0x4000:])
    for a,old,new in patch.sites:expected[a-0x4000:a-0x4000+len(new)] = new
    bad += [('RAM',i+0x4000,a,b) for i,(a,b) in enumerate(zip(expected,view.ram[0x4000:])) if a!=b]
    if model.nr[0x51] != 255:bad.append(('MMU',model.nr[0x51]))
    if model.game_io:bad.append(('game I/O',model.game_io))
    return bad,view,model

def verify_default(patch,rzx_path,stop=None,collect=0,progress=None):
    from . import rzx
    c,examples,states = Counter(),{},[]
    page,speed,opened = bytearray(patch.page),0,False
    pending=None
    ends={t for _,_,target in SITES.values() for t in (target if isinstance(target,tuple)else(target,))}
    def fail(key,detail):
        c[key+'!']+=1
        if len(examples.setdefault(key,[]))<5:examples[key].append(detail)
    def visit(pc,sim):
        nonlocal page,speed,opened,pending
        if pc in ends:pending=None
        if pc not in SITES:
            if pc in INTERIORS and (pending is None or not pending[0]<pc<pending[1]):
                fail('jump into patched instruction',pc)
            return
        pending=(pc,pc+len(SITES[pc][0]))
        mem,regs = bytes(sim.memory),list(sim.registers)
        if collect and sum(s[0]==pc for s in states)<collect:states.append((pc,regs,mem))
        for a,(old,_,_) in SITES.items():
            if mem[a:a+len(old)]!=old:fail('original patch bytes changed',a)
        bad,view,model=compare_hook(mem,regs,patch,page,speed)
        if bad:fail('state differs',{'pc':pc,'details':bad[:8]})
        closes=pc in (0x9AD8,0x9765,0x981F) or (pc in (0x9827,0x9856) and regs[1]&64)
        if pc in (0x9822,0x985A,0x95EF,0x976D):
            if opened:fail('nested drawing window',pc)
            opened,wanted=True,3
        elif closes:
            if not opened:fail('close without open',pc)
            opened,wanted=False,0;c['erase windows' if pc!=0x9AD8 else 'drawing windows']+=1
        else:wanted=speed
        if model.nr[7]!=wanted:fail('clock differs',[pc,model.nr[7],wanted])
        page,speed=view.page,model.nr[7]
        c['hooks']+=1;c['R comparisons']+=1;c['RAM bytes compared']+=49152
        if progress and c['hooks']%500==0:progress(c)
    c['frames'],error=rzx.trace(str(rzx_path),set(SITES)|set(INTERIORS)|ends,visit,stop)
    if error:fail('recording desynchronised',error)
    if opened:c['unfinished window at recording end']+=1
    return (c,examples,states) if collect else (c,examples)


def mono(value):
    return bytes(255 if value&(128>>bit) else 0 for bit in range(8))

class ColourOracle:
 def __init__(self,patch,shots=(),wrong_shift=False):
  data=Path(patch.colour_source).read_bytes()
  @lru_cache(maxsize=65536)
  def pixel(a):
   if a in patch.paint_overrides:return patch.paint_overrides[a]
   off=(5,2,0)[(a>>14)-1]*16384*9+(a&16383)*9
   return bytes(sum(((data[off+p]>>(7-b))&1)<<p for p in range(8)) for b in range(8))
  self.pixel=pixel
  self.shots=set(shots);self.images=[];self.frame=0;self.counts=Counter();self.bad=[];self.samples=[];self.wrong_shift=wrong_shift
 def on_sim(self,sim):
  self.sim=sim;self.r=sim.registers;self.m=sim.memory
  self.col=[mono(self.m[a]) for a in range(65536)];self.bit=[mono(self.m[a]) for a in range(65536)]
  for lo,hi in ((0x5b01,0x5bd7),(0x5e60,0x6420),(0x7100,0x7900),(0x9544,0x95e2),(0xa490,0xa4ed),(0xab00,0xb0a0),(0xb8f0,0xd900)):
   for a in range(lo,hi):self.col[a]=self.pixel(a)
 def pair(self,i):return self.r[i]*256+self.r[i+1]
 def copy(self,d,s):
  self.col[d]=self.col[s];self.bit[d]=self.bit[s]
 def fill(self,d,v):self.col[d]=self.bit[d]=mono(v)
 def before(self,pc):
  r=self.r;m=self.m
  # Original scenery copy operations, including the save-under background.
  if pc in (0x9615,0x9622,0x9778,0x9783,0x97b6,0x97e8,0x97fb,0x9846,0xa3de,0xa5f0,0xa603,0xa9eb,0xaa4c,0xaa79):
   self.copy(self.pair(4),self.pair(6));self.counts[f'copy-{pc:04x}']+=1
  elif pc==0x960b:self.copy(self.pair(4),self.pair(8)+8)
  elif pc==0x9610:self.copy(self.pair(4),self.pair(8))
  elif pc in (0x9641,0x964d):self.copy(self.pair(6),self.pair(8))
  elif pc==0xa911:self.copy(self.pair(6),self.pair(8))
  elif pc==0xa916:self.copy(self.pair(6),self.pair(8)+8)
  elif pc in (0x96bf,0x9734):self.copy(self.pair(8),self.pair(6))
  elif pc==0x9773:self.fill(self.pair(6),255)
  elif pc==0xa3d9:self.fill(self.pair(6),0)
  elif pc in (0x99a0,0x99a2,0x99a4,0xa5cd,0xa5cf,0xa5d1):
   # The first dirty-cell row overlaps the tail of the drawing buffer.
   self.fill(self.pair(6),r[0])
  elif pc in (0xb8da,0xb8de,0xb8e3,0xb8ea):
   a=self.pair(4);self.bit[a]=mono(r[0]);self.col[a]=bytes([0])*8
   # Text keeps the original ULA attributes; sentinel is held separately.
   self.col[a]=tuple([256]*8)
  elif pc in (0x9790,0x9795):
   a=self.pair(6);mask=128 if pc==0x9790 else 1
   self.col[a]=bytes(255 if mask&(128>>b) else v for b,v in enumerate(self.col[a]));self.bit[a]=mono(r[0])
  elif pc in (0x9933,0x99d1,0x9a26,0x9a70):
   # Each draw is 24 bottom-first rows, three mask bytes then three ink bytes.
   src=self.pair(4);dst=self.pair(2);shift={0x9933:2,0x99d1:-4,0x9a26:-2,0x9a70:0}[pc]
   if self.wrong_shift:shift+=1
   self.counts[f'actor-{pc:04x}']+=1
   if len(self.samples)<20:self.samples.append({'frame':self.frame,'pc':pc,'source':src,'destination':dst,'shift':shift,'ix':self.pair(8)})
   for y in range(24):
    masks=[255 if m[src+y*6+x//8]&(128>>(x&7)) else 0 for x in range(24)]
    inks=[255 if m[src+y*6+3+x//8]&(128>>(x&7)) else 0 for x in range(24)]
    colours=[self.pixel(src+y*6+3+x//8)[x&7] for x in range(24)]
    if shift==2:
     masks=[masks[0]]*2+masks[:22];inks=[0,0]+inks[:22];colours=[0,0]+colours[:22]
    elif shift==-2:
     masks=masks[2:]+[255,masks[0]];inks=inks[2:]+[0,0];colours=colours[2:]+[0,0]
    elif shift==-4:masks=masks[4:20];inks=inks[4:20];colours=colours[4:20]
    elif shift!=0:
     # The deliberate wrong-position control moves the unshifted source.
     masks=([255]*max(shift,0)+masks[max(-shift,0):])[:24]
     inks=([0]*max(shift,0)+inks[max(-shift,0):])[:24]
     colours=([0]*max(shift,0)+colours[max(-shift,0):])[:24]
    for xx,(mask,ink,colour) in enumerate(zip(masks,inks,colours)):
     d=dst-y*32+xx//8
     if not 0<=d<65536:raise ValueError('Draw outside memory')
     cb=list(self.col[d]);mb=list(self.bit[d]);k=xx&7
     cb[k]=(cb[k]&mask)|colour;mb[k]=(mb[k]&mask)|ink
     self.col[d]=bytes(cb);self.bit[d]=bytes(mb)
  elif pc==0x9abc:
   self.copy(self.pair(4),self.pair(6))
  elif pc==0x9ad8:
   self.counts['commits']+=1
   mismatches=[a for a in range(0x4000,0x5800) if self.bit[a]!=mono(m[a])]
   # HUD and untouched top rows are outside this initial playfield model.
   bad=[a for a in mismatches if (((a>>8)&7)|((a>>2)&0x38)|((a>>5)&0xc0))<144]
   if bad:
    self.counts['incorrect commits']+=1
    if len(self.bad)<12:self.bad.append({'frame':self.frame,'count':len(bad),'first':[hex(a) for a in bad[:12]]})


def verify(patch,rzx_path,stop=None,collect=0,progress=None):
    if not patch.colour_source:return verify_default(patch,rzx_path,stop,collect,progress)
    from types import SimpleNamespace
    from . import rzx
    p=patch
    ss=prepared(p.source);m=bytes(16384)+ss.banks[5]+ss.banks[2]+ss.banks[0];oracle=ColourOracle(p);oracle.on_sim(SimpleNamespace(memory=list(m),registers=[0]*29));oracle.col[0x5b00]=mono(m[0x5b00])
    dirty=set();vd=set()
    class Watch(list):
     def __setitem__(self,a,v):
      super().__setitem__(a,v);dirty.add(a)
    oracle.col=Watch(oracle.col)
    page=bytearray(p.page);colours={n:bytearray(v)for n,v in p.colours.items()};speed=0;c=Counter();examples=[];skip=Counter();states=[]
    bulk={pc for pc,(old,_,_)in COLOUR_SITES.items()if old[:2]in (b'\xed\xb0',b'\xed\xb8')}
    pending=None
    ends={t for _,_,target in p.site_map.values() for t in (target if isinstance(target,tuple)else (target,)) if t is not None}
    interiors={a+k for a,(old,_,_)in p.site_map.items()for k in range(1,len(old))}
    def failure(kind,data):
     c[kind+'!']+=1
     if len(examples)<10:examples.append((kind,data))
     if sum(v for k,v in c.items()if k.endswith('!'))>20:raise RuntimeError(examples)
    def visit(pc,sim):
     nonlocal page,speed,colours,pending
     if pc in ends:pending=None
     if pc not in p.site_map:
      if pc in interiors and (pending is None or not pending[0]<pc<pending[1]):failure('interior',hex(pc))
      return
     pending=(pc,pc+len(p.site_map[pc][0]))
     if skip[pc]:skip[pc]-=1;return
     mem=bytes(sim.memory);r=list(sim.registers)
     if collect and sum(s[0]==pc for s in states)<collect:states.append((pc,r,mem))
     for a,(old,_,_) in p.site_map.items():
      if mem[a:a+len(old)]!=old:failure('original bytes changed',hex(a))
     dirty.clear();vd.clear();oracle.r=r.copy();oracle.m=sim.memory
     if pc in bulk:
      count=(r[2]*256+r[3])or 65536;direction=-1 if mem[pc+1]==0xb8 else 1
      src=r[6]*256+r[7];dst=r[4]*256+r[5];skip[pc]=count-1
      for i in range(count):
       if dst>=0x4000 and pc!=0xb3a7:
        if pc==0x97dd:
         oracle.fill(dst,mem[src])
         value=mem[src]
         if value&7==(value>>3)&7:
          cell=dst-0x5800
          for yy in range(8):
           y=cell//32*8+yy;a=0x4000+(y&7)*256+(y&0x38)*4+(y&0xc0)*32+(cell&31)
           oracle.col[a]=bytes([227])*8
        else:oracle.copy(dst,src)
       src=(src+direction)&65535;dst=(dst+direction)&65535
     elif pc in(0x96b8,0x972d):
      for y in range(8):oracle.copy(r[8]*256+r[9]+y*32,r[6]*256+r[7]+y)
     elif pc==0x978d:
      count=r[2]or 256;skip[pc]=count-1
      for y in range(count):
       for a,bit in(((r[6]*256+r[7]+y*(r[4]*256+r[5]+1))&65535,0),((r[6]*256+r[7]+y*(r[4]*256+r[5]+1)+r[4]*256+r[5])&65535,7)):
        v=list(oracle.col[a]);v[bit]=255;oracle.col[a]=v
     elif pc==0x983d:
      dst=r[6]*256+r[7]
      for y in range(24):
       for x in range(3):oracle.copy(dst-y*32+x,(dst+0xf005-y*32+x)&65535)
     elif pc==0x9a9b:
      table=0x9bfc
      while mem[table]:
       count=mem[table];src=int.from_bytes(mem[table+1:table+3],'little');dst=int.from_bytes(mem[table+3:table+5],'little');flags=int.from_bytes(mem[table+5:table+7],'little')
       for col in range(count):
        attr=mem[0x5800+((dst>>8)&0x18)*32+(dst&255)]
        if mem[flags] and attr&7!=(attr>>3)&7:
         for y in range(8):oracle.copy(dst-y*256,(src&0xff00)|((src-y*32)&255))
        src=(src&0xff00)|((src-1)&255);dst=(dst&0xff00)|((dst-1)&255);flags=(flags&0xff00)|((flags-1)&255)
       table+=7
     elif pc in (0x99a0,0xa5cd):
      count=(r[2]or 256)if pc==0x99a0 else 1
      if pc==0x99a0:skip[pc]=count-1
      for row in range(count):
       for i in range(3):oracle.fill((r[6]*256+r[7]+row*(r[4]*256+r[5]+2)+i)&65535,r[0])
     elif pc in (0x979f,0xa3af):oracle.fill(r[6]*256+r[7],0 if pc==0x979f else 82)
     elif pc==0xb8b6:oracle.fill(r[4]*256+r[5],r[0])
     elif pc not in SITES:oracle.before(pc)
     bad,view,model=compare_hook(mem,r,p,page,speed,colours)
     if bad:failure('state',{'pc':hex(pc),'bad':bad[:5]})
     closes=pc in(0x9ad8,0x9765,0x981f) or (pc in (0x9827,0x9856) and r[1]&64)
     want=3 if pc in(0x985a,0x9822,0x95ef,0x976d) else 0 if closes else speed
     if model.nr[7]!=want:failure('clock',[hex(pc),model.nr[7],want])
     for pg,group in view.colour_writes:
      if 12<=pg<18:
       off=(pg-12)*8192+group*8;y,x=divmod(off,256)
       dirty.add(0x4000+(y&7)*256+(y&0x38)*4+(y&0xc0)*32+x//8)
      elif 50<=pg<92:dirty.add(0x5800+(pg-50)*1024+group)
      else:failure('write to immutable graphics',{'page':pg,'group':group})
     for a in dirty:
      if a<0x4000:continue
      pg,off=colour_location(a);want=bytes(227 if v==256 else v for v in oracle.col[a]);got=bytes(view.colours[pg][off:off+8])
      if got!=want:failure('colour',{'pc':hex(pc),'at':hex(a),'got':list(got),'want':list(want)})
     page,speed,colours=view.page,model.nr[7],view.colours;c['hooks']+=1;c['R comparisons']+=1;c['pc-'+hex(pc)]+=1;c['colour bytes']+=8*len(dirty);c['visible groups']+=len(vd)
     if progress and c['hooks']%1000==0:progress(c)
    c['frames'],error=rzx.trace(str(rzx_path),set(p.site_map)|interiors|ends,visit,stop)
    if error:failure('desync',error)
    return (c,examples,states) if collect else (c,examples)


def unit_colour_pixels(p):
    import random
    from types import SimpleNamespace
    from . import simpool
    from .dizzy6 import _rw_simulator
    snap=prepared(p.source);mem=bytes(16384)+snap.banks[5]+snap.banks[2]+snap.banks[0]
    view=ColourMemory(mem,p,colours={n:bytearray(v)for n,v in p.colours.items()});sim=simpool.machine(_rw_simulator(),view,[0]*29,'highway-colour-plot')
    model=HookModel(sim,3);view.model=model;model.nr[0x51]=24
    rng=random.Random(83);counts=0;times=[]
    oracle=ColourOracle(p);oracle.on_sim(SimpleNamespace(registers=[0]*29,memory=list(mem)))
    for frame in range(57):
     for variant,pc in enumerate((0x9933,0x99d1,0x9a26,0x9a70)):
      for dest in (0xf2e0,0xf2ff,0xf3ff):
       src=0xb8f0+frame*144
       for a in range(dest-23*32,dest+3):
        values=rng.randbytes(8);oracle.col[a]=values
        page,offset=colour_location(a);view.colours[page][offset:offset+8]=values
       oracle.r[2:6]=[dest>>8,dest&255,src>>8,src&255];oracle.before(pc)
       old=bytes(view.ram);start=model.now()
       hooklib.call(sim,p.syms['colour_plot'],{0:variant,2:dest>>8,3:dest&255,4:src>>8,5:src&255,12:0x3ef0})
       times.append(model.now()-start)
       for a in range(dest-23*32,dest+3):
        page,offset=colour_location(a)
        assert view.colours[page][offset:offset+8]==oracle.col[a],(frame,variant,hex(a),list(view.colours[page][offset:offset+8]),list(oracle.col[a]))
       assert bytes(view.ram)==old
       assert [model.nr[n]for n in (0x55,0x56,0x57)]==[5,0,1]
       counts+=1
    controls=[]
    for kind in ('wrong cached pixel','wrong position'):
     oracle=ColourOracle(p);oracle.on_sim(SimpleNamespace(registers=[0]*29,memory=list(mem)))
     dest=0xf3ff;src=0xb8f0
     for a in range(0xd900,0xfd00):
      oracle.col[a]=bytes(8);page,off=colour_location(a);view.colours[page][off:off+8]=bytes(8)
     oracle.r[2:6]=[dest>>8,dest&255,src>>8,src&255];oracle.before(0x9a70)
     cache_offset=3*720+6;cp=CACHE_PAGES[cache_offset//8192];co=cache_offset%8192
     if kind=='wrong cached pixel':view.colours[cp][co]^=128
     target=dest+(kind=='wrong position')
     hooklib.call(sim,p.syms['colour_plot'],{0:3,2:target>>8,3:target&255,4:src>>8,5:src&255,12:0x3ef0})
     bad=[]
     for a in range(dest-23*32,dest+4):
      page,off=colour_location(a)
      if view.colours[page][off:off+8]!=oracle.col[a]:bad.append(a)
     if kind=='wrong cached pixel':view.colours[cp][co]^=128
     controls.append(dict(name=kind,caught=bool(bad),different_bytes=len(bad)))
     assert bad,kind
    return Counter({'figure pixel cases':counts, **{'negative '+c['name']+(' caught'if c['caught']else'!'):1 for c in controls}})


def unit_colour_copy(p,captured):
    sites={0x9615,0x9622,0x9778,0x9783,0x97b6,0x97e8,0x97fb,0xa3de,0xa5f0,0xa603,0xa9eb,0xaa4c,0xaa79,0x97a4};states={}
    states={pc:(memory,regs)for pc,regs,memory in captured if pc in sites}
    # The demo never reaches the final ship. Exercise its copy instructions with
    # original game code and explicit in-range operands; this is unit coverage.
    for pc in sites-states.keys():
     z=prepared(p.source);mem=bytearray(bytes(16384)+z.banks[5]+z.banks[2]+z.banks[0]);r=list(captured[0][1])
     r[24]=pc;r[2:8]=[0,32,0xec,0x1f,0xeb,0x1f];r[12]=0xff00
     mem[0xff00:0xff02]=(0xfff0).to_bytes(2,'little');states[pc]=(bytes(mem),r)
    cases=[]
    for pc,(mem,r) in sorted(states.items()):
     for speed in (0,1,2,3):
      rr=r.copy();rr[15]=(0,127,128,255)[speed];rr[26]=speed&1
      colours={n:bytearray(v)for n,v in p.colours.items()};expected={n:bytearray(v)for n,v in colours.items()}
      def publish(a):
       y=((a>>8)&7)|((a>>2)&0x38)|((a>>5)&0xc0)
       attr=0x5800+(y//8)*32+(a&31);ap,ao=colour_location(attr)
       value=sum(((v>>7)&1)<<(7-i)for i,v in enumerate(expected[ap][ao:ao+8]))
       bp,bo=colour_location(a)
       expected[bp-32][bo:bo+8]=(expected[bp][bo:bo+8] if value&7!=(value>>3)&7 else bytes([227])*8)
      src=(r[6]<<8)|r[7];dst=(r[4]<<8)|r[5];count=(r[2]<<8)|r[3]
      direction=-1 if mem[pc+1]==0xb8 else 1
      for i in range(count or 65536):
       if dst>=0x4000:
        sp,so=colour_location(src);dp,do=colour_location(dst)
        expected[dp][do:do+8]=expected[sp][so:so+8]
       src=(src+direction)&65535;dst=(dst+direction)&65535
      bad,view,model=compare_hook(mem,rr,p,speed=speed,colours=colours)
      if model.nr[7]!=speed:bad.append(('clock',model.nr[7],speed))
      if any(view.colours[n]!=expected[n]for n in expected):bad.append(('colour copy differs',))
      cases.append(dict(pc=hex(pc),count=count,speed=speed,bad=bad))
    return Counter({'copy cases':len(cases),'copy!':sum(bool(c['bad'])for c in cases)})


def unit_colour_attributes(p,captured):
    sites={0x97dd,0xb3a4};states={}
    states={pc:(memory,regs)for pc,regs,memory in captured if pc in sites}
    # The demo never reaches the final ship. Exercise its copy instructions with
    # original game code and explicit in-range operands; this is unit coverage.
    for pc in sites-states.keys():
     z=prepared(p.source);mem=bytearray(bytes(16384)+z.banks[5]+z.banks[2]+z.banks[0]);r=list(captured[0][1])
     r[24]=pc;r[2:8]=[0,32,0xec,0x1f,0xeb,0x1f];r[12]=0xff00
     mem[0xff00:0xff02]=(0xfff0).to_bytes(2,'little');states[pc]=(bytes(mem),r)
    cases=[]
    for pc,(mem,r) in sorted(states.items()):
     for speed in (0,1,2,3):
      rr=r.copy();rr[15]=(0,127,128,255)[speed];rr[26]=speed&1
      colours={n:bytearray(v)for n,v in p.colours.items()};expected={n:bytearray(v)for n,v in colours.items()}
      def publish(a):
       y=((a>>8)&7)|((a>>2)&0x38)|((a>>5)&0xc0)
       attr=0x5800+(y//8)*32+(a&31);ap,ao=colour_location(attr)
       value=sum(((v>>7)&1)<<(7-i)for i,v in enumerate(expected[ap][ao:ao+8]))
       bp,bo=colour_location(a)
       expected[bp-32][bo:bo+8]=(expected[bp][bo:bo+8] if value&7!=(value>>3)&7 else bytes([227])*8)
      src=(r[6]<<8)|r[7];dst=(r[4]<<8)|r[5];count=(r[2]<<8)|r[3] if pc==0x97dd else 1
      direction=-1 if mem[pc+1]==0xb8 else 1
      for i in range(count or 65536):
       if dst>=0x4000 and pc!=0xb3a4:
        sp,so=colour_location(src);dp,do=colour_location(dst)
        expected[dp][do:do+8]=bytes(255 if mem[src]&(128>>b)else 0 for b in range(8))
        value=mem[src]
        if value&7==(value>>3)&7:
         cell=dst-0x5800
         for yy in range(8):
          y=cell//32*8+yy;a=0x4000+(y&7)*256+(y&0x38)*4+(y&0xc0)*32+(cell&31)
          pg,off=colour_location(a);expected[pg][off:off+8]=bytes([227])*8
       src=(src+direction)&65535;dst=(dst+direction)&65535
      bad,view,model=compare_hook(mem,rr,p,speed=speed,colours=colours)
      if model.nr[7]!=speed:bad.append(('clock',model.nr[7],speed))
      if any(view.colours[n]!=expected[n]for n in expected):bad.append(('colour copy differs',))
      cases.append(dict(pc=hex(pc),count=count,speed=speed,bad=bad))
    return Counter({'attribute cases':len(cases),'attribute!':sum(bool(c['bad'])for c in cases)})


def unit_tests(patch,states,neg=None):
    import copy
    counts=Counter();by_site={pc:(r,m)for pc,r,m in states}
    if not states:return Counter({'no replay states!':1})
    for pc,(r,mem) in by_site.items():
        for speed in range(4):
            for iff in ((0,1) if pc in SITES else (speed&1,)):
                for refresh in ((0,1,63,127,128,129,191,255) if pc in SITES else (0,255)):
                    rr=r.copy();rr[15]=refresh;rr[26]=iff
                    page=bytearray(patch.page)
                    for offset in (0x1e30,0x1e96,0x1ec1):page[offset]=speed
                    bad,view,model=compare_hook(mem,rr,patch,page,speed)
                    wanted=3 if pc in (0x985a,0x9822,0x95ef,0x976d) else speed
                    if model.nr[7]!=wanted:bad.append(('clock',))
                    counts['ABI cases']+=1
                    if bad:counts['ABI!']+=1
    for name,needle,replacement,site,speed in (
        ('R','3ef5','3ef6',0x985a,0),
        ('MMU','ed9151ff','ed915118',0x985a,0),
        ('speed','3a303eed9207','af0000ed9207',0x9ad8,2)):
        if site not in by_site:
            counts['missing negative state!']+=1;continue
        broken=copy.deepcopy(patch);raw=bytes.fromhex(needle);at=broken.page.index(raw,broken.syms['h_open']-0x2000)
        broken.page[at:at+len(raw)]=bytes.fromhex(replacement)
        page=bytearray(broken.page)
        for offset in (0x1e30,0x1e96,0x1ec1):page[offset]=speed
        r,mem=by_site[site];bad,view,model=compare_hook(mem,r,broken,page,speed)
        wanted=3 if site==0x985a else speed
        caught=bool(bad or model.nr[7]!=wanted)
        counts['negative '+name+(' caught'if caught else'!')]+=1
    counts.update(unit_scene_budgets(states))
    if 0x985a in by_site:
        r,mem=by_site[0x985a];counts.update(unit_trainers(mem,r))
    if patch.colour_source:
        counts.update(unit_colour_pixels(patch))
        for name,backend in (('current',(0x32,0)),('old core',(0x29,0)),('hardware IM2',(0x33,1))):
            probe=copy.copy(patch);probe.test_backend=backend
            result=unit_colour_copy(probe,states)
            counts.update({name+' '+key:value for key,value in result.items()})
        counts.update(unit_colour_attributes(patch,states))
    return counts


def auto(a,z80,name,out,say):
    """Exact local archive, approved colour planes and native editable sheet."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True);inputs=Path(z80).resolve().parent
    colour=inputs/'colour-source.256';palette=inputs/'source-palette.pal';loading=inputs/'HIGHWAY.scr'
    painting=os.environ.get('NEXCLASH_HIGHWAY_PAINTING')
    for key,value in dict(patch_by='Jon Attree',title='Highway Encounter',publisher='Vortex, 1985',
                          colours_by='MatGubbins (Spec256)',fix_label='Presentation').items():
        if not getattr(a,key,None):setattr(a,key,value)
    snap=prepared(z80);memory=bytes(16384)+snap.banks[5]+snap.banks[2]+snap.banks[0]
    pok=''
    for title,items in TRAINERS.items():
        pok+='N'+title+'\n'+''.join(('Z'if i==len(items)-1 else'M')+
            f' 8 {address} {value} {memory[address]}\n'for i,(address,value)in enumerate(items.items()))
    pok+='Y\n';trainer_path=out/(name+'_verified.pok');trainer_path.write_text(pok)
    if getattr(a,'pok',None) and Path(a.pok).read_bytes()!=pok.encode():
        raise ValueError('Use the verified Highway Encounter trainers generated by this engine')
    a.pok=str(trainer_path);ok=True;patches=[]
    say('Game      : '+name)
    for label,suffix,enabled,enhanced in (('Plain','',False,False),('Sprites','_sprites',True,False),('Enhanced','_enhanced',True,True)):
        path=out/(name+suffix+'.nex')
        options=dict(enabled=enabled,colour_source=colour if enhanced else None,palette_source=palette,
                     painting=painting if enhanced else None)
        patch=build(z80,path,**options);bad=boot_check(path,z80,patch);ok &= not bad
        say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK'if not bad else bad))
        if enabled:
            loaded=out/(name+suffix+'_loading.nex');build(z80,loaded,loading=loading,**options)
            bad=boot_check(loaded,z80,patch);ok &= not bad
            if bad:say('Loading   : '+str(bad))
            patches.append(patch)
        if enhanced and not painting:painting_sheets(patch,out)
    recordings=list(getattr(a,'rzx',None)or [])
    for patch in patches:
        states={};mode='enhanced'if patch.colour_source else'default'
        for recording in recordings:
            counts,examples,captured=verify(patch,recording,stop=getattr(a,'quick',None),collect=1,
                progress=lambda c:say('Progress  : '+mode+' '+str(c['hooks'])+' hooks'))
            for pc,r,m in captured:states.setdefault(pc,(pc,r,m))
            bad={k:v for k,v in counts.items()if k.endswith('!') and v};ok &= not bad
            say('Verify    : %s %s %s'%(Path(recording).name,mode,dict(counts)))
            (out/(name+'_'+Path(recording).stem+'_'+mode+'_verification.json')).write_text(
                json.dumps(dict(counts=counts,examples=examples),indent=2)+'\n')
        if recordings:
            units=unit_tests(patch,list(states.values()));ok &= not any(v for k,v in units.items()if k.endswith('!'))
            say('Unit      : '+mode+' '+str(dict(units)))
            (out/(name+'_'+mode+'_units.json')).write_text(json.dumps(dict(units),indent=2)+'\n')
            say('Coverage  : '+mode+' reached '+','.join(hex(pc)for pc in sorted(states)))
    if recordings:
        from . import nextboot,runchecks,rzx
        runtime=out/(name+'_runtime.z80');runtime.write_bytes(entry_snapshot(z80))
        nexes=sorted(str(p)for p in out.glob(name+'*.nex'));report={};archive=zt.Z80Snapshot(z80)
        with tempfile.TemporaryDirectory()as temp:
            for recording in recordings:
                extracted,extension=rzx.extract(recording,str(Path(temp)/'start.z80'))
                if extension!='z80':raise ValueError('Highway proof requires Z80 recording snapshots')
                first=zt.Z80Snapshot(extracted)
                prefix=first.pc==archive.pc and all(first.banks[b]==archive.banks[b]for b in (5,2,0))
                part=nextboot.rom_paths(nexes,[recording],stop=getattr(a,'quick',None),z80=str(runtime),start_pc=ENTRY if prefix else None)
                for nex,(kind,lines,faults,coverage)in part.items():
                    if nex not in report:report[nex]=(kind,[],{}, {})
                    report[nex][1].extend(lines);report[nex][2].update(faults);report[nex][3].update(coverage)
        status,why,coverage=runchecks.rom_paths(report,recordings,nexes)
        runchecks.add(runchecks.RUN,'rom_paths',status,why,coverage=coverage);ok &= status=='pass'
        for result in report.values():
            for line in result[1]:say('ROM paths : '+line)
    say('Result    : '+('PASSED'if ok else'FAILED'))
    return bool(ok)


def unit_trainers(memory,registers):
    from . import simpool
    from skoolkit.simulator import Simulator
    base=list(memory);initial=list(registers)
    variants={'time':{37268:43},'legacy_immunity':{40772:201,40905:0},'incoming':{40905:8,40918:190,40923:182},'outgoing':{40763:81,40767:195,40768:81},'objects':{40890:195}}
    combined={**variants['incoming'],**variants['outgoing']};release={'Infinite time':variants['time'],'Immunity':combined,'Objects: shots only':variants['objects']}
    def run(pc,changes,setup,exits):
     mem=base[:];r=initial[:];r[24]=pc;r[12]=0xff80;r[8:10]=[0x8a,0x10];r[4:6]=[0x8a,0];r[6:8]=[0x8b,0];mem[0xff80:0xff82]=[0x1a,0x9e]
     mem[0x8a00:0x8a20]=[0]*32;mem[0x8f15]=0
     setup(mem,r)
     for a,v in changes.items():mem[a]=v
     sim=simpool.machine(Simulator,mem,r,"highway-trainers",copy=True)
     for n in range(100000):
      if n and sim.registers[24]in exits:return list(sim.memory),list(sim.registers),n
      sim.opcodes[sim.memory[sim.registers[24]]]()
     raise AssertionError(hex(sim.registers[24]))
    rows=[]
    for counter in(2,10,3500):
     def setup(mem,r):mem[0x8f1a:0x8f1c]=[counter&255,counter>>8]
     a,_,_=run(0x918c,{},setup,{0x91c6});b,_,_=run(0x918c,variants['time'],setup,{0x91c6})
     assert a[0x8f1a]+a[0x8f1b]*256==counter-1
     assert b[0x8f1a]+b[0x8f1b]*256==3500
     rows.append(dict(case='timer',start=counter,original=counter-1,enabled=3500))
    def incoming(mem,r):
     mem[0x8a00]=1;mem[0x8a03]=10;mem[0x8a06]=0;mem[0x8a10]=2;mem[0x8a16]=1
    for name,pokes in [('off',{}),('legacy_immunity',variants['legacy_immunity']),('incoming',variants['incoming']),('combined',combined),('all',{a:v for d in release.values()for a,v in d.items()})]:
     a,r,n=run(0x9fb5,pokes,incoming,{0x9e1a,0x9e45});dead=bool(a[0x8a06]&128 or a[0x8f15]&64)
     rows.append(dict(case='object hits Vorton',variant=name,player_dead=dead,enemy_dead=a[0x8a10]==254,exit=hex(r[24])))
     assert dead==(name=='off'),rows[-1]
     assert (a[0x8a10]==254)==(name!='all'),rows[-1]
    for kind in(5,6,1):
     def outgoing(mem,r):
      r[8:10]=[0x8a,0];r[4:6]=[0x8a,0x10];mem[0x8a00]=1;mem[0x8a10]=2;mem[0x8a14]=kind
     for name,pokes in [('off',{}),('legacy_immunity',variants['legacy_immunity']),('outgoing',variants['outgoing']),('combined',combined),('all',{a:v for d in release.values()for a,v in d.items()})]:
      a,r,n=run(0x9f20,pokes,outgoing,{0x9e1a,0x9e45});dead=bool(a[0x8a08]&128 or a[0x8f15]&64)
      rows.append(dict(case='Vorton hits object',kind=kind,variant=name,player_dead=dead,exit=hex(r[24])));assert dead==(name=='off'),rows[-1]
    for kind in(1,5,6):
     def objects(mem,r):incoming(mem,r);mem[0x8a16]=kind
     a,_,_=run(0x9fb5,{},objects,{0x9e1a,0x9e45});b,_,_=run(0x9fb5,variants['objects'],objects,{0x9e1a,0x9e45})
     assert(a[0x8a10]==254)==(kind!=5);assert b[0x8a10]==2
     rows.append(dict(case='object collision immunity',kind=kind,original_dead=a[0x8a10]==254,enabled_dead=False))
    # The incompatible alternate POK addresses are plot instructions in this release.
    assert bytes(base[39225:39228])==bytes.fromhex('7e2346'),bytes(base[39225:39228]).hex()
    assert release==TRAINERS
    return Counter({'original trainer behaviour cases':len(rows)})


def unit_scene_budgets(states):
    from . import simpool
    from skoolkit.simulator import Simulator
    counts=Counter()
    for pc,registers,memory in states:
        if pc not in (0x95ef,0x976d):continue
        sim=simpool.machine(Simulator,list(memory),list(registers),'highway-scene-budget',copy=True)
        sim.registers[25]=0
        end,budget={0x95ef:(0x9765,375864),0x976d:(0x981f,247097)}[pc]
        for step in range(200000):
            at=sim.registers[24]
            if at==end:break
            op=sim.memory[at]
            assert pc<=at<end and op not in (0xd3,0xdb)
            assert not(op==0xed and sim.memory[(at+1)&65535]&0xc6==0x40)
            sim.opcodes[op]()
        assert sim.registers[24]==end and sim.registers[25]==budget
        counts['original fixed scene budgets']+=1
    return counts
