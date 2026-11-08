"""Bubbler (Ultimate, 1987, 48K): original drawing and sound, paced renderer.

The archive contains the game's original complementing loader. Build preparation
executes that loader to its first game instruction; no alternate release is used.
Enhanced is optional and uses the approved MatGubbins colour map. The NEX keeps
the archive's complemented payload; its unchanged decoder restores it at boot.
"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import hashlib
import json
import os
import tempfile
from . import hooklib, simpool, z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT/'docs/profiles/bubbler.json'
SOURCE_MD5 = '85d7841306333321838d372ea8797ff2'
CMP = tuple(hooklib.CMP_R)
SITES = {0xCE10: (0xAC40, 'h_open'), 0xCE19: (0xA837, 'h_close')}
INTERIORS = tuple(a+k for a in SITES for k in (1, 2))
DECISIONS = {'figures': 'original ordered mask/ink pixels', 'scenery': 'original monochrome playfield and original HUD',
             'pace': 'shared original-pace limiter; separately measured quiet, busy and death scenes', 'outline': 'none',
             'enhanced': 'optional approved MatGubbins colours; default off'}

def load_profile():
    return json.loads(PROFILE.read_text())

def _peek(snap):
    banks = getattr(getattr(snap, 'memory', None), 'banks', None) or getattr(snap, 'banks', None)
    if banks is not None:
        return lambda a: banks[{1: 5, 2: 2, 3: 0}[a >> 14]][a & 16383]
    ram = snap.ram(-1)
    return lambda a: ram[a-16384]

def is_bubbler(snap):
    if getattr(snap, 'machine', '48K') != '48K' or getattr(snap, 'is128', False):
        return False
    try:
        peek = _peek(snap)
        expected = bytes.fromhex('21005e01b4917e2f77230b78b120f7c3005e')
        return bytes(peek(0xF000+i) for i in range(len(expected))) == expected
    except (AttributeError, KeyError, TypeError, IndexError):
        return False

@lru_cache(maxsize=2)
def entry_snapshot(source):
    """Execute the archive's real startup, including inversion, to PC5E00."""
    from .machine import Machine, parse_inputs
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Use the supported Bubbler archive, MD5 '+SOURCE_MD5)
    machine = Machine(str(source))
    regs = machine.sim.registers
    last = [regs[24]]
    class Reached(Exception): pass
    class FrameEnd(Exception): pass
    def trace(fc, pc):
        if pc == 0x5E00:
            raise Reached()
        if regs[25] >= 69888:
            raise FrameEnd()
        last[0] = pc
    for frame in range(100):
        machine.held = parse_inputs('SPACE' if 5 <= frame <= 12 else '')
        try:
            machine.sim.exec_frame(65535, None, trace)
        except Reached:
            return machine.z80_bytes()
        except FrameEnd:
            pass
        regs[25] = 0
        if regs[26]:
            if machine.sim.memory[last[0]] == 0x76:
                regs[24] = (regs[24]+1) & 65535
            machine.sim.accept_interrupt(regs, machine.sim.memory, 0)
    raise ValueError('Original Bubbler loader did not reach game entry')

def prepared(source):
    fd, name = tempfile.mkstemp(suffix='.z80')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(entry_snapshot(str(source)))
        return zt.Z80Snapshot(name)
    finally:
        os.unlink(name)

