"""Head Over Heels (Ocean, 1987), exact128K release and optional Enhanced renderer.

Private derived drawing assets are supplied by the caller, never stored in this repository.
Enhanced colours: Anthony Lycett (Spec256).
"""
import hashlib
import json
from pathlib import Path
from . import z80tonex as Z, hooklib

SOURCE_MD5 = '757bbabf443a643cbe376ebfb11baa79'
CMP = hooklib.CMP_R
ROOT = Path(__file__).resolve().parents[1]


def load_profile():
    return json.loads((ROOT / 'docs/profiles/head_over_heels.json').read_text())


def is_head_over_heels(snap):
    from .simrun import addr_view
    if getattr(snap, 'machine', '') not in ('128K', '+2', '+2A', '+3'):
        return False
    mem = addr_view(snap)
    return all(bytes(mem[pc:pc + len(bytes.fromhex(old))]) == bytes.fromhex(old)
               for pc, old, _ in EnhancedPatch.entries)


class OriginalPatch:
    """Restore the temporary loader workspace before the captured ROM interrupt resumes."""
    name = 'Head Over Heels original presentation'
    tail_addr = 0x5B00
    uses_printer_buffer = False
    setup_call = None
    stub_extra = b''
    hook_page_data = b''

    def __init__(self):
        self.slot1 = (24, 0x3B00)
        self.altrom = self.altrom0 = (0x3900, 0x3B14)
        self.page = Z.rom48()[8192:]
        self.extra_banks = {}
        self.sites = []

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Head Over Heels requires the supported 128K release')
        self.entry = snap.pc
        tail, _, restore, _ = Z.build_tail(snap, self.tail_addr, self.slot1, True)
        if len(tail) > 256:
            raise ValueError('Temporary startup tail exceeds the restored workspace')
        page = bytearray(self.page)
        page[0x1900:0x1A00] = snap.banks[5][0x1B00:0x1C00]
        # Copy all NEXLOAD printer-buffer bytes, not merely our shorter tail.
        resume = bytes.fromhex('F321003911005B010001EDB0') + tail[restore:]
        if 0x3A00 + len(resume) > 0x3B00:
            raise ValueError('Resume code overlaps the register block')
        page[0x1A00:0x1A00 + len(resume)] = resume
        self.page = bytes(page)
        self.extra_banks[12] = self.page + bytes(8192)
        snap.pc = 0x3A00


def build_original(source, destination):
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Unsupported Head Over Heels source')
    patch = OriginalPatch()
    Z.convert(str(source), str(destination), patch=patch, quiet=True)
    return patch


