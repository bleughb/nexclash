"""Cisco Heat (Image Works 1991, 128K): the smooth engine (games/cisco_heat.md).

The original draws about 6 frames a second (one race update = 4..12 frames). This engine runs the real update
unchanged at 28 MHz, keeps the original's pace (each update lasts as long as it did: P = 7.24 D + 1.87 frames,
D its 28 MHz time) and fills the rest of that time with in-between frames on a 25 fps cadence: the next update run
ahead with a fraction of its forward step, presented, then every byte it wrote put back (asm/cisco_heat_hooks.asm).
The tape stages load from Next pages.

Inputs beside the snapshot: the stage snapshots, .z80 or .rzx under any name (the user's CiscoHeat1-5 and
CiscoHeatEnd recordings): each was taken at the STOP TAPE wait after its stage's load and holds the unpacked
block in bank 1; they are found by content (STAGE_MD5). Nothing of the game is in this repository.

Evidence (verify / unit_tests):
  V1 the real update: the patched update (smooth frames off) against the original 0x8AFE from the same state,
     interrupts delivered at the same game instruction in both (the patched run decides where), the LD A,R
     random reads supplied (R_SITES; R itself is the documented exception: games/cisco_heat.md "R").
     Exact: registers CMP, all RAM but hook RAM and the dead stack, port writes.
  V2 the in-between frames: smooth on against smooth off, same start line, interrupts by the line clock.
     Exact on all RAM but the display (screens, back buffer, 0x5B8B/0x5B8C), hook RAM, bank 6; the ISR's
     sound port writes identical.
"""
import collections
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from . import z80tonex as zt, hooklib

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / 'docs' / 'profiles'
PUBLISHER = 'Image Works, 1991'
STAGE_KEYS = '12345X'
LOAD_SCREEN = 'cisco_heat_loading.scr'        # the tape's cisco$ block (6,912 bytes), beside the snapshot
LOAD_MD5 = 'dcada32d9b00f736b583beae1cc4760d'
START_DELAY = 0                                # NEX header byte 133 (boot_wait holds the screen: 4 s or a key)
SCR_PAGE = 27                                  # asm SCR_PAGE: the snapshot's display bytes in a loading screen build
STAGE_PAGES = (16, 17, 18, 19, 22, 23)       # asm STAGE_PAGE0.. (bank 10 = pages 20/21 is the stub's)
STAGE_MD5 = {'1': 'dbe4ab364061deaf540cfd7e37ad3a63', '2': '4d9eda09cd622f457b83fa7a532bee16',     # header + block
             '3': '61f5d23e7c806680914df41d37c43b8f', '4': 'e131dc4ddd4fcec0ca64b96751a65667',
             '5': '7103c3459413b7afbbde57f2639af50f', 'X': '69b7b0505f354fff006e2cac035131ab'}
TAIL_ADDR = 0x7C80                             # hook RAM area (0x7B00-0x7D7C, never used by the game)
HOOK_RAM = (0x7B00, 0x7D7D)
V = 0x7B00
V_EN, V_DMA, DMA_LEN = V + 2, V + 208, 15
V_CAD = V + 0x148                              # asm v_cad: spec frame cadence, 1 (up to 50 a second) or 2 (25)
V_FAST = V + 0x144                             # asm v_fast: the fast paths (copy by zxnDMA, sprite rows)
V_CAR = 0x7CD8                                 # asm CAR: c_on (the player's car as sprites, Patch.fast), then its state
DMA_CYCLES = 6                                 # model: 28 MHz cycles a DMA byte (3 + 3 after reset; docs/DDMA.md)
G_STAGE, G_HDR = 0x8E4C, 0x851C
R_SITES = (0x98AC, 0xA468)                     # the only LD A,R in the game
CMP = tuple(i for i in hooklib.CMP_R if i != 15)
FRAME = 228 * 311                              # 128K frame, T at 3.5 MHz
FAST = 7.17     # 28 MHz against 3.5: 8 T a T less one per memory read (the recordings' median, games/cisco_heat.md)
SCREENS = ((5, 0x0000, 0x1B00), (7, 0x0000, 0x1B00), (5, 0x2000, 0x3B00))   # (bank, from, to): screens, back buffer
DISPLAY = (0x5B8B, 0x5B8C)
HANDLER_SCRATCH = (0x9E47, 0x9E69)            # the handler's saved SP and own stack: dead after it returns
SP_SCRATCH = (0xA62D, 0xA62F)                 # a draw routine's saved SP (LD (0xA62D),SP .. LD SP,(0xA62D)): one call level deeper


def _profile_path(name='cisco_heat'):
    return PROFILES / (name + '.json')


def load_profile(name='cisco_heat'):
    return json.loads(_profile_path(name).read_text())


def _sig():
    return {int(a, 16): bytes.fromhex(v) for a, v in load_profile()['signature'].items()}


def _read(banks, port7ffd, a):
    bank = 5 if 0x4000 <= a < 0x8000 else 2 if 0x8000 <= a < 0xC000 else port7ffd & 7
    return banks[bank][a & 0x3FFF]


def is_cisco_heat(snap):
    """128K and the profile's signature bytes (zt.Z80Snapshot or skoolkit's Snapshot)."""
    banks = getattr(snap, 'banks', None)
    try:
        if banks is not None and hasattr(snap, 'is128'):
            if not snap.is128:
                return False
            return all(bytes(_read(banks, snap.port7ffd, a + i) for i in range(len(v))) == v for a, v in _sig().items())
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v)]) == v for a, v in _sig().items())
    except (KeyError, TypeError, IndexError, AttributeError):
        return False


# ----------------------------------------------------------------------------------------------- stages

