"""Chase H.Q. (Ocean, 1989; 128K): the speed engine with its optional Enhanced colours, as published in .nxc 1.2.
games/chase_hq.md has the design, results and evidence.

One engine, three builds (asm/chase_hq_hooks.asm, CHQ_SET):
- default: Speed (road, scenery and screen copy at 28 MHz, capped at the original's quiet-scene pace), Enhanced off
  (enh_enable 0: no Layer 2, sprites, Copper or row hooks); lists banks 0-45, fits a 1MB Next;
- "Speed" colour set: Enhanced colours at the Speed pace;
- "Orig. pace" colour set: Enhanced colours, the pace target following the original's time for each update.
The colour sets list banks 0-109 (header byte 8 = 1792K): a 2MB Next.

Code: the hidden-ROM page (alt ROM 0x2000-0x3FFF, bank 12: docs/profiles/chase_hq*.json) and the Enhanced code in banks
8 and 28 (asm/chase_hq_banks.asm). Data that is not code - the painted figure, roadside, portrait, dashboard and horizon
pages and their caches (banks 9, 11, 15, 29-43, 46-109) - is Jon Attree's painting compiled over the game's own graphics:
game-derived, so it is a local input, never in this repository. It sits beside the snapshot as ART (chase_hq_art.bin,
MD5 in ART_MD5), with the tape's loading screen (LOAD_SCREEN). Every build carries both, the default too, because the
published bytes do; the default never reads the art pages (Enhanced off).

    python -m nexclash.chase_hq SNAPSHOT OUTDIR       the three builds (ART and LOAD_SCREEN beside SNAPSHOT)

`nexclash.py auto` (nexclash/engines.py: is_chase_hq) builds the three and boot-checks each. The replay, lockstep, pace,
soak and real-loader proofs are the pilot run's (games/chase_hq.md "Evidence"); there is no RZX verifier here yet.
"""
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from . import hooklib
from . import z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / 'docs/profiles'
CMP = tuple(hooklib.CMP_R)
SETS = {'default': 'chase_hq', 'Speed': 'chase_hq_speed', 'Orig. pace': 'chase_hq_orig'}   # set -> its hook profile
OUTPUTS = {'default': 'chase_hq.nex', 'Speed': 'chase_hq_speed.nex', 'Orig. pace': 'chase_hq_orig_pace.nex'}
ART = 'chase_hq_art.bin'
ART_MD5 = '83797b5c34542c17b23d610722d54283'
ART_BANKS = (9, 11, 15) + tuple(range(29, 44)) + tuple(range(46, 110))
ART_STAGE = 1                 # the art's asset caches are the menu snapshot's stage's (0x8007)
LOAD_SCREEN = 'chase_hq_loading.scr'
LOAD_MD5 = 'aed0ca7e0dc3b00f1a0a55c12f5359f6'
ALT_SOURCES = (45, 44)        # z80tonex ROM48_BANK, ROM128_0_BANK: below the default's top bank 45 (1MB Next)
BASE_TOP = 45
PUBLISHER = 'Ocean, 1989'


def _profile_path(name='chase_hq'):
    return PROFILES / (name + '.json')


def load_profile(name='chase_hq'):
    return json.loads(_profile_path(name).read_text())


def is_chase_hq(snap):
    """The 128K release at its main loop (profile signature in bank 2): zt.Z80Snapshot (banks) or skoolkit's Snapshot."""
    sig = {int(a, 16): bytes.fromhex(v) for a, v in load_profile()['signature'].items()}
    banks = getattr(snap, 'banks', None)
    if banks is None:
        if getattr(snap, 'machine', '48K') == '48K':
            return False
        return all(bytes(snap.memory[a:a + len(v)]) == v for a, v in sig.items())
    if not getattr(snap, 'is128', False):
        return False
    try:
        return all(bytes(banks[2][a - 0x8000:a - 0x8000 + len(v)]) == v for a, v in sig.items())
    except (KeyError, TypeError, IndexError):
        return False


