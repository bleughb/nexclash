"""Treasure Island Dizzy 128K v1.1: shared speed/pace/IFF, exact R, original display.

Opt-in through NEXCLASH_REWORK=tid128_v11. The older dedicated engines retain
identical outputs. Dean Woodyatt's patterns and virtual pixel read are reused.
Approved Enhanced source colours are imported only when explicitly selected.
"""
import collections
import copy
import hashlib
import json
import os
from pathlib import Path
from skoolkit.simulator import Simulator
from . import tid128 as old, dizzy_patch as DP, hooklib
from .verify import _M

CMP = hooklib.CMP_R
ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/tid128_v11.json'
PRINTER = (0x5B00, 0x5B40)
SITE_KIND = {61578:'plot',40087:'erase',44931:'wipe',61362:'isr',63000:'bub'}


def load_profile():
    return dict(old.PROFILE, **json.loads(PROFILE.read_text()))


def is_tid128_v11(snap):
    return os.environ.get('NEXCLASH_REWORK') == 'tid128_v11' and old.is_tid128(snap)


def plot_budgets(memory):
    """Original CALL+plot costs at every real frame and both four-pixel alignments.

    No original bytes stored: assemble budgets from the user's validated input.
    The entry/exit address and stack are checked; interrupts are not injected.
    """
    rows = []
    for frame in range(DP.NUM_FRAMES):
        for shift in (0,1):
            sim = Simulator(list(memory));r=sim.registers
            r[0]=frame;r[5]=32+shift;r[7]=120;r[12]=0x5FFE;r[24]=61578;r[26]=1
            n=0
            while not(r[24]==61581 and r[12]==0x5FFE):
                sim.opcodes[sim.memory[r[24]]]()
                n+=1
                if n>10000:raise ValueError('original player plot did not return')
            rows.append(dict(frame=frame,shift=shift,tstates=r[25],m1=r[15]&127,
                             lines16=hooklib.lines16(r[25],228)))
    return rows


class Machine(_M):
    """Legacy TID differential memory/display model plus elapsed-clock video reads.

    Instruction elapsed time is accumulated at the incoming NR7 of that instruction.
    This is a routine model, not hardware bus/interrupt timing evidence.
    """
    def __init__(self, rec, hook):
        super().__init__(rec,hook)
        self.sim.int_active=0  # routine tests inject IRQ/IFF faults explicitly
        self.elapsed=0.0
        self.iff_read_glitch=False
        self.iff_glitches=0
        me=self
        class Tr:
            selected=0
            def read_port(s,regs,port):
                if port!=0x253B:return 255
                line=int(me.elapsed/228)%311
                if s.selected==0x1E:return line>>8
                if s.selected==0x1F:return line&255
                return me.nr.get(s.selected,0)
            def write_port(s,regs,port,value,*args):
                if port==0x243B:s.selected=value
        self.sim.set_tracer(Tr())
    def load(self,mm,regs):
        super().load(mm,regs);self.elapsed=0.0;self.nr={}
    def run(self,ret_pc,ret_sp,limit=3000000):
        r,m,ops=self.R,self.mem,self.sim.opcodes;n=0
        while not(r[24]==ret_pc and r[12]==ret_sp):
            speed=self.nr.get(7,0)&3;t=r[25];pc=r[24]
            iff_read=m[pc]==0xED and m[(pc+1)&65535]==0x57
            ops[m[r[24]]]()
            if self.iff_read_glitch and not self.iff_glitches and iff_read and r[26]:
                # NMOS interrupted LD A,I reports P/V=0 although the handler
                # returns with interrupts on. Exercise the engine's retry.
                r[1]&=~4;self.iff_glitches+=1
            self.elapsed+=(r[25]-t)/((1,2,4,6.5)[speed]);n+=1
            if n>limit:raise RuntimeError(f'routine did not return: pc={r[24]:04x}, expected {ret_pc:04x}')