def stage_block(snap):
    """(key, 16 header bytes, unpacked block) of a snapshot taken after a stage load, else None."""
    if not getattr(snap, 'is128', False):
        return None
    b2 = snap.banks[2]
    key = chr(b2[G_STAGE - 0x8000])
    hdr = bytes(b2[G_HDR - 0x8000:G_HDR - 0x8000 + 16])
    if key not in STAGE_KEYS or hdr[:6] != ('STAGE' + key).encode():
        return None
    n = hdr[10] | hdr[11] << 8
    if not 0 < n <= 0x1FE0:
        return None
    return key, hdr, bytes(snap.banks[1][:n])


def _md5(hdr, data):
    return hashlib.md5(hdr + data).hexdigest()


def _snapshot(path):
    """zt.Z80Snapshot of a .z80 or of an RZX's first snapshot."""
    path = str(path)
    if path.lower().endswith('.rzx'):
        from . import rzx as RZ
        with tempfile.TemporaryDirectory() as d:
            out, ext = RZ.extract(path, os.path.join(d, 'x.z80'))
            if ext != 'z80':
                return None
            return zt.Z80Snapshot(out)
    return zt.Z80Snapshot(path)


def find_stages(directory):
    """{key: (hdr, data)} from the snapshots / recordings in directory, by content."""
    found = {}
    for p in sorted(Path(directory).iterdir()):
        if p.suffix.lower() not in ('.z80', '.rzx'):
            continue
        try:
            s = _snapshot(p)
            blk = s and stage_block(s)
        except Exception:
            continue
        if blk and (not STAGE_MD5 or STAGE_MD5.get(blk[0]) == _md5(blk[1], blk[2])):
            found.setdefault(blk[0], blk[1:])
    return found


def stage_page(hdr, data):
    p = bytearray(8192)
    p[:len(data)] = data
    p[0x1FE0:0x1FF0] = hdr
    p[0x1FFE:0x2000] = zt.w16(len(data))
    return bytes(p)


# ----------------------------------------------------------------------------------------------- the patch

class Patch:
    """The z80tonex patch object. stages: {key: (hdr, data)} (find_stages); smooth: in-between frames on."""
    uses_printer_buffer = False
    tail_addr = TAIL_ADDR
    max_tail = HOOK_RAM[1] - TAIL_ADDR
    stub_extra = b''
    setup_call = None
    hook_page_data = b''

    def __init__(self, stages, smooth=True, screen=None, fast=True, fps50=True, car=True, hold=True):
        missing = [k for k in STAGE_KEYS if k not in stages]
        if missing:
            raise ValueError('Cisco Heat: stage blocks missing: %s (games/cisco_heat.md "Inputs")' % ','.join(missing))
        self.stages, self.smooth, self.screen, self.fast = stages, smooth, screen, fast
        self.fps50 = fps50                      # in-between frames up to 50 a second (v_cad 1), else 25 (2)
        self.car = car                          # the player's car as sprites (with fast); False: its cells red as the game's
        self.hold = hold                        # the loading screen held 4 s or a key after loading; False: none (NXC)
        self.name = 'Cisco Heat smooth engine' + ('' if smooth else ' (in-between frames off)')
        prof = load_profile()
        h = prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        rom = bytes.fromhex(h['rom'])
        self.page = bytearray(8192)
        self.page[:len(rom)] = rom
        self.page = bytes(self.page)
        self.altrom = self.altrom0 = (0x2000, self.syms['rom_end'])
        self.slot1 = (24, self.syms['regblock'])
        self.sites = []
        for a, old, op, sym in prof['sites']:
            old = bytes.fromhex(old)
            self.sites.append((int(a, 16), old, bytes.fromhex(op) + zt.w16(self.syms[sym]) + bytes(len(old) - 3)))
        banks = {}
        for k, pg in zip(STAGE_KEYS, STAGE_PAGES):
            b = bytearray(banks.get(pg >> 1, bytes(16384)))
            b[(pg & 1) * 8192:(pg & 1) * 8192 + 8192] = stage_page(*stages[k])
            banks[pg >> 1] = bytes(b)
        banks[12] = self.page + bytes(8192)
        self.extra_banks = banks

    def variant(self, smooth):
        if smooth == self.smooth:
            return self
        q = copy.copy(self)
        q.smooth = smooth
        return q

    def plain(self):
        """This patch with the fast paths off (the game's own copy and sprite loop run, the car's cells red
        as the game's, no sprites). V1 uses it: its
        interrupt replay counts game instructions, which a fast path does not run; V3 shows the two equal."""
        q = copy.copy(self)
        q.fast = False
        return q

    def hook_ram(self):
        """The initial hook RAM (0x7B00..): zeros, v_en, the DMA program."""
        v = bytearray(HOOK_RAM[1] - HOOK_RAM[0])
        v[V_EN - V] = 1 if self.smooth else 0
        v[V_FAST - V] = 1 if self.fast else 0
        v[V_CAD - V] = 1 if self.fps50 else 2
        mg = self.syms['MG_50' if self.fps50 else 'MG_25']
        v[V_CAD - V + 1:V_CAD - V + 3] = bytes((mg & 255, mg >> 8))
        v[V_CAR - V] = 1 if self.fast and self.car else 0
        t = self.syms['dma_tpl'] - 0x2000
        v[V_DMA - V:V_DMA - V + DMA_LEN] = self.page[t:t + DMA_LEN]
        return bytes(v)

    def patch_banks(self, banks):
        """Sites + hook RAM into a list/dict of 8 banks (bytearrays), in place. Refuses differing bytes."""
        for a, old, new in self.sites:
            bank = 5 if a < 0x8000 else 2
            off = a & 0x3FFF
            if bytes(banks[bank][off:off + len(old)]) != old:
                raise ValueError('Cisco Heat site %04X: %s, expected %s' % (a, bytes(banks[bank][off:off + len(old)]).hex(),
                                                                           old.hex()))
            banks[bank][off:off + len(new)] = new
        lo, hi = HOOK_RAM[0] - 0x4000, HOOK_RAM[1] - 0x4000
        # leftover bytes there: never read or written by the game in the six recordings (games/cisco_heat.md)
        banks[5][lo:hi] = self.hook_ram()
        if any(banks[6]):
            raise ValueError('Cisco Heat: bank 6 (the in-between frames\' save area) is not free')

    def apply(self, snap):
        if not snap.is128 or not is_cisco_heat(snap):
            raise ValueError('Cisco Heat: not the 128K game')
        banks = {n: bytearray(snap.banks[n]) for n in range(8)}
        self.patch_banks(banks)
        for n in range(8):
            snap.banks[n] = bytes(banks[n])
        self.set_boot(snap)
        if self.screen is not None:
            self.extra_banks[SCR_PAGE >> 1] = bytes(8192) + bytes(snap.banks[5][:6912]) + bytes(8192 - 6912)
        self.original_pc = snap.pc
        snap.pc = self.syms['boot_resume']

    def set_boot(self, snap):
        """The boot continuation's data: the snapshot's 0x5B00-0x5BFF, its IFF and PC."""
        page = bytearray(self.page)
        a = self.syms['printer_saved'] - 0x2000
        page[a:a + 256] = snap.banks[5][0x1B00:0x1C00]
        page[self.syms['boot_iff'] - 0x2000] = 0xFB if snap.iff1 else 0x00
        page[self.syms['boot_scr'] - 0x2000] = 1 if self.screen is not None else 0
        page[self.syms['boot_shadow'] - 0x2000] = 0x40 if snap.port7ffd & 8 else 0
        if not self.hold:
            page[self.syms['boot_frames'] - 0x2000] = 0
        a = self.syms['boot_jump'] - 0x2000
        page[a + 1:a + 3] = zt.w16(snap.pc)
        self.page = bytes(page)
        self.extra_banks[12] = self.page + bytes(8192)