def _lut():
    """Bank 14: the ink/paper lookup tables of the Enhanced row plotter (table 1: solid paper for the end label)."""
    lut = bytearray()
    for dark, light in [(1, 255), (100, 172), (12, 56), (255, 0)]:
        for v in range(256):
            lut.extend(dark if v & (128 >> b) else light for b in range(8))
    lut[2048:4096] = bytes(1 if v & (128 >> b) else 31 for v in range(256) for b in range(8))
    return bytes(lut) + bytes([255]) * 8192


class Patch:
    """The z80tonex patch object of one set (SETS). art: the ART file's bytes."""
    uses_printer_buffer = False
    tail_addr = 0x5B00
    max_tail = 128
    stub_extra = b''
    setup_call = None
    hook_page_data = b''

    def __init__(self, cset='default', art=None):
        if art is None or hashlib.md5(art).hexdigest() != ART_MD5:
            raise ValueError('Chase H.Q. needs its art pages %s (MD5 %s) beside the snapshot' % (ART, ART_MD5))
        self.cset = cset
        self.name = 'Chase H.Q. speed engine, %s' % ('Enhanced off' if cset == 'default' else 'Enhanced [%s]' % cset)
        main = load_profile()
        h = load_profile(SETS[cset])['hooks']
        b = load_profile('chase_hq_banks')['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.rom = bytes.fromhex(h['rom'])
        self.slot1 = (24, self.syms['regblock'])
        self.altrom = (0x2000, self.syms['rom_end'])
        self.altrom0 = self.altrom
        self.sites = []
        for a, old, op, sym in main['sites']:
            old = bytes.fromhex(old)
            self.sites.append((int(a, 16), old, bytes.fromhex(op) + zt.w16(self.syms[sym]) + bytes(len(old) - 3)))
        row = [int(a, 16) for a in main['row_sites']]
        self.row_sites = [s for a in row for s in self.sites if s[0] == a]     # installed by colour_init, in this order
        banks = {}
        art = bytes(art)
        for i, n in enumerate(ART_BANKS):
            banks[n] = art[i * 16384:(i + 1) * 16384]
        table = bytearray([len(self.row_sites)])
        for a, old, new in self.row_sites:
            table += bytes([a & 255, a >> 8, len(old)]) + old + new
        hud = bytes.fromhex(b['hud'])
        b8 = bytearray(16384)
        b8[:len(hud)] = hud
        b8[0x1000:0x1000 + len(table)] = table
        banks[8] = bytes(b8)
        b13 = bytearray(zt.rom128_0()[:0x1C00]) + bytes(0x400 + 8192)
        aux = bytes.fromhex(h['aux'])
        b13[0x1100:0x1100 + len(aux)] = aux
        b13[0x1D5B] = ART_STAGE
        banks[13] = bytes(b13)
        banks[14] = _lut()
        for n in range(16, 24):
            banks[n] = bytes(16384)
        patterns = bytes(1 if v & (128 >> (x & 7)) else 0 for v in range(256) for x in range(256))
        for i in range(4):
            banks[24 + i] = patterns[i * 16384:(i + 1) * 16384]
        b28 = bytearray(16384)
        for key, at in (('steering', 0), ('row', 0x800), ('polish', 0x1400), ('motion', 0x2000)):
            code = bytes.fromhex(b[key])
            b28[at:at + len(code)] = code
        banks[28] = bytes(b28)
        self.extra_banks = banks
        self._set_page(self.rom)

    def _set_page(self, rom):
        self.page = rom + bytes(8192 - len(rom))
        self.extra_banks[12] = self.page + bytes(8192)

    def apply(self, snap):
        """Hidden-ROM boot continuation (the printer buffer, the game's PC and interrupt state), then the CALL / JP
        sites the game runs from the start; the row sites are installed by colour_init after the game unpacks its
        plotters (Enhanced only). Refuses a snapshot whose bytes differ at a site."""
        if not snap.is128 or snap.port7ffd != 0:
            raise ValueError('Chase H.Q.: expected the 128K snapshot with bank 0 at 0xC000')
        stage = snap.banks[2][7]
        if (stage if 1 <= stage <= 5 else 1) != ART_STAGE:
            raise ValueError('Chase H.Q.: the art caches are stage %d\'s, the snapshot is at stage %d' % (ART_STAGE, stage))
        rom = bytearray(self.rom)
        a = self.syms['printer_saved'] - 0x2000
        rom[a:a + 256] = snap.banks[5][0x1B00:0x1C00]
        a = self.syms['boot_jump'] - 0x2000
        rom[a + 1:a + 3] = zt.w16(snap.pc)
        rom[self.syms['boot_iff'] - 0x2000] = 0xFB if snap.iff1 else 0
        self.rom = bytes(rom)
        self._set_page(self.rom)
        self.original_pc = snap.pc
        snap.pc = self.syms['boot_resume']
        row = {s[0] for s in self.row_sites}
        for a, old, new in self.sites:
            if a in row:
                continue
            bank = 2 if a < 0xC000 else 0
            off = a & 16383
            b = bytearray(snap.banks[bank])
            if bytes(b[off:off + len(old)]) != old:
                raise ValueError('Chase H.Q. site %04X: %s, expected %s' % (a, b[off:off + len(old)].hex(), old.hex()))
            b[off:off + len(new)] = new
            snap.banks[bank] = bytes(b)


@contextmanager
def _alt_sources():
    """The alt ROM image sources at banks 45/44 (as published), for this build only."""
    saved = zt.ROM48_BANK, zt.ROM128_0_BANK
    zt.ROM48_BANK, zt.ROM128_0_BANK = ALT_SOURCES
    try:
        yield
    finally:
        zt.ROM48_BANK, zt.ROM128_0_BANK = saved


def layout(raw, enhanced):
    """The published layout: the loading screen in the file (byte 10 = 2); the default lists banks 0-45 only; a colour
    set lists every bank and its header's byte 8 says 1792K."""
    raw = bytearray(raw)
    h = raw[:512]
    screen = {0: 0, 2: 6912}[h[10]]
    listed = [b for b in [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112)) if h[18 + b]]
    if max(listed) != 109:
        raise ValueError('Chase H.Q.: expected banks up to 109, got %d' % max(listed))
    if enhanced:
        raw[8] = 1
        return bytes(raw)
    keep = bytearray(raw[:512 + screen])
    at = 512 + screen
    for b in listed:
        if b <= BASE_TOP:
            keep += raw[at:at + 16384]
        else:
            keep[18 + b] = 0
            keep[9] -= 1
        at += 16384
    return bytes(keep)


