"""Elite (Firebird 1985), the STANDARD 48K releases: engine 'elite_std'. Additive module: reachable only through
is_elite_std(). games/elite_std.md (design, measurements, milestones); the Russian 128K hack keeps its own engine
'elite' (nexclash/elite.py), its changes are notes for an NXC option (games/elite_hack.md).

Three versions (VERSIONS; games/elite_std.md "## Versions"), each built from its real start (start_state()):
  a     the "[a]" tape: Lenslok, then the entry 0xD07F (title, "Load New Commander (Y/N)?").  Layout A.
  jcv   ELITEJCV / "[Joystick]" tape: a frozen game; its loader sets IM 2, I = 0xFD, SP 0xFFFD and JPs 0xD07F, which
        returns into the title loop ("Press Space, Commander"). Layout A (the [a] code), commander MILICEVIC.
  e128  ELITE128 / the original Firebird tape: a scrambled block, unpacked by USR 28672, entry 0x716B (title,
        "Load New Commander (Y/N)?"). Layout B: the same game assembled at other addresses; still a 48K game.
The game is unchanged in look and pace. The one change is the IM 2 fix where it is needed (layout A: the table at
0xFD00-0xFE00 is not uniform, so the vector 0xFEFE holds only for bus byte 0xFF; CSpect's is not 0xFF): the game's
I = 0xFD -> 0x39 (the version's sites; jcv's start state too) over a uniform table in alt ROM image 1 (Sinclair's 48K
ROM + 317 bytes in its free 0xFF area, asm/elite_std_hooks.asm), vector 0x3A3A = JP 0xFEFE. e128's own table is
uniform (257 x 0xFE): no fix. Also: the title ship redrawn every frame (VERSIONS[v]['ttl']) and the commander save /
load on the SD card instead of tape (VERSIONS[v]['sd']; games/elite_std.md "## SD save"). Verifier:
nexclash/elite_std_verify.py (scripted states, lockstep original vs build; sd_check for the SD hooks).
"""
import hashlib
import json
import os
from pathlib import Path

from . import hooklib

PUBLISHER = 'Firebird, 1985'
CMP = [i for i in hooklib.CMP_R if i != 14]     # not I: 0x39 in the build where the fix applies (elite_std_verify)
ROM_ORG = 0x3900
ALT_PAGE = 24               # 8K page: alt ROM image of 0x2000-0x3FFF (bank 12 lower half)
LOW_PAGE = 25               # 8K page: alt ROM image of 0x0000-0x1FFF (bank 12 upper half)
IM2_I = 0x39
GAME_I = 0xFD
ISR = 0xFEFE                # the game's IM 2 handler in both layouts
LENSLOK_CODE = 0xC799       # [a]: the two characters the Lenslok check expects (0xC664 compares 0xC7A1 with them)

# Per version: entry (start PC), fix sites (LD A,0xFD -> 0x39), tail, and the addresses the verifier and the scripted
# states use: loop = main-loop top (a pass starts; event injection returns here), clear = the buffer clear (once per
# pass), dispatch = the encounter dispatcher (A = event: ships spawned by the game's own code).
VERSIONS = {
    'a': dict(title='Elite ([a] tape, Lenslok)', entry=0xD07F, layout='A',
              sites=((0xD09E, '3efd', '3e39'), (0xFF4C, '3efd', '3e39')),
              tail=0xBE00, loop=0x74E4, clear=0x8080, dispatch=0xB867,
              keys='250-270:N;550-570:SPACE;850-870:1'),          # from the start: title, docked, launch
    'jcv': dict(title='Elite (Joystick / cursor tape)', entry=0xD07F, layout='A',
                sites=((0xFF4C, '3efd', '3e39'),),
                tail=0x5000, loop=0x74E4, clear=0x8080, dispatch=0xB867,
                keys='200-220:SPACE;500-520:1'),
    'e128': dict(title='Elite (original Firebird tape)', entry=0x716B, layout='B', sites=(),
                 tail=0x5000, loop=0x72FD, clear=0x745F, dispatch=0xF2CA,
                 keys='320-340:N;700-720:SPACE;1000-1020:1'),
}
# The NXC toggle "Russian hack gameplay" (games/elite_std.md ## NXC): a layout-A start state with the hack's code and data
# swapped in (C:\1NEXT\elite_work\std\mkhack.py). Same sites and addresses; it starts on the status page (the hack has
# no title), so the keys are jcv's for both. Verified as its own original: build with hooks vs the swapped game.
# The 50 fps title ship (games/elite_std.md "## Smooth title ship"; asm/elite_std_hooks.asm M5): per version the two
# title loops' CALL sites ("Load New Commander (Y/N)?" and "Press Space, Commander"; jcv shows only the second) ->
# (address, original bytes, hook symbol), the routines the hooks call (draw = the ship draw entry after the rotation,
# copy = buffer -> screen, clear, rot = rotate + draw), kf
# = K - 8 in 1/256 (lines at 3.5 MHz per line at 28 MHz: the pass length log in CSpect against the original's mean
# frames per pass, 8.68 / 10.90 / 10.86: K = 8.27 / 8.28 / 8.29), rng = the draw's work bytes put back after
# the renders (the slot first; write sets measured with C:/1NEXT/elite_work/std/drawwrites.py, widened).
RNG_A = ((0x6159, 0x28), (0x9C90, 0x10), (0xA6D8, 0x10), (0xA8F0, 0x210), (0xAC98, 0x10), (0xB430, 0xB0),
         (0xBCC0, 0x20))
