"""Bruce Lee exact-entry sprites and optional externally supplied Enhanced scenery.
The original plotter can retain its calculations while omitting its four display writes.
"""
import os,tempfile,hashlib,json
from pathlib import Path
from collections import Counter
from . import z80tonex as zt,hooklib
CMP=hooklib.CMP_R
SOURCE_MD5='6e088cc665d1cdbcd32effa061ad6e8e'
COLOUR_MD5='eba01279d6c7bf307a28b25782aa2083'
LOADING_MD5='fd3cce1f2481373716de0fed62335674'
ENTRY=0xE200
TAIL_ADDR=0x5B00
SITES={0xC7D2:(bytes.fromhex('dd211ccb'),'h_commit',0xC7D6),
       0xCAC0:(bytes.fromhex('21ddfc'),'h_gameover',0xCAC3),
       0xC1F8:(bytes.fromhex('214060'),'h_roomdraw',0xC216),
       0xC2EC:(bytes.fromhex('dd7e0a'),'h_copy',None),
       0xC2AC:(bytes.fromhex('af320bfe'),'h_full',0xC2B0),
       0xC3CB:(bytes.fromhex('dde5e1'),'h_plot',0xC3CE),
       0xC2B8:(bytes.fromhex('2aa8fe'),'h_tile',0xC2BB),
       0xD636:(bytes.fromhex('e511005d'),'h_lantern',0xD63A),
       0xC16E:(bytes.fromhex('f33a03fe'),'h_room',0xC172),
       0xC4BD:(bytes.fromhex('3e07320b60'),'h_title',0xC4C2)}
INTERIORS={a+i for a,(old,_,_) in SITES.items()for i in range(1,len(old))}
DRAW_WRITES={0xC45A:b'\x02',0xC47F:b'\x02',0xC49E:b'\x02',0xC4B6:b'\x77'}
IRQ_ENTRY=bytes.fromhex('f5c5d5')
COPY_SHA256='2bbf8d2e4e3e1d7a2aab48ef56c631e1c0d958d255a306fb3cbd5a252ef0151c'
ROOM_SHA256='377fc674da5f2b383e2c46e7690a66aa317a0975dd1c9a038a795aec8e5a66d6'
TRAINERS={
    'Infinite lives':[(0xCA53,b'\x15',b'\0')],
    'No walking sound':[(0xCF00,b'\xd3\xfe',b'\x18\0')],
    'Faster movement':[(0xCCA6,b'\3',b'\1')],
    'No enemies':[(0xC7FA,b'\xcd\x4e\xd2',b'\0'*3),(0xC801,b'\xcd\x4e\xd2',b'\0'*3)]}