def find_screen(directory):
    """The loading screen beside the snapshot, or None. A different file is refused."""
    p = Path(directory) / LOAD_SCREEN
    if not p.is_file():
        return None
    data = p.read_bytes()
    if hashlib.md5(data).hexdigest() != LOAD_MD5:
        raise ValueError("%s is not the tape's loading screen (MD5 %s)" % (p.name, LOAD_MD5))
    return data


def with_screen(raw, screen):
    """The .nex with the loading screen: in the header (byte 10 = 2: NEXLOAD shows it before the banks), in the
    file's bank 5 too (loaded first, it would replace the picture; boot_resume puts the snapshot's bytes back from
    SCR_PAGE). After loading, boot_resume keeps it 4 s or until a key (START_DELAY 0: no NEXLOAD wait)."""
    raw = bytearray(raw)
    if raw[10] != 0 or len(screen) != 6912 or not raw[18 + 5] or zt.BANK_FILE_ORDER[0] != 5:
        raise ValueError('Cisco Heat: expected a .nex without a screen, bank 5 first, and a 6,912-byte screen')
    raw[10] = 2
    raw[133] = START_DELAY
    raw[512:512 + 6912] = screen
    return bytes(raw[:512]) + screen + bytes(raw[512:])


def build(z80, out, stages=None, smooth=True, screen=None, **kw):
    """kw: Patch's fps50, car, hold (the NXC menu's toggles and its build: games/cisco_heat.md "NXC patch")."""
    stages = stages if stages is not None else find_stages(Path(z80).resolve().parent)
    patch = Patch(stages, smooth, screen, **kw)
    zt.convert(str(z80), str(out), quiet=True, patch=patch)
    if screen is not None:
        Path(out).write_bytes(with_screen(Path(out).read_bytes(), screen))
    return patch