RNG_B = ((0x6159, 0x28), (0xDA00, 0x20), (0xE218, 0x208), (0xE5C0, 0x10), (0xE910, 0x20), (0xF200, 0xB0))
TS_A = ((0x7378, 'cd8080', 'h_top'), (0x737E, 'cdaf9c', 'h_bg'), (0x7381, 'cdbe7f', 'h_copy'), (0x7384, '3a0dfc', 'h_prea'),
        (0x73C3, 'cd8080', 'h_top'), (0x73C9, 'cdaf9c', 'h_bg'), (0x73CC, 'cdbe7f', 'h_copy'), (0x73CF, '011fff', 'h_prej'))
TS_B = ((0x71A2, 'cd5f74', 'h_top'), (0x71A8, 'cddddf', 'h_bg'), (0x71AB, 'cd9873', 'h_copy'), (0x71AE, '3a13fc', 'h_pree'),
        (0x71E5, 'cd5f74', 'h_top'), (0x71EB, 'cddddf', 'h_bg'), (0x71EE, 'cd9873', 'h_copy'), (0x71F1, '011fff', 'h_prej'))
VERSIONS['a']['ttl'] = dict(sites=TS_A, draw=0xA6DF, copy=0x7FBE, clear=0x8080, rot=0x9CAF, kf=68, rng=RNG_A)
VERSIONS['jcv']['ttl'] = dict(sites=TS_A, draw=0xA6DF, copy=0x7FBE, clear=0x8080, rot=0x9CAF, kf=72, rng=RNG_A)
VERSIONS['e128']['ttl'] = dict(sites=TS_B, draw=0xE008, copy=0x7398, clear=0x745F, rot=0xDFDD, kf=74, rng=RNG_B)
# SD save / load (games/elite_std.md "## SD save"; asm/elite_std_hooks.asm "SD save / load"): the ACCESS MENU's tape
# CALLs -> CALLs of the hooks (load, save), and the "Start Tape, Then Press Any Key" wait before the save -> NOPs.
SD_A = ((0xD954, 'cd6205', 'h_lda'), (0xD99C, 'cdc604', 'h_sva'), (0xD996, 'cdf7e1', None))
SD_B = ((0xD32E, 'cd6205', 'h_ldb'), (0xD376, 'cdc604', 'h_svb'), (0xD370, 'cd48af', None))
VERSIONS['a']['sd'] = VERSIONS['jcv']['sd'] = SD_A
VERSIONS['e128']['sd'] = SD_B
SD_OFF = 0x1000             # the SD code's place in BUF_PG (asm ORG 0x5000: the page at slot 2)
SD_I, SD_VEC = 0x5B, 0x5D5D # the IM 2 table (257 x 0x5D) and its EI / RETI in that page, while esxDOS runs
STATE_BANK = 13             # asm STATE_PG 26 (code, variables, saves) / BUF_PG 27 (the title's background)
# (the hack has no title: no title hooks; its own save / load is disk code at other addresses: no SD hooks)
VERSIONS['a_hack'] = dict(VERSIONS['a'], title='Elite ([a] tape) + Russian hack gameplay', keys='200-220:SPACE;500-520:1',
                          ttl=None, sd=None)