class Patch:
    name = 'Bubbler: original presentation and original pace'
    uses_printer_buffer = False
    tail_addr = 0x5B00
    max_tail = 128
    hook_page_data = b''
    setup_call = 0xD000
    def __init__(self, source, enabled=True, resume=False):
        self.source = str(source)
        self.enabled = enabled
        self.resume = resume
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.code = bytes.fromhex(h['rom'])
        self.stub_extra = bytes.fromhex(h['setup'])
        self.slot1 = (24, self.syms['regblock'])
        self.altrom = self.altrom0 = (0x2800, 0x3D00)
        self.page = bytearray(zt.rom48()[0x2000:0x4000])
        self.page[0x800:0x800+len(self.code)] = self.code
        self.page[0x1E00:0x1F00] = bytes(256)
        self.sites = [(a, b'\xcd'+zt.w16(body), b'\xcd'+zt.w16(self.syms[name]))
                      for a, (body, name) in SITES.items()] if enabled else []
        self.extra_banks = {12: bytes(self.page)+bytes(8192)}
    def apply(self, snap):
        if not self.resume:
            if not is_bubbler(snap):
                raise ValueError('Not the supported Bubbler loader snapshot')
            snap.__dict__.update(prepared(self.source).__dict__)
        else:
            # Development comparisons may start at a captured original state.
            # The supported archive is still verified before using that state.
            entry_snapshot(self.source)
            peek = _peek(snap)
            for a, (body, _) in SITES.items():
                if bytes(peek(a+k) for k in range(3)) != b'\xcd'+zt.w16(body):
                    raise ValueError('Captured state has different original code')
        self.page[0x1C00:0x1D00] = snap.banks[5][0x1B00:0x1C00]
        if self.resume and 'boot_decode_done' in self.syms:
            # Paused development fixtures are already decoded. The default
            # archive path always executes its original inverter at F000.
            offset = self.syms['boot_decode_done']-3-0x2000
            self.page[offset:offset+3] = bytes(3)
        for name, value, width in [('boot_r', ((snap.r-5)&127)|(snap.r&128), 1),
                                   ('boot_sp', snap.sp, 2), ('boot_jump', snap.pc, 2)]:
            o = self.syms[name]-0x2000+1
            self.page[o:o+width] = value.to_bytes(width, 'little')
        self.extra_banks = {12: bytes(self.page)+bytes(8192)}
        if self.enabled:
            # Sets share a NEX header and bank inventory. Default never maps
            # these empty colour buffers and retains its two original hooks.
            self.extra_banks.update({b:bytes(16384)for b in (14,15,16,*range(20,38))})
        ram = bytearray(snap.banks[5]+snap.banks[2]+snap.banks[0])
        for a, old, new in self.sites:
            if ram[a-0x4000:a-0x4000+len(old)] != old:
                raise ValueError('Original bytes differ at '+hex(a))
            ram[a-0x4000:a-0x4000+len(new)] = new
        if not self.resume and 'boot_decode_done' in self.syms:
            if ram[0xB00F:0xB012] != bytes.fromhex('C3005E'):
                raise ValueError('Original decoder exit differs')
            for i in range(0x1E00,0xAFB4):
                ram[i] ^= 255
            ram[0xB010:0xB012] = zt.w16(self.syms['boot_decode_done'])
        snap.banks[5], snap.banks[2], snap.banks[0] = bytes(ram[:16384]), bytes(ram[16384:32768]), bytes(ram[32768:])
        snap.pc = self.syms['boot_resume']

def build(source, destination, enabled=True):
    patch = Patch(source, enabled)
    zt.convert(str(source), str(destination), patch=patch, quiet=True)
    return patch