class TidPatch128V11(old.TidPatch128):
    name='Treasure Island Dizzy 128K v1.1: original-pace hardware sprites'
    code_base=0x2200
    cmp_regs=CMP
    printer_span=PRINTER
    @property
    def machine(self):
        if getattr(self,'enhanced',None):
            from .tid128_colour import ColourMachine
            return lambda rec,hook:ColourMachine(self,rec,hook)
        return Machine
    def sprite_expected(self,memory,regs):
        if getattr(self,'enhanced',None):
            h,pixels=self.colour_frames[regs[0]]
            return {(regs[5]*4+x,regs[7]-h+y):self.colour_index[c] for (x,y),c in pixels.items()}
        h,pixels=DP.read_frames(lambda a:memory[a])[regs[0]]
        return {(regs[5]*4+x,regs[7]-h+y):DP.COLOUR[c] for (x,y),c in pixels.items() if c!='T'}
    def apply(self,snap):
        original=bytes(16384)+bytes(snap.banks[5])+bytes(snap.banks[2])+bytes(snap.banks[0])
        self.budgets=plot_budgets(original)
        super().apply(snap)
        p=load_profile()['hooks'];sy={k:int(v,16)for k,v in p['syms'].items()}
        self.syms=sy
        self.code=bytes.fromhex(p['tramp'])
        self.sites=[]
        for a,orig,new in DP.site_patches():
            if a in SITE_KIND:
                target=sy['e_'+SITE_KIND[a]]
                opcode=0xCD if a in(61578,61362,63000)else 0xC3
                new=bytes([opcode,target&255,target>>8])+bytes(len(orig)-3)
            self.sites.append((a,orig,new))
            bank,off=(5,a-0x4000)if a<0x8000 else(2,a-0x8000)if a<0xC000 else(0,a-0xC000)
            b=bytearray(snap.banks[bank]);b[off:off+len(new)]=new;snap.banks[bank]=bytes(b)
        self.extra_events={}
        if not os.environ.get('NEXCLASH_TID128_ENHANCED'):
            at=0xF4F7;expected=bytes.fromhex('3A0BB1')
            if original[at:at+3]!=expected:raise ValueError('unexpected bubble-list entry')
            target=sy['bscope_entry'];new=bytes([0xC3,target&255,target>>8])
            self.sites.append((at,expected,new));self.extra_events[at]='bubble_scope'
            bank=bytearray(snap.banks[0]);bank[at-0xC000:at-0xC000+3]=new;snap.banks[0]=bytes(bank)
        prn=bytes(0x40)+original[0x5B40:0x5C00]
        page=bytearray(self.page);page[0x200:0x200+len(self.code)]=self.code;self.page=bytes(page)
        self.extra_banks[12]=self.page+self.altrom_low[1]
        b=bytearray(snap.banks[5]);b[0x1B00:0x1C00]=prn;snap.banks[5]=bytes(b);self.printer=prn
        hp=bytearray(8192)
        hp[:len(DP.HOOKS)]=DP.HOOKS
        hp[len(DP.HOOKS):len(DP.HOOKS)+len(self.table)]=self.table
        code=bytes.fromhex(p['hooks']);hp[0x300:0x300+len(code)]=code
        budgets=b''.join(x['lines16'].to_bytes(2,'little')for x in self.budgets)
        hp[0x1000:0x1000+len(budgets)]=budgets;self.hook_page_data=bytes(hp)
        self.stub_extra=self.stub_extra[:-256]+prn
        self.enhanced=os.environ.get('NEXCLASH_TID128_ENHANCED')
        if self.enhanced:
            from . import tid128_colour
            tid128_colour.apply(self,snap,original,self.enhanced,
                os.environ.get('NEXCLASH_TID128_PALETTE',str(Path(self.enhanced).with_suffix('.pal'))))


def verify(patch,rzx_path,stop=None,collect=0):
    return old.verify(patch,rzx_path,stop,collect)