def find_inputs(z80):
    """(art bytes, loading screen bytes) beside the snapshot; None where absent. A different file is refused."""
    here = Path(z80).resolve().parent
    got = []
    for f, want in ((ART, ART_MD5), (LOAD_SCREEN, LOAD_MD5)):
        p = here / f
        if not p.is_file():
            got.append(None)
            continue
        data = p.read_bytes()
        if hashlib.md5(data).hexdigest() != want:
            raise ValueError('%s is not the expected file (MD5 %s)' % (f, want))
        got.append(data)
    return tuple(got)


def build(z80, out, cset, art, screen):
    """One set -> its .nex at out (published layout). -> the patch (its original_pc for the boot check)."""
    p = Patch(cset, art)
    tmp = str(out) + '.tmp'
    with _alt_sources():
        zt.convert(str(z80), tmp, patch=p, quiet=True)
    raw = bytearray(open(tmp, 'rb').read())
    os.remove(tmp)
    if raw[10] != 0 or len(screen) != 6912:
        raise ValueError('Chase H.Q.: expected a .nex without a screen and a 6,912-byte loading screen')
    raw[10] = 2
    raw = bytes(raw[:512]) + screen + bytes(raw[512:])
    open(out, 'wb').write(layout(raw, cset != 'default'))
    return p