class EnhancedPatch(Patch):
    """One private indexed canvas, double-buffered Layer2, original game RAM."""
    name = 'Bubbler Enhanced: approved colours and original pace'
    def __init__(self,source,colours=None,resume=False):
        from . import bubbler_art as art
        super().__init__(source,False,resume)
        profile=json.loads((ROOT/'docs/profiles/bubbler_enhanced.json').read_text())
        h=profile['hooks'];self.syms={k:int(v,16)for k,v in h['syms'].items()}
        self.code=bytes.fromhex(h['colour_hooks']);self.aux=bytes.fromhex(h['auxiliary'])
        self.page=bytearray(zt.rom48()[0x2000:0x4000])
        self.page[0x800:0x800+len(self.code)]=self.code
        self.page[0x1D00:0x2000]=bytes(768)
        self.page[self.syms['P_FRONT']&8191]=64
        self.page[self.syms['P_NEXT']&8191]=70
        self.slot1=(24,self.syms['regblock'])
        snap=prepared(self.source);peek=_peek(snap)
        raw=bytearray(65536);raw[16384:]=bytes(peek(a)for a in range(16384,65536))
        self.colours=art.load_colours() if colours is None else colours
        self.art=art.compile(raw,self.colours)
        palette=[]
        for i,rgb in enumerate(self.art['palette']):
            r,g,b=[(v*7+127)//255 for v in rgb]
            palette.extend([0xE3,0]if i==255 else[(r<<5)|(g<<2)|(b>>1),b&1])
        self.stub_extra=bytes.fromhex(h['setup'])+bytes(palette)
        self.site_rows={int(k):v for k,v in profile['sites'].items()}
        self.sites=[(a,bytes(peek(a+i)for i in range(row['size'])),
                     bytes([0xCD if row.get('kind')=='call' else 0xC3,
                            self.syms[row['name']]&255,self.syms[row['name']]>>8])+bytes(row['size']-3))
                    for a,row in self.site_rows.items()]

    def apply(self,snap):
        super().apply(snap)
        pages={24:bytes(self.page),25:self.aux.ljust(8192,b'\0'),**self.art['pages']}
        for page in range(28,34):pages[page]=bytes(8192)
        for page in range(64,76):pages[page]=bytes([255])*8192
        for page,data in pages.items():
            bank=page//2;whole=bytearray(self.extra_banks.get(bank,bytes(16384)))
            offset=(page&1)*8192;whole[offset:offset+8192]=data
            self.extra_banks[bank]=bytes(whole)


from .bubbler_art import COLOURS,load_colours
RECOLOUR={'game':'bubbler','output':'enhanced','colours':'docs/profiles/bubbler_colours.json',
          'clear':False,'note':'Original mask/ink pixel addresses; one plus the runtime colour index, zero default.'}

def nex_peek(nex):
    """Recover the original decoded graphics from our compact NEX payload."""
    from . import nxc
    banks=nxc.nex_banks(nex)
    if not {0,2,5,12,20,31,32,37,47}<=set(banks):raise ValueError('Not a Bubbler Enhanced build')
    raw=bytearray(16384)+bytearray(banks[5]+banks[2]+banks[0])
    for a in range(0x5E00,0xEFB4):raw[a]^=255
    return lambda a:raw[a]

def colour_identity(peek):
    from .bubbler_art import colour_identity as identity
    return identity(peek)

def recolour(nex_bytes,cmap):
    from . import nxc,bubbler_art as art
    banks=nxc.nex_banks(nex_bytes);peek=nex_peek(nex_bytes)
    h=json.loads((ROOT/'docs/profiles/bubbler_enhanced.json').read_text())['hooks']
    syms={k:int(v,16)for k,v in h['syms'].items()};code=bytes.fromhex(h['colour_hooks'])
    end=syms['boot_resume']-0x2800
    if banks[12][0x800:0x800+end]!=code[:end]:raise ValueError('Bubbler renderer differs; rebuild this version')
    aux=bytes.fromhex(h['auxiliary'])
    if banks[12][8192:8192+len(aux)]!=aux:raise ValueError('Bubbler compositor differs; rebuild this version')
    raw=bytes(peek(a)for a in range(65536));compiled=art.compile(raw,cmap)
    updates={}
    for page,data in compiled['pages'].items():
        bank=page//2;whole=updates.setdefault(bank,bytearray(banks[bank]));offset=(page&1)*8192
        whole[offset:offset+8192]=data
    result=bytearray(nex_bytes);offset=512+nxc.screen_size(result[10]);changed=[]
    for bank in zt.BANK_FILE_ORDER:
        if bank not in banks:continue
        if bank in updates and bytes(updates[bank])!=banks[bank]:
            result[offset:offset+16384]=updates[bank];changed.append(bank)
        offset+=16384
    assert offset==len(result)
    return bytes(result),{'banks changed':changed,'map entries used':len(cmap),'map entries ignored':0}

def sheets(source,out,name='BUBBLER',colours=None):
    from . import bubbler_art as art
    snap=prepared(str(source));peek=_peek(snap)
    raw=bytes(16384)+bytes(peek(a)for a in range(16384,65536))
    return art.sheets(raw,out,name,colours)

class HookMemory:
    """Game RAM plus the writable hook page and its hidden-ROM twin."""
    def __init__(self, memory, patch, page=None):
        self.ram = bytearray(memory)
        self.patch = patch
        self.page = bytearray(patch.page if page is None else page)
        self.model = None
        for address, old, new in patch.sites:
            self.ram[address:address+len(new)] = new

    def __len__(self):
        return 65536

    def __getitem__(self, address):
        if isinstance(address, slice):
            return bytes(self[i] for i in range(*address.indices(65536)))
        if 0x2000 <= address < 0x4000:
            if self.model and self.model.nr.get(0x51,255) == 24:
                return self.page[address-0x2000]
            if 0x2800 <= address < 0x3D00:
                return self.patch.page[address-0x2000]
        return self.ram[address]

    def __setitem__(self, address, value):
        if 0x2000 <= address < 0x4000 and self.model and self.model.nr.get(0x51,255) == 24:
            self.page[address-0x2000] = value
        elif address >= 0x4000:
            self.ram[address] = value

class HookModel(hooklib.NextModel):
    def __init__(self, sim, speed):
        super().__init__(sim,speed)
        self.nr[0x51] = 255
        self.game_io = []

    def write_port(self, regs, port, value, *args):
        if port in (0x243B,0x253B):
            return super().write_port(regs,port,value,*args)
        self.game_io.append((port,value))

def run_hook(memory, registers, patch, page=None, speed=0):
    from .dizzy6 import _rw_simulator
    view = HookMemory(memory,patch,page)
    sim = simpool.machine(_rw_simulator(),view,list(registers),'bubbler-hook')
    model = HookModel(sim,speed)
    # Semantic induction does not replay the elapsed native clock. Supply a
    # short, forward window here; native tests independently check actual pace.
    if registers[24] == 0xCE19:
        model.real = 2000
    view.model = model
    target = SITES[registers[24]][0]
    for step in range(2000000):
        if step and sim.registers[24] == target:
            return list(sim.registers),view,model
        sim.opcodes[view[sim.registers[24]]]()
    raise AssertionError('Bubbler hook did not return to the original body')

def compare_hook(memory, registers, patch, page=None, speed=0):
    """Meet immediately before the unchanged CALL body, including all game RAM."""
    from skoolkit.simulator import Simulator
    reference = simpool.machine(Simulator,list(memory),list(registers),'bubbler-original-call')
    reference.opcodes[memory[registers[24]]]()
    got,view,model = run_hook(memory,registers,patch,page,speed)
    differences = []
    for index in CMP:
        a,b = reference.registers[index],got[index]
        if (bool(a) != bool(b)) if index == 26 else (a != b):
            differences.append(('register',index,a,b))
    expected = bytearray(reference.memory[0x4000:])
    for address,old,new in patch.sites:
        expected[address-0x4000:address-0x4000+len(new)] = new
    differences.extend(('RAM',i+0x4000,a,b) for i,(a,b) in enumerate(zip(expected,view.ram[0x4000:])) if a != b)
    if model.nr[0x51] != 255:
        differences.append(('MMU',model.nr[0x51]))
    if model.game_io:
        differences.append(('extra game I/O',model.game_io))
    return differences,view,model

def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    if isinstance(patch,EnhancedPatch):
        from .bubbler_verify import verify as verify_colours
        return verify_colours(patch,rzx_path,stop,collect,progress)
    from . import rzx
    counts,examples,states = Counter(),{},[]
    page,speed,opened = bytearray(patch.page),0,False
    def fail(key, detail):
        counts[key+'!'] += 1
        if len(examples.setdefault(key,[])) < 5:
            examples[key].append(detail)
    def visit(pc, sim):
        nonlocal page,speed,opened
        if pc not in SITES:
            fail('jump into patched instruction',pc)
            return
        memory,registers = bytes(sim.memory),list(sim.registers)
        if collect and sum(s[0] == pc for s in states) < collect:
            states.append((pc,registers,memory))
        for address,(body,name) in SITES.items():
            if memory[address:address+3] != b'\xcd'+zt.w16(body):
                fail('original patch bytes changed',address)
        differences,view,model = compare_hook(memory,registers,patch,page,speed)
        if differences:
            fail('state differs',{'pc':pc,'differences':differences[:8]})
        if pc == 0xCE10:
            if opened: fail('nested window',pc)
            opened,wanted = True,3
        else:
            if not opened: fail('close without open',pc)
            opened,wanted = False,0
            counts['render windows'] += 1
        if model.nr[7] != wanted:
            fail('clock differs',{'pc':pc,'actual':model.nr[7],'expected':wanted})
        page,speed = view.page,model.nr[7]
        counts['hooks'] += 1
        counts['R comparisons'] += 1
        counts['RAM bytes compared'] += 49152
        if progress and counts['hooks']%500 == 0: progress(counts)
    counts['frames'],error = rzx.trace(str(rzx_path),set(SITES)|set(INTERIORS),visit,stop)
    if error: fail('recording desynchronised',error)
    if opened: counts['unfinished window at recording end'] += 1
    return (counts,examples,states) if collect else (counts,examples)

def unit_tests(patch, states):
    """Every hook, all clocks/IFF/R boundaries; broken R and clock restoration."""
    if isinstance(patch,EnhancedPatch):
        from .bubbler_verify import unit_tests as colour_tests
        return colour_tests(patch,states)
    import copy
    counts = Counter()
    for pc,registers,memory in states:
        for clock in range(4):
            for iff in (0,1):
                for refresh in (0,127,128,255):
                    regs = list(registers)
                    regs[15],regs[26] = refresh,iff
                    page = bytearray(patch.page)
                    page[0x1E30] = clock
                    differences,view,model = compare_hook(memory,regs,patch,page,clock if pc == 0xCE10 else 3)
                    assert not differences,(hex(pc),clock,iff,refresh,differences[:8])
                    assert model.nr[7] == (3 if pc == 0xCE10 else clock)
                    counts['ABI cases'] += 1
        bad = copy.copy(patch)
        bad.page = bytearray(patch.page)
        offset = bad.page.index(b'\x3e\xf4\xcd',patch.syms[SITES[pc][1]]-0x2000)
        bad.page[offset+1] += 1
        differences,_,_ = compare_hook(memory,registers,bad,speed=0 if pc == 0xCE10 else 3)
        assert any(d[:2] == ('register',15) for d in differences),'broken R escaped'
        counts['R-error controls caught'] += 1
    return counts


TRAINERS={
    'Infinite time':[(0xCD35,0x3D,0x00)],
    'Infinite lives':[(0xE0AA,0x3D,0xB7)],
    'Immunity':[(0xCD17,0x3D,0x00)],
    'Next level on life loss':[(0xE0A2,0x28,0x18)],
}

def loading_nex(data,screen):
    if len(screen)!=6912 or data[10]!=0:raise ValueError('Expected a plain NEX and original 6912-byte screen')
    header=bytearray(data[:512]);header[10]=2
    return bytes(header)+screen+data[512:]

def boot_check(nex,source,patch):
    """Original decoded entry, all registers/R and all 48K, no stack masks."""
    from . import nextboot
    from .machine import Machine
    fd,name=tempfile.mkstemp(suffix='.z80')
    try:
        with os.fdopen(fd,'wb')as f:f.write(entry_snapshot(str(source)))
        original=Machine(name)
    finally:os.unlink(name)
    expected=bytearray(original.sim.memory)
    for a,old,new in patch.sites:
        if expected[a:a+len(old)]!=old:raise ValueError('Original hook bytes differ')
        expected[a:a+len(new)]=new
    bad=[]
    for nexload in(False,True):
        state=nextboot.boot(str(nex),0x5E00,nexload=nexload,sysrom=nextboot.system_rom3()[0])
        bad += [('register',nexload,i,original.sim.registers[i],state['R'][i])for i in CMP
                if(bool(original.sim.registers[i])!=bool(state['R'][i])if i==26 else original.sim.registers[i]!=state['R'][i])]
        bad += [('RAM',nexload,hex(a),expected[a],state['mem'][a])for a in range(0x4000,65536)if expected[a]!=state['mem'][a]]
        bad += [('ROM',nexload,v)for v in state['bad']]
    return bad

def auto(a,z80,name,out,say):
    from . import rzx as recordings
    out=Path(out);out.mkdir(parents=True,exist_ok=True);ok=True
    say('Game      : '+name)
    say('Engine    : bubbler; original drawing and pace, optional approved Enhanced colour canvas')
    if not getattr(a,'publisher',None):a.publisher='Ultimate Play The Game, 1987'
    if not getattr(a,'colours_by',None):a.colours_by='MatGubbins'
    if not getattr(a,'fix_label',None):a.fix_label='Original pace'
    source=zt.Z80Snapshot(str(z80));screen=source.banks[5][:6912]
    trainer=out/(name+'_verified.pok')
    trainer.write_text(''.join('N'+title+'\n'+''.join(
        ('Z'if i==len(items)-1 else'M')+f' 8 {address} {value^255} {old^255}\n'
        for i,(address,old,value)in enumerate(items))for title,items in TRAINERS.items())+'Y\n')
    requested=getattr(a,'pok',None)
    if not requested or hashlib.sha256(Path(requested).read_bytes()).hexdigest()=='56435ba1b0f42182b697c4954fc5f3918d439f84ca8dfcc868ceb286a7d10180':
        a.pok=str(trainer)
    say('Trainers  : '+trainer.name+'; original decoder operands translated, all off by default')
    built={}
    for label,patch,suffix in [('Plain',Patch(z80,False),''),('Sprites',Patch(z80),'_sprites'),('Enhanced',EnhancedPatch(z80),'_enhanced')]:
        path=out/(name+suffix+'.nex');zt.convert(str(z80),str(path),patch=patch,quiet=True)
        bad=boot_check(path,z80,patch);ok &= not bad
        say('%-10s: %s %s boot %s'%(label,path.name,hashlib.md5(path.read_bytes()).hexdigest(),'OK'if not bad else str(bad[:5])))
        if label!='Plain':
            built[label]=patch
            loading=out/(name+suffix+'_loading.nex');loading.write_bytes(loading_nex(path.read_bytes(),screen))
    all_states={}
    for recording in list(getattr(a,'rzx',None)or[]):
        if len(recordings.read_segments(recording))!=1:raise ValueError('Use a continuous recording without autosave segments')
        for label,patch in built.items():
            counts,examples,states=verify(patch,recording,stop=getattr(a,'quick',None),collect=1)
            failures={k:v for k,v in counts.items()if k.endswith('!')};ok &= not failures
            say('Verify    : %s %s %d frames, %d hooks, all 48K RAM/R, %d complete canvases: %s'%(
                Path(recording).name,label,counts['frames'],counts['hooks'],counts['canvases'],'IDENTICAL'if not failures else str(failures)))
            all_states.setdefault(label,[]).extend(states)
            # Negatives need a state where their operation changes pixels. A
            # later recording may start after an early restore; keep prior
            # captured contexts rather than declaring a no-op mutation safe.
            units=unit_tests(patch,all_states[label]);failed={k:v for k,v in units.items()if k.endswith('!')};ok &= not failed
            say('Unit      : '+str(dict(units)))
            (out/(name+'_'+label.lower()+'_'+Path(recording).stem+'_verification.json')).write_text(json.dumps(
                dict(recording=Path(recording).name,counts=counts,examples=examples,units=units),indent=2)+'\n')
            for key,details in examples.items():say('            '+key+': '+str(details[:2]))
    rzxs=list(getattr(a,'rzx',None)or[])
    if rzxs:
        from . import nextboot,runchecks
        nexes=sorted(str(p)for p in out.glob('*.nex'))
        coverage={};statuses=[];reasons=[]
        entry=_peek(prepared(str(z80)))
        runtime_dir=tempfile.TemporaryDirectory(prefix='bubbler-rom-')
        runtime_snapshot=Path(runtime_dir.name)/'runtime.z80'
        runtime_snapshot.write_bytes(entry_snapshot(str(z80)))
        signature=bytes(entry(a)for a in range(0x5E00,0x5E10))
        for recording in rzxs:
            peek=_peek(recordings.read_segments(recording)[0][0])
            before=bytes(peek(a)for a in range(0x5E00,0x5E10))
            if before not in(signature,bytes(v^255 for v in signature)):
                raise ValueError('Recording starts with an unsupported original code image')
            start=0x5E00 if before!=signature else None
            report=nextboot.rom_paths(nexes,[recording],stop=getattr(a,'quick',None),z80=str(runtime_snapshot),start_pc=start)
            status,why,cov=runchecks.rom_paths(report,[recording],nexes)
            statuses.append(status);reasons.append(why)
            for nex,rows in cov.items():coverage.setdefault(nex,{}).update(rows)
            for result in report.values():
                for line in result[1]:say('ROM paths : '+line)
        runtime_dir.cleanup()
        status='fail'if 'fail'in statuses else'incomplete'if 'incomplete'in statuses else'pass'
        runchecks.add(runchecks.RUN,'rom_paths',status,'; '.join(r for r in reasons if r),coverage=coverage)
        ok &= status=='pass'
    if not(out/(name+'_PAINTING_SPRITES.png')).exists():sheets(z80,out,name)
    say('Result    : '+('PASSED'if ok else'FAILED'))
    return bool(ok)