VERSIONS['jcv_hack'] = dict(VERSIONS['jcv'], title='Elite (Joystick tape) + Russian hack gameplay',
                            ttl=None, sd=None)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = {}


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'elite_std.json'), os.path.join(_HERE, 'elite_std.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('elite_std.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def _sigs():
    if 'sig' not in _CACHE:
        _CACHE['sig'] = {v: {int(a, 16): bytes.fromhex(b) for a, b in s.items()}
                         for v, s in load_profile()['versions'].items()}
    return _CACHE['sig']


def _peek_of(snap):
    if hasattr(snap, 'is128'):
        if snap.is128:
            return None
        ram = snap.banks[5] + snap.banks[2] + snap.banks[0]
        return lambda a: ram[a - 0x4000]
    if getattr(snap, 'machine', '48K') != '48K':
        return None
    return lambda a: snap.memory[a]


def version_of(snap):
    """'a' / 'jcv' / 'e128' for a start state of that version (48K, the profile's per-version signature), else None.
    Signatures hold at the start state only (a's 0xD09E init is later overwritten by commander data)."""
    try:
        peek = _peek_of(snap)
        if peek is None:
            return None
        for v, sig in _sigs().items():
            if all(bytes(peek(a + i) for i in range(len(b))) == b for a, b in sig.items()):
                return v
    except (KeyError, TypeError, IndexError, AttributeError):
        pass
    return None


def is_elite_std(snap):
    """A start state of one of the three standard 48K versions (version_of)."""
    return version_of(snap) is not None


class EliteStdPatch:
    def __init__(self, version='a', prof=None):
        from .build import rom48
        self.version = version
        self.v = VERSIONS[version]
        self.name = '%s: the original from its real start, IM 2 fix %s' % (
            self.v['title'], 'on (alt ROM table)' if self.v['sites'] else 'not needed (uniform table)')
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom_code = bytes.fromhex(h['rom'])
        if self.syms['rom_start'] != ROM_ORG:
            raise ValueError('profile rom block does not start at ROM_ORG')
        self.stub_extra = b''
        self.setup_call = None
        self.hook_page_data = b''
        self.uses_printer_buffer = True        # 0x5B00-0x5BFF is read before written (access scans)
        self.keep_printer_buffer = True
        self.tail_addr = self.v['tail']
        self.max_tail = 512
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long (0x3D00-0x3DFF must stay free: BRIEFING A1)')
        rom = rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free (0xFF) in the 48K ROM')
        self.slot1 = (ALT_PAGE, self.regblock)
        self.altrom = (0x2000, 0x4000)          # the whole image is the build's: Sinclair's ROM (layout A calls 0x22B0)
        self.altrom_low = (LOW_PAGE, bytes(rom[:0x2000]))
        hi = bytearray(rom[0x2000:0x4000])
        hi[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(hi)
        self.extra_banks = {12: self.page + self.altrom_low[1]}
        self.sites = [(a, bytes.fromhex(o), bytes.fromhex(n)) for a, o, n in self.v['sites']]
        self.tsites = []                        # the title hooks (CALLs of the same length)
        t = self.v.get('ttl')
        if t:
            self.tsites = [(a, bytes.fromhex(o), bytes([0xCD]) + self.syms[sym].to_bytes(2, 'little'))
                           for a, o, sym in t['sites']]
        self.sdsites = [(a, bytes.fromhex(o), bytes([0xCD]) + self.syms[sym].to_bytes(2, 'little') if sym else bytes(3))
                        for a, o, sym in self.v.get('sd') or ()]
        self.extra_banks[STATE_BANK] = self.state_bank(t)  # also without a title (the hack): the NXC's toggle
                                                            # builds must list the same banks

    def state_bank(self, t):
        """Bank 13 (t = VERSIONS[v]['ttl'] or None): STATE_PG = the hook page (asm, from 0x0000) with prm filled in; BUF_PG = zeros but for the alt ROM's
        0x3900-0x3A3C (IM 2 table, h_isr) at the same place, for interrupts while it is mapped at slot 1."""
        page = bytearray(bytes.fromhex(self.prof['hooks']['page']))
        prm, end = self.syms['prm'], self.syms['prm_end']
        if not t:
            t = dict(draw=0, copy=0, clear=0, rot=0, kf=0, rng=((0x6159, 0x28),))     # never entered
        rng = b''.join(a.to_bytes(2, 'little') + n.to_bytes(2, 'little') for a, n in t['rng'])
        if t['rng'][0] != (0x6159, 0x28) or sum(n for a, n in t['rng']) > 0x400:
            raise ValueError('title ranges: the slot first, 0x400 bytes at most')
        blk = b''.join(t[k].to_bytes(2, 'little') for k in ('draw', 'copy', 'clear', 'rot')) + bytes([t['kf']]) + rng
        if len(blk) + 2 > end - prm:
            raise ValueError('title parameters do not fit prm')
        page[prm:prm + len(blk)] = blk
        st = bytes(page) + bytes(8192 - len(page))
        buf = bytearray(8192)
        buf[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + 0x13D] = self.page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + 0x13D]
        sd = bytes.fromhex(self.prof['hooks']['sd'])
        if self.syms['sd_start'] != 0x4000 + SD_OFF or SD_OFF + len(sd) > ROM_ORG - 0x2000:
            raise ValueError('SD code must sit at BUF_PG 0x1000, below the alt ROM table copy')
        buf[SD_OFF:SD_OFF + len(sd)] = sd
        buf[SD_I * 256 - 0x4000:SD_I * 256 - 0x4000 + 257] = bytes([SD_VEC & 255]) * 257
        buf[SD_VEC - 0x4000:SD_VEC - 0x4000 + 3] = b'\xFB\xED\x4D'      # EI; RETI
        return st + bytes(buf)

    def patch_ram(self, ram, regs=None, check=True):
        """Apply the sites to a 48K RAM image (bytearray of 0x4000-0xFFFF) and, with regs (dict with 'I', 'IM'), the
        running IM 2's I. Used for the start state (apply, check=True: every site's original bytes) and for the
        verifier's mid-game states (check=False: a site the game has since overwritten - [a]'s init 0xD09E becomes
        commander data - is left as the game wrote it, as in the build). -> the sites applied."""
        done = []
        for a, old, new in self.sites + self.tsites + self.sdsites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                if check:
                    raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
                continue
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
            done.append((a, old, new))
        if regs is not None and self.sites and regs['IM'] == 2 and regs['I'] == GAME_I:
            regs['I'] = IM2_I
        return done

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Elite (standard) patch expects a 48K start state (start_state())')
        if snap.pc != self.v['entry']:
            raise ValueError('start state PC 0x%04X, expected the entry 0x%04X' % (snap.pc, self.v['entry']))
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        regs = {'I': snap.i, 'IM': snap.im}
        self.patch_ram(ram, regs)
        snap.i = regs['I']
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])