class EnhancedPatch(OriginalPatch):
    """Direct companion pixels, with the original four-IRQ game pace retained."""
    name = 'Head Over Heels Enhanced'
    blocks = {'columns': 0x2800, 'masked': 0x2A00, 'expanded': 0x2C00,
              'shared': 0x2C80, 'plot': 0x2D00, 'loops': 0x2F00,
              'irq': 0x3000, 'normal': 0x3200, 'generic': 0x3400}
    entries = (
        (0xA19A, '3A57A0', 'h_plot'), (0x7376, 'F5C5E5', 'normal_irq'),
        (0x9EF6, '3D87D9', 'h_shift'), (0x9F36, 'F13C08', 'h_shift_done'),
        (0xAECD, 'E5D5EB', 'h_mirror_three'), (0xAF09, 'E5D5EB', 'h_mirror_four'),
        (0x9ECE, 'D516B9', 'h_mirror_two'), (0xA339, '0E060602', 'h_xor'),
        (0xA277, '1E0073', 'h_clear'), (0x81EE, 'EDB0E1', 'h_copy_forward'),
        (0x76DB, 'EDB8C9', 'h_copy_backward'), (0x9D6D, '3E04EDA0', 'h_edge'),
        (0x820D, '0EFC1813', 'h_crop'), (0x9DF8, 'D947EB', 'h_clear_column_one'),
        (0x9E07, 'D947EB', 'h_clear_column_two'), (0x9EAE, '477E12', 'h_stored_column_one'),
        (0x9EBC, '477E12', 'h_stored_column_two'), (0x9E57, '26006F', 'h_tiled_column_two'),
        (0x9E91, '26006F', 'h_tiled_column_one'), (0x9562, '7C2100B8', 'h_ui'),
        (0xA0B6, 'ED5354A0', 'h_render_begin'), (0x93E8, '2A52A0', 'h_display_copy'),
        (0xA59A, 'E5FDE1', 'h_player'))

    def __init__(self, assets):
        super().__init__()
        assets = Path(assets)
        hooks = json.loads((ROOT / 'docs/profiles/head_over_heels.json').read_text())['hooks']
        self.syms = {k: int(v, 16) for k, v in hooks['syms'].items()}
        self.altrom = self.altrom0 = (0x2000, 0x4000)
        page = bytearray(self.page)
        for key, at in self.blocks.items():
            data = bytes.fromhex(hooks[key])
            page[at - 8192:at - 8192 + len(data)] = data
        page[0x1732:0x1739] = bytes(7)
        page[0x1740:0x175C] = bytes(28)
        self.page = bytes(page)
        low = bytearray(Z.rom48()[:8192])
        low[0x38:0x3B] = bytes.fromhex('C30030')
        for key, at in (('kernel', 0x0800), ('mutation', 0x1000), ('pace', 0x1600)):
            data = bytes.fromhex(hooks[key])
            low[at:at + len(data)] = data
        self.extra_banks[13] = bytes(low) + bytes(8192)
        colours = (assets / 'colours.bin').read_bytes()
        palette = (assets / 'palette.bin').read_bytes()
        if len(colours) != 393216 or len(palette) != 512:
            raise ValueError('Head Over Heels drawing asset length mismatch')
        self.assets = assets
        self.colours = colours
        for i in range(24):
            self.extra_banks[14 + i] = colours[i * 16384:(i + 1) * 16384]
        for bank in range(38, 41):
            self.extra_banks[bank] = bytes([71]) * 16384
        values = [int.from_bytes(palette[i:i + 2], 'little') for i in range(0, 512, 2)]
        if any(v > 511 for v in values) or values[71] >> 1 != 7:
            raise ValueError('Invalid Enhanced palette or transparency reservation')
        if any(v >> 1 == 7 for i, v in enumerate(values) if i != 71):
            raise ValueError('Painted colour collides with transparency')
        setup = bytearray()

        def nr(n, v):
            setup.extend((0xED, 0x91, n, v))

        for n, v in ((0x69, 0), (0x12, 38), (0x70, 0), (0x16, 0), (0x17, 0),
                     (0x15, 0), (0x1C, 1), (0x18, 0), (0x18, 255), (0x18, 0), (0x18, 191),
                     (0x43, 0), (0x40, 24), (0x44, 0), (0x44, 0), (0x43, 0x10), (0x40, 0)):
            nr(n, v)
        for value in values:
            nr(0x44, value >> 1)
            nr(0x44, value & 1)
        nr(0x14, 7)
        nr(0x69, 0x80)
        setup.append(0xC9)
        self.setup_call = 0xD000
        self.stub_extra = bytes(setup)

    def apply(self, snap):
        if not snap.is128:
            raise ValueError('Head Over Heels Enhanced requires the supported128K release')
        self.sites = []
        for pc, expected, label in self.entries:
            old = bytes.fromhex(expected)
            at = self.syms[label]
            new = bytes((0xC3, at & 255, at >> 8)) + bytes(len(old) - 3)
            bank = 5 if pc < 0x8000 else 2
            offset = pc & 16383
            actual = snap.banks[bank][offset:offset + len(old)]
            if actual != old:
                raise ValueError(f'Head Over Heels hook {pc:04X}: {actual.hex()} != {old.hex()}')
            data = bytearray(snap.banks[bank])
            data[offset:offset + len(new)] = new
            snap.banks[bank] = bytes(data)
            self.sites.append((pc, old, new))
        super().apply(snap)


def build(source, destination, assets=None, loading=None):
    """Exact archive release; private assets opt into Enhanced, loading is a .scr."""
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != SOURCE_MD5:
        raise ValueError('Unsupported Head Over Heels source')
    patch = EnhancedPatch(assets) if assets else OriginalPatch()
    Z.convert(str(source), str(destination), patch=patch, quiet=True)
    if loading:
        screen = Path(loading).read_bytes()
        if hashlib.md5(screen).hexdigest() != '9ce8b2d53cd49ed8341a39a8de6c2e1c':
            raise ValueError('Unsupported Head Over Heels loading screen')
        data = Path(destination).read_bytes()
        header = bytearray(data[:512]); header[10] = 2; header[133] = 50
        Path(destination).write_bytes(header + screen + data[512:])
    return patch