def boot_check(nex, z80, patch):
    """The converter's loader and NEXLOAD, to the game's PC: registers with R, the mapped 48K against the patched
    snapshot (the tail's bytes in the hook RAM excepted), unmapped banks, the stage pages, both alt ROM images."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    tail = zt.build_tail(s, TAIL_ADDR, patch.slot1, True)[0]
    copy.copy(patch).apply(s)
    s.pc = patch.original_pc
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255,
            26: s.iff1, 27: s.im}
    bad = []
    banks, _, _ = nextboot.load_nex(str(nex))
    for b in (1, 3, 4, 6, 7):
        if b != s.port7ffd & 7 and bytes(banks[b]) != bytes(s.banks[b]):
            bad.append(('unmapped bank', b))
    for b, data in patch.extra_banks.items():
        if bytes(banks[b]) != bytes(data):
            bad.append(('extra bank', b))
    for nexload in (False, True):
        st = nextboot.boot(str(nex), s.pc, nexload=nexload)
        bad += [('loader', nexload) + tuple(x) for x in st['bad']]
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 0x10000):
            if TAIL_ADDR <= a < TAIL_ADDR + len(tail) or V + 60 <= a < V + 63:    # tail; HLIB_V_R (boot_resume)
                continue
            v = _read(s.banks, s.port7ffd, a)
            if st['mem'][a] != v:
                bad.append(('RAM', nexload, hex(a), v, st['mem'][a]))
                if len(bad) > 20:
                    return bad
        rp = copy.copy(patch)
        page = bytearray(patch.page)
        block = zt.build_tail(zt.Z80Snapshot(str(z80)), TAIL_ADDR, patch.slot1, True)[3]
        page[patch.syms['regblock'] - 0x2000:patch.syms['regblock'] - 0x2000 + len(block)] = block
        rp.page = bytes(page)
        for n, img in ((0, nextboot.alt_image0(rp)), (1, nextboot.alt_image(rp))):
            if bytes(st['alt'][n]) != bytes(img):
                bad.append(('hidden ROM', nexload, n))
    return bad


# ----------------------------------------------------------------------------------------------- simulation

def _sim_class():
    from .dizzy6 import _rw_simulator
    return _rw_simulator()


class NextMem(object):
    """128K memory as the Next maps it for this game: 7FFD paging (bank at 0xC000, ROM 0/1 = alt images 0/1),
    MMU slot 0 = a RAM page when NextReg 0x50 is not 0xFF. pages: {page: bytearray(8192)} beyond the 128K."""

    def __init__(self, banks, o7ffd, roms, pages):
        self.banks = [bytearray(b) for b in banks]
        self.roms = [bytearray(r) for r in roms]
        self.pages = pages
        self.mmu0 = 0xFF
        self.o7ffd = o7ffd
        self.map = [None] * 4
        self.out7ffd(o7ffd)

    def out7ffd(self, v):
        self.mmu0 = 0xFF                # the Next: a 7FFD write maps ROM back into slots 0-1 (z80tonex build_tail)
        self.o7ffd = v
        self.map = [self.roms[(v >> 4) & 1], self.banks[5], self.banks[2], self.banks[v & 7]]

    def _page(self, p):
        if p < 16:
            b = self.banks[p >> 1]
            return memoryview(b)[(p & 1) * 8192:(p & 1) * 8192 + 8192]
        return (self.pages.get(p) or self.pages.setdefault(p, bytearray(8192)))

    def __getitem__(self, a):
        if a < 0x2000 and self.mmu0 != 0xFF:
            return self._page(self.mmu0)[a]
        return self.map[a >> 14][a & 0x3FFF]

    def __setitem__(self, a, v):
        if a < 0x4000:
            if a < 0x2000 and self.mmu0 != 0xFF:
                self._page(self.mmu0)[a] = v
            return
        self.map[a >> 14][a & 0x3FFF] = v

    def __len__(self):
        return 65536


class Model(hooklib.NextModel):
    """NextModel + this game's machine: 7FFD paging, MMU slot 0, ports logged (AY, ULA), no keys pressed."""

    def __init__(self, sim, mem, line=0):
        self.mem = mem
        self.log = []
        super().__init__(sim, speed=0, t_line=228, lines=311, fast=FAST, line=line)
        self.dma.stall = self._stall

    def _stall(self, n):
        """A DMA job holds the CPU: DMA_CYCLES 28 MHz cycles a byte (counted as CPU T at the current clock)."""
        self.R[hooklib.T] += DMA_CYCLES * n

    def nextreg(self, reg, v):
        if reg == 0x50:
            self.mem.mmu0 = v
        super().nextreg(reg, v)

    def read_port(self, regs, port):
        if port & 0xFF in (0x3B,):
            return super().read_port(regs, port)
        if port & 0xFF == 0x1F:
            return 0
        return 0xFF

    def write_port(self, regs, port, value, *x):
        if port & 0x8002 == 0:
            self.mem.out7ffd(value)
            self.log.append(('7ffd', value))
        elif port & 0xC002 == 0xC000:
            self.log.append(('ay sel', value))
        elif port & 0xC002 == 0x8000:
            self.log.append(('ay', value))
        elif port & 1 == 0:
            self.log.append(('fe', value & 0x18))
        else:
            super().write_port(regs, port, value, *x)