def boot_check(nex, z80, patch):
    """Booted as the converter's loader and as NEXLOAD leaves the machine, to the game's own PC after the hidden-ROM
    continuation: every register with R and all 48K of RAM against the patched snapshot, no tail exemption (the
    continuation restores the printer buffer whole). -> problems."""
    from . import nextboot
    s = zt.Z80Snapshot(str(z80))
    q = Patch(patch.cset, b''.join(patch.extra_banks[n] for n in ART_BANKS))
    q.apply(s)
    want = {0: s.a, 1: s.f, 2: s.bc >> 8, 3: s.bc & 255, 4: s.de >> 8, 5: s.de & 255, 6: s.hl >> 8, 7: s.hl & 255,
            8: s.ix >> 8, 9: s.ix & 255, 10: s.iy >> 8, 11: s.iy & 255, 12: s.sp, 14: s.i, 15: s.r, 16: s.a_, 17: s.f_,
            18: s.bc_ >> 8, 19: s.bc_ & 255, 20: s.de_ >> 8, 21: s.de_ & 255, 22: s.hl_ >> 8, 23: s.hl_ & 255,
            26: s.iff1, 27: s.im}
    bad = []
    for nexload in (False, True):
        st = nextboot.boot(str(nex), q.original_pc, nexload=nexload)
        bad += [('loader', nexload) + tuple(x) for x in st['bad']]
        bad += [('register', nexload, i, v, st['R'][i]) for i, v in want.items()
                if (bool(st['R'][i]) != bool(v) if i == 26 else st['R'][i] != v)]
        for a in range(0x4000, 0x10000):
            bank = 5 if a < 0x8000 else 2 if a < 0xC000 else 0
            if st['mem'][a] != s.banks[bank][a & 16383]:
                bad.append(('RAM', nexload, hex(a), s.banks[bank][a & 16383], st['mem'][a]))
                if len(bad) > 20:
                    return bad
    return bad


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Not an RZX verifier yet: Chase H.Q.'s proof is the pilot run's paired-hook replay (1.0), native lockstep against
    the original in JNext, tunnel routes, stage checkpoints and negatives (games/chase_hq.md "Evidence")."""
    raise NotImplementedError('chase_hq: no RZX verifier yet (games/chase_hq.md "Evidence")')


def unit_tests(patch, states, neg=None):
    """No unit tests in the engine yet: the clock, R, MMU, cadence and broken-build cases ran in the pilot run
    (games/chase_hq.md "Evidence")."""
    raise NotImplementedError('chase_hq: no unit tests yet (games/chase_hq.md "Evidence")')


def auto(a, z80, name, out, say):
    """nexclash.py auto: the default build and both colour sets as published, each boot-checked. Needs ART and
    LOAD_SCREEN beside the snapshot (module docstring); without them it builds nothing and says so."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if not getattr(a, 'colours_by', None):
        a.colours_by = 'Jon Attree'
    if not getattr(a, 'fix_label', None):
        a.fix_label = 'Speed'
    say('Game      : %s' % name)
    say('Engine    : chase_hq (speed engine; Enhanced colours in two sets: Speed, Orig. pace)')
    art, screen = find_inputs(z80)
    missing = [f for f, d in ((ART, art), (LOAD_SCREEN, screen)) if d is None]
    if missing:
        say('Inputs    : %s not beside the snapshot (local inputs: games/chase_hq.md "Inputs"); nothing built'
            % ', '.join(missing))
        say('Result    : FAILED')
        return False
    ok = True
    for cset, f in OUTPUTS.items():
        nex = out / f
        p = build(z80, nex, cset, art, screen)
        bad = boot_check(nex, z80, p)
        ok &= not bad
        say('%-10s: %s  %s' % ('Default' if cset == 'default' else cset[:10], f, hashlib.md5(nex.read_bytes()).hexdigest()))
        say('Boot      : %s' % ('OK (registers with R, 48K RAM, no tail exemption; converter loader and NEXLOAD)'
                                if not bad else 'MISMATCH %s' % str(bad[:3])[:300]))
    say('Verify    : not in this engine (games/chase_hq.md "Evidence")')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) != 2:
        raise SystemExit(__doc__)
    z80, out = a
    os.makedirs(out, exist_ok=True)
    art, screen = find_inputs(z80)
    if art is None or screen is None:
        raise SystemExit('%s and %s must be beside %s' % (ART, LOAD_SCREEN, z80))
    for cset, f in OUTPUTS.items():
        build(z80, os.path.join(out, f), cset, art, screen)
        print(f, hashlib.md5(open(os.path.join(out, f), 'rb').read()).hexdigest())


if __name__ == '__main__':
    main()