def boot_problems(nex, source, patch):
    """Full128K RAM, registers/R and hidden-ROM checks, including NEXLOAD workspace."""
    import copy
    from skoolkit import CSimulator
    from skoolkit.snapshot import Snapshot
    from skoolkit.simutils import from_snapshot
    from . import nextboot
    original = from_snapshot(CSimulator, Snapshot.get(str(source)))
    expected = Z.Z80Snapshot(str(source)); q = copy.deepcopy(patch); q.apply(expected)
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), q.entry, nexload=nexload, sysrom=nextboot.system_rom3()[0])
        bad.extend(('ROM', nexload, v) for v in st['bad'])
        for i in CMP:
            a, b = original.registers[i], st['R'][i]
            if (bool(a) != bool(b)) if i == 26 else (a != b):
                bad.append(('register', nexload, i, a, b))
        for bank in range(8):
            st['mmu'][6:8] = [bank * 2, bank * 2 + 1]
            mismatch = [i for i in range(16384) if st['mem'][0xC000 + i] != expected.banks[bank][i]]
            if mismatch: bad.append(('RAM', nexload, bank, len(mismatch), mismatch[:8]))
    return bad


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Recorded-input differential proof; native timing is a separate release check."""
    if not isinstance(patch, EnhancedPatch):
        raise ValueError('Default has no game hooks; use its complete boot and native pace checks')
    return _verify(patch, rzx_path, stop=stop, collect=collect, progress=progress)


def unit_tests(patch, states, neg=None):
    return _unit_tests(patch, states, neg=neg)


def auto(a, z80, name, out, say):
    import os
    for key, value in (('publisher', 'Ocean, 1987'), ('colours_by', 'Anthony Lycett'),
                       ('fix_label', 'Next presentation')):
        if not getattr(a, key, None): setattr(a, key, value)
    assets = os.environ.get('NEXCLASH_HEAD_OVER_HEELS_ASSETS')
    loading = os.environ.get('NEXCLASH_HEAD_OVER_HEELS_SCREEN')
    adjacent = Path(z80).resolve().parent
    if not assets and all((adjacent / n).is_file() for n in ('colours.bin', 'palette.bin')):
        assets = adjacent
    if not loading and Path(z80).with_suffix('.scr').is_file():
        loading = Path(z80).with_suffix('.scr')
    modes = [('Plain', None)] + ([('Enhanced', assets)] if assets else [])
    ok = True
    for label, data in modes:
        destination = Path(out) / (name + ('_enhanced' if data else '') + '.nex')
        patch = build(z80, destination, data, loading)
        errors = boot_problems(destination, z80, patch); ok &= not errors
        say(f'{label:10}: {destination.name} {hashlib.md5(destination.read_bytes()).hexdigest()}')
        say(f'Boot      : {errors[:3] if errors else "PASS (128K RAM, registers/R, hidden ROM, NEXLOAD)"}')
        if data:
            for recording in getattr(a, 'rzx', []) or []:
                counts, failures, states = verify(patch, recording, stop=getattr(a, 'quick', None), collect=1, progress=say)
                units = unit_tests(patch, states)
                ok &= not failures and not any(v for k, v in units.items() if k.endswith('!'))
                say(f'Verify    : {dict(counts)} {failures[:2]}')
                say(f'Unit      : {dict(units)}')
            recordings = getattr(a, 'rzx', []) or []
            if recordings and not getattr(a, 'quick', None):
                for fault in ('source', 'position', 'refresh'):
                    broken = EnhancedPatch(assets); broken.proof_fault = fault
                    _, failures = verify(broken, recordings[0], stop=3000)
                    ok &= bool(failures)
                    say(f'Negative  : {fault}: ' + ('DETECTED' if failures else 'FAILED'))
    manifest = {'default': name + '.nex', 'plain': None, 'colours': {}}
    if assets: manifest['colours']['Enhanced'] = {'default': name + '_enhanced.nex'}
    (Path(out) / (name + '_outputs.json')).write_text(json.dumps(manifest, indent=1) + '\n')
    say('Result    : ' + ('PASSED' if ok else 'FAILED'))
    return bool(ok)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Head Over Heels128K, original or private Enhanced assets')
    parser.add_argument('source'); parser.add_argument('destination')
    parser.add_argument('--assets'); parser.add_argument('--loading')
    args = parser.parse_args(argv)
    patch = build(args.source, args.destination, args.assets, args.loading)
    bad = boot_problems(args.destination, args.source, patch)
    if bad: raise SystemExit(str(bad[:8]))


# Independent colour model and per-event CPU/pixel verifier. No private game data.
import collections,time
from . import rzx, z80n
from .dizzy6 import _rw_simulator
class Mem:
 def __init__(self,pages,mapping,rom):self.pages=pages;self.mapping=mapping;self.rom=rom
 def __len__(self):return 65536
 def __getitem__(self,a):
  if isinstance(a,slice):return [self[i]for i in range(*a.indices(65536))]
  slot=a>>13;page=self.mapping[slot]
  return self.rom[slot*8192+(a&8191)]if page==255 else self.pages[page][a&8191]
 def __setitem__(self,a,v):
  if isinstance(a,slice):
   for i,val in zip(range(*a.indices(65536)),v):self[i]=val
   return
  page=self.mapping[a>>13]
  if page!=255:self.pages[page][a&8191]=v
class Machine:
 def __init__(self,source,private,clock,regs):
  p=load_profile()["hooks"];BLOCKS=EnhancedPatch.blocks
  self.pages={2*b+h:list(source.mem.banks[b][h*8192:(h+1)*8192])for b in range(8)for h in range(2)}
  rom=list(source.mem)[:16384];alt=rom[:]
  for key,at in BLOCKS.items():data=bytes.fromhex(p[key]);alt[at:at+len(data)]=data
  self.pages[24]=alt[8192:];self.pages[25]=[0]*8192;self.pages[26]=rom[:8192]
  self.pages[26][0x38:0x3b]=[0xc3,0x00,0x30]
  blob=bytes.fromhex(p['pace']);self.pages[26][0x1600:0x1600+len(blob)]=blob
  self.pages[24][0x1740:0x175c]=[0]*28
  self.pages[28]=[0x55]*8192;self.pages[29]=[0xaa]*8192
  mapping=[26,24,10,11,4,5,28,29]if private else[255,255,25,11,4,5,0,1]
  self.mem=Mem(self.pages,mapping,alt);self.nr={7:3 if private else clock,**{0x50+i:v for i,v in enumerate(mapping)}}
  self.mem[0x3732]=0;self.mem[0x3734]=0;self.mem[0x3735]=0;self.mem[0x3736]=0;self.mem[0x3737]=0
  self.mem[0x3702]=0xab;self.mem[0x3705]=clock;self.mem[0x3706]=0;self.mem[0x3707]=1
  self.sim=_rw_simulator()(self.mem,config={'int_active':0});self.r=self.sim.registers;self.r[:]=regs
  self.selected=0;self.ay=[];self.ay_clocks=[];self.paging=[];self.clock_log=[]
  self.sim.set_tracer(self);z80n.install(self.sim,self.nextreg)
 def nextreg(self,n,v):
  self.nr[n]=(self.nr.get(n,0)&~v)if n==0xc8 else v
  if 0x50<=n<=0x57:self.mem.mapping[n-0x50]=v
  if n==7:self.clock_log.append(v)
 def read_port(self,r,p):
  if p==0x253b and self.selected in(0x1e,0x1f)and hasattr(self,'beam_base'):
   line=int((self.beam_base+(r[25]-self.beam_t)/(1<<self.nr[7]))/228)%311
   return line>>8 if self.selected==0x1e else line&255
  return self.nr.get(self.selected,0)if p==0x253b else 255
 def write_port(self,r,p,v,*args):
  if p==0x243b:self.selected=v;return
  if p&0x8002==0:
   self.paging.append(v)
   for i,value in ((0,255),(1,255),(6,2*(v&7)),(7,2*(v&7)+1)):self.nextreg(0x50+i,value)
  if p&0xc002 in(0xc000,0x8000):self.ay.append((p,v));self.ay_clocks.append(self.nr[7])
 def run(self,end,sp):
  for n in range(200000):
   if self.r[24]==end and self.r[12]==sp:return
   self.sim.opcodes[self.mem[self.r[24]]]()
  raise RuntimeError(('IRQ timeout',hex(self.r[24]),hex(self.r[12])))

BLITS={0x9a25:(1,3),0x9a3a:(2,3),0x9a56:(3,3),0x9a79:(1,4),
       0x9a90:(2,4),0x9aae:(3,4),0x9ad3:(4,4),0x9afe:(1,5),
       0x9b17:(2,5),0x9b37:(3,5),0x9b5e:(4,5),0x9b8b:(5,5)}
COPIES={0x9424,0x9442,0x9444,0x9462,0x9464,0x9466,
        0x9484,0x9486,0x9488,0x948a,0x94a9,0x94ab,0x94ad,0x94af,0x94b1,
        0x94cc,0x94ce,0x94d0,0x94d2,0x94d4,0x94d6}

class Preview:
 def __init__(self,sim,colours):
  self.sim=sim;self.mem=sim.memory
  self.col=[bytes(8)]*16384+[colours[i:i+8]for i in range(0,len(colours),8)]
  self.mono=bytearray(self.mem);self.fallback=bytearray(65536)
  self.count=collections.Counter();self.error=[];self.frame_no=0
 def w(self,n):return self.sim.registers[n]*256+self.sim.registers[n+1]
 def copy(self,d,s):
  if 0xb66d<=s<0xb67d:
   self.mono[s]=self.mem[s];self.fallback[s]=1
  self.col[d]=self.col[s];self.mono[d]=self.mono[s];self.fallback[d]=self.fallback[s]
 def flip(self,at,w,h):
  for y in range(h):
   row=b''.join(self.col[at+y*w+i]for i in range(w))[::-1]
   for i in range(w):self.col[at+y*w+i]=row[i*8:i*8+8]
   row=bytes(int(f'{self.mono[at+y*w+i]:08b}'[::-1],2)for i in range(w))[::-1]
   self.mono[at+y*w:at+(y+1)*w]=row
 def before(self,pc):
  r=self.sim.registers;m=self.mem
  if pc==0x9562:self.ui_text=r[6]==8 and r[3]==1
  elif pc in BLITS:
   width,stride=BLITS[pc];dest=self.w(18);src=self.w(20);mask=self.w(22);height=r[2]
   self.count['masked']+=1
   for y in range(height):
    for x in range(width):
     d=(dest&0xff00)|((dest+y*6+x)&255);s=src+y*stride+x;k=mask+y*stride+x
     old=self.col[d];new=self.col[s];mask_pixels=self.col[k]
     self.col[d]=bytes((old[j]&mask_pixels[j])|new[j] for j in range(8))
     self.mono[d]=(self.mono[d]&self.mono[k])|self.mono[s]
     self.fallback[d]=0
  elif pc in COPIES:
   src=self.w(6)
   if self.mono[src]!=m[src]:
    self.count['mono_mismatch']+=1
    if len(self.error)<20:self.error.append([self.frame_no,hex(pc),hex(src),self.mono[src],m[src]])
   self.copy(self.w(4),src);self.count['screen_copy']+=1
  elif pc==0x9569:
   if getattr(self,"ui_text",False):self.mono[self.w(4)]=m[self.w(4)]
   self.copy(self.w(6),self.w(4))
   if getattr(self,"ui_text",False):self.fallback[self.w(6)]=1
  elif pc in (0x9e5f,0x9e63,0x9e99,0x9eb0,0x9ebe,0x9ec2):self.copy(self.w(4),self.w(6))
  elif pc in (0x9dfd,0x9e0c,0x9e0e):self.col[self.w(6)]=bytes(8);self.mono[self.w(6)]=0;self.fallback[self.w(6)]=0
  elif pc in(0x76db,0x9d6f,0x81ee):self.copy(self.w(4),self.w(6))
  elif pc==0x8213:
   at=self.w(4);mask=r[3]
   self.col[at]=bytes(v if mask&(128>>i) else 0 for i,v in enumerate(self.col[at]))
   self.mono[at]&=mask
  elif pc==0x821a:
   at=self.w(6);mask=r[3]
   self.col[at]=bytes(v if mask&(128>>i) else 255 for i,v in enumerate(self.col[at]))
   self.mono[at]|=mask^255
  elif pc==0xa33f:
   d=self.w(6);s=self.w(4)
   self.col[d]=bytes(a^b for a,b in zip(self.col[d],self.col[s]))
   self.mono[d]^=self.mono[s]
  elif pc==0xa279:
   at=self.w(6);self.col[at]=bytes(8);self.mono[at]=0;self.fallback[at]=0
  elif pc in(0xaecd,0xaf09):
   width=3 if pc==0xaecd else 4
   self.flip(self.w(4),width,r[2]);self.count['mirror']+=1
  elif pc==0x9ece:self.flip(self.w(6),2,r[2]);self.count['floor_mirror']+=1
  elif pc==0x9ef6:
   shift=r[0]*2;width=m[0xada4];height=m[0xa057]
   for half,src in enumerate((self.w(6),self.w(4))):
    dest=0xbf20+half*height*(width+1);pad=255 if half else 0
    for y in range(height):
     row=bytes([pad])*shift+b''.join(self.col[src+y*width+x]for x in range(width))+bytes([pad])*(8-shift)
     for x in range(width+1):self.col[dest+y*(width+1)+x]=row[x*8:x*8+8]
     bits=('1'if half else'0')*shift+''.join(f'{self.mono[src+y*width+x]:08b}'for x in range(width))+('1'if half else'0')*(8-shift)
     for x in range(width+1):self.mono[dest+y*(width+1)+x]=int(bits[x*8:x*8+8],2)
   self.count['shift']+=1

def _verify(patch,rzx_path,stop=None,collect=0,progress=None):
    p=load_profile()['hooks'];states={}
    SYM={k:int(v,16)for k,v in p['syms'].items()};MAP=[255,255,10,11,4,5,0,1]
    ROWS={pc:(bytes.fromhex(old),label)for pc,old,label in EnhancedPatch.entries}
    MODEL=set(BLITS)|set(COPIES)|{0x9569,0x9e5f,0x9e63,0x9e99,0x9eb0,0x9ebe,0x9ec2,
        0x9dfd,0x9e0c,0x9e0e,0x76db,0x9d6f,0x81ee,0x8213,0x821a,0xa33f,0xa279,
        0xaecd,0xaf09,0x9ece,0x9ef6}
    oracle=None;counts=collections.Counter();pixels=0;checks=0;started=time.monotonic()
    a=b=None;failure=None;broken=getattr(patch,'proof_fault',None);last_player_line=None
    def run(m,end,sp):
        for i in range(1600000):
            if m.r[24]==end and m.r[12]==sp:return
            m.sim.opcodes[m.mem[m.r[24]]]()
        raise RuntimeError(('timeout',hex(m.r[24]),hex(end),m.r[12],sp))
    def event(pc,sim):
        nonlocal a,b,pixels,checks,last_player_line,oracle
        if oracle is None:oracle=Preview(sim,patch.colours)
        oracle.sim=sim;oracle.mem=sim.memory
        if pc in ROWS:
            bank=getattr(sim.memory,'o7ffd',0)&7
            entry_map=MAP[:6]+[2*bank,2*bank+1]
            if collect and len(states.get(pc,[]))<collect:
                states.setdefault(pc,[]).append(([bytes(v)for v in sim.memory.banks],list(sim.registers),list(sim.memory)[:16384]))
            counts[f'{pc:04x}']+=1
            regs=list(sim.registers);old,label=ROWS[pc];size=len(old)
            if a is None:
                a=Machine(oracle,False,0,regs);a.nextreg(0x52,10)
                b=Machine(oracle,True,0,regs)
                for n,v in [(7,0)]+[(0x50+i,v)for i,v in enumerate(MAP)]:b.nextreg(n,v)
                colour=patch.colours
                for page in range(28,76):b.pages[page]=list(colour[(page-28)*8192:(page-27)*8192])
                for page in range(76,82):b.pages[page]=[71]*8192
                blob=bytes.fromhex(p['mutation']);b.pages[26][0x1000:0x1000+len(blob)]=blob
                b.pages[24][0x1738]=0
                if broken=='position':
                    at=SYM['display_copy'];code=bytes(b.pages[26][at:at+20]);i=code.index(bytes.fromhex('D64087'));b.pages[26][at+i+1]=63
                if broken=='refresh':
                    code=bytes.fromhex(p['generic']);i=code.index(bytes.fromhex('3E5B28'));b.pages[24][0x1400+i+1]=90
                if broken=='source':
                    code=bytes.fromhex(p['plot']);i=code.index(bytes.fromhex('2A0A37'));b.pages[24][0xd00+i+1]=0x0c
            clock=b.nr[7]
            for bank in range(8):
                data=list(sim.memory.banks[bank])
                for half in range(2):
                    part=data[half*8192:(half+1)*8192]
                    a.pages[bank*2+half]=part;b.pages[bank*2+half]=part[:]
            a.r[:]=regs;b.r[:]=regs
            # This is a per-event proof, not a clock-continuous replay. Supply the
            # original recording's elapsed frame time at the player boundary. The
            # native matrix and beam-driven unit cases independently prove waits.
            b.beam_base=counts['7376']*70908+regs[25];b.beam_t=regs[25]
            if pc==0xa59a:
                now=b.beam_base//228
                elapsed=0 if last_player_line is None else max(0,now-last_player_line)
                for off,value in ((0,now%311),(2,elapsed),(14,0),(18,0),(26,0)):
                    b.pages[24][0x1740+off:0x1742+off]=[value&255,value>>8]
                last_player_line=now
            # Original code can page outside our hooks. Start each isolated
            # comparison with the recording's actual visible bank.
            for n,v in [(7,clock)]+[(0x50+i,v)for i,v in enumerate(entry_map)]:a.nextreg(n,v)
            for i,v in enumerate(entry_map):b.nextreg(0x50+i,v)
            assert bytes(b.mem[pc:pc+size])==old,(hex(pc),'original changed')
            at=SYM[label];b.mem[pc:pc+size]=[0xc3,at&255,at>>8]+[0]*(size-3)
            end=pc+size;sp=regs[12];expected_clock=clock
            if pc==0x7376:
                # Compare the complete original ISR at every recorded entry,
                # including R and AY writes. Give the reference the same reserved
                # stack as the bridge; only dead foreground-stack writes differ
                # by design. No game RAM is excluded from this comparison.
                end=oracle.mem[sp]+256*oracle.mem[sp+1]
                a.nextreg(0x52,25);a.nextreg(7,0);a.r[12]=0x5fee
                a.mem[0x5fee:0x5ff0]=[end&255,end>>8]
                a.ay.clear();b.ay.clear();a.ay_clocks.clear();b.ay_clocks.clear()
                run(a,end,0x5ff0);run(b,end,sp+2)
                a.r[12]=sp+2;a.nextreg(0x52,10)
                rd=[(i,a.r[i],b.r[i])for i in hooklib.CMP_R if a.r[i]!=b.r[i]]
                b.mem[pc:pc+size]=old
                md=[page for page in range(16)if a.pages[page]!=b.pages[page]]
                if rd or md or b.mem.mapping!=a.mem.mapping or b.nr[7]!=clock or a.ay!=b.ay or a.ay_clocks!=b.ay_clocks:
                    raise AssertionError(dict(pc=hex(pc),label=label,registers=rd,ram_pages=md,
                                              mapping=[a.mem.mapping,b.mem.mapping],clock=[clock,b.nr[7]],ay_equal=a.ay==b.ay,
                                              ay_clocks=[a.ay_clocks[:4],b.ay_clocks[:4]]))
                checks+=1
                return
            if pc in(0xaecd,0xaf09):sp-=4
            if pc==0x9ece:sp-=2
            if pc in(0x81ee,0x9f36):sp+=2
            if pc in(0xa339,0xa277,0x76db,0x9d6d,0x9eae,0x9ebc):
                end=oracle.mem[sp]+256*oracle.mem[sp+1];sp+=2
            if pc==0x820d:end=0x8224
            if pc in(0x9ef6,0xa0b6):expected_clock=3
            if pc==0x9f36:expected_clock=b.pages[24][0x1735]
            if pc==0x93e8 and b.pages[24][0x1736]:expected_clock=b.pages[24][0x1737]
            run(a,end,sp);run(b,end,sp)
            rd=[(i,a.r[i],b.r[i])for i in hooklib.CMP_R if a.r[i]!=b.r[i]]
            for i,v in enumerate(old):b.pages[entry_map[pc>>13]][(pc&8191)+i]=v
            md=[page for page in range(16)if a.pages[page]!=b.pages[page]]
            if rd or md or b.mem.mapping!=entry_map or b.nr[7]!=expected_clock:
                raise AssertionError(dict(pc=hex(pc),label=label,registers=rd,ram_pages=md,
                                          mapping=b.mem.mapping,clock=[expected_clock,b.nr[7]]))
            if pc==0x93e8:
                x=(oracle.mem[0xa053]-64)*2;y=oracle.mem[0xa055]-oracle.mem[0x940b]
                width=(oracle.mem[0xa052]-oracle.mem[0xa053])//4;height=oracle.mem[0xa054]-oracle.mem[0xa055]
                mismatch=[]
                for row in range(height):
                    for byte in range(width):
                        addr=0xb800|((row*6+byte)&255)
                        expected=oracle.col[addr]
                        fallback=oracle.fallback[addr]
                        for bit,v in enumerate(expected):
                            dest=(y+row)*256+x+byte*8+bit;got=b.pages[76+dest//8192][dest%8192]
                            want=71 if fallback else 63 if v==71 else v
                            if got!=want and len(mismatch)<12:mismatch.append((x+byte*8+bit,y+row,got,want))
                            pixels+=1
                if mismatch:raise AssertionError(dict(pc=hex(pc),label=label,rectangle=[x,y,width,height],pixels=mismatch))
            checks+=1
            if progress and checks%1000==0:progress(f'hooks {checks}; pixels {pixels}; {time.monotonic()-started:.0f}s')
        if pc in MODEL or pc==0x9562:oracle.before(pc)

    try:
        frames,desync=rzx.trace(str(rzx_path),set(ROWS)|MODEL,event,stop=stop)
        if desync:failure=desync
    except Exception as exc:
        frames=None;failure=repr(exc)
    counts['frames']=frames or 0;counts['pixels']=pixels;counts['hook_checks']=checks
    examples=[]
    if failure:counts['comparison!']+=1;examples.append(failure)
    return (counts,examples,states)if collect else(counts,examples)


def _unit_tests(patch,states,neg=None):
    """Unreached reverse-copy caller, all clocks/IFFs and source/refresh controls."""
    from types import SimpleNamespace
    import itertools
    counts=collections.Counter()
    captured=next((v[0]for v in states.values()if v),None)
    if captured is None:return collections.Counter({'missing_state!':1})
    banks,regs,rom=captured
    class Memory(list):pass
    mem=Memory(rom+list(banks[5])+list(banks[2])+list(banks[0]));mem.banks=banks
    source=SimpleNamespace(mem=mem)
    p=load_profile()['hooks'];syms={k:int(v,16)for k,v in p['syms'].items()}
    mapping=[255,255,10,11,4,5,0,1]
    cases=[(clock,iff,n,None)for clock,iff,n in itertools.product(range(4),(0,1),(1,2,16,257))]
    cases += [(0,1,16,'source'),(0,1,16,'refresh')]
    for clock,iff,n,fault in cases:
        r=list(regs);r[24]=0x76db;r[12]=0xff80;r[26]=iff;r[15]=255;r[25]=0
        r[2]=n>>8;r[3]=n&255;r[6]=0xc1;r[7]=0x0a;r[4]=0xd2;r[5]=0x03
        a=Machine(source,False,clock,r);a.nextreg(0x52,10)
        b=Machine(source,True,clock,r)
        for k,v in [(7,clock)]+[(0x50+i,v)for i,v in enumerate(mapping)]:b.nextreg(k,v)
        for m in(a,b):m.mem[0xff80:0xff82]=[0x00,0x80]
        for page in range(28,76):b.pages[page]=[(page*11+i*7)&255 for i in range(8192)]
        initial=bytes(v for page in range(28,76)for v in b.pages[page])
        blob=bytes.fromhex(p['mutation']);b.pages[26][0x1000:0x1000+len(blob)]=blob
        if fault=='source':
            # Damage the source pixel bank only; the independently retained
            # expected canvas must still detect it.
            off=(0xc10a-0x4000)*8;b.pages[28+off//8192][off%8192]^=1
        if fault=='refresh':
            code=bytes.fromhex(p['generic']);i=code.index(bytes.fromhex('3E5B28'));b.pages[24][0x1400+i+1]=90
        at=syms['h_copy_backward'];old=list(b.mem[0x76db:0x76de]);b.mem[0x76db:0x76de]=[0xc3,at&255,at>>8]
        for m in(a,b):m.run(0x8000,0xff82)
        b.mem[0x76db:0x76de]=old
        expected=bytearray(initial)
        for i in range(n):
            d=(0xd203-i-0x4000)*8;s=(0xc10a-i-0x4000)*8;expected[d:d+8]=initial[s:s+8]
        actual=bytes(v for page in range(28,76)for v in b.pages[page])
        mismatch=any(a.r[i]!=b.r[i]for i in hooklib.CMP_R)or any(a.pages[i]!=b.pages[i]for i in range(16))
        mismatch |= b.mem.mapping!=mapping or b.nr[7]!=clock or actual!=expected
        if fault:counts['negative_'+fault+(''if mismatch else'!')]+=1
        else:counts['backward'+('!'if mismatch else'')]+=1
    return counts


if __name__ == '__main__':
    main()