# ---------------------------------------------------------------------------------------------- start state

def tape_version(tap):
    """The version a .tap holds, from its block lengths (the data block, flag byte and checksum included)."""
    d = open(tap, 'rb').read()
    lens, i = [], 0
    while i + 2 <= len(d):
        n = d[i] | d[i + 1] << 8
        lens.append(n)
        i += 2 + n
    if 49068 in lens:
        return 'a'
    if 42242 in lens:
        return 'jcv'
    if 40803 in lens:
        return 'e128'
    raise ValueError('not a known Elite tape (block lengths %s)' % lens)


def start_state(tap, out_z80, say=print):
    """The real start from a tape: load it (skoolkit tap2sna, 128K machine with the 48K ROM paged, as the tapes
    expect), run to the version's entry and write the 48K .z80. [a]: ENTER at the Lenslok screen, then the code the
    game expects (read from LENSLOK_CODE). Deterministic (no recorded input): the same tape gives the same bytes.
    -> (out_z80, version)."""
    import shutil
    import tempfile
    from skoolkit.tap2sna import main as tap2sna
    from skoolkit.simutils import get_state
    from skoolkit.snapshot import write_snapshot, Snapshot
    from . import simrun
    ver = tape_version(tap)
    v = VERSIONS[ver]
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        shutil.copy(tap, os.path.join(tmp, 'g.tap'))
        os.chdir(tmp)                            # tap2sna reads a drive letter as a URL: relative names only
        tap2sna(['-c', 'machine=128', 'g.tap', 'g.z80'])
        loaded = os.path.join(tmp, 'g.z80')
        os.chdir(cwd)
        keys = ''
        if ver == 'a':
            _, sim = simrun.free_run(loaded, 800, None, keys='420-425:ENTER')
            code = bytes(sim.memory[LENSLOK_CODE + i] for i in range(2)).decode('ascii').upper()
            if len(code) != 2 or not code.isalnum() or \
                    bytes(sim.memory[0xC664 + i] for i in range(3)) != bytes.fromhex('2199c7'):
                raise ValueError('no Lenslok code at 0x%04X after 800 frames (%r)' % (LENSLOK_CODE, code))
            say('Lenslok   : code %s' % code)
            keys = '420-425:ENTER;820-825:%s;840-845:%s' % (code[0], code[1])
        f, sim = simrun.free_run(loaded, 2000, None, keys=keys, stop_pc=v['entry'])
        if sim.registers[24] != v['entry']:
            raise ValueError('the entry 0x%04X was not reached (PC 0x%04X after %d frames)' % (v['entry'], sim.registers[24], f))
        ram, regs, state, machine = get_state(sim)
        mem = sim.memory
        ram48 = list(mem.banks[5]) + list(mem.banks[2]) + list(mem.banks[mem.o7ffd & 7])
        st48 = [x for x in state if not x.startswith(('ay[', '7ffd', 'fffd'))]
        write_snapshot(str(out_z80), ram48, regs, st48, '48K')
        got = version_of(Snapshot.get(str(out_z80)))
        if got != ver:
            raise ValueError('the start state matches version %r, expected %r' % (got, ver))
        say('Start     : %s (%s), entry 0x%04X at frame %d' % (out_z80, ver, v['entry'], f))
        return out_z80, ver
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- build / checks