class Machine(object):
    """One run from a captured state (state: {'regs', 'o7ffd', 'banks'} at 0x8BDE, outside the handler).
    patch None: the original. ints: None = interrupts by the clock (every FRAME of real time, from `line`);
    a list = interrupts at those counts of game instructions (counted outside the hook ROM, the sites and the
    handler). rseq: the values the LD A,R at R_SITES return."""

    def __init__(self, state, patch=None, smooth=False, line=0, ints=None, rseq=None, img=None):
        banks = [bytearray(b) for b in state['banks']]
        if patch is not None:
            q = patch.variant(smooth)
            q.patch_banks(banks)
            for n, b in getattr(patch, 'break_banks', {}).items():      # negative controls
                banks[n][:] = b
            roms = img or _images(patch)
            pages = {pg: bytearray(stage_page(*patch.stages[k])) for k, pg in zip(STAGE_KEYS, STAGE_PAGES)}
        else:
            roms, pages = (zt.rom128_0(), zt.rom48()), {}
        self.mem = NextMem(banks, state['o7ffd'], roms, pages)
        self.sim = _sim_class()(self.mem, {}, config={'int_active': 0})
        self.R = self.sim.registers
        self.R[:] = list(state['regs'])
        self.model = Model(self.sim, self.mem, line)
        self.patched = patch is not None
        self.ints, self.rseq, self.rk = ints, rseq or [0], 0
        self.next_int = (int(self.model.now()) // FRAME + 1) * FRAME
        self.game = 0              # game instructions run
        self.taken = []            # game-instruction count at each interrupt taken
        self.isr = []              # (return PC, SP) of the handlers running
        self.c = collections.Counter()
        self.dbg = None
        self.watch, self.events = None, []      # diagnostics: PCs to time
        self.skip = _site_bytes()

    def _interrupt(self, prev):
        R = self.R
        ret, sp = R[24], R[12]
        if self.sim.accept_interrupt(R, self.mem, prev):
            self.isr.append((ret, sp))
            self.taken.append(self.game)
            return True
        return False

    def run(self, stop_pc, limit=60_000_000):
        """Run to stop_pc at the starting SP + 2 (the race loop's return), interrupts as configured."""
        R, m, ops, model = self.R, self.mem, self.sim.opcodes, self.model
        stop_sp = R[12] if stop_pc == 0x8BE1 else None
        pend, prev, n = None, R[24], 0
        ints = list(self.ints) if self.ints is not None else None
        while True:
            pc = R[24]
            if self.isr and pc == self.isr[-1][0] and R[12] == self.isr[-1][1]:
                self.isr.pop()
            in_isr = bool(self.isr)
            if ints is None:
                now = model.now()
                if now >= self.next_int:
                    pend = self.next_int
                    self.next_int += FRAME
                    while self.next_int <= now:
                        self.next_int += FRAME
                        self.c['interrupt lost (clock)'] += 1
                if pend is not None:
                    if R[26] and self._interrupt(prev):
                        pend = None
                        continue
                    if model.now() - pend > 32:
                        self.c['interrupt lost (DI)'] += 1
                        if self.dbg is not None:
                            self.dbg.append((pc, R[26], pend))
                        pend = None
            elif ints and not in_isr and self.game >= ints[0]:
                if R[26] and self._interrupt(prev):
                    ints.pop(0)
                    continue
            if pc == stop_pc and not in_isr and (stop_sp is None or R[12] == stop_sp):
                if ints:
                    self.c['interrupts left at the stop'] += 1
                    self._interrupt(prev)
                    ints.pop(0)
                    continue
                return
            if not in_isr and pc not in self.skip and not (0x2000 <= pc < 0x4000):
                self.game += 1
            if self.watch is not None and pc in self.watch:
                self.events.append((pc, model.now()))
            prev = pc
            ops[m[pc]]()
            if pc in R_SITES and m[pc] == 0xED:
                a = self.rseq[self.rk % len(self.rseq)]
                self.rk += 1
                R[0] = a
                R[1] = (R[1] & 1) | (a & 0xA8) | (0x40 if a == 0 else 0) | (4 if R[26] else 0)
            n += 1
            if n > limit:
                raise RuntimeError('no return to %04X (PC %04X)' % (stop_pc, R[24]))

    def peek(self, a):
        return self.mem[a]

    def hook(self, off):
        return self.mem.banks[5][V - 0x4000 + off]


_CACHE = {}


def _site_bytes():
    if 'sites' not in _CACHE:
        _CACHE['sites'] = frozenset(int(a, 16) + i for a, old, op, sym in load_profile()['sites']
                                    for i in range(len(old) // 2))
    return _CACHE['sites']


def _images(patch):
    key = ('img', hashlib.md5(patch.page).hexdigest())
    if key not in _CACHE:
        from . import nextboot
        _CACHE[key] = (bytes(nextboot.alt_image0(patch)), bytes(nextboot.alt_image(patch)))
    return _CACHE[key]


def _mem_diff(a, b, skip=lambda bank, off: False, limit=8):
    """[(bank, offset, a, b)] over the 8 banks."""
    out = []
    for n in range(8):
        x, y = a.mem.banks[n], b.mem.banks[n]
        if x == y:
            continue
        for i in range(16384):
            if x[i] != y[i] and not skip(n, i):
                out.append((n, i, x[i], y[i]))
                if len(out) >= limit:
                    return out
    return out


def _hookram(n, i):
    """Hook RAM and the patched site bytes (the original's code there differs by construction)."""
    if n in (2, 5) and (0x4000 if n == 5 else 0x8000) + i in _site_bytes():
        return True
    if n == 2 and (HANDLER_SCRATCH[0] <= 0x8000 + i < HANDLER_SCRATCH[1] or SP_SCRATCH[0] <= 0x8000 + i < SP_SCRATCH[1]):
        return True
    return n == 5 and HOOK_RAM[0] - 0x4000 <= i < HOOK_RAM[1] - 0x4000


def _dead_stack(sp):
    def f(n, i):
        a = 0x4000 + i
        return n == 5 and 0x7F01 <= a < sp
    return f


def _display(n, i):
    if any(n == b and lo <= i < hi for b, lo, hi in SCREENS):
        return True
    return n == 5 and 0x4000 + i in DISPLAY or n == 6


def case_v1(patch, state, line=0, rseq=None):
    """The real update: patched (smooth off) vs the original. -> list of problems."""
    rseq = rseq or [(37 * k + 11) & 0xFF for k in range(97)]
    p = Machine(state, patch.plain(), smooth=False, line=line, rseq=rseq)
    p.run(0x8BE1)
    o = Machine(state, None, ints=p.taken, rseq=rseq)
    o.run(0x8BE1)
    bad = []
    bad += [('register', i, o.R[i], p.R[i]) for i in CMP if i not in (25, 29) and o.R[i] != p.R[i]]
    sp = p.R[12]
    bad += [('RAM',) + d for d in _mem_diff(o, p, lambda n, i: _hookram(n, i) or n == 6 or _dead_stack(sp)(n, i))]
    lo = [x for x in o.model.log if x[0] != 'nr']
    lp = [x for x in p.model.log if x[0] != 'nr']
    if lo != lp:
        bad.append(('ports', len(lo), len(lp)))
    if p.rk != o.rk:
        bad.append(('R reads', o.rk, p.rk))
    for k, v in p.c.items():
        bad.append(('patched ' + k, v))
    return bad, p, o


def case_v2(patch, state, line=0, rseq=None):
    """The in-between frames: smooth on vs off, same start. -> (problems, on machine, off machine)."""
    rseq = rseq or [(53 * k + 7) & 0xFF for k in range(89)]
    on = Machine(state, patch, smooth=True, line=line, rseq=rseq)
    on.run(0x8BE1)
    off = Machine(state, patch, smooth=False, line=line, rseq=rseq)
    off.run(0x8BE1)
    bad = []
    bad += [('register', i, off.R[i], on.R[i]) for i in CMP if i not in (25, 29) and off.R[i] != on.R[i]]
    sp = on.R[12]
    bad += [('RAM',) + d for d in _mem_diff(off, on, lambda n, i: _hookram(n, i) or _display(n, i) or
                                             _dead_stack(sp)(n, i))]
    snd = lambda m: [x for x in m.model.log if x[0] != '7ffd']
    if snd(on) != snd(off):
        bad.append(('sound ports', len(snd(off)), len(snd(on))))
    if abs(on.model.now() - off.model.now()) > 228 * 4:
        bad.append(('return time', off.model.now(), on.model.now()))
    if on.c != off.c:
        bad.append(('interrupts', dict(off.c), dict(on.c)))
    return bad, on, off


def spec_stats(m):
    """Diagnostics of a smooth run from hook RAM: (spec frames, aborted, late presents)."""
    return m.hook(33), m.hook(34), m.hook(35)


# ----------------------------------------------------------------------------------------------- verify

def capture(rzx_path, every=25, stop=None):
    """States at 0x8BDE (outside the handler), every `every`th update of a recording."""
    from .simrun import play_rzx
    out = []

    class H(object):
        def __init__(s):
            s.ist, s.n = [], 0

        def on_sim(s, sim):
            s.sim = sim

        def on_desync(s, f, msg):
            raise RuntimeError('%s: replay desynchronised at frame %d (%s)' % (rzx_path, f, msg))

        def on_interrupt(s, sim, prev):
            s.ist.append((sim.registers[24], sim.registers[12]))

        def before(s, pc):
            R = s.sim.registers
            if s.ist and pc == s.ist[-1][0] and R[12] == s.ist[-1][1]:
                s.ist.pop()
            if pc == 0x8BDE and not s.ist:
                s.n += 1
                if s.n % every == 0:
                    m = s.sim.memory
                    out.append({'regs': list(R), 'o7ffd': m.o7ffd, 'banks': [bytes(b) for b in m.banks]})
    play_rzx(rzx_path, H(), stop=stop)
    return out


def check_state(patch, st, k, c, examples, keep=5):
    line = (k * 97) % 311
    bad1 = case_v1(patch, st, line)[0]
    bad2, on, off = case_v2(patch, st, line)
    ns, nab, nlate = spec_stats(on)
    c['cases'] += 1
    c['in-between frames'] += ns
    c['in-between aborted'] += nab
    c['in-between late'] += nlate
    for key, bad in (('real update', bad1), ('in-between', bad2)):
        if bad:
            c[key + ' mismatch!'] += 1
            if len(examples.setdefault(key, [])) < keep:
                examples[key].append((k, bad[:6]))
        else:
            c[key + ' exact'] += 1


def verify(patch, rzx_path, stop=None, collect=0, progress=None, every=25):
    """V1 + V2 on every `every`th race update of the recording. -> (Counter, examples, states)."""
    states = capture(rzx_path, every, stop)
    c, examples = collections.Counter(), {}
    for k, st in enumerate(states):
        check_state(patch, st, k, c, examples)
        if progress and k % 10 == 9:
            progress('%s %d/%d' % (Path(rzx_path).name, k + 1, len(states)))
    return c, examples, states[:collect] if collect else []


# ----------------------------------------------------------------------------------------------- unit tests

def unit_tests(patch, states, neg=True):
    """Stage loads (each block lands as the snapshot holds it, loader exit carry), the pace formula against the
    asm, and the negative controls: a W range left out must fail V2, no supplied R must fail V1."""
    c = collections.Counter()
    patch.unit_failures = []
    for key in STAGE_KEYS:
        hdr, data = patch.stages[key]
        if _md5(hdr, data) != STAGE_MD5.get(key):
            c['stage md5!'] += 1
        ok = _t_load(patch, key, states[0] if states else None)
        c['stage load ' + ('exact' if ok is True else 'differs!')] += 1
        if ok is not True:
            patch.unit_failures.append(('load', key, ok))
    if states:
        for shown in (0, 8):
            ok = _t_copy(patch, states[0], shown)
            c['copy DMA = LDI ' + ('exact' if ok is True else 'differs!')] += 1
            if ok is not True:
                patch.unit_failures.append(('copy', shown, ok))
    if states:
        for st in states[::max(1, len(states) // 6)]:
            for call in sprite_calls(patch, st):
                bad = t_sprite(patch, call)
                c['sprite fast = game ' + ('exact' if not bad else 'differs!')] += 1
                if bad:
                    patch.unit_failures.append(('sprite', bad[:4]))
            for call in car_calls(patch, st):
                bad = t_car(patch, call)
                c['car sprites = blit ' + ('exact' if not bad else 'differs!')] += 1
                if bad:
                    patch.unit_failures.append(('car', bad[:4]))
    if neg and states:
        st = states[len(states) // 2]
        nb = negative_patch(patch)
        for cand in states[::-1]:            # a state whose in-between frames run (speed above 0)
            bad, on, off = case_v2(nb, cand, 50)
            if spec_stats(on)[0]:
                break
        else:
            bad = None
        c['negative W' + (' caught' if bad else ' missed!' if bad is not None else ' no spec frames!')] += 1
        p = Machine(st, patch, smooth=False, line=50, rseq=[1, 2, 3])
        p.run(0x8BE1)
        o = Machine(st, None, ints=p.taken, rseq=[200, 100, 50])
        o.run(0x8BE1)
        diff = _mem_diff(o, p, lambda n, i: _hookram(n, i) or n == 6 or _dead_stack(p.R[12])(n, i), 1)
        c['negative R' + (' caught' if (diff or p.rk == 0) else ' missed!')] += 1
    return c


def _t_copy(patch, st, shown):
    """h_copy (site 0x8847) on a random back buffer, zxnDMA vs the game's LDI copy: the screen written (bank 5
    or 7 as 0x5B8B selects), A and the flags, the bytes around it. -> True or the difference."""
    import random
    rnd = random.Random(shown + 1)
    buf = bytes(rnd.randrange(256) for _ in range(0x1B00))
    out = []
    for cpm in (1, 0):
        m = Machine(st, patch, smooth=False, ints=[])
        R, mem = m.R, m.mem
        mem.banks[5][0x2000:0x3B00] = buf
        mem.banks[5][0x5B8B - 0x4000] = shown
        mem[V_FAST] = cpm
        if shown:                                   # registers: A 0, F 1, D 4, E 5, H 6, L 7, SP 12, PC 24
            R[0], R[6], R[7], R[4], R[5] = 0, 0x60, 0, 0x40, 0
        else:
            mem.out7ffd((mem.o7ffd & 0xF8) | 0x17)
            R[0], R[6], R[7], R[4], R[5] = 8, 0x60, 0, 0xC0, 0
        R[1] = 0x55
        mem[0x5CFE], mem[0x5CFF] = 0x4A, 0x88
        R[12] = 0x5CFE
        R[24] = patch.syms['h_copy']
        t0 = R[25]
        m.run(0x884A)
        out.append((bytes(mem.banks[5][:0x1B00]), bytes(mem.banks[7][:0x1B00]), R[0], R[1], R[12], R[25] - t0))
    d, l = out
    if d[5] * 5 > l[5] * 4:
        return 'the DMA path did not run (%d T against %d)' % (d[5], l[5])
    if d[:5] == l[:5]:
        return True
    return [(k, d[k] == l[k]) for k in range(5)]


def sprite_calls(patch, st, n=8, pc=0x9144):
    """Machine states at a fast path's routine entry (the sprite blit 0x9144, the plot 0xA7F1; outside the
    interrupt handler) in a plain update."""
    m = Machine(st, patch.plain(), smooth=False, line=50)
    out = []

    class L(list):
        def append(s, x):
            if len(out) < n and not m.isr:
                banks = [bytearray(b) for b in m.mem.banks]
                for a, old, new in patch.sites:              # the game as it was (Machine patches it again)
                    banks[5 if a < 0x8000 else 2][a & 0x3FFF:(a & 0x3FFF) + len(old)] = old
                banks[6][:] = bytes(16384)
                out.append({'regs': list(m.R), 'o7ffd': m.mem.o7ffd, 'banks': [bytes(b) for b in banks]})
    m.watch, m.events = {pc}, L()
    m.run(0x8BE1)
    return out


def t_sprite(patch, call):
    """One routine call (a sprite_calls state) to its return, fast path vs the game's code, no interrupts.
    -> list of differences (registers but T, RAM but hook RAM and the stack below SP)."""
    ms = []
    for q in (patch, patch.plain()):
        m = Machine(call, q, smooth=False, ints=[])
        ret = m.mem[m.R[12]] | m.mem[m.R[12] + 1] << 8
        m.run(ret)
        ms.append(m)
    f, o = ms
    bad = [('register', i, o.R[i], f.R[i]) for i in CMP if i not in (25, 29) and o.R[i] != f.R[i]]
    bad += [('RAM',) + d for d in _mem_diff(o, f, lambda n, i: _hookram(n, i) or _dead_stack(f.R[12])(n, i))]
    return bad


CAR_DRAW = 0x8F48                               # the player's car: two blits (0x9042, 0x90C0), red ink (0x9078)
CAR_VIEW = (24, 231, 48, 151)                   # asm car_present: the clip window stays inside the road view


def car_calls(patch, st, n=1):
    """Machine states at the car routine 0x8F48 in a plain update."""
    return sprite_calls(patch, st, n, CAR_DRAW)


def car_pixels(model, clip):
    """The visible 4-bit sprites' non-transparent pixels inside clip (x1, x2, y1, y2) as screen (x, y); X mirror
    honoured (the car's only transform)."""
    px = set()
    x1, x2, y1, y2 = clip
    for a in model.attrs:
        if not a[3] & 0x80:
            continue
        x, y = a[0] | (a[2] & 1) << 8, a[1]
        base = (a[3] & 63) * 256 + (128 if a[4] & 0x40 else 0)
        for r in range(16):
            for c in range(16):
                b = model.pattern[base + r * 8 + c // 2]
                if (b >> 4 if c % 2 == 0 else b) & 15:
                    q = (x + (15 - c if a[2] & 8 else c) - 32, y + r - 32)      # attribute 2 bit 3: X mirror
                    if x1 <= q[0] <= x2 and y1 <= q[1] <= y2:
                        px.add(q)
    return px


def t_car(patch, call):
    """The car routine on a clear back buffer (pixels 0, attributes paper 5 ink 0), the game's code (red ink
    into the car's cells) against the car as sprites (car_note, car_present, car_flip in the model): the
    sprites show exactly the car pixels the game makes red (inside the road view), the attributes stay.
    -> list of differences (t_car.red: the red pixels compared)."""
    out = []
    for q, on in ((patch.plain(), 0), (patch, 1)):
        m = Machine(call, q, smooth=False, ints=[])
        mem, R = m.mem, m.R
        for a in range(0x6000, 0x7800):
            mem[a] = 0
        for a in range(0x7800, 0x7B00):
            mem[a] = 0x28
        mem[V_CAR], mem[V_CAR + 2] = on, on
        m.run(mem[R[12]] | mem[R[12] + 1] << 8)
        ula = bytes(mem[a] for a in range(0x6000, 0x7B00))
        if on:
            for sym in ('car_present', 'car_flip'):
                R[12] = (R[12] - 2) & 0xFFFF
                mem[R[12]], mem[R[12] + 1] = 0x00, 0xFF
                R[24] = patch.syms[sym]
                while R[24] != 0xFF00:
                    m.sim.opcodes[mem[R[24]]]()
            clip = tuple(mem[patch.syms['c_cpd'] + k] for k in range(4))
            sh = patch.syms['c_sh']                      # the shown frame's two parts (CP_LEN 7)
            red = car_pixels(m.model, clip) if mem[sh] or mem[sh + 7] else set()
        else:
            x1, x2, y1, y2 = CAR_VIEW
            red = set()
            for i in range(0x1800):
                y, cx = i >> 5, i & 31
                if not ula[0x1800 + (y >> 3) * 32 + cx] & 2:
                    continue
                for k in range(8):
                    if ula[i] & 0x80 >> k and x1 <= cx * 8 + k <= x2 and y1 <= y <= y2:
                        red.add((cx * 8 + k, y))
        out.append((ula, red))
    (uo, ro), (uf, rf) = out
    bad = []
    if uf[:0x1800] != uo[:0x1800]:
        bad.append(('pixels differ',))
    if any(v != 0x28 for v in uf[0x1800:]):
        bad.append(('attributes changed',))
    bad += sorted((p, p in ro, p in rf) for p in ro ^ rf)
    t_car.red = len(ro)
    return bad


def _t_load(patch, key, st):
    """h_load from a state with the stage digit set: bank 1 and the header copy as the stage snapshot has them."""
    if st is None:
        return 'no state'
    hdr, data = patch.stages[key]
    st = dict(st)
    banks = [bytearray(b) for b in st['banks']]
    banks[2][G_STAGE - 0x8000] = ord(key)
    st['banks'] = banks
    m = Machine(st, patch, smooth=True)
    m.mem.out7ffd((m.mem.o7ffd & 0xF8) | 0x11)
    R = m.R
    R[26] = 1
    sp = (R[12] - 2) & 0xFFFF
    m.mem[sp], m.mem[sp + 1] = 0x00, 0xFF      # return to 0xFF00 (a stop)
    R[12], R[24] = sp, patch.syms['h_load']
    n = 0
    while R[24] != 0xFF00:
        m.sim.opcodes[m.mem[R[24]]]()
        n += 1
        if n > 200000:
            return 'no return'
    b1 = m.mem.banks[1]
    if bytes(b1[:len(data)]) != data:
        return 'bank 1'
    if bytes(m.mem.banks[2][G_HDR - 0x8000:G_HDR - 0x8000 + 16]) != hdr:
        return 'header'
    if not R[1] & 1:
        return 'carry'
    if m.mem.mmu0 != 0xFF or not R[26]:
        return 'mmu0 / iff'
    return True


def negative_patch(patch):
    """A broken build from its own table: the in-between frames' save table (wtab) keeps 1 byte of the main
    variables range 0x5B90-0x5F7F, so a spec frame's writes there are not put back."""
    q = Patch(patch.stages, patch.smooth)
    page = bytearray(q.page)
    i = q.syms['wtab'] - 0x2000
    while page[i] | page[i + 1]:
        if page[i] | page[i + 1] << 8 == 0x5B90:
            page[i + 2:i + 4] = zt.w16(1)
            break
        i += 5
    else:
        raise ValueError('wtab has no 0x5B90 range')
    q.page = bytes(page)
    return q


# ----------------------------------------------------------------------------------------------- auto

def auto(a, z80, name, out, say):
    """Smooth build (default) and the in-between-frames-off build, boot checks, V1/V2 on each `a.rzx`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for key, value in dict(publisher=PUBLISHER, title='Cisco Heat', fix_label='Smooth').items():
        if not getattr(a, key, None):
            setattr(a, key, value)
    say('Game      : %s' % name)
    stages = find_stages(Path(z80).resolve().parent)
    missing = [k for k in STAGE_KEYS if k not in stages]
    if missing:
        say('Inputs    : stage blocks %s not found beside the snapshot (games/cisco_heat.md "Inputs")' % ','.join(missing))
        say('Result    : FAILED')
        return False
    screen = find_screen(Path(z80).resolve().parent)
    say('Screen    : %s' % ('%s (4 s after loading, or a key)' % LOAD_SCREEN if screen else
                            'none (%s not beside the snapshot)' % LOAD_SCREEN))
    ok = True
    patches = []
    for label, suffix, smooth in (('Smooth', '', True), ('Plain', '_orig_pace', False)):
        nex = out / (name + suffix + '.nex')
        p = build(z80, nex, stages, smooth, screen)
        bad = boot_check(nex, z80, p)
        ok &= not bad
        patches.append(p)
        say('%-10s: %s %s boot %s' % (label, nex.name, hashlib.md5(nex.read_bytes()).hexdigest(),
                                      'OK' if not bad else str(bad[:3])))
    states = []
    for rec in list(getattr(a, 'rzx', None) or []):
        c, ex, st = verify(patches[0], rec, stop=getattr(a, 'quick', None), collect=3,
                           progress=lambda s: say('Progress  : ' + s))
        states += st
        ok &= not any(v for k, v in c.items() if k.endswith('!'))
        say('Verify    : %s %s' % (Path(rec).name, dict(c)))
        (out / (name + '_' + Path(rec).stem + '_verification.json')).write_text(
            json.dumps(dict(counts=c, examples=ex), indent=1, default=str) + '\n')
    if states:
        u = unit_tests(patches[0], states)
        ok &= not any(v for k, v in u.items() if k.endswith('!'))
        say('Unit      : %s' % dict(u))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return bool(ok)
