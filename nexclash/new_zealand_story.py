"""The New Zealand Story (Ocean, 1989, 128K): the colour build, from the game's two tape files and a start state.
GPL-3.0-or-later. Facts, decisions and evidence: games/new_zealand_story.md.

The first engine whose build reads tapes (nexclash/tapeset.py): the snapshot is the emulator start state (the 128K game
loaded from Side A, world 1 in memory, on the title screen); the worlds the game loads later come from the tapes,
`--tape SIDE_A.tap|.tzx --tape SIDE_B.tzx`, checked against the releases in the profile (tape_sets).

Three stages, as the published patch (github.com/jattree/nxc, v1.2; v1.3 = + the v2.10 fix-up) was built, now one engine:
  1. multiload from RAM (stage1()): the 37 world-load blocks raw from the tapes in banks 12-22 (no block across an 8K
     page), their headers and directory and the loader (asm/new_zealand_story_loader.asm) in bank 11; a 12-byte stub
     replaces the game's LD-BYTES entry (bank 1 0x11EA, copied to 0x43AF), so a world load reads RAM, not the tape.
  2. colour (nexclash/new_zealand_story_paint.py): tilemap scenery from each level's map and char set, every figure
     a painted 4-bit sprite program; hooks (asm/new_zealand_story_hooks.asm) in alt ROM image 1 0x2000-0x3FFF, the
     1.1 speed pass in them (drawing at 28 MHz, a PAL-line cap before the player update); "Smooth scrolling" toggle.
  3. "Backdrops" toggle (v1.2): Layer 2 backdrops behind the sky (nexclash/new_zealand_story_backdrops.py; original
     tiles by Jon Attree, assets/new_zealand_story/backdrops), asm/new_zealand_story_backdrop.asm at alt ROM 0x3300.
The hooks are assembled at build time with the pinned sjasmplus (their tables come from the tapes; herbert does the
same), so there is no hook hex in the profile and no asm2profile check.

Outputs (the four builds of the published patch v1.3, byte for byte): NAME_sprites.nex (default), NAME_smooth.nex,
NAME_backdrops.nex, NAME_smooth_backdrops.nex; NAME_outputs.json names the two toggles.

Two things are kept as published, both local to this engine:
  - alt ROM image 1 is filled as v1.2 filled it (_altrom_fill_v209: NextZXOS's ROM3 + the hooks) plus, since v1.3,
    NextZXOS v2.10's ROM3 fix-ups (_altrom_fill_v210): the 11-byte ROM3 copy becomes a JP to the copy + the fix-ups
    (z80tonex.rom3_fixup_code, every site) in the stub page's free tail at V210_AT, which jumps back, so every other
    stub byte keeps its v1.2 address (the bytes the v2.10 fix's patch_nex gave the published v1.3);
  - the start-up tail goes in the game's dead stack below SP in bank 0 (0xFFxx), with a setup that maps bank 0's upper
    page at MMU7 for the copy and a tail that writes 7FFD before 1FFD (_stage1_tail(), patched into z80tonex for the
    one convert() call and restored).

Proof: not a differential RZX verifier. The published builds were proven in the run folder by lockstep JSON-input
replays on its Next simulator (v1.1: 52 replays / 141,000 frames; v1.2: 34 runs / 51,000 frames, Layer 2 against
bd model at every interrupt, negatives detected), JNext pace, flicker and soak runs; this engine reproduces those
builds byte for byte, which is what the record checks. verify() / unit_tests() say so rather than pretend.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import tapeset
from . import z80tonex

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
ASM = os.path.join(ROOT, 'asm')
RECORD = 'new_zealand_story'
CMP = None                                  # no register comparison here: see verify()

# ---------------------------------------------------------------- stage 1: multiload from RAM
HOOK_BANK = 11
HOOK_PAGE = 2 * HOOK_BANK                   # 22
DATA_BANK0 = 12
NBLK = 37                                   # world blocks 0..36; 36 (header seq 37, 'M@') is on Side B only
STUB_OFF = 0x11EA                           # bank 1 offset of the game's LD-BYTES entry (its 0x43AF copy)
STUB_ORIG = bytes.fromhex('37140815f33e0fd3fec36205')
CV, BCV = 0x43, 0xB021                      # C at LD-FLAG and BC after the last edge, measured on a real-tape load
SETUP = 0xD000                              # stub bank, STUB_ORG + 0x1000 (z80tonex stub_extra)

# ---------------------------------------------------------------- stage 2/3: hook sites (address: original, label)
SITES = {0xA397: ('cd2ec2', 'h_paced_player'), 0xA388: ('cd14d8', 'h_fast_scroll'), 0xA38E: ('cdd1d9', 'h_fast_scenery'),
         0xA391: ('cd26db', 'h_fast_figures'), 0xA3A0: ('cdc1da', 'h_fast_copy'), 0xA461: ('fbed4d', 'h_irq_return'),
         0xFDFD: ('c304a4', 'h_irq'), 0xD5C3: ('2104a4', 'h_setim'), 0xDAC1: ('010012', 'h_copy'),
         0xDB16: ('7bc620', 'h_row'), 0xD973: ('214001', 'h_level'), 0xA2E1: ('21b5d1', 'h_ready'),
         0xA200: ('f33100', 'h_title'), 0xDDCC: ('ebd5d9', 'h_plot'),
         0xDAC4: ('2100e7', 'bd_copy'), 0xA404: ('f5c5d5', 'bd_irq'), 0xA300: ('cd48a9', 'bd_ready'),
         0xA394: ('cd5da7', 'bd_pre')}     # the last four: Backdrops only
BD_ORG = 0x3300
VARIANTS = (('sprites', 0, 0), ('smooth', 1, 0), ('backdrops', 0, 1), ('smooth_backdrops', 1, 1))
TOGGLES = {'smooth': 'Smooth scrolling', 'backdrops': 'Backdrops'}


def _profile_path():
    return os.path.join(ROOT, 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_new_zealand_story(snap):
    if snap.machine == '48K':
        return False
    return all(bytes(snap.memory[s['addr']:s['addr'] + len(s['bytes']) // 2]).hex() == s['bytes']
               for s in load_profile()['signature'])


def tape_sets():
    """The releases the build accepts: [[md5 Side A, md5 Side B], ...] (profile tape_sets)."""
    return [s['md5'] for s in load_profile()['tape_sets']]


# ---------------------------------------------------------------- the tapes' world blocks
def world_blocks(ts):
    """[(header 16 bytes, data block flag..checksum)] for world blocks 0..36: each header (flag 0xAA, sequence k+1)
    and the block after it in the same file, the first found in set order. Found by content, so the .tap and the .tzx
    of Side A give the same blocks although their block numbers differ."""
    out = []
    for k in range(NBLK):
        hits = ts.after(lambda b, k=k: len(b) == 16 and b[0] == 0xAA and b[1] == k + 1)
        if not hits or hits[0][1] is None:
            raise ValueError('the tapes have no world block %d (header sequence %d): Side B missing?' % (k, k + 1))
        hdr, data = hits[0]
        if data[:1] != bytes([0x81 + k]) or len(data) - 2 != hdr[13] | hdr[14] << 8:
            raise ValueError('world block %d: its data block does not match its header' % k)
        out.append((hdr, data))
    return out


def level_blocks(wb):
    """{name: data bytes without flag and checksum} of world blocks 0..35, as the game names them (the header's 2
    letters; the sprite set CK is CK0)."""
    res = {}
    for k in range(36):
        h, d = wb[k]
        nm = h[2:4].decode()
        res[nm + (str(k) if nm == 'CK' else '')] = d[1:-1]
    return res


# ---------------------------------------------------------------- assembling (pinned sjasmplus)
def _sjasm():
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'sjasmplus'))
    import sjasm
    return sjasm.find()


def assemble(src, out, defs, wd, raw_defs=None):
    """asm/<src> into wd as gen_<out>.asm: SAVEBIN "OUT.bin" -> <out>.bin, each def NAME=v set by replacing the source's
    own `NAME = 0` (or STAGEF's `= 1`) line, as the build always did -> (bytes, {label: address})."""
    s = open(os.path.join(ASM, src)).read().replace('"OUT.bin"', '"%s.bin"' % out)
    for k, v in defs.items():
        s = s.replace('%s = %d' % (k, 1 if k == 'STAGEF' else 0), '%s = %d' % (k, v), 1)
    g = os.path.join(wd, 'gen_' + out + '.asm')
    open(g, 'w').write(s)
    r = subprocess.run([_sjasm(), '--nologo', '--msg=war', '--lst=%s.lst' % out, g], cwd=wd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('sjasmplus %s:\n%s' % (src, r.stdout + r.stderr))
    syms = {}
    for line in open(os.path.join(wd, out + '.lst')):
        t = line.split(';')[0].split()
        if len(t) >= 3 and t[-1].endswith(':') and not t[-1].startswith('.') and '~' not in t:
            try:
                syms[t[-1][:-1]] = int(t[1], 16)
            except ValueError:
                pass
    return open(os.path.join(wd, out + '.bin'), 'rb').read(), syms


def loader_code(wd):
    """The stage 1 loader (asm/new_zealand_story_loader.asm), org 0x0100 of page 22."""
    out = os.path.join(wd, 'loader.bin')
    r = subprocess.run([_sjasm(), '--nologo', '--zxnext', '--raw=' + out, '-DCV=0x%02X' % CV, '-DBCV=0x%04X' % BCV,
                        os.path.join(ASM, 'new_zealand_story_loader.asm')], cwd=wd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('sjasmplus loader:\n%s' % (r.stdout + r.stderr))
    return open(out, 'rb').read()


# ---------------------------------------------------------------- stage 1
def stage1(wb, wd):
    """-> ({page: 8K} of banks 11-22, the 12-byte stub). The 37 raw data blocks packed largest first, no block
    across a page; page 22: loader at 0x0100, directory (page, length, source) at 0x0200, headers at 0x0400."""
    code = loader_code(wd)
    blocks = [d for _, d in wb]
    order = sorted(range(NBLK), key=lambda k: -len(blocks[k]))
    free, place = [], {}
    for k in order:
        n = len(blocks[k])
        for i, f in enumerate(free):
            if f >= n:
                place[k] = (i, 8192 - f)
                free[i] -= n
                break
        else:
            free.append(8192 - n)
            place[k] = (len(free) - 1, 0)
    npages = len(free)
    hook = bytearray(8192)
    hook[0x100:0x100 + len(code)] = code
    data = [bytearray(8192) for _ in range(npages + (npages & 1))]
    for k in range(NBLK):
        hdr, b = wb[k]
        hook[0x400 + 16 * k:0x410 + 16 * k] = hdr
        i, off = place[k]
        data[i][off:off + len(b)] = b
        n, src = len(b) - 2, 0x2000 + off + 1
        hook[0x200 + 5 * k:0x205 + 5 * k] = bytes((2 * DATA_BANK0 + i, n & 255, n >> 8, src & 255, src >> 8))
    pages = {HOOK_PAGE: bytes(hook), HOOK_PAGE + 1: bytes(8192)}
    for i, d in enumerate(data):
        pages[2 * DATA_BANK0 + i] = bytes(d)
    stub = bytes((0xED, 0x91, 0x50, HOOK_PAGE, 0xC3, 0x00, 0x01, 0xED, 0x91, 0x50, 0xFF, 0xC9))
    banks = {p // 2: pages[p] + pages.get(p + 1, bytes(8192)) for p in sorted(pages) if p % 2 == 0}
    return banks, stub


# ---------------------------------------------------------------- frozen stub pieces (published bytes)
def _altrom_fill_v209(org, page, lo, hi):
    """z80tonex.altrom_fill as it was before NextZXOS v2.10's fix-ups (main 2026-11-06): NextZXOS's ROM3 copied into
    alt ROM image 1, then bytes lo..hi-1 of page over it. The published 1.2 has these bytes."""
    Z = z80tonex
    c = bytearray()
    c += Z.nextreg(0x54, Z.STUB_PAGE_LO) + Z.nextreg(0x55, page)
    c += b'\xC3' + Z.w16(org + len(c) + 3 - 0x4000)
    c += Z.read_nextreg(0x08) + b'\xF6\x80' + Z.nextreg_a(0x08)
    c += Z.out_port(0x1FFD, 0x04) + Z.out_port(0x7FFD, 0x10)
    c += Z.nextreg(0x8C, 0xC0)
    c += b'\x21\x00\x00\x11\x00\x00\x01\x00\x40\xED\xB0'
    c += b'\x21' + Z.w16(0xA000 + lo - 0x2000) + b'\x11' + Z.w16(lo) + b'\x01' + Z.w16(hi - lo) + b'\xED\xB0'
    c += Z.nextreg(0x8C, 0x00)
    c += Z.nextreg(0x56, Z.STUB_PAGE_LO) + Z.nextreg(0x57, Z.STUB_PAGE_HI)
    c += b'\xC3' + Z.w16(org + len(c) + 3)
    c += Z.nextreg(0x54, 4) + Z.nextreg(0x55, 5)
    return bytes(c)


ROM3_COPY = bytes.fromhex('210000110000010040EDB0')     # LD HL,0 / LD DE,0 / LD BC,$4000 / LDIR (the ROM3 copy)
V210_AT = 0x1D3B                            # stub page offset of the v2.10 fix-up routine: the page's free tail, below
                                            # the stub's stack (0x1E00-0x1FFF), as the v2.10 fix's patch_nex put it


def _v210_routine(at, back):
    """The 1.3 ROM3 copy with NextZXOS v2.10's fix-ups (v2.10 fix tools/patch_nex.py + fix/rom3fix.asm, bytes as the
    published 1.3): run at `at` (slot-4 alias), the 11-byte copy, then z80tonex.rom3_fixup_code for every site of
    ROM3_V210_FIXUPS (this build writes none of them itself: the hooks are 0x2000-0x3FFF) ending in JP back."""
    Z = z80tonex
    fx = bytearray(Z.rom3_fixup_code(at + len(ROM3_COPY)))
    tlen = sum(3 + len(new) + len(old) for _, new, old in Z.ROM3_V210_FIXUPS) + 3
    j = len(fx) - tlen - 3
    assert fx[j] == 0xC3, fx[j]
    fx[j + 1:j + 3] = Z.w16(back)
    return ROM3_COPY + bytes(fx)


def _altrom_fill_v210(org, page, lo, hi):
    """_altrom_fill_v209 with the v2.10 fix-up (1.3): its 11-byte ROM3 copy becomes JP to _v210_routine at V210_AT
    (the copy and the fix-ups there, then back to the overlay copy) + 8 zero bytes, so every other byte stays at its
    1.2 address. -> (fill code, routine at V210_AT)."""
    c = bytearray(_altrom_fill_v209(org, page, lo, hi))
    k = c.find(ROM3_COPY)
    assert k > 0 and c.count(ROM3_COPY) == 1
    at = org - 0x4000 - (SETUP - 0xC000) + V210_AT          # the routine's address in the slot-4 alias of the page
    c[k:k + len(ROM3_COPY)] = b'\xC3' + z80tonex.w16(at) + bytes(8)
    return bytes(c), _v210_routine(at, org - 0x4000 + k + len(ROM3_COPY))


def _with_v210(setup, routine):
    """The setup code (stub_extra at SETUP) padded with zeros to V210_AT, then the fix-up routine."""
    o = V210_AT - (SETUP - 0xC000)
    assert len(setup) <= o and o + len(routine) <= 0x2000 - 0x200, (len(setup), o)
    return setup + bytes(o - len(setup)) + routine


def _bd_fill(org, page, lo, hi):
    """_altrom_fill_v209 without its ROM3 copy: only bytes lo..hi-1 of page into alt ROM image 1 (run after the colour
    fill, so the colour hooks stay), alt ROM left on for reads as the setup left it."""
    Z = z80tonex
    c = bytearray()
    c += Z.nextreg(0x54, Z.STUB_PAGE_LO) + Z.nextreg(0x55, page)
    c += b'\xC3' + Z.w16(org + len(c) + 3 - 0x4000)
    c += Z.read_nextreg(0x08) + b'\xF6\x80' + Z.nextreg_a(0x08)
    c += Z.out_port(0x1FFD, 0x04) + Z.out_port(0x7FFD, 0x10)
    c += Z.nextreg(0x8C, 0xC0)
    c += b'\x21' + Z.w16(0xA000 + lo - 0x2000) + b'\x11' + Z.w16(lo) + b'\x01' + Z.w16(hi - lo) + b'\xED\xB0'
    c += Z.nextreg(0x8C, 0x80)
    c += Z.nextreg(0x56, Z.STUB_PAGE_LO) + Z.nextreg(0x57, Z.STUB_PAGE_HI)
    c += b'\xC3' + Z.w16(org + len(c) + 3)
    c += Z.nextreg(0x54, 4) + Z.nextreg(0x55, 5)
    return bytes(c)


class _stage1_tail:
    """The start-up tail in the game's dead stack below SP (0xFFFE, bank 0), not in game data: z80tonex refuses a tail
    above 0xC000 because the stub copies it with its own bank 10 at C000 and the tail's 7FFD write swaps C000-FFFF.
    Here the setup maps bank 0's upper page (Next page 1) at MMU7 first (NEXTREG $57,1), so the copy lands in bank 0;
    and the tail writes 7FFD before 1FFD, so each legacy paging write leaves bank 0, and the tail, in place.
    A context manager: z80tonex's own functions are back as soon as the build's convert() returns."""

    def __enter__(self):
        Z = z80tonex
        self.saved = Z.build_tail, Z.choose_tail_addr
        orig = Z.build_tail

        def build_tail(snap, org, slot1=None, altrom=False, *rest):
            code, p3, rest_, regs = orig(snap, org, slot1, altrom, *rest)
            a, b = code[0:7], code[7:14]
            assert a[:3] == b'\x01\xfd\x1f' and b[:3] == b'\x01\xfd\x7f', (a.hex(), b.hex())
            return b + a + code[14:], p3, rest_, regs

        def choose_tail_addr(snap, length, requested, avoid_printer_buffer=False):
            assert snap.is128 and snap.port7ffd & 7 == 0 and snap.sp >= 0xFF00 + length + 16
            return snap.sp - length - 16, 'dead stack below SP, bank 0 (MMU7 = page 1 for the copy)'
        Z.build_tail, Z.choose_tail_addr = build_tail, choose_tail_addr
        return self

    def __exit__(self, *exc):
        z80tonex.build_tail, z80tonex.choose_tail_addr = self.saved
        return False


# ---------------------------------------------------------------- stages 2 and 3
def variant(wd, smooth=0, bd=0, neg=None):
    """-> (pages {8K page: bytes}, info, hook code, symbols, setup code) for one build."""
    from . import new_zealand_story_paint as G
    pages, info = G.build_all(wd, 'own', neg, bd=bool(bd))
    defs = {'STAGEF': 1}
    if smooth:
        defs['SMOOTH'] = 1
    code, syms = assemble('new_zealand_story_hooks.asm', 'hooks', defs, wd)
    img = bytearray(8192)
    img[0:len(code)] = code
    pages[G.ALTPG] = bytes(img)
    fill, v210 = _altrom_fill_v210(SETUP, G.ALTPG, 0x2000, 0x2000 + len(code))
    open(os.path.join(wd, 'altfill.bin'), 'wb').write(fill)
    if not bd:
        setup, _ = assemble('new_zealand_story_setup.asm', 'setup', {}, wd)
        return pages, info, code, syms, _with_v210(setup, v210)
    from . import new_zealand_story_backdrops as BD
    bdpages, bdinfo = BD.layout()
    k = syms['speed_irq_original'] - syms['h_irq'] - (3 if smooth else 0)   # where the smooth build has its JP h_irq_smooth
    assert k == 49, k
    open(os.path.join(wd, 'bd_layout.inc'), 'w').write(BD.layout_inc(bdinfo, k))
    bdefs = {n: 1 for n in ('NEG_SCROLL', 'NEG_LEVEL') if neg == n}
    bcode, bsyms = assemble('new_zealand_story_backdrop.asm', 'backdrop', bdefs, wd)
    assert bsyms['bd_start'] == BD_ORG and BD_ORG + len(bcode) <= 0x4000
    o = BD_ORG - 0x2000
    assert len(code) <= o and not any(img[o:o + len(bcode)])
    img[o:o + len(bcode)] = bcode
    pages[G.ALTPG] = bytes(img)
    for pg, b in bdpages.items():
        assert pg not in pages
        pages[pg] = b
    syms = dict(syms)
    syms.update({n: v for n, v in bsyms.items() if n in ('bd_copy', 'bd_irq', 'bd_start', 'bd_end', 'bd_ctail', 'bd_itail',
                                                       'bd_ready', 'bd_rtail', 'bd_pre', 'bd_ptail')})
    n = len(_bd_fill(SETUP, G.ALTPG, BD_ORG, BD_ORG + len(bcode)))
    open(os.path.join(wd, 'bdfill.bin'), 'wb').write(bytes(n))          # placeholder of the right length: where is bdfill?
    _, ss = assemble('new_zealand_story_setup.asm', 'setup', {'BACKDROP': 1}, wd)
    open(os.path.join(wd, 'bdfill.bin'), 'wb').write(_bd_fill(ss['bdfill'], G.ALTPG, BD_ORG, BD_ORG + len(bcode)))
    setup, ss2 = assemble('new_zealand_story_setup.asm', 'setup', {'BACKDROP': 1}, wd)
    assert ss2['bdfill'] == ss['bdfill']
    info['bd'] = bdinfo
    return pages, info, code, syms, _with_v210(setup, v210)


class Patch:
    """The colour build over stage 1: stage 1's banks 11-22 and stub, the colour data pages, hooks at SITES."""
    name = 'The New Zealand Story colour (tilemap scenery + sprite figures) on the multiload from RAM'
    uses_printer_buffer = False
    hook_page_data = b''

    def __init__(self, pages, syms, setup, s1banks, s1stub):
        self.syms, self.stub_extra, self.setup_call = syms, setup, SETUP
        self.s1stub, self.pages = s1stub, pages
        self.extra_banks = dict(s1banks)
        for p in sorted(pages):
            if p >= 16:
                bk = p // 2
                base = s1banks.get(bk, bytes(16384))      # stage 1's half of a shared bank is kept
                for half, pg in ((0, 2 * bk), (1, 2 * bk + 1)):
                    if pg in pages and bk in s1banks:
                        assert not any(base[half * 8192:(half + 1) * 8192]), "page %d is stage 1's" % pg
                self.extra_banks[bk] = pages.get(2 * bk, base[:8192]) + pages.get(2 * bk + 1, base[8192:])

    def apply(self, snap):
        b1 = bytearray(snap.banks[1])
        if bytes(b1[STUB_OFF:STUB_OFF + 12]) != STUB_ORIG:
            raise ValueError('bank 1 0x%04X differs from the release: not this start state' % STUB_OFF)
        b1[STUB_OFF:STUB_OFF + 12] = self.s1stub
        snap.banks[1] = bytes(b1)
        for a, (orig, lab) in SITES.items():
            if lab not in self.syms:
                continue
            bk, off = (0, a - 0xC000) if a >= 0xC000 else (2, a - 0x8000)
            b = bytearray(snap.banks[bk])
            if b[off:off + 3].hex() != orig:
                raise ValueError('site 0x%04X differs from the release' % a)
            t = self.syms[lab]
            b[off:off + 3] = bytes([0xC3, t & 255, t >> 8])
            snap.banks[bk] = bytes(b)
        snap.banks[7] = self.pages[14] + self.pages[15]


def build(z80, tapes, out, name, say, variants=VARIANTS):
    """Every variant from the start state z80 and the tape files (in order) -> {key: path}. ValueError on the wrong
    tapes or start state."""
    from skoolkit.snapshot import Snapshot
    from . import new_zealand_story_paint as G
    sets = load_profile()['tape_sets']
    try:
        ts, si = tapeset.load(tapes, tape_sets())
    except ValueError as e:
        raise ValueError('%s. The releases: %s' % (e, '; or '.join(' + '.join(s['files']) for s in sets)))
    say('Tapes     : set %s: %s' % (sets[si]['set'], ', '.join('%s %s' % (os.path.basename(p), m[:8])
                                                             for p, m in zip(ts.paths, ts.md5s))))
    want = load_profile()['start']['md5']
    got = hashlib.md5(open(z80, 'rb').read()).hexdigest()
    if got != want:
        say('Start     : %s md5 %s, the verified start state is %s: building anyway, outputs will differ' % (
            os.path.basename(z80), got, want))
    wb = world_blocks(ts)
    snap = Snapshot.get(z80)
    G.use(level_blocks(wb), bytes(snap.memory[0:65536]))
    res = {}
    with tempfile.TemporaryDirectory(prefix='nzs_') as wd:
        s1banks, s1stub = stage1(wb, wd)
        say('Stage 1   : %d world blocks from the tapes in banks %d-%d, loader in bank %d' % (
            len(wb), DATA_BANK0, max(s1banks), HOOK_BANK))
        for key, smooth, bd in variants:
            vd = os.path.join(wd, key)
            os.makedirs(vd)
            pages, info, code, syms, setup = variant(vd, smooth, bd)
            p = os.path.join(out, '%s_%s.nex' % (name, key))
            with _stage1_tail():
                z80tonex.convert(z80, p, None, patch=Patch(pages, syms, setup, s1banks, s1stub), quiet=True)
            res[key] = p
            say('%-10s: %s  %s  (hooks %d bytes%s)' % (
                {'sprites': 'Sprites', 'smooth': 'Smooth', 'backdrops': 'Backdrops'}.get(key, 'Both'), os.path.basename(p),
                hashlib.md5(open(p, 'rb').read()).hexdigest(), len(code), ', toggle ' + ' + '.join(
                    TOGGLES[t] for t in key.split('_') if t in TOGGLES) if key != 'sprites' else ''))
    return res


# ---------------------------------------------------------------- the contract
def auto(a, z80, name, out, say):
    """The four builds from the start state and the tapes (--tape, in order); no differential verification here (see
    the module docstring): `Verify` and `Unit` say so, and `Result` is BUILT, never PASSED."""
    say('Game      : %s' % name)
    say('Engine    : new_zealand_story (The New Zealand Story, 128K, tape set)')
    try:
        res = build(z80, list(getattr(a, 'tape', None) or []), out, name, say)
    except ValueError as e:
        say('Refused   : %s' % e)
        say('Result    : FAILED')
        return False
    json.dump({'default': os.path.basename(res['sprites']),
               'toggles': {TOGGLES['smooth']: os.path.basename(res['smooth']),
                           TOGGLES['backdrops']: os.path.basename(res['backdrops'])},
               'combined': {'+'.join((TOGGLES['smooth'], TOGGLES['backdrops'])): os.path.basename(res['smooth_backdrops'])}},
              open(os.path.join(out, name + '_outputs.json'), 'w'), indent=1)
    say('Boot      : not simulated (128K tape build; the published builds boot in JNext, games/new_zealand_story.md)')
    if getattr(a, 'rzx', None):
        say('Verify    : not run: this engine has no RZX verifier; the proof is the run-folder replay suite '
            '(games/new_zealand_story.md "Evidence"), which these byte-identical builds inherit')
    say('Unit      : none in this engine (see Verify)')
    say('Result    : BUILT (byte-for-byte builds; no differential verification in this run)')
    return True


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Not an RZX verifier: NZS's proof is the run folder's lockstep JSON-input replays on its own Next simulator
    (games/new_zealand_story.md "Evidence"). Porting that harness is the open item; until then this says so."""
    raise NotImplementedError('new_zealand_story: no RZX verifier yet (games/new_zealand_story.md "Open")')


def unit_tests(patch, states, neg=None):
    """No unit tests in the engine yet: the negative controls ran in the run folder (games/new_zealand_story.md)."""
    raise NotImplementedError('new_zealand_story: no unit tests yet (games/new_zealand_story.md "Open")')