def _version(z80):
    from skoolkit.snapshot import Snapshot
    v = version_of(Snapshot.get(str(z80)))
    if v is None:
        raise ValueError('%s is not a start state of a standard Elite version' % z80)
    return v


def build(z80, nex, quiet=False):
    from . import z80tonex
    return z80tonex.convert(str(z80), str(nex), patch=EliteStdPatch(_version(z80)), quiet=quiet)


def boot_check(nex, z80, patch):
    """nextboot.check (48K): the loader, with and without NEXLOAD, to the start state's PC; registers, RAM except the
    tail, alt ROM image, paging. -> [problem]."""
    from . import nextboot, z80tonex as zt
    s = zt.Z80Snapshot(str(z80))
    tail = zt.build_tail(s, patch.tail_addr, patch.slot1, True)[0]
    bad = []
    for nexload in (False, True):
        bad += [(nexload,) + tuple(x) if isinstance(x, tuple) else (nexload, x)
                for x in nextboot.check(str(nex), str(z80), patch, (patch.tail_addr, patch.tail_addr + len(tail)),
                                        nexload)]
    return bad


def _fix_problems(banks, extra, version):
    """The IM 2 path as built, for every bus byte: I (the sites' value, or the game's own 0xFD) -> the 257-byte table
    at I * 256 in the image the CPU sees (alt ROM image below 0x4000, RAM above) is uniform, and its vector reaches
    the game's handler 0xFEFE (directly, or by the alt ROM's JP). The rest of the alt ROM = Sinclair's 48K ROM.
    banks: RAM banks 5/2/0; extra: {12: alt ROM bank}. -> [problem]."""
    from .build import rom48
    v = VERSIONS[version]
    bad = []
    ram = bytes(banks[5]) + bytes(banks[2]) + bytes(banks[0])
    img = bytes(extra[12][8192:16384]) + bytes(extra[12][0:8192]) + ram      # 0x0000-0xFFFF as the CPU sees it
    i_val = GAME_I
    for a, old, new in v['sites']:
        got = ram[a - 0x4000:a - 0x4000 + 2]
        if got != bytes.fromhex(new):
            bad.append(('I site', hex(a), got.hex()))
        i_val = bytes.fromhex(new)[1]
    tab = img[i_val * 256:i_val * 256 + 257]
    if len(set(tab)) != 1:
        bad.append(('IM 2 table at 0x%02X00 not uniform' % i_val, sorted(set(tab))[:4]))
    else:
        t = tab[0] * 257
        if t != ISR and img[t:t + 3] != bytes([0xC3, ISR & 255, ISR >> 8]):
            bad.append(('vector 0x%04X' % t, img[t:t + 3].hex()))
    rom = rom48()
    hi = ROM_ORG + len(bytes.fromhex(load_profile()['hooks']['rom']))
    if any(img[a] != rom[a] for a in range(0x4000) if not ROM_ORG <= a < hi):
        bad.append(('alt ROM differs from Sinclair 48K outside the hooks',))
    return bad