def routine_case(patch, state, clock=0, iff=None, refresh=None, frame=None, xy=None, iff_glitch=False):
    """Run real original and patched instructions to their common continuation.

    Captured game bytes are never copied over the broken hook's tables. Compare
    every live register including R, game memory, and the player-free screen.
    Plot sprites are checked separately against the original masked artwork,
    including black pixels and transparent edges at their absolute positions.
    """
    kind, pc, mem, regs, screen, applied, nr15, attrs = state
    regs=list(regs)
    if iff is not None:regs[26]=iff
    if refresh is not None:regs[15]=refresh
    if frame is not None:regs[0]=frame
    if xy is not None:regs[5],regs[7]=xy
    if kind=='isr':ret,sp=old.ISR_SOUND,regs[12]-2
    elif kind in ('plot','bub'):ret,sp=pc+3,regs[12]
    else:ret,sp=mem[regs[12]]|mem[regs[12]+1]<<8,regs[12]+2
    hook=list(patch.hook_page_data)
    a,b=patch.machine(True,hook),patch.machine(False,hook)
    b.iff_read_glitch=iff_glitch
    a.mem.lo,a.mem.hi=39774,40140
    a.load(mem,regs);a.mem.P=list(screen)
    b.load(mem,regs)
    sites=[(at,new)for at,original,new in patch.sites]
    if kind=='bubble_scope':
        old._patched(a,patch,[(at,new)for at,new in sites if at!=pc],list(patch.code),applied,screen,nr15,attrs)
    old._patched(b,patch,sites,list(patch.code),applied,screen,nr15,attrs)
    # The boot wrapper initialises this private state; the original game does
    # not own it. Each independent routine test begins with no timing debt.
    b.mem[PRINTER[0]+1:PRINTER[1]]=bytes(PRINTER[1]-PRINTER[0]-1)
    a.nr[7]=b.nr[7]=clock
    a.run(ret,sp);b.run(ret,sp)
    bad=[]
    if iff_glitch and b.iff_glitches!=1:bad.append(('IFF fault not injected',))
    rr=[i for i in CMP if a.R[i]!=b.R[i]]
    if rr:bad.append(('registers',rr))
    exclude=set(range(*PRINTER))|set(range(sp-(128 if kind=='bubble_scope'else 40),sp))
    for at,new in sites:exclude.update(range(at,at+len(new)))
    md=[at for at in range(0x5800,65536)if at not in exclude and a.mem[at]!=b.mem[at]]
    if md:bad.append(('memory',md[:8]))
    if bytes(b.mem[0x4000:0x5800])!=bytes(a.mem.P):bad.append(('screen',))
    if b.nr.get(7,0)&3!=clock:bad.append(('clock',))
    if kind=='plot':
        expected=patch.sprite_expected(mem,regs)
        actual={}
        if b.nr.get(0x15,0)&1:
            for sprite in range(4):
                attr=b.attrs[sprite]
                if not attr[3]&128:continue
                x=(attr[0]|((attr[2]&1)<<8))-32;y=attr[1]-32
                pat=((attr[3]&63)<<1)|((attr[4]>>6)&1)
                raw=patch.extra_banks[11][128*pat:128*(pat+1)]
                for yy in range(16):
                    for xx in range(16):
                        col=(raw[8*yy+xx//2]>>(4 if xx%2==0 else 0))&15
                        if col:actual[x+xx,y+yy]=col
        if actual!=expected:bad.append(('sprite positions/colours',len(set(actual.items())^set(expected.items()))))
    if kind=='wipe' or (kind=='isr' and not applied):
        if b.nr.get(0x15,0)&1:bad.append(('sprite not hidden',))
    return bad,a.elapsed,b.elapsed


def negatives(patch):
    """Mutated runtime bytes; no good table restored by the unit harness."""
    out={}
    def hook_change(name,at,data):
        p=copy.copy(patch);h=bytearray(p.hook_page_data);h[at:at+len(data)]=data
        p.hook_page_data=bytes(h);out[name]=p
    p=copy.copy(patch);p.extra_banks=dict(patch.extra_banks)
    p.extra_banks[11]=bytes((v<<4&240)|(v>>4)for v in patch.extra_banks[11])
    out['pattern nibbles swapped']=p
    at=len(DP.HOOKS);tab=patch.hook_page_data[at:at+len(patch.table)]
    hook_change('frame table rotated',at,tab[8:]+tab[:8])
    hook_change('ISR hide omitted',patch.syms['isr_hide'],bytes(4))
    hook_change('wipe hide omitted',patch.syms['wipe_hide'],bytes(4))
    # hlib_r_set begins PUSH BC / LD C,A. INC A shifts every R result by one.
    hook_change('R off by one',patch.syms['hlib_r_set']+1,b'\x3C')
    p=copy.copy(patch);h=bytearray(p.hook_page_data)
    needle=bytes.fromhex('3A055BED9207');at=h.index(needle)
    h[at:at+6]=bytes.fromhex('ED9107000000');p.hook_page_data=bytes(h)
    out['forced 3.5 MHz exit']=p
    p=copy.copy(patch);code=bytearray(p.code)
    # xret_on's EI is changed to DI: only incoming-IFF-on bubble calls catch it.
    at=p.syms['xret_on']-p.code_base+4;assert code[at]==0xFB
    code[at]=0xF3;p.code=bytes(code);out['bubble loses IFF']=p
    if getattr(patch,'extra_events',None):
        p=copy.copy(patch);code=bytearray(p.code)
        at=p.syms['bscope_entry']-p.code_base;needle=bytes.fromhex('3A305B47C6FA')
        pos=code.index(needle,at);code[pos+5]=0xFB;p.code=bytes(code)
        out['bubble-list R off by one']=p
        p=copy.copy(patch);code=bytearray(p.code);at=p.syms['bscope_return']-p.code_base
        pos=code.index(bytes.fromhex('F53A335BED9207F1'),at)
        code[pos:pos+8]=bytes.fromhex('ED91070000000000');p.code=bytes(code)
        out['bubble-list forced 3.5 MHz exit']=p
    return out


def unit_tests(patch,states,negs=None):
    by={}
    for state in states:by.setdefault(state[0],state)
    c=collections.Counter()
    for kind in SITE_KIND.values():
        if kind not in by:c['missing '+kind+' state!']+=1
    for kind,state in by.items():
        for clock in range(4):
            for iff in (0,1):
                for refresh in (0,0x7F,0x80,0xFF):
                    bad,_,_=routine_case(patch,state,clock,iff,refresh)
                    c['clock/IFF/R cases']+=1
                    for err in bad:c[kind+' '+str(err)+'!']+=1
        for clock in (() if kind=='bubble_scope' else (0,3)):
            bad,_,_=routine_case(patch,state,clock,1,0xFF,iff_glitch=True)
            c['interrupted IFF-read cases']+=1
            for err in bad:c[kind+' '+str(err)+'!']+=1
    if 'plot' in by:
        for frame in range(DP.NUM_FRAMES):
            for xy in ((2,40),(3,40),(32,120),(33,120),(56,144),(57,144)):
                bad,_,_=routine_case(patch,by['plot'],frame=frame,xy=xy)
                c['frame/position cases']+=1
                for err in bad:c['plot '+str(err)+'!']+=1
    for name,broken in (negs if negs is not None else negatives(patch)).items():
        caught=False
        for kind,state in by.items():
            # A hidden-player ISR and wipe must start with visible sprites.
            if kind in ('isr','wipe'):
                state=list(state);state[5]=0;state[6]=1
            bad,_,_=routine_case(broken,state,3,1,0xFF)
            if bad:caught=True;break
        c['negative '+name+(' caught'if caught else' not caught!')]+=1
    return c


LOADING_BANK = 44
LOADING_SCREEN_MD5 = '91b2df45ff454c507e7563f66fa6a29b'


def loading_nex(nex, screen):
    """Show the original screen, restore every displaced byte, then enter bank 10.

    The source-only loader follows dizzy1_loading.asm; bank 44 leaves all colour
    pages intact and remains within 1MB. No game screen is embedded in this engine.
    """
    from . import nxc
    if hashlib.md5(screen).hexdigest() != LOADING_SCREEN_MD5:
        raise ValueError('incorrect Treasure Island Dizzy loading screen')
    if nex[10] or nex[139] != 10 or nex[140] or nex[141] or nex[12:16] != bytes.fromhex('fedf00c0'):
        raise ValueError('loading screen expects entry bank 10, SP DFFE, PC C000')
    banks = nxc.nex_banks(nex)
    if 5 not in banks or LOADING_BANK in banks or max(banks) > 47:
        raise ValueError('loading screen needs free bank 44 and a 1MB bank layout')
    hooks = json.loads((ROOT / 'docs/profiles/tid128_loading.json').read_text())['hooks']
    head, tail = bytes.fromhex(hooks['head']), bytes.fromhex(hooks['tail'])
    banks[LOADING_BANK] = head + banks[5][:6912] + bytes(16384-len(head)-6912-len(tail)) + tail
    banks[5] = screen + banks[5][6912:]
    header = bytearray(nex[:512]);header[9] += 1;header[18+LOADING_BANK] = 1;header[139] = LOADING_BANK
    return bytes(header) + b''.join(banks[b] for b in nxc.ORDER if b in banks)


ENHANCED_ONLY_BANKS = (14, 16, 17, 18) + tuple(range(20, 44))  # tid128_colour: code, Layer 2, colour source


def published_default(nex):
    """The default build as the single .nxc 1.1 carries it: Enhanced's banks reserved, zero filled, so both colour
    sets share one header. Default's code does not use them; every other byte stays the loading build's."""
    from . import nxc
    banks = nxc.nex_banks(nex)
    if any(b in banks for b in ENHANCED_ONLY_BANKS):
        raise ValueError('published default expects the default build, without Enhanced banks')
    header = bytearray(nex[:512])
    for b in ENHANCED_ONLY_BANKS:
        banks[b] = bytes(16384)
        header[18+b] = 1
    header[9] = len(banks)
    return bytes(header) + b''.join(banks[b] for b in nxc.ORDER if b in banks)


def auto(a,z80,name,out,say):
    from . import z80tonex as zt
    for key in ('NEXCLASH_TID128_ENHANCED','NEXCLASH_TID128_PALETTE'):
        value=os.environ.get(key)
        if value and not os.path.isabs(value):os.environ[key]=str(Path(z80).resolve().parent/value)
    patch=TidPatch128V11()
    target=os.path.join(out,name+'_sprites.nex')
    conv=zt.convert(z80,target,None,True,quiet=True,patch=patch)
    bad=old.boot_check(target,z80,patch,(conv[1],conv[1]+len(conv[2])))
    say('Engine    : tid128_v11 (128K, original-pace hardware sprites'+(', Enhanced scenery)'if patch.enhanced else')'))
    say('Sprites   : %s  %s  boot %s'%(os.path.basename(target),hashlib.md5(Path(target).read_bytes()).hexdigest(),'OK'if not bad else'MISMATCH '+str(bad)))
    for screen in sorted(Path(z80).resolve().parent.glob('*.scr')):
        if hashlib.md5(screen.read_bytes()).hexdigest()==LOADING_SCREEN_MD5:
            loaded=Path(target).with_name(Path(target).stem+'_loading.nex')
            loaded.write_bytes(loading_nex(Path(target).read_bytes(),screen.read_bytes()))
            say('Loading   : %s  %s (original screen, bank 44)'%(loaded.name,hashlib.md5(loaded.read_bytes()).hexdigest()))
            if not patch.enhanced:
                published=Path(target).with_name(Path(target).stem+'_published.nex')
                published.write_bytes(loading_nex(published_default(Path(target).read_bytes()),screen.read_bytes()))
                say('Published : %s  %s (.nxc 1.1 default: the loading build with Enhanced\'s banks reserved)'%(published.name,hashlib.md5(published.read_bytes()).hexdigest()))
            break
    if getattr(a,'decisions',None):return not bad
    ok=not bad
    states=[];total=collections.Counter();colour_states={}
    for path in a.rzx or []:
        v=verify(patch,path,getattr(a,'quick',None),collect=2)
        states.extend(v['states']);total.update(v['stats'])
        say('Verify    : %s -> %s %s'%(Path(path).name,'IDENTICAL'if v['passed']else'FAILED',v['stats']))
        if v['examples']:say('Examples  : '+str(v['examples']))
        ok=ok and v['passed']
        if patch.enhanced:
            from . import tid128_colour
            cv=tid128_colour.verify(patch,path,getattr(a,'quick',None),collect=1)
            colour_states.update(cv['states'])
            say('Colours   : %s -> %s %s'%(Path(path).name,'IDENTICAL'if cv['passed']else'FAILED',cv['stats']))
            if cv['examples']:say('Examples  : '+str(cv['examples']))
            ok=ok and cv['passed']
    if a.rzx:
        expected=list(SITE_KIND.values())+list(patch.extra_events.values())
        missing=[kind for kind in expected if not total[kind+' ok']]
        say('Coverage  : '+('all %d hook kinds'%len(expected)if not missing else'missing '+', '.join(missing)))
        units=unit_tests(patch,states)
        say('Unit      : '+str(dict(units)))
        ok=ok and not missing and not any(k.endswith('!')for k in units)
        if patch.enhanced:
            cu=tid128_colour.unit_tests(patch,colour_states)
            say('Colour unit: '+str(dict(cu)))
            ok=ok and not any(k.endswith('!')for k in cu)
    say('Result    : %s (%s)'%('PASSED'if ok else'FAILED','development quick check'if getattr(a,'quick',None)else'full recording and routine checks'if a.rzx else'build and boot only'))
    return ok