def painting_frames(memory):
    """Canonical native sheet layout; frame identity is independent of PNG metadata."""
    for figure,ix in enumerate((0xCB1C,0xCBBE,0xCCA5)):
        for frame in range(22):
            pointer=ix+frame*4+0x16
            desc=int.from_bytes(memory[pointer:pointer+2],'little')
            for bank in (0,1):
                index=figure*44+frame*2+bank
                yield index,(index%12)*40,(index//12)*40,memory[desc]*8,memory[desc+1]*8

def import_painting(folder,memory,raw,scenery,palette,palette_source):
    """Read native PNGs without blending. Unedited source pixels keep their exact indices."""
    from PIL import Image
    values=list(map(int,Path(palette_source).read_text().split()))
    source_rgb=[tuple(values[i:i+3])for i in range(0,768,3)]
    data=bytearray(b''.join(raw[k]for k in sorted(raw))[:132*1024])
    tiles=bytearray(scenery);palette=list(palette)
    used=set(data)|set(tiles)|{227};changes=Counter()
    def colour(pixel,old,where):
        if pixel[3] not in (0,255):raise ValueError('Partial alpha at '+where)
        if not pixel[3]:
            if where.startswith('tile'):raise ValueError('Scenery must remain opaque: '+where)
            return 227
        if old!=227 and pixel[:3]==source_rgb[old]:return old
        rgb=tuple(round(v*7/255)for v in pixel[:3])
        if where.startswith('tile') and ((rgb[0]<<5)|(rgb[1]<<2)|(rgb[2]>>1))==1:
            raise ValueError('Scenery colour collides with Layer 2 transparency: '+where)
        for i,c in enumerate(palette):
            if i!=227 and c==rgb:
                used.add(i);return i
        free=next((i for i in range(256)if i not in used),None)
        if free is None:raise ValueError('Painting exceeds the 255 opaque colour palette')
        used.add(free);palette[free]=rgb
        return free
    for name,size in (('SPRITES',(480,440)),('SCENERY',(128,128))):
        path=Path(folder)/('BRUCE_LEE_PAINTING_'+name+'.png')
        if not path.is_file():continue
        im=Image.open(path).convert('RGBA')
        if im.size!=size:raise ValueError(path.name+' must be native size '+str(size))
        if name=='SPRITES':
            for index,x0,y0,w,h in painting_frames(memory):
                for y in range(40):
                    for x in range(40):
                        pixel=im.getpixel((x0+x,y0+y))
                        if x>=w or y>=h:
                            if pixel[3]:raise ValueError('Paint outside frame '+str(index))
                            continue
                        at=index*1024+(y//16*2+x//16)*256+(y%16)*16+x%16
                        value=colour(pixel,data[at],f'frame {index} ({x},{y})')
                        changes['sprite pixels']+=value!=data[at];data[at]=value
        else:
            for tile in range(256):
                for y in range(8):
                    for x in range(8):
                        at=tile*64+y*8+x
                        value=colour(im.getpixel((tile%16*8+x,tile//16*8+y)),tiles[at],f'tile {tile} ({x},{y})')
                        changes['scenery pixels']+=value!=tiles[at];tiles[at]=value
    pages={26+i//8192:bytes(data[i:i+8192]).ljust(8192,b'\xe3')for i in range(0,len(data),8192)}
    return pages,bytes(tiles),palette,dict(changes)

def load_profile():
    return json.loads((Path(__file__).resolve().parents[1]/'docs/profiles/bruce_lee.json').read_text())

def is_bruce_lee(snap):
    if getattr(snap,'is128',False)or getattr(snap,'machine','48K')!='48K':return False
    peek=snap.read if hasattr(snap,'read')else lambda a:snap.memory[a]
    return (bytes(peek(0xC003+i)for i in range(3))==IRQ_ENTRY and
            all(bytes(peek(a+i)for i in range(len(old)))==old for a,(old,_,_)in SITES.items()))

def entry_snapshot(source):
    """Run the original BASIC/USR prefix, stopping before the first E200 instruction."""
    from .machine import Machine, parse_inputs
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Use the supported Bruce Lee archive, MD5 '+SOURCE_MD5)
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
    raise ValueError('Original loader did not reach E200')

def prepared(source):
    fd, name = tempfile.mkstemp(suffix='.z80')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(entry_snapshot(str(source)))
        return zt.Z80Snapshot(name)
    finally:
        os.unlink(name)

def assets(source,memory,enhanced):
    data=Path(source).read_bytes()if enhanced else None
    if data is not None and hashlib.md5(data).hexdigest()!=COLOUR_MD5:raise ValueError('Unsupported colour master')
    def row(a):
        if data is None:return bytes(255 if memory[a]&(128>>b)else 0 for b in range(8))
        off=(5,2,0)[(a>>14)-1]*16384*9+(a&16383)*9
        if data[off+8]!=memory[a]:raise ValueError('Graphic source differs at '+hex(a))
        return bytes(sum(((data[off+k]>>(7-b))&1)<<k for k in range(8))for b in range(8))
    result=bytearray()
    for ix in (0xCB1C,0xCBBE,0xCCA5):
        for frame in range(1,23):
            p=ix+(frame-1)*4+0x16;desc=int.from_bytes(memory[p:p+2],'little');w,h=memory[desc:desc+2]
            if not(1<=w<=4 and 1<=h<=4):raise ValueError('Unexpected image size')
            for bank in (0,1):
                pixels=bytearray([227]*1024)
                for y in range(h*8):
                    for x in range(w):
                        tile=memory[desc+2+(y//8)*w+x];a=0xA000+bank*0x800+tile*8+(y&7)
                        colours=row(a);mask=memory[a+0x1000]
                        for bit,v in enumerate(colours):
                            if mask&(128>>bit):
                                if v:raise ValueError('Mask/colour overlap')
                            else:pixels[y*32+x*8+bit]=v
                for sy,sx in ((0,0),(0,16),(16,0),(16,16)):
                    for y in range(16):result+=pixels[(sy+y)*32+sx:(sy+y)*32+sx+16]
    return {26+i//8192:bytes(result[i:i+8192]).ljust(8192,b'\xe3')for i in range(0,len(result),8192)}

def packed_assets(raw):
    """Keep 116 common parts resident; each of 12 active parts owns a spare slot."""
    data=b''.join(raw[k] for k in sorted(raw))[:132*1024]
    tiles=[data[i:i+256] for i in range(0,len(data),256)]
    sets=sorted({frozenset(v)-{227} for v in tiles},key=lambda v:(-len(v),sorted(v)))
    palettes=[]
    for colours in sets:
        if len(colours)>15:raise ValueError('Part needs more than 15 opaque colours')
        for pal in palettes:
            if len(pal|colours)<=15:pal.update(colours);break
        else:palettes.append(set(colours))
    palettes=[sorted(v) for v in palettes]
    if len(palettes)>16:raise ValueError('Too many sprite palettes')
    entries=[]
    for pixels in tiles:
        pi=next(i for i,p in enumerate(palettes) if set(pixels)-{227}<=set(p))
        mp={c:i+1 for i,c in enumerate(palettes[pi])};mp[227]=0
        choices=[]
        for flip in (0,4,8,12):
            q=bytes(mp[pixels[(15-y if flip&4 else y)*16+(15-x if flip&8 else x)]]
                    for y in range(16) for x in range(16))
            choices.append((bytes(q[i]*16+q[i+1] for i in range(0,256,2)),flip))
        pattern,flip=min(choices);entries.append((pattern,(pi<<4)|flip))
    frequencies=Counter(p for p,f in entries)
    patterns=sorted(frequencies,key=lambda p:(-frequencies[p],p))
    if len(patterns)>256:raise ValueError('Pattern index exceeds one byte')
    lookup={p:i for i,p in enumerate(patterns)};table=bytearray()
    for i,(p,flags) in enumerate(entries):
        index=lookup[p];slot=index if index<116 else 116+(i//176)*4+i%4
        table+=bytes((index,flags,0xC0|(slot>>1),0x80|((slot&1)<<6)))
    packed=b''.join(patterns)
    pages={26+i//8192:packed[i:i+8192].ljust(8192,b'\0') for i in range(0,max(16384,len(packed)),8192)}
    return pages,bytes(table),palettes,len(patterns)

def scenery_assets(source,memory):
    """All20 room descriptors select the same original256-tile graphics table."""
    data=Path(source).read_bytes();pixels=bytearray()
    if hashlib.md5(data).hexdigest()!=COLOUR_MD5:raise ValueError('Unsupported colour master')
    for a in range(0x9800,0xA000):
        off=2*16384*9+(a&16383)*9
        if data[off+8]!=memory[a]:raise ValueError('Scenery bitmap mismatch '+hex(a))
        pixels.extend(sum(((data[off+k]>>(7-b))&1)<<k for k in range(8))for b in range(8))
    return bytes(pixels)

class Patch:
    name='Bruce Lee figure sprites and optional Enhanced scenery'
    uses_printer_buffer=False
    tail_addr=TAIL_ADDR
    max_tail=128
    hook_page_data=b''
    setup_call=0xD000
    altrom_whole=True
    def __init__(self,source,enhanced=False,colour_source=None,palette_source=None,resume=False,enabled=True,remove_figures=False,background=False,painting=None,trainers=()):
        self.source=str(source);self.enhanced=enhanced;self.site_map=SITES;self.resume=resume;self.background=background and enhanced
        h=load_profile()['hooks'];self.syms={k:int(v,16)for k,v in h['syms'].items()}
        self.code=bytes.fromhex(h['rom']);self.stub_extra=bytes.fromhex(h['setup'])
        if enhanced:
            if not colour_source or not palette_source:raise ValueError('Enhanced needs owner colour files')
            values=list(map(int,Path(palette_source).read_text().split()))
            if len(values)!=768:raise ValueError('Palette length')
            pal=[tuple(round(v*7/255)for v in values[i:i+3])for i in range(0,768,3)]
        else:pal=[(0,0,0)]*256;pal[255]=(7,7,7)
        self.base_palette=pal;self.colour_source=colour_source;self.palette_source=palette_source
        self.painting=painting;self.trainers=tuple(trainers);self.paint_changes={}
        unknown=set(self.trainers)-TRAINERS.keys()
        if unknown:raise ValueError('Unknown trainers: '+str(unknown))
        if painting and not enhanced:raise ValueError('Painting is only available in Enhanced')
        self.slot1=(24,self.syms['regblock']);self.altrom=self.altrom0=(0x2800,0x3D00)
        self.page=bytearray(zt.rom48()[0x2000:0x4000]);self.page[0x800:0x800+len(self.code)]=self.code
        background_code=bytes.fromhex(h.get('background',''))
        background_offset=self.syms['background']-0x2000
        self.page[background_offset:background_offset+len(background_code)]=background_code
        self.page[0x3FF:0x401]=zt.w16(self.syms['h_irq'])
        pace_code=bytes.fromhex(h['pace']);pace_offset=self.syms['pace_start']-0x2000
        self.page[pace_offset:pace_offset+len(pace_code)]=pace_code
        self.page[0x1E00:0x1F00]=bytes(256);self.page[0x1E40:0x1E4C]=b'\xff'*12
        self.page[0x1E50]=int(self.background)
        self.sites=[(a,old,b'\xc3'+zt.w16(self.syms[name])+bytes(len(old)-3))for a,(old,name,_)in SITES.items()]if enabled else []
        if enabled and remove_figures:self.sites.extend((a,old,b'\0')for a,old in DRAW_WRITES.items())
        self.extra_banks={}
    def apply(self,snap):
        if not is_bruce_lee(snap):raise ValueError('Unsupported Bruce Lee snapshot')
        if self.resume:entry_snapshot(self.source)
        else:snap.__dict__.update(prepared(self.source).__dict__)
        self.page[0x1C00:0x1E00]=snap.banks[5][0x1B00:0x1D00]
        for name,value,width in (('boot_r',((snap.r-5)&127)|(snap.r&128),1),('boot_sp',snap.sp,2),('boot_jump',snap.pc,2)):
            o=self.syms[name]-0x2000+1;self.page[o:o+width]=value.to_bytes(width,'little')
        ram=bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        original_copy=ram[0x82EC:0x8366]
        if hashlib.sha256(original_copy).hexdigest()!=COPY_SHA256:
            raise ValueError('Original display copier differs')
        self.page[0x300:0x300+len(original_copy)]=original_copy
        original_room=ram[0x81F8:0x8216]
        if hashlib.sha256(original_room).hexdigest()!=ROOM_SHA256:
            raise ValueError('Original room composer differs')
        self.page[0x380:0x380+len(original_room)+1]=original_room+b'\xc9'
        self.assets=assets(self.colour_source,bytes(16384)+ram,self.enhanced)
        self.scenery=scenery_assets(self.colour_source,bytes(16384)+ram)if self.background else bytes(16384)
        if self.painting:
            if not self.background:raise ValueError('Painting import requires the complete Enhanced set')
            self.assets,self.scenery,self.base_palette,self.paint_changes=import_painting(
                self.painting,bytes(16384)+ram,self.assets,self.scenery,self.base_palette,self.palette_source)
        self.pattern_pages,table,palettes,self.pattern_count=packed_assets(self.assets)
        self.palette_lookup=[227]*256
        if 0x3000+len(table)>self.syms['pace_start']:
            raise ValueError('Figure table overlaps pace code')
        self.page[0x1000:0x1000+len(table)]=table
        palette=[(0,0,0)]*256
        for pi,indices in enumerate(palettes):
            for nibble,index in enumerate(indices,1):
                palette[pi*16+nibble]=self.base_palette[index]
                self.palette_lookup[pi*16+nibble]=index
        self.stub_extra=bytes.fromhex(load_profile()['hooks']['setup'])+bytes(
            value for r,g,b in palette for value in ((r<<5)|(g<<2)|(b>>1),b&1))
        l2palette=[]
        for i,(r,g,b) in enumerate(self.base_palette):
            l2palette.extend((1,0)if i==227 else((r<<5)|(g<<2)|(b>>1),b&1))
        self.stub_extra+=bytes(l2palette)
        if self.background:
            if 227 in self.scenery:raise ValueError('Scenery uses reserved transparent index')
            if any(l2palette[i*2]==1 for i in set(self.scenery)):raise ValueError('Scenery transparency collision')
        self.pattern_pages.update({30:self.scenery[:8192],31:self.scenery[8192:]})
        self.layer_pages={i:bytes([227])*8192 for i in range(32,38)}
        if self.resume:
            mem=bytes(16384)+ram
            self.page[0x1E4C:0x1E4F]=bytes(mem[ix+2]for ix in (0xCB1C,0xCBBE,0xCCA5))
            if self.background and mem[0x6000:0x6002]==b'\0\x98':
                self.page[0x1E51]=1
                self.page[0x40:0x300]=mem[0x6040:0x6300]
                image=bytearray([227])*49152
                for cell in range(64,768):
                    tile=mem[0x6000+cell];x=(cell%32)*8;y=(cell//32)*8
                    for row in range(8):image[(y+row)*256+x:(y+row)*256+x+8]=self.scenery[tile*64+row*8:tile*64+row*8+8]
                self.layer_pages={32+i//8192:bytes(image[i:i+8192])for i in range(0,49152,8192)}
        self.pattern_pages.update(self.layer_pages)
        for page,data in self.pattern_pages.items():
            bank=self.extra_banks.setdefault(page//2,bytearray(16384));bank[(page&1)*8192:(page&1)*8192+8192]=data
        self.extra_banks[12]=bytes(self.page)+bytes(8192)
        for a,old,new in self.sites:
            if ram[a-0x4000:a-0x4000+len(old)]!=old:raise ValueError('Patch bytes differ '+hex(a))
            ram[a-0x4000:a-0x4000+len(new)]=new
        for trainer in self.trainers:
            for a,old,new in TRAINERS[trainer]:
                if ram[a-0x4000:a-0x4000+len(old)]!=old:raise ValueError('Trainer bytes differ: '+trainer)
                ram[a-0x4000:a-0x4000+len(new)]=new
        snap.banks[5],snap.banks[2],snap.banks[0]=bytes(ram[:16384]),bytes(ram[16384:32768]),bytes(ram[32768:])
        snap.pc=self.syms['boot_resume']

def build(source,destination,enhanced=False,colour_source=None,palette_source=None,checkpoint=None,enabled=True,remove_figures=False,background=False,painting=None,trainers=(),loading=None):
    patch=Patch(source,enhanced,colour_source,palette_source,checkpoint is not None,enabled,remove_figures,background,painting,trainers)
    zt.convert(str(checkpoint or source),str(destination),patch=patch,quiet=True)
    if loading is not None:
        screen=Path(loading).read_bytes()
        if hashlib.md5(screen).hexdigest()!=LOADING_MD5:raise ValueError('Use the verified original BRUCE.scr')
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
        for a,old,new in TRAINERS[trainer]:expected[a:a+len(new)]=new
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
        self.layers={k:bytearray(v)for k,v in patch.layer_pages.items()}
        self.model = None
        for a,old,new in patch.sites:
            self.ram[a:a+len(new)] = new
    def __len__(self): return 65536
    def __getitem__(self,a):
        if isinstance(a,slice):
            return bytes(self[i] for i in range(*a.indices(65536)))
        if 0x8000 <= a < 0xA000 and self.model and self.model.nr.get(0x54,4)!=4:
            return self.patch.pattern_pages[self.model.nr[0x54]][a-0x8000]
        if 0xA000 <= a < 0xC000 and self.model and self.model.nr.get(0x55,5)!=5:
            return self.layers[self.model.nr[0x55]][a-0xA000]
        if 0x2000 <= a < 0x4000:
            if self.model and self.model.nr.get(0x51,255) == 24:
                return self.page[a-0x2000]
            if self.patch.altrom[0] <= a < self.patch.altrom[1]:
                return self.patch.page[a-0x2000]
            return self.ram[a]
        return self.ram[a]
    def __setitem__(self,a,v):
        if 0xA000 <= a < 0xC000 and self.model and self.model.nr.get(0x55,5)!=5:
            self.layers[self.model.nr[0x55]][a-0xA000]=v
        elif 0x2000 <= a < 0x4000 and self.model and self.model.nr.get(0x51,255) == 24:
            self.page[a-0x2000] = v
        elif a >= 0x4000:
            self.ram[a] = v

class HookModel(hooklib.NextModel):
    def __init__(self,sim,speed):
        super().__init__(sim,speed);self.nr[0x51]=255;self.game_io=[]
    def write_port(self,regs,port,value,*args):
        if port in (0x243B,0x253B,0x303B) or port&255==0x5B:
            return super().write_port(regs,port,value,*args)
        self.game_io.append((port,value))

def compare_hook(memory,registers,patch,page=None,speed=0,colours=None):
    from skoolkit.simulator import Simulator
    from . import simpool
    from .dizzy6 import _rw_simulator
    ref = simpool.machine(Simulator,list(memory),list(registers),'bruce-original',copy=True)
    # Isolated scopes do not deliver interrupts. SkoolKit otherwise clears P/V
    # on both LD A,I reads during its raw-T /INT window without running an ISR.
    # Actual interrupts are tested separately at every eligible instruction.
    ref.int_active=0
    target = patch.site_map[registers[24]][2]
    if target is None:
        sp=registers[12];target=memory[sp]+256*memory[(sp+1)&65535]
    targets=target if isinstance(target,tuple) else (target,)
    for step in range(1000000):
        if step and ref.registers[24] in targets:break
        ref.opcodes[ref.memory[ref.registers[24]]]()
    else:raise AssertionError('Original hook scope failed to return')
    target=ref.registers[24]
    view = HookMemory(memory,patch,page)
    sim = simpool.machine(_rw_simulator(),view,list(registers),'bruce-hook')
    sim.int_active=0
    model = HookModel(sim,speed);view.model = model
    model.pattern[:]=patch.pattern_pages[26]+patch.pattern_pages[27]
    if colours is not None:
        model.pattern[:]=colours.pattern
        model.attrs=[a[:] for a in colours.attrs]
        view.layers={k:bytearray(v)for k,v in colours.layers.items()}
    model.layers=view.layers
    for step in range(5000000):
        if step and sim.registers[24] == target:break
        sim.opcodes[view[sim.registers[24]]]()
    else:raise AssertionError('Bruce hook failed to return at '+hex(sim.registers[24]))
    bad = [('register',i,ref.registers[i],sim.registers[i]) for i in CMP
           if (bool(ref.registers[i]) != bool(sim.registers[i]) if i == 26
               else ref.registers[i] != sim.registers[i])]
    expected = bytearray(ref.memory[0x4000:])
    for a,old,new in patch.sites:expected[a-0x4000:a-0x4000+len(new)] = new
    actual=view.ram[0x4000:]
    if expected!=actual:
        bad += [('RAM',i+0x4000,a,b) for i,(a,b) in enumerate(zip(expected,actual)) if a!=b]
    if model.nr[0x51] != 255:bad.append(('MMU',model.nr[0x51]))
    if model.game_io:bad.append(('game I/O',model.game_io))
    return bad,view,model

def verify(patch,rzx_path,stop=None,collect=0,progress=None):
    from . import rzx
    count=Counter();errors=[];states=[];page=bytearray(patch.page);pending=[];model=None;last=None;expected=None
    def visit(pc,sim):
        nonlocal page,model,last,expected
        if pc not in SITES:
            if pending and pc==pending[0]:pending.pop(0);count['original displaced sequel']+=1
            else:count['interior!']+=1;errors.append(('interior',hex(pc)))
            return
        pending[:]=[0xC4BF]if pc==0xC4BD else [0xC16F]if pc==0xC16E else [0xC3CD]if pc==0xC3CB else [0xD637]if pc==0xD636 else [0xC2AD]if pc==0xC2AC else []
        mem=bytes(sim.memory);r=list(sim.registers)
        if collect and sum(x[0]==pc for x in states)<collect:states.append((pc,mem,r))
        bad,view,model=compare_hook(mem,r,patch,page,colours=model)
        if model.nr[7]!=0:bad.append(('clock',model.nr[7]))
        if model.nr.get(0x54,4)!=4:bad.append(('asset mapping',))
        if model.nr.get(0x55,5)!=5:bad.append(('display mapping',))
        page=view.page;count['hooks']+=1;count['R comparisons']+=1
        count['site '+hex(pc)]+=1
        if pc in (0xC7D2,0xC2AC):
            if page[0x1E68]:
                count['game-over sprite checks']+=1
                if any(a[3]&128 for a in model.attrs[:12]):bad.append(('game-over sprites remain visible',))
            if patch.background and page[0x1E51]:
                tiles=mem[0x6040:0x6300]
                if tiles!=last:
                    expected=bytearray([227])*49152
                    for i,tile in enumerate(tiles,64):
                        x=(i%32)*8;y=(i//32)*8
                        for row in range(8):expected[(y+row)*256+x:(y+row)*256+x+8]=patch.scenery[tile*64+row*8:tile*64+row*8+8]
                    last=tiles;count['different tile maps']+=1
                count['background screens']+=1
                if expected!=b''.join(model.layers[k]for k in range(32,38)):bad.append(('background pixels',))
        if bad:count['state!']+=1;errors.extend((hex(pc),x)for x in bad[:6])
        if len(errors)>30:raise AssertionError(errors[:30])
        if progress and count['hooks']%500==0:progress(count)
    count['frames'],err=rzx.trace(str(rzx_path),set(SITES)|INTERIORS,visit,stop)
    if err:count['replay!']+=1;errors.append(err)
    return (count,errors,states)if collect else(count,errors)



def verify_composition(patch,recording,stop=None):
    """Replay native display writes versus their omission, then compose real sprites.

    This catches live-RAM dependencies and retained/stale figures that a descriptor
    pixel oracle cannot see. Store original states on disk rather than retaining a
    full playthrough in memory. Only proven write-before-read stack bytes are waived.
    """
    import pickle,zlib
    from . import rzx,simpool
    from .dizzy6 import _rw_simulator
    counts=Counter();errors=[];watch=set(SITES);page=None;model=None
    def overwritten_first(memory,registers,address):
        class Access(Exception):pass
        class Memory:
            def __init__(self):self.data=bytearray(memory);self.kind=None
            def __len__(self):return 65536
            def __getitem__(self,a):
                if isinstance(a,slice):return self.data[a]
                if a==address:self.kind='read';raise Access()
                return self.data[a]
            def __setitem__(self,a,v):
                if a==address:self.kind='write';raise Access()
                if a>=16384:self.data[a]=v
        memory=Memory();sim=simpool.machine(_rw_simulator(),memory,list(registers),'bruce-first-access')
        sim.int_active=0
        try:
            for _ in range(10000):
                r=sim.registers;pc=r[24];sim.opcodes[memory[pc]]()
                if r[25]>=69888:
                    r[25]-=69888
                    if r[26]:sim.accept_interrupt(r,memory,pc)
        except Access:return memory.kind=='write'
        return False
    live=[];lo=0x5B00
    for address in sorted(DRAW_WRITES):
        live.append((lo,address));lo=address+1
    live.extend(((lo,0xE000),(0xFB00,65536)))
    with tempfile.TemporaryFile()as recorded:
        def before(pc,sim):
            pickle.dump((pc,list(sim.registers),zlib.compress(bytes(sim.memory),1)),recorded)
            counts['source events']+=1
        frames,error=rzx.trace(recording,watch,before,stop)
        if error:return Counter({'composition replay!':1}),[error]
        recorded.seek(0)
        def after(pc,sim):
            nonlocal page,model
            wantpc,regs,packed=pickle.load(recorded);wanted=zlib.decompress(packed);memory=bytes(sim.memory)
            counts['composition events']+=1
            if pc!=wantpc:raise AssertionError(('composition diverged',pc,wantpc))
            if any(regs[i]!=sim.registers[i]for i in CMP):counts['composition registers!']+=1
            different=[]
            for lo,hi in live:
                if wanted[lo:hi]!=memory[lo:hi]:
                    different.extend(a for a in range(lo,hi)if wanted[a]!=memory[a])
            for address in different[:]:
                if sim.registers[12]-32<=address<sim.registers[12]and overwritten_first(memory,list(sim.registers),address):
                    different.remove(address);counts['stack bytes proven write-first']+=1
            if different:
                counts['composition RAM!']+=1
                if len(errors)<5:errors.append(('RAM',hex(pc),different[:8]))
            bad,view,model=compare_hook(memory,list(sim.registers),patch,page,colours=model);page=view.page
            if bad:
                counts['composition hook!']+=1
                if len(errors)<5:errors.append((hex(pc),bad[:5]))
            if pc not in (0xC7D2,0xC2AC):return
            bitmap=bytearray(memory[0x4000:0x5800])
            for a in model.attrs[:12]:
                if not a[3]&128:continue
                pat=(a[3]&63)*256+(128 if a[4]&64 else 0)
                for y in range(16):
                    for x in range(16):
                        yy=15-y if a[2]&4 else y;xx=15-x if a[2]&8 else x
                        byte=model.pattern[pat+yy*8+(xx>>1)];value=(byte&15)if xx&1 else byte>>4
                        if not value:continue
                        sx=a[0]+((a[2]&1)<<8)-32+x;sy=a[1]-32+y
                        if not(0<=sx<256 and 0<=sy<192):continue
                        address=((sy&0xC0)<<5)|((sy&7)<<8)|((sy&0x38)<<2)|(sx>>3);bit=128>>(sx&7)
                        if patch.palette_lookup[(a[2]&240)|value]:bitmap[address]|=bit
                        else:bitmap[address]&=~bit
            counts['composed pictures']+=1
            if bitmap!=wanted[0x4000:0x5800]:
                counts['composition pixels!']+=1
                if len(errors)<5:errors.append(('picture',hex(pc),counts['composition events']))
        frames,error=rzx.trace(recording,watch,after,stop,rom={address:b'\0'for address in DRAW_WRITES})
        counts['composition frames']=frames
        if error:counts['composition replay!']+=1;errors.append(error)
        if recorded.read(1):counts['composition events missing!']+=1
    return counts,errors

def figure_pixels(patch, model, figure):
    """Decode actual hardware attributes/patterns, independent of the source images."""
    out=bytearray([227])*49152
    for a in model.attrs[figure*4:figure*4+4]:
        if not a[3]&128:continue
        pat=(a[3]&63)*256+(128 if a[4]&64 else 0)
        for y in range(16):
            for x in range(16):
                yy=15-y if a[2]&4 else y;xx=15-x if a[2]&8 else x
                b=model.pattern[pat+yy*8+(xx>>1)];v=(b&15)if xx&1 else b>>4
                if not v:continue
                dx=a[0]+((a[2]&1)<<8)-32+x;dy=a[1]-32+y
                if 0<=dx<256 and 0<=dy<192:out[dy*256+dx]=patch.palette_lookup[(a[2]&240)|v]
    return out


def source_figure_pixels(patch, memory, figure):
    """Place the immutable, unpacked colour image at the original figure position."""
    ix=(0xCB1C,0xCBBE,0xCCA5)[figure];fr=memory[ix+2];out=bytearray([227])*49152
    if not 1<=fr<=22:return out
    index=figure*44+(fr-1)*2+bool(memory[ix+3])
    raw=patch.assets[26+index//8][(index&7)*1024:(index&7)*1024+1024]
    for part,(oy,ox)in enumerate(((0,0),(0,16),(16,0),(16,16))):
        for y in range(16):
            for x in range(16):
                dx=memory[ix+6]*8+ox+x;dy=memory[ix+7]*8+memory[ix+4]+oy+y;v=raw[part*256+y*16+x]
                if v!=227 and 0<=dx<256 and 0<=dy<192:out[dy*256+dx]=v
    return out


def unit_tests(patch, states, neg=None):
    """All frames, clipping, cache reuse, lifecycle, four clocks and broken builds."""
    import copy
    counts=Counter();by_site={pc:(memory,regs)for pc,memory,regs in states}
    if 0xC7D2 not in by_site:return Counter({'no commit state!':1})
    for pc,(memory,regs)in by_site.items():
        for speed in range(4):
            for iff in (0,1):
                for refresh in (0,1,63,127,128,129,191,255):
                    rr=list(regs);rr[15]=refresh;rr[26]=iff
                    bad,view,model=compare_hook(memory,rr,patch,speed=speed)
                    if model.nr[7]!=speed:bad.append(('clock',))
                    counts['ABI cases']+=1
                    if bad:counts['ABI!']+=1
        for phase in (0,69476,69880):
            rr=list(regs);rr[25]=phase;rr[26]=1
            bad,view,model=compare_hook(memory,rr,patch)
            counts['isolated INT-window cases']+=1
            if bad:counts['isolated INT window!']+=1
    memory,regs=by_site[0xC7D2];page=bytearray(patch.page);model=None
    page[0x1E4C:0x1E4F]=b'\1'*3
    for x,y,offset in ((0,0,0),(14,10,3),(31,23,7)):
        for frame in (*range(1,23),*range(22,0,-1)):
            for direction in (0,1):
                mm=bytearray(memory)
                for ix in (0xCB1C,0xCBBE,0xCCA5):
                    mm[ix+2:ix+5]=bytes((frame,direction,offset));mm[ix+6:ix+10]=bytes((x,y,x,y))
                bad,view,model=compare_hook(mm,regs,patch,page,colours=model);page=view.page
                if bad:counts['frame state!']+=1
                for figure in range(3):
                    counts['figure pixel cases']+=1
                    if figure_pixels(patch,model,figure)!=source_figure_pixels(patch,mm,figure):counts['figure pixels!']+=1
    # Replay-captured or synthetic lifecycle: marker -> last copy -> room/title reset.
    for reset in (0xC16E,0xC4BD):
        page=bytearray(patch.page);page[0x1E4C:0x1E4F]=b'\1'*3
        rr=list(regs);rr[24]=0xCAC0
        bad,view,model=compare_hook(memory,rr,patch,page)
        if bad or view.page[0x1E68]!=1:counts['game-over marker!']+=1
        rr[24]=0xC2AC;bad,view,model=compare_hook(memory,rr,patch,view.page,colours=model)
        if bad or any(a[3]&128 for a in model.attrs[:12]):counts['game-over visibility!']+=1
        rr[24]=reset;bad,view,model=compare_hook(memory,rr,patch,view.page,colours=model)
        if bad or view.page[0x1E68]:counts['reset!']+=1
        counts['lifecycle cases']+=1
    for name,needle,replacement,speed in (
        ('R','3eb7cd','3eb8cd',0),('MMU','ed9151ff','ed915118',0),
        ('speed','3a323eed9207','af0000ed9207',2)):
        broken=copy.deepcopy(patch);raw=bytes.fromhex(needle);new=bytes.fromhex(replacement)
        assert raw in broken.page
        broken.page=broken.page.replace(raw,new)
        bad,view,model=compare_hook(memory,regs,broken,speed=speed)
        caught=bool(bad or model.nr[7]!=speed)
        counts['negative '+name+(' caught'if caught else'!')]+=1
    broken=copy.deepcopy(patch);needle=bytes.fromhex('c62032393e');at=broken.page.index(needle)
    broken.page[at+1]=33;page=bytearray(broken.page);page[0x1E4C:0x1E4F]=b'\1'*3
    rr=list(regs);rr[24]=0xC2AC
    bad,view,model=compare_hook(memory,rr,broken,page)
    caught=any(figure_pixels(broken,model,i)!=source_figure_pixels(broken,memory,i)for i in range(3))
    counts['negative position'+(' caught'if caught else'!')]+=1
    broken=copy.deepcopy(patch);at=broken.page.index(bytes.fromhex('3e0132683e'),broken.syms['background']-0x2000)
    broken.page[at+1]=0;page=bytearray(broken.page);page[0x1E4C:0x1E4F]=b'\1'*3
    rr[24]=0xCAC0;bad,view,model=compare_hook(memory,rr,broken,page)
    rr[24]=0xC2AC;bad,view,model=compare_hook(memory,rr,broken,view.page,colours=model)
    caught=any(a[3]&128 for a in model.attrs[:12])
    counts['negative game-over'+(' caught'if caught else'!')]+=1
    return counts


def painting_sheets(patch, destination):
    """Native-size sheets; existing editable masters are never overwritten."""
    from PIL import Image
    folder=Path(destination);folder.mkdir(parents=True,exist_ok=True)
    snap=prepared(patch.source);memory=bytes(16384)+snap.banks[5]+snap.banks[2]+snap.banks[0]
    values=list(map(int,Path(patch.palette_source).read_text().split()))
    rgb=[tuple(values[i:i+3])for i in range(0,768,3)]
    im=Image.new('RGBA',(480,440))
    for index,x0,y0,w,h in painting_frames(memory):
        raw=patch.assets[26+index//8][(index&7)*1024:(index&7)*1024+1024]
        for y in range(h):
            for x in range(w):
                value=raw[(y//16*2+x//16)*256+(y%16)*16+x%16]
                if value!=227:im.putpixel((x0+x,y0+y),(*rgb[value],255))
    path=folder/'BRUCE_LEE_PAINTING_SPRITES.png'
    if not path.exists():im.save(path)
    im=Image.new('RGB',(128,128))
    for tile in range(256):
        for y in range(8):
            for x in range(8):im.putpixel((tile%16*8+x,tile//16*8+y),rgb[patch.scenery[tile*64+y*8+x]])
    path=folder/'BRUCE_LEE_PAINTING_SCENERY.png'
    if not path.exists():im.save(path)


def auto(a,z80,name,out,say):
    """Rebuild from the exact archive and local, separately supplied colour files."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True);inputs=Path(z80).resolve().parent
    colour=inputs/'colour-source.256';palette=inputs/'source-palette.pal';loading=inputs/'BRUCE.scr'
    painting=os.environ.get('NEXCLASH_BRUCE_PAINTING')
    if not getattr(a,'patch_by',None):a.patch_by='Jon Attree'
    if not getattr(a,'title',None):a.title='Bruce Lee'
    if not getattr(a,'publisher',None):a.publisher='U.S. Gold, 1985'
    if not getattr(a,'colours_by',None):a.colours_by='Armando Quaranta (Spec256)'
    if not getattr(a,'fix_label',None):a.fix_label='Presentation'
    pok=''
    for title,items in TRAINERS.items():
        values=[(address+i,old[i],value)for address,old,new in items for i,value in enumerate(new)]
        pok+='N'+title+'\n'+''.join(('Z'if i==len(values)-1 else'M')+f' 8 {address} {value} {old}\n'for i,(address,old,value)in enumerate(values))
    pok+='Y\n';trainer_path=out/(name+'_verified.pok');trainer_path.write_text(pok)
    if getattr(a,'pok',None) and Path(a.pok).read_bytes()!=pok.encode():
        if hashlib.md5(Path(a.pok).read_bytes()).hexdigest()!='feb611d0c2ff2bb0a292358d40acd89f':raise ValueError('Unverified Bruce Lee trainers')
    a.pok=str(trainer_path);ok=True;patches=[]
    say('Game      : '+name)
    for label,suffix,enabled,enhanced in (('Plain','',False,False),('Sprites','_sprites',True,False),('Enhanced','_enhanced',True,True)):
        path=out/(name+suffix+'.nex')
        options=dict(enhanced=enhanced,enabled=enabled,colour_source=colour,palette_source=palette,
                     remove_figures=True,background=True,painting=painting if enhanced else None)
        patch=build(z80,path,**options);bad=boot_check(path,z80,patch);ok &= not bad
        say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK'if not bad else bad))
        if enabled:
            loaded=out/(name+suffix+'_loading.nex');build(z80,loaded,loading=loading,**options)
            bad=boot_check(loaded,z80,patch);ok &= not bad
            if bad:say('Loading   : '+str(bad))
            patches.append(patch)
        if enhanced and not painting:painting_sheets(patch,out)
    for recording in list(getattr(a,'rzx',None)or []):
        for patch in patches:
            counts,examples,states=verify(patch,recording,stop=getattr(a,'quick',None),collect=1)
            units=unit_tests(patch,states)
            if not patch.enhanced:
                composition,problems=verify_composition(patch,str(recording),getattr(a,'quick',None))
                counts.update(composition);examples.extend(problems)
            bad={k:v for k,v in (counts+units).items()if k.endswith('!')};ok &= not bad
            mode='enhanced'if patch.enhanced else'default'
            say('Verify    : %s %s %s'%(Path(recording).name,mode,dict(counts)))
            say('Unit      : '+str(dict(units)))
            (out/(name+'_'+Path(recording).stem+'_'+mode+'_verification.json')).write_text(json.dumps(dict(counts=counts,examples=examples,units=units),indent=2)+'\n')
    recordings=list(getattr(a,'rzx',None)or [])
    if recordings:
        from . import nextboot,runchecks,rzx
        runtime=out/(name+'_runtime.z80');runtime.write_bytes(entry_snapshot(z80))
        nexes=sorted(str(p)for p in out.glob(name+'*.nex'))
        report={}
        archive=zt.Z80Snapshot(z80)
        with tempfile.TemporaryDirectory()as temp:
            for recording in recordings:
                extracted,extension=rzx.extract(recording,str(Path(temp)/'start.z80'))
                if extension!='z80':raise ValueError('Bruce Lee proof requires Z80 recording snapshots')
                first=zt.Z80Snapshot(extracted)
                # A decoded in-game recording receives the complete ROM audit.
                # Only the exact archive prefix is replaced by the proved E200 boot.
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