def negative_variants(banks, version):
    """The broken builds of the negative controls: (name, banks, {12: alt ROM bank}): one byte of the table the
    version's I selects changed (the alt ROM's, or e128's own in RAM), and (fix versions) the last site left at 0xFD."""
    out = []
    v = VERSIONS[version]
    if v['sites']:
        b12 = bytearray(banks[12])
        b12[ROM_ORG - 0x2000 + 7] ^= 1
        out.append(('table', banks, {12: bytes(b12)}))
        b = dict(banks)
        a = v['sites'][-1][0]
        k, base = {2: (0, 0xC000), 1: (2, 0x8000), 0: (5, 0x4000)}[(a >> 14) - 1]
        bb = bytearray(b[k])
        bb[a - base + 1] = GAME_I
        b[k] = bytes(bb)
        out.append(('site', b, {12: banks[12]}))
    else:
        b = dict(banks)
        bb = bytearray(b[0])
        bb[GAME_I * 256 - 0xC000 + 7] ^= 1
        b[0] = bytes(bb)
        out.append(('table', b, {12: banks[12]}))
    return out


def unit_tests(patch, states=None, neg=True, nex=None):
    """Unit cases on the built .nex: the IM 2 path (_fix_problems); neg: the negative controls (negative_variants)
    must be caught. The lockstep verify of the game itself: elite_std_verify. -> Counter, failures end in '!'."""
    import collections
    from . import nextboot
    c = collections.Counter()
    banks, _, _ = nextboot.load_nex(str(nex))
    extra = {12: banks[12]}
    bad = _fix_problems(banks, extra, patch.version)
    c['im2 path ok' if not bad else 'im2 path!'] += 1
    if patch.sdsites:                       # the SD save / load hooks (elite_std_verify.sd_check), with negatives
        from . import elite_std_verify as V
        sc, _ = V.sd_check(patch, nex, neg=neg)
        c.update(sc)
    if neg:
        for name, nb, ne in negative_variants(banks, patch.version):
            c['neg %s caught' % name if _fix_problems(nb, ne, patch.version) else 'neg %s missed!' % name] += 1
    return c


def verify(patch, z80, rzx=None, frames=None, keys=None, progress=None, quick=False, collect=0):
    """Free-run engine (no RZX of the standard game exists): the lockstep differential test from scripted states
    (nexclash/elite_std_verify.py: its docstring is the method). -> (Counter, examples, states)."""
    from . import elite_std_verify as V
    return V.verify(patch, z80, progress=progress, quick=quick)


def auto(a, z80, name, out, say):
    """The build, its boot checks, the IM 2 unit cases with the negative controls, the lockstep verify from scripted
    states (a.quick: fewer cases). -> True on PASS."""
    from . import z80tonex as zt
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ver = _version(z80)
    for key, value in dict(publisher=PUBLISHER, title='Elite', fix_label='Original').items():
        if not getattr(a, key, None):
            setattr(a, key, value)
    say('Game      : %s' % name)
    say('Engine    : elite_std, version %s: %s' % (ver, VERSIONS[ver]['title']))
    nex = out / (name + '.nex')
    patch = EliteStdPatch(ver)
    zt.convert(str(z80), str(nex), quiet=True, patch=patch)
    nex.write_bytes(zt.automap_off(nex.read_bytes()))
    bad = boot_check(nex, z80, patch)
    say('Plain     : %s %s boot %s' % (nex.name, hashlib.md5(nex.read_bytes()).hexdigest(),
                                       'OK' if not bad else str(bad[:3])))
    u = unit_tests(patch, nex=nex, neg=True)
    say('Unit      : %s' % dict(u))
    ok = not bad and not any(k.endswith('!') for k in u)
    if not getattr(a, 'no_verify', False):
        c, ex, _ = verify(patch, z80, progress=lambda s: say('Progress  : ' + s), quick=bool(getattr(a, 'quick', None)))
        say('Verify    : %s' % dict(c))
        (out / (name + '_verification.json')).write_text(json.dumps(dict(counts=c, examples=ex), indent=1,
                                                                    default=str) + chr(10))
        ok = ok and not any(k.endswith('!') for k in c)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'start':
        start_state(sys.argv[2], sys.argv[3])
    else:
        build(sys.argv[1], sys.argv[2])
