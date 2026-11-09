"""Optional Treasure Island Dizzy colour planes, mapped onto the 128K release.

The colour file supplies artwork only. No executable bytes from its snapshot
are used. Default builds neither read the colour source nor add these hooks.
"""
import json
from pathlib import Path
from . import dizzy_patch as DP

ROOT = Path(__file__).resolve().parents[1]
SITES = [
    (0x7BED, 'row', '2B3A7178'),
    (0x7C2F, 'halves', '3A7178'),
    (0xAF99, 'wipe', '36002310FB'), (0x7711, 'text', '36002310FB'),
    (0x75CB, 'scroll', 'EDB03D'),
    (0xE860, 'box', '712313'), (0xE8FB, 'undo', '772313'),
    (0xF59B, 'bubbles', 'DD7E02'),
]


def planes(path, palette_path):
    raw = Path(path).read_bytes()
    if len(raw) < 8 * 16384 * 9:
        raise ValueError('missing eight 16K, nine-plane colour banks')
    master = bytearray(65536)
    expanded = bytearray(49152 * 8)
    for a in range(16384, 65536):
        off = (5, 2, 0)[(a >> 14) - 1] * 16384 * 9 + (a & 16383) * 9
        master[a] = raw[off + 8]
        for b in range(8):
            expanded[(a - 16384) * 8 + b] = sum(((raw[off + p] >> (7 - b)) & 1) << p for p in range(8))
    vals = list(map(int, Path(palette_path).read_text().split()))
    if len(vals) != 768:
        raise ValueError('expected 256 RGB palette entries')
    rgb = [tuple(round((255 * (v >> 2) // 63) * 7 / 255) for v in vals[i:i + 3])
           for i in range(0, 768, 3)]
    return bytes(master), bytes(expanded), rgb


def rgb9(rgb):
    r, g, b = rgb
    return bytes([(r << 5) | (g << 2) | (b >> 1), b & 1])


def sprite_patterns(original, expanded, rgb):
    frames = []
    colours = set()
    for f in range(39):
        a = DP.FRAME_BASE + original[DP.FRAME_TABLE + 2*f] + 256*original[DP.FRAME_TABLE + 2*f + 1]
        h = original[a]
        pixels = {}
        for y in range(h):
            for bx in range(3):
                ad = a + 3 + y*6 + bx*2
                for b in range(8):
                    if not original[ad - 1] & (128 >> b):
                        c = expanded[(ad - 16384)*8 + b]
                        pixels[bx*8 + b, y] = rgb[c]
                        colours.add(rgb[c])
        frames.append((h, pixels))
    colours = sorted(colours)
    if len(colours) > 15:
        raise ValueError(f'player needs {len(colours)} opaque colours; 15 available')
    pal = [(0, 0, 0)] + colours
    pal += [(0, 0, 0)] * (16 - len(pal))
    index = {c: n + 1 for n, c in enumerate(colours)}
    patterns, lookup, table = [], {}, bytearray()
    for h, px in frames:
        for qx, qy in DP.QUADS:
            pix = [index.get(px.get((qx+x, qy+y-(32-h))), 0) for y in range(16) for x in range(16)]
            if not any(pix):
                table += b'\0\0'
                continue
            key = bytes(pix)
            if key not in lookup:
                lookup[key] = len(patterns)
                patterns.append(bytes((pix[i] << 4) | pix[i+1] for i in range(0,256,2)))
            p = lookup[key]
            table += bytes([0xC0 | (p >> 1), 0x80 | ((p & 1) << 6)])
    if len(patterns) > 128:
        raise ValueError(f'player needs {len(patterns)} patterns, 128 available')
    return b''.join(patterns), bytes(table), b''.join(rgb9(c) for c in pal), frames, index


def apply(patch, snap, original, path, palette_path):
    master, expanded, rgb = planes(path, palette_path)
    used = set(range(32505, 39760)) | set(range(63020, 63036))
    for f in range(39):
        a = DP.FRAME_BASE + original[DP.FRAME_TABLE + 2*f] + 256*original[DP.FRAME_TABLE + 2*f + 1]
        used.update(range(a, a + 2 + original[a]*6))
    bad = [a for a in sorted(used) if master[a] != original[a]]
    if bad:
        raise ValueError(f'colour source differs from 128K artwork at {bad[:8]} ({len(bad)} bytes)')
    p = json.loads((ROOT/'docs/profiles/tid128_colour.json').read_text())['hooks']
    sy = {k: int(v,16) for k,v in p['syms'].items()}
    patch.colour_syms = sy
    patch.printer_span=(0x5B00,0x5B66)
    printer=bytearray(patch.printer);printer[0x50:0x66]=bytes(22);printer[0x5C]=snap.im;patch.printer=bytes(printer)
    ram5=bytearray(snap.banks[5]);ram5[0x1B00:0x1C00]=patch.printer;snap.banks[5]=bytes(ram5)
    patch.colour_source = expanded
    patch.colour_master = master
    patch.colour_rgb = rgb
    patch.colour_sites = []
    for at, name, expected in SITES:
        expected = bytes.fromhex(expected)
        if original[at:at+len(expected)] != expected:
            raise ValueError(f'unexpected colour hook bytes at {at:04X}')
        target = sy['e_'+name]
        data = bytes([0xC3,target&255,target>>8]) + bytes(len(expected)-3)
        site = (at, expected, data)
        patch.sites.append(site); patch.colour_sites.append(site)
        bank,off = (5,at-16384) if at<32768 else (2,at-32768) if at<49152 else (0,at-49152)
        b=bytearray(snap.banks[bank]);b[off:off+len(data)]=data;snap.banks[bank]=bytes(b)
    patch.scope_sites=[]
    for at,expected,name in ((0xAFDF,'CDE2F4','scope_entry'),(0xEF9B,'F3F5C5','game_irq_entry'),(0xEFB9,'E1D1C1','game_irq_exit'),(0xEF7B,'ED5E3EC3','mode2'),(0xEF97,'ED56FB','mode1'),(0xF4F7,'3A0BB1','bubble_scope')):
        expected=bytes.fromhex(expected)
        if original[at:at+len(expected)]!=expected:raise ValueError(f'scope signature {at:04x}')
        target=sy[name];data=bytes([0xC3,target&255,target>>8])+bytes(len(expected)-3)
        patch.sites.append((at,expected,data));patch.scope_sites.append((at,expected,data))
        bank,off=(5,at-16384)if at<32768 else(2,at-32768)if at<49152 else(0,at-49152)
        b=bytearray(snap.banks[bank]);b[off:off+len(data)]=data;snap.banks[bank]=bytes(b)
    pats,table,sprpal,frames,index = sprite_patterns(original,expanded,rgb)
    patch.colour_frames, patch.colour_index = frames,index
    patch.table=table;patch.num_patterns=len(pats)//128
    hp=bytearray(patch.hook_page_data);hp[len(DP.HOOKS):len(DP.HOOKS)+len(table)]=table
    hisr=patch.syms['hisr'];dispatch=hp.index(bytes([0xCA,hisr&255,hisr>>8]))
    hp[dispatch+1:dispatch+3]=bytes([0,0x11])
    clear=bytearray.fromhex(p['irqclear']);clear[-2:]=bytes([hisr&255,hisr>>8])
    hp[0x1100:0x1100+len(clear)]=clear
    patch.hook_page_data=bytes(hp)
    patch.extra_banks[11]=pats+bytes(16384-len(pats))
    page=bytearray(patch.page);rom=bytes.fromhex(p['rom']);page[0x400:0x400+len(rom)]=rom
    patch.page=bytes(page);patch.extra_banks[12]=patch.page+patch.altrom_low[1]
    # Include both modern default and colour trampolines in verifier ROM overlay.
    patch.code=patch.page[patch.code_base-0x2000:0x400+len(rom)]
    hooks=bytes.fromhex(p['hooks']);patch.extra_banks[14]=hooks+bytes(16384-len(hooks))
    for n in range(24):patch.extra_banks[20+n]=expanded[n*16384:(n+1)*16384]
    # The release snapshot already contains the HUD and rope frame. Match each
    # original screen byte before importing its colours, as in the approved
    # replay preview. Unmatched bytes retain the original black/ink rendering.
    canvas=bytearray(49152)
    for a in range(0x4000,0x5800):
        x,y=xy(a)
        cs=expanded[(a-16384)*8:(a-16384)*8+8] if master[a]==original[a] else bytes(255 if original[a]&(128>>b) else 0 for b in range(8))
        canvas[y*256+x:y*256+x+8]=cs
    for n in range(16,19):patch.extra_banks[n]=bytes(canvas[(n-16)*16384:(n-15)*16384])
    palette=b''.join(rgb9(c) for c in rgb[:255])+bytes([0xE3,0]) + sprpal
    setup=bytes.fromhex(p['setup'])+palette
    # Existing pattern upload, new palette setup, then printer-buffer restoration.
    base=bytearray(patch.stub_extra[:len(DP.SETUP)])
    base[DP.SETUP_NBLOCKS2_OFF]=max(0,len(pats)-8192+255)//256
    prefix=bytes(base)+bytes(0x200-len(base))+setup
    patch.setup_call=DP.SETUP_ORG+len(prefix)
    copy_at=patch.setup_call+18
    patch.stub_extra=prefix+bytes([0xCD,0,0xD0,0xCD,0,0xD2,0x21,copy_at&255,copy_at>>8,
                                   0x11,0,0x5B,0x01,0,1,0xED,0xB0,0xC9])+patch.printer


def xy(a):
    o=a-16384
    return (o&31)*8, ((o>>8)&7)|((o>>2)&56)|((o>>5)&192)


def expected_canvas(patch, name, memory, registers, canvas, undo):
    """Independent byte-array implementation of the original drawing operation."""
    r=registers;de=r[4]*256+r[5];hl=r[6]*256+r[7]
    result=bytearray(canvas);saved=bytearray(undo)
    def source(a):return patch.colour_source[(a-16384)*8:(a-16384)*8+8]
    def offset(a):
        x,y=xy(a);return y*256+x
    def put(a, values, mode=0, shift=0):
        off=offset(a)+shift
        for i,v in enumerate(values):
            result[off+i]=result[off+i]^v if mode==1 else result[off+i]|v if mode==2 else v
    mode=memory[0x7741]
    if name=='row':
        mirror=memory[0x7BF3]==0xCD
        for n in range(memory[0x7871]):
            src=source(de-n if mirror else de+n)
            put(hl+n,src[::-1] if mirror else src,mode)
    elif name=='halves':
        src_at=de;dst_at=hl;half=memory[0x7872];mirror=memory[0x7BF3]==0xCD
        for n in range(memory[0x7871]):
            src=source(src_at)
            if mirror:src=src[::-1]
            if half:
                put(dst_at,src[4:],mode);src_at+=-1 if mirror else 1
            else:
                put(dst_at,src[:4],mode,4);dst_at+=1
            half^=1
    elif name in ('hi','lo','mhi','mlo'):
        src=source(de)
        if name.startswith('m'):src=src[::-1]
        if name.endswith('hi'):put(hl,src[:4],mode,4)
        else:put(hl,src[4:],mode)
    elif name in ('wipe','text'):
        for n in range(r[2] or 256):put(hl+n,bytes(8))
    elif name=='scroll':
        for n in range(r[2]*256+r[3]):
            off=offset(hl+n);put(de+n,result[off:off+8])
    elif name=='box':
        src=source(r[8]*256+r[9]);off=offset(hl);ua=(de&255)*8
        saved[ua:ua+8]=bytes(a^b for a,b in zip(result[off:off+8],src))
        put(hl,src)
    elif name=='undo':put(hl,saved[(de&255)*8:(de&255)*8+8],1)
    elif name=='bubbles':
        ix=r[8]*256+r[9];x=memory[ix];y=memory[ix+1];frame=memory[ix+2]
        for n in range(4):
            ptr=29729+2*(y+n);dest=memory[ptr]+256*memory[ptr+1]+(x>>1)
            src=source(63020+4*frame+n)
            put(dest,src[4:]+src[:4] if x&1 else src,1)
    return result,saved


class ColourMemory(list):
    """Verifier MMU: game view remains separate from writable extra pages."""
    def __getitem__(self,a):
        if isinstance(a,int) and (a>>13) in self.mapping:
            page=self.mapping[a>>13]
            if page is not None:return self.pages[page][a&8191]
        return list.__getitem__(self,a)
    def __setitem__(self,a,v):
        if isinstance(a,int) and (a>>13) in self.mapping:
            page=self.mapping[a>>13]
            if page is not None:self.pages[page][a&8191]=v;return
        list.__setitem__(self,a,v)


from .tid128_v11 import Machine


class ColourMachine(Machine):
    """Default verifier's machine, with all colour MMU pages and writable low RAM.

    The original-side recording memory retains its screen reconstruction tracer.
    Physical page copies are confined to MMU changes, never to original game I/O.
    """
    def __init__(self,patch,rec,hook):
        from .dizzy6 import _rw_simulator
        from . import z80n
        super().__init__(rec,hook)
        self.patch=patch;self.sim=_rw_simulator()(self.mem,config={'int_active':0});self.R=self.sim.registers
        if rec:self.mem.R=self.R
        me=self
        def nextreg(reg,value):
            if reg==0xC8:
                me.nr[reg]=me.nr.get(reg,0)&~value;return
            me.nr[reg]=value
            if reg in (0x50,0x53,0x54):
                slot=reg-0x50;start=slot*8192;old=me.mapped[slot]
                me.pages[old]=list(me.mem[start:start+8192])
                list.__setitem__(me.mem,slice(start,start+8192),me.pages[value])
                me.mapped[slot]=value
            elif reg==0x34:me.sel=value&127
            elif 0x35<=reg<=0x39:me.attrs[me.sel][reg-0x35]=value
        z80n.install(self.sim,nextreg)
        class Trace:
            selected=0
            def read_port(s,r,port):
                if port!=0x253B:return 255
                line=int(me.elapsed/228)%311
                if s.selected==0x1E:return line>>8
                if s.selected==0x1F:return line&255
                return me.nr.get(s.selected,0)
            def write_port(s,r,port,value,*args):
                if port==0x243B:s.selected=value
        self.sim.set_tracer(Trace())
    def load(self,mm,regs):
        super().load(mm,regs)
        self.pages={}
        for bank,data in self.patch.extra_banks.items():
            for half in range(2):self.pages[2*bank+half]=list(data[half*8192:(half+1)*8192])+[0]*max(0,8192-len(data[half*8192:(half+1)*8192]))
        self.pages[21]=list(self.hook0)
        self.pages[255]=list(mm[:8192]);self.pages[11]=list(mm[0x6000:0x8000]);self.pages[4]=list(mm[0x8000:0xA000])
        self.mem[0x5B5C]=regs[27]
        self.mapped={0:255,3:11,4:4};self.nr.update({0x50:255,0x53:11,0x54:4})


def colour_case(patch,state,clock=0,iff=None,refresh=None,canvas=None,undo=None,glitch=False,irq_at=None,scope_clock=None):
    """Execute real original/patched instructions; compare R, RAM, MMU and colour pixels."""
    from skoolkit.simulator import Simulator
    from . import z80n,hooklib
    pc,mm,rr=state;r=list(rr)
    name=next((n for a,n,_ in SITES if a==pc),{0xAFDF:'scope',0xEF9B:'irq_start',0xEFB9:'irq_end',0xEF7B:'mode2',0xEF97:'mode1',0xF4F7:'bubble_scope'}.get(pc))
    canvas=bytearray((i*17+i//256)%256 for i in range(49152)) if canvas is None else bytearray(canvas)
    undo=bytearray((i*11+37)%256 for i in range(2048)) if undo is None else bytearray(undo)
    scoped_canvas,scoped_undo=bytearray(canvas),bytearray(undo)
    if iff is not None:r[26]=iff
    if refresh is not None:r[15]=refresh
    if irq_at is not None:
        mm=list(mm);r[26]=1
        # A controlled ISR whose code and data require the original slot 3/4
        # mappings. It re-enters the colour clear hook, exactly as game ISR
        # drawing can. The same handler executes in the original control.
        body=bytes.fromhex('F5C5D5E5DDE5FDE5')+bytes.fromhex('21D05A343A008032D15A')
        body+=bytes.fromhex('2100500601CD1177FDE1DDE1E1D1C1F1FBC9')
        mm[0x6000:0x6000+len(body)]=body
        mm[0x38:0x3B]=bytes.fromhex('C30060');mm[0xFEFF:0xFF01]=bytes.fromhex('0060')
        mm[0x7716]=0xC9
    orig=Simulator(list(mm),config={'int_active':0});orig.registers[:]=r
    if irq_at is not None:assert orig.accept_interrupt(orig.registers,orig.memory,0x5B80)
    sp=r[12];end=pc+len(next(o for a,o,n in patch.sites if a==pc))
    if name in ('scope','bubble_scope'):end=mm[sp]+256*mm[sp+1];sp+=2
    if name=='irq_start':sp-=4
    if name=='irq_end':sp+=6
    if name in ('bubble','bubble4'):sp+=2
    if name in ('wipe','text'):end=0xAF9E if name=='wipe' else 0x7716
    original_steps=0
    while not(orig.registers[24]==end and orig.registers[12]==sp):
        if name in ('scope','bubble_scope'):
            sub=next((n for a,n,_ in SITES if a==orig.registers[24]),None)
            if sub:scoped_canvas,scoped_undo=expected_canvas(patch,sub,orig.memory,orig.registers,scoped_canvas,scoped_undo)
        orig.opcodes[orig.memory[orig.registers[24]]]()
        original_steps+=1
        if original_steps>2000000:raise RuntimeError(f'original {name} did not return')
    m=ColourMemory(mm);m.mapping={0:None,3:None,4:None};m.pages={}
    for bank,data in patch.extra_banks.items():
        for half in range(2):m.pages[bank*2+half]=bytearray(data[half*8192:(half+1)*8192]).ljust(8192,b'\0')
    for n in range(6):m.pages[32+n][:]=canvas[n*8192:(n+1)*8192]
    m.pages[28][0x1000:0x1800]=undo
    m[0x2000:0x4000]=patch.page
    for a,old,new in patch.colour_sites:m[a:a+len(new)]=new
    if name in ('scope','bubble_scope','irq_start','irq_end','mode1','mode2'):
        for a,old,new in patch.scope_sites:m[a:a+len(new)]=new
        m[0x5B50:0x5B60]=bytes(16)
        if name=='irq_end':m[0x5B5B]=clock
        if scope_clock is not None:
            m[0x5B54]=1;m[0x5B53]=scope_clock;m[0x5B5B]=scope_clock
    from .dizzy6 import _rw_simulator
    m[0x5B5C]=r[27]
    sim=_rw_simulator()(m,config={'int_active':0});sim.registers[:]=r
    nr={7:clock,0x50:255,0x53:11,0x54:4};elapsed=0.0;speed_ticks=[0,0,0,0]
    def nextreg(reg,val):
        if reg==0xC8:
            nr[reg]=nr.get(reg,0)&~val;return
        nr[reg]=val
        for address,slot,default in ((0x50,0,255),(0x53,3,11),(0x54,4,4)):
            if reg==address:m.mapping[slot]=None if val==default else val
    z80n.install(sim,nextreg)
    class Trace:
        selected=0
        def write_port(self,regs,port,value,*args):
            if port==0x243B:self.selected=value
        def read_port(self,regs,port):return nr.get(self.selected,0) if port==0x253B else 255
    sim.set_tracer(Trace());n=0;injected=0;di_max=0.0;di_start=None;irq_count=0;irq_steps=0
    while not(sim.registers[24]==end and sim.registers[12]==sp):
        p=sim.registers[24];t=sim.registers[25];speed=nr[7]
        if irq_at=='pending' and not irq_count and p==patch.colour_syms['done']:
            nr[0xC8]=1;irq_count=1
        read=m[p]==0xED and m[(p+1)&65535]==0x57
        sim.opcodes[m[p]]()
        if glitch and not injected and read and sim.registers[26]:sim.registers[1]&=~4;injected+=1
        if isinstance(irq_at,int) and not irq_count and sim.registers[26] and sim.registers[24]<0x2000:
            irq_steps+=1
            if irq_steps>irq_at and sim.accept_interrupt(sim.registers,m,p):irq_count=1
        elapsed+=(sim.registers[25]-t)/(1,2,4,6.5)[speed]
        speed_ticks[speed]+=sim.registers[25]-t
        if not sim.registers[26] and di_start is None:di_start=elapsed
        if sim.registers[26] and di_start is not None:di_max=max(di_max,elapsed-di_start);di_start=None
        n+=1
        if n>2000000:raise RuntimeError(f'colour {name} did not return: {p:04x}')
    if di_start is not None:di_max=max(di_max,elapsed-di_start)
    bad=[('register',i,orig.registers[i],sim.registers[i]) for i in hooklib.CMP_R if orig.registers[i]!=sim.registers[i]]
    excluded=set(range(0x5B30,0x5B66))|set(range(r[12]-(256 if name in ('scope','bubble_scope') else 128 if irq_at is not None else 32),r[12]))
    for a,old,new in patch.colour_sites:excluded.update(range(a,a+len(new)))
    for a,old,new in patch.scope_sites:excluded.update(range(a,a+len(new)))
    md=[a for a in range(0x4000,65536) if a not in excluded and orig.memory[a]!=m[a]]
    if md:bad.append(('game memory',len(md),md[:4]))
    target_clock=scope_clock if scope_clock is not None and name in ('irq_start','irq_end')else clock
    if nr[7]!=target_clock or any(v is not None for v in m.mapping.values()):bad.append(('clock/MMU',nr))
    if name in ('mode1','mode2') and m[0x5B5C]!=orig.registers[27]:bad.append(('interrupt mode latch',m[0x5B5C],orig.registers[27]))
    if name=='irq_start' and m[0x5B5B]!=clock:bad.append(('IRQ speed latch',))
    actual=bytearray().join(m.pages[32+n]for n in range(6));actual_undo=m.pages[28][0x1000:0x1800]
    want,wundo=(scoped_canvas,scoped_undo) if name in ('scope','bubble_scope') else expected_canvas(patch,name,mm,r,canvas,undo)
    if irq_at is not None:
        x,y=xy(0x5000);want[y*256+x:y*256+x+8]=bytes(8)
        if not irq_count:bad.append(('IRQ not injected',))
    diff=[i for i,(a,b) in enumerate(zip(actual,want)) if a!=b]
    if diff:bad.append(('colour pixels',len(diff),diff[:8]))
    ud=[i for i,(a,b)in enumerate(zip(actual_undo,wundo))if a!=b]
    if ud:bad.append(('colour undo',len(ud),ud[:8]))
    return dict(name=name,bad=bad,original_t=orig.registers[25]-r[25],patched_t=elapsed,
                di_t=di_max,glitches=injected,speed_ticks=speed_ticks),actual,actual_undo


class Overlay(list):
    """Small per-event write set over the paused original recording's 128K view."""
    def __init__(self):
        super().__init__([0]*65536)
        self.parent=None;self.changed={};self.mapping={};self.pages={};self.rom=None;self.fixed={}
    def __getitem__(self,a):
        if isinstance(a,int):
            pg=self.mapping.get(a>>13)
            if pg is not None:return self.pages[pg][a&8191]
            if a in self.changed:return self.changed[a]
            if a in self.fixed:return self.fixed[a]
            if self.rom is not None and 0x2000<=a<0x4000:return self.rom[a-0x2000]
            return self.parent[a]
        return [self[x]for x in range(a.start or 0,a.stop or 65536,a.step or 1)]
    def __setitem__(self,a,v):
        if isinstance(a,int):
            pg=self.mapping.get(a>>13)
            if pg is not None:self.pages[pg][a&8191]=v
            else:self.changed[a]=v
        else:
            for x,b in zip(range(a.start or 0,a.stop or 65536,a.step or 1),v):self[x]=b


def verify(patch,replay,stop=None,collect=0):
    """Every colour-hook invocation, with persistent canvas and XOR undo state.

    The original RZX drives the inputs. Each colour hook executes its real Z80
    bytes against a paused original state. No full game or colour bank is copied
    over a mutant between events. MMU/clock/R/game RAM and every colour pixel
    are checked at the original continuation, not at an arbitrary frame average.
    """
    import collections
    from skoolkit.simulator import Simulator
    from .dizzy6 import _rw_simulator
    from . import rzx,z80n,hooklib
    om,pm=Overlay(),Overlay()
    a,b=Simulator(om,config={'int_active':0}),_rw_simulator()(pm,config={'int_active':0})
    pm.rom=patch.page
    for at,old,new in patch.colour_sites+patch.scope_sites:
        pm.fixed.update({at+i:v for i,v in enumerate(new)})
    for bank,data in patch.extra_banks.items():
        for half in range(2):pm.pages[bank*2+half]=bytearray(data[half*8192:(half+1)*8192]).ljust(8192,b'\0')
    nr={7:0,0x50:255,0x53:11,0x54:4}
    def nextreg(reg,val):
        if reg==0xC8:
            nr[reg]=nr.get(reg,0)&~val;return
        nr[reg]=val
        for address,slot,default in ((0x50,0,255),(0x53,3,11),(0x54,4,4)):
            if reg==address:pm.mapping[slot]=None if val==default else val
    z80n.install(b,nextreg)
    class Trace:
        selected=0
        def write_port(self,r,port,v,*args):
            if port==0x243B:self.selected=v
        def read_port(self,r,port):return nr.get(self.selected,0)if port==0x253B else 255
    b.set_tracer(Trace())
    stats=collections.Counter();examples=[];canvas=None;undo=bytearray(2048);states={}
    names={at:name for at,name,_ in SITES}
    names.update({0xAFDF:'scope',0xEF9B:'irq_start',0xEFB9:'irq_end',0xEF7B:'mode2',0xEF97:'mode1',0xF4F7:'bubble_scope'})
    lengths={at:len(old)for at,old,_ in patch.colour_sites+patch.scope_sites}
    busy=set();ends={at+length:at for at,length in lengths.items()}
    def hit(pc,sim):
        nonlocal canvas,undo
        if pc in ends:
            busy.discard(ends[pc]);return
        if pc in busy:return
        busy.add(pc)
        parent=sim.memory;r=list(sim.registers);name=names[pc]
        if collect and pc not in states:states[pc]=(pc,[parent[a]for a in range(65536)],r)
        if name in ('scope','bubble_scope'):
            state=(pc,[parent[a]for a in range(65536)],r)
            row,*_=colour_case(patch,state)
            stats[name+(' FAILED'if row['bad']else' ok')]+=1
            if row['bad']and len(examples)<6:examples.append((pc,row['bad']))
            return
        if canvas is None:
            canvas=bytearray(49152)
            for ad in range(0x4000,0x5800):
                x,y=xy(ad);v=parent[ad]
                cs=patch.colour_source[(ad-16384)*8:(ad-16384)*8+8]if patch.colour_master[ad]==v else bytes(255 if v&(128>>bit)else 0 for bit in range(8))
                canvas[y*256+x:y*256+x+8]=cs
            for n in range(6):pm.pages[32+n][:]=canvas[n*8192:(n+1)*8192]
        om.parent=pm.parent=parent;om.changed.clear();pm.changed.clear()
        a.registers[:]=r;b.registers[:]=r;pm.changed[0x5B5C]=r[27]
        pm.changed[0x5B54]=pm.changed[0x5B5B]=0
        end=pc+lengths[pc];sp=r[12]+(2 if name in ('bubble','bubble4')else 0)
        if name=='irq_start':sp-=4
        if name=='irq_end':sp+=6
        for machine in (a,b):
            rr=machine.registers;mem=machine.memory;ops=machine.opcodes;n=0
            while not(rr[24]==end and rr[12]==sp):
                ops[mem[rr[24]]]()
                n+=1
                if n>100000:raise RuntimeError(f'{name} did not return at {rr[24]:04x}')
        bad=[]
        regs=[i for i in hooklib.CMP_R if a.registers[i]!=b.registers[i]]
        if regs:bad.append(('registers',regs))
        changed=set(om.changed)|set(pm.changed)
        md=[ad for ad in changed if not 0x5B30<=ad<0x5B66 and not r[12]-32<=ad<r[12]
            and ad>=0x4000 and ad not in pm.fixed and om[ad]!=pm[ad]]
        if md:bad.append(('memory',md[:8]))
        if nr[7]!=0 or any(v is not None for v in pm.mapping.values()):bad.append(('speed/MMU',dict(nr)))
        canvas,undo=expected_canvas(patch,name,parent,r,canvas,undo)
        actual=b''.join(pm.pages[32+n]for n in range(6))
        if actual!=canvas:
            diff=[i for i,(x,y)in enumerate(zip(actual,canvas))if x!=y]
            bad.append(('colour pixels',len(diff),diff[:8]))
        if pm.pages[28][0x1000:0x1800]!=undo:bad.append(('colour undo',))
        stats[name+(' FAILED'if bad else' ok')]+=1
        if bad and len(examples)<6:examples.append((pc,bad))
        if sum(stats.values())%10000==0:print('Colour hooks',sum(stats.values()),'failures',sum(v for k,v in stats.items()if 'FAILED'in k),flush=True)
    frames,error=rzx.trace(replay,set(names)|set(ends),hit,stop=stop)
    return dict(passed=not error and not examples and bool(stats),frames=frames,desync=error,
                stats=dict(stats),examples=examples,states=states)


def unit_tests(patch,states):
    import copy,collections
    states=dict(states);stats=collections.Counter()
    # The recordings do not open/close every UI box. Exercise both exact
    # displaced segments from matching real clear/box register and memory states.
    for pc,other in ((0x7711,0xAF99),(0xE8FB,0xE860)):
        if pc not in states and other in states:
            _,m,r=states[other];r=list(r);r[24]=pc;states[pc]=(pc,m,r)
    def check(st,**kwargs):
        row,*_=colour_case(patch,st,**kwargs)
        stats['colour routine cases']+=1
        if row['bad']:stats['colour routine failures!']+=1
    for pc,st in states.items():
        if pc in (0xAFDF,0xF4F7):
            for clock in range(4):check(st,clock=clock,refresh=255)
            continue
        for clock in range(4):
            for iff in (0,1):
                for refresh in (0,127,128,255):check(st,clock=clock,iff=iff,refresh=refresh)
        for clock in (0,3):check(st,clock=clock,iff=1,refresh=255,glitch=True)
        if pc in (0xEF9B,0xEFB9):
            for clock in range(4):
                for scope_clock in range(4):check(st,clock=clock,scope_clock=scope_clock,refresh=255)
    if 0xF59B in states:
        pc,m0,r0=states[0xF59B];ix=r0[8]*256+r0[9]
        for frame in range(4):
            for x in (0,1,62,63):
                for y in (0,31,64,188):
                    m=list(m0);m[ix:ix+3]=[x,y,frame]
                    check((pc,m,list(r0)))
    if 0x7BED in states:
        pc,m0,r0=states[0x7BED]
        for mirror in (False,True):
            for mode in (0,1,2):
                for x,y in ((0,0),(16,31),(248,191)):
                    m=list(m0);r=list(r0);m[0x7BF3]=0xCD if mirror else 0;m[0x7741]=mode;m[0x7871]=1
                    addr=0x4000|((y&192)<<5)|((y&7)<<8)|((y&56)<<2)|(x>>3)
                    r[6],r[7]=addr>>8,addr&255
                    check((pc,m,r))
    if 0x7C2F in states:
        pc,m0,r0=states[0x7C2F]
        for mirror in (False,True):
            for mode in (0,1,2):
                for half in (0,1):
                    for width in (1,2,3,8):
                        m=list(m0);r=list(r0)
                        m[0x7BF3]=0xCD if mirror else 0;m[0x7741]=mode
                        m[0x7872]=half;m[0x7871]=width;r[6]=0x40;r[7]=1
                        check((pc,m,r))
    for pc in (0x7BED,0x7C2F):
        if pc not in states:continue
        _,m0,r0=states[pc]
        for src,mirror in ((0x83FF,0),(0x8400,0xCD)):
            m=list(m0);r=list(r0);m[0x7BF3]=mirror;m[0x7871]=4;m[0x7872]=0
            r[4],r[5]=src>>8,src&255;r[6],r[7]=0x40,1
            check((pc,m,r))
    if 0x7BED in states:
        pc,m,r0=states[0x7BED]
        for im in (1,2):
            for clock in range(4):
                for point in (0,30,100,'pending'):
                    if point=='pending' and im==1:continue
                    r=list(r0);r[14]=0 if im==1 else 254;r[27]=im;r[6]=0x48;r[7]=0
                    row,*_=colour_case(patch,(pc,m,r),clock=clock,refresh=255,irq_at=point)
                    stats['colour IRQ forwarding cases']+=1
                    if row['bad']:
                        stats['colour IRQ forwarding failures!']+=1
    # Independent corruptions of actual runtime bytes, never the expected source.
    mutants={}
    def mutate(name,needle,index,value):
        p=copy.copy(patch);p.extra_banks=dict(patch.extra_banks);h=bytearray(p.extra_banks[14])
        at=h.index(bytes.fromhex(needle))+index;h[at]=value;p.extra_banks[14]=bytes(h);mutants[name]=p
    mutate('colour row displaced 32 pixels vertically','CE20ED9253',1,33)
    p=copy.copy(patch);p.extra_banks=dict(patch.extra_banks);h=bytearray(p.extra_banks[14])
    h[patch.colour_syms['bulk_start.or']+1]=0xAE;p.extra_banks[14]=bytes(h)
    mutants['colour OR changed to XOR']=p
    p=copy.copy(patch);p.extra_banks=dict(patch.extra_banks);h=bytearray(p.extra_banks[14])
    h[h.index(bytes.fromhex('3AF37BFECD'))+4]=0;p.extra_banks[14]=bytes(h)
    mutants['colour mirror omitted']=p
    mutate('colour box undo omitted','DD77001A77',0,0)
    p=copy.copy(patch);p.extra_banks=dict(patch.extra_banks)
    for bank in range(20,44):p.extra_banks[bank]=bytes(v^1 for v in p.extra_banks[bank])
    mutants['source colour bits changed']=p
    candidates=list(states.values())
    candidates=[st for st in candidates if st[0]not in (0xAFDF,0xF4F7)]
    if 0x7BED in states:
        pc,m,r=states[0x7BED]
        for mode in (1,2):
            for mirror in (0,0xCD):
                mm=list(m);mm[0x7741]=mode;mm[0x7BF3]=mirror;candidates.append((pc,mm,r))
    for name,p in mutants.items():
        caught=False
        for st in candidates:
            row,*_=colour_case(p,st)
            if row['bad']:caught=True;break
        stats['negative '+name+(' caught'if caught else' not caught!')]+=1
    # Whole-room and bubble wrappers restore the incoming speed and exact R.
    for pc,label,needle,index,value in (
        (0xAFDF,'room R off by one','3A505B47C6ED',5,0xEE),
        (0xAFDF,'room forced 3.5 MHz exit','F53A535BED9207F1',None,None),
        (0xF4F7,'bubble-list R off by one','3A605B47C6FA',5,0xFB),
        (0xEF97,'wrong interrupt mode latch','3E01325C5B',1,2),
    ):
        if pc not in states:
            stats['missing negative '+label+' case!']+=1;continue
        p=copy.copy(patch);page=bytearray(p.page);at=page.index(bytes.fromhex(needle))
        if index is None:page[at:at+8]=bytes.fromhex('ED91070000000000')
        else:page[at+index]=value
        p.page=bytes(page)
        row,*_=colour_case(p,states[pc],clock=3)
        stats['negative '+label+(' caught'if row['bad']else' not caught!')]+=1
    for a,name,_ in SITES:
        if a not in states:stats['missing colour '+name+' case!']+=1
    return stats
