"""Target: Renegade v1.2 (Jon Attree's .nxc, github.com/jattree/nxc): opt-in rework of the renegade engine
(NEXCLASH_REWORK=target_renegade_v12). GPL-3.0-or-later. Facts: games/target_renegade.md "v1.2 (rework)".

The published v1.2 builds, byte for byte, from the game's loader snapshot (the record's):
  - start state: renegade.build's (loader run + front end), the same as Dean's build;
  - hooks: the v1.1 hook-speed pass (asm/renegade_speed_common.asm; profiles target_renegade_speed /
    target_renegade_enh_speed): the same pictures as Dean's hooks, a RAM content cache (RC, pages 46-63: a 1MB
    Next), plot hooks at 28 MHz, a hash index; every hook that switches to 28 MHz latches NextREG 7 on entry and
    writes it back on exit (the caller's speed, never a fixed 3.5 MHz);
  - Enhanced (colour set "Enhanced"): renegade_enh.EnhPatch, painted by Jon Attree; the paint (target_renegade_
    enhanced.json: per-level words, signatures, palette) is read from beside the snapshot;
  - the loading screen (target_renegade_loading.scr, the tape's, beside the snapshot) in bank 5 of the file with
    v1.0's stub in bank 20 (asm ldscr in renegade_speed_hooks.asm), as v1.0 / v1.1 / v1.2 carry it;
  - NextZXOS v2.10's ROM3 fix-ups in v1.2's layout (_v210): the start-up fill's 11-byte ROM3 copy becomes JP to the
    copy + z80tonex.rom3_fixup_code (every site) in the stub page's free tail (offset V210_AT), which jumps back; the
    setup's own second copy (0x9024) is left as main's builder leaves it. So every other stub byte keeps its v1.1
    address: the bytes the v2.10 fix's patch_nex (first copy only) gave the published v1.2.
Game data stays out of this repo: the screen and the paint (it holds the game's graphic signatures) are inputs.
"""
import hashlib
import json
import os

from . import renegade as R
from . import z80tonex

REWORK = 'target_renegade_v12'          # NEXCLASH_REWORK value that opts in
LOAD_BANK = 20                          # the loading screen's entry bank (pages 40, 41), as v1.0
LOAD_SCREEN = 'target_renegade_loading.scr'    # the tape's 6,912-byte screen (MD5 18681406), beside the snapshot
DESIGN = 'target_renegade_enhanced.json'       # the Enhanced paint (words, sigs, palette), beside the snapshot
_PROF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'profiles')
ROM3_COPY = bytes.fromhex('210000110000010040EDB0')     # LD HL,0 / LD DE,0 / LD BC,$4000 / LDIR (the ROM3 copy)
V210_AT = 0x1D3B                        # stub page offset of the fix-up routine: its free tail, below the stub stack


CMP = R.CMP                             # the contract's names: renegade's verifier and unit tests run the v1.2 patches
verify = R.verify
unit_tests = R.unit_tests


def load_profile():
    return profile('target_renegade_speed')


def is_renegade_v12(snap):
    """Target Renegade (renegade.is_renegade) and the opt-in asked for: NEXCLASH_REWORK=target_renegade_v12."""
    return os.environ.get('NEXCLASH_REWORK') == REWORK and R.is_renegade(snap)


def profile(name):
    return json.load(open(os.path.join(_PROF, name + '.json')))


def load_design(path):
    """The Enhanced paint: ({level: {graphic address: word}}, {level: signatures}, palette bytes)."""
    d = json.load(open(path))
    words = {int(k): {int(a, 16): v for a, v in ws.items()} for k, ws in d['words'].items()}
    sigs = {int(k): [tuple(x) for x in v] for k, v in d['sigs'].items()}
    return words, sigs, bytes.fromhex(d['palette'])


# ---------------------------------------------------------------- v1.2's start-up fill (v2.10 fix-ups, its layout)
def _fill_v209(org, page, lo, hi):
    """z80tonex.altrom_fill as it was before NextZXOS v2.10's fix-ups (main before 2026-11-06), for lo..hi of page."""
    Z = z80tonex
    c = bytearray()
    c += Z.nextreg(0x54, Z.STUB_PAGE_LO) + Z.nextreg(0x55, page)
    c += b'\xC3' + Z.w16(org + len(c) + 3 - 0x4000)
    c += Z.read_nextreg(0x08) + b'\xF6\x80' + Z.nextreg_a(0x08)
    c += Z.out_port(0x1FFD, 0x04) + Z.out_port(0x7FFD, 0x10)
    c += Z.nextreg(0x8C, 0xC0)
    c += ROM3_COPY
    c += b'\x21' + Z.w16(0xA000 + lo - 0x2000) + b'\x11' + Z.w16(lo) + b'\x01' + Z.w16(hi - lo) + b'\xED\xB0'
    c += Z.nextreg(0x8C, 0x00)
    c += Z.nextreg(0x56, Z.STUB_PAGE_LO) + Z.nextreg(0x57, Z.STUB_PAGE_HI)
    c += b'\xC3' + Z.w16(org + len(c) + 3)
    c += Z.nextreg(0x54, 4) + Z.nextreg(0x55, 5)
    return bytes(c)


def _routine(at, back):
    """At `at` (slot-4 alias of the stub page): the ROM3 copy, z80tonex.rom3_fixup_code for every site, JP back."""
    Z = z80tonex
    fx = bytearray(Z.rom3_fixup_code(at + len(ROM3_COPY)))
    j = len(fx) - (sum(3 + len(new) + len(old) for _, new, old in Z.ROM3_V210_FIXUPS) + 3) - 3
    assert fx[j] == 0xC3, fx[j]
    fx[j + 1:j + 3] = Z.w16(back)
    return ROM3_COPY + bytes(fx)


class _v210:
    """For one convert(): z80tonex.altrom_fill -> v1.2's fill (the 11-byte copy becomes JP to _routine + 8 zero
    bytes) and the patch's stub_extra (the setup, stub page offset 0x1000) padded with zeros to V210_AT + _routine,
    whose JP back is the copy's next address; z80tonex's own function and fill mode back on exit."""

    def __init__(self, patch):
        self.patch = patch

    def __enter__(self):
        Z, p = z80tonex, self.patch
        self.saved = Z.altrom_fill, Z.ALTROM_FILL
        at = 0x8000 + V210_AT
        extra = p.stub_extra
        o = V210_AT - 0x1000
        assert len(extra) <= o

        def fill(org, page, lo, hi, low=None, whole=False, img0=None):
            assert low is None and img0 is None, 'v1.2 fill: lo..hi only'
            c = bytearray(_fill_v209(org, page, lo, hi))
            k = c.find(ROM3_COPY)
            c[k:k + len(ROM3_COPY)] = b'\xC3' + Z.w16(at) + bytes(len(ROM3_COPY) - 3)
            r = _routine(at, org - 0x4000 + k + len(ROM3_COPY))
            assert o + len(r) <= 0x1000 - 0x200
            p.stub_extra = extra + bytes(o - len(extra)) + r
            return bytes(c)
        Z.altrom_fill, Z.ALTROM_FILL = fill, 'rom3'
        return self

    def __exit__(self, *exc):
        z80tonex.altrom_fill, z80tonex.ALTROM_FILL = self.saved
        return False


def convert(start, path, patch):
    """One v1.2 build: start state + patch with v1.2's start-up fill."""
    with _v210(patch):
        z80tonex.convert(start, path, quiet=True, patch=patch)


def loading_nex(nex, scr):
    """A built .nex -> the same with the loading screen (v1.0's stub, nexclash-patch build/all2/add_screen.py's,
    bank 20): bank 5's screen area in the file = the screen, new bank 20 = the entry bank whose stub shows it for
    250 frames or a key, puts bank 5's bytes back and falls into 0xC000 of bank 10. -> (bytes, problems)."""
    import struct
    hk = profile('target_renegade_speed')['hooks']
    head, tail = bytes.fromhex(hk['ldhead']), bytes.fromhex(hk['ldtail'])
    orig = nex[512:512 + 6912]
    bank = head + bytes(0x200 - len(head)) + orig + bytes(0x3FD0 - 0x200 - 6912) + tail
    bad = []
    if len(scr) != 6912:
        bad.append('screen is %d bytes, not 6912' % len(scr))
    if struct.unpack_from('<HH', nex, 12) != (0xDFFE, 0xC000) or nex[10] or not nex[18 + 5] or nex[139] != 10 or \
            nex[140] or nex[141] or any(nex[18 + k] for k in range(LOAD_BANK, 112)):
        bad.append('start state, screen block, entry bank or bank %d+ not as the stub assumes' % LOAD_BANK)
    h = bytearray(nex[:512])
    h[9] += 1
    h[18 + LOAD_BANK] = 1
    h[139] = LOAD_BANK
    n = bytes(h) + scr + nex[512 + 6912:] + bank
    if [i for i in range(512) if nex[i] != n[i]] != [9, 18 + LOAD_BANK, 139]:
        bad.append('header bytes')
    if n[512 + 6912:len(nex)] != nex[512 + 6912:] or n[len(nex) + 0x200:len(nex) + 0x200 + 6912] != orig:
        bad.append("rest of the file or the stub's copy of bank 5")
    return n, bad


def _beside(z80, f):
    p = os.path.join(os.path.dirname(os.path.abspath(z80)), f)
    return p if os.path.isfile(p) else None


def _patch(tag, design):
    if tag == 'speed':
        return R.RenegadePatch(prof=profile('target_renegade_speed'), colours={})
    from . import renegade_enh as E
    words, sigs, pal = load_design(design)
    return E.EnhPatch(words, sigs, pal, prof=profile('target_renegade_enh_speed'))


def _verify_job(job):
    """One replay (a worker process): (set, paint, start state, recording, NR 7 at every hook's entry, quick) ->
    counters. The patch applied to the start state first, as renegade.auto does."""
    tag, design, start, r, clock, quick = job
    p = _patch(tag, design)
    p.apply(z80tonex.Z80Snapshot(start))
    R.INCLOCK = clock                       # 0: the game's 3.5 MHz; 3: entered at 28 MHz (the exit must give it back)
    c, ex, st = R.verify(p, r, stop=quick)
    fails = {k: v for k, v in c.items() if k.endswith('!')}
    return (c['frames'], c['pairs %d' % R.PLOT] + c['pairs %d' % R.PLOT_M], c['commits'], c['sprite pixels compared'],
            {k: (v, ex.get(k[:-1], '')) for k, v in fails.items()})


def auto(a, z80, name, out, say):
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    say('Game      : %s' % name)
    say('Engine    : renegade_v12 (opt-in rework of renegade, Target: Renegade .nxc v1.2: hook-speed pass, RAM '
        'content cache, Enhanced, loading screen, v2.10 fix-ups)')
    ok, (plain, spr, start), _ = R.build(z80, out, name, say)
    sets = [('speed', lambda: _patch('speed', None))]
    dz = _beside(z80, DESIGN)
    if dz is None:
        say('Enhanced  : no %s beside the snapshot: no Enhanced build' % DESIGN)
    else:
        words, sigs, pal = load_design(dz)
        say('Enhanced  : paint %s (%d levels, %d words)' % (md5(dz)[:8], len(words), sum(len(w) for w in words.values())))
        sets.append(('enhanced', lambda: _patch('enhanced', dz)))
    sc_path = _beside(z80, LOAD_SCREEN)
    scr = open(sc_path, 'rb').read() if sc_path else None
    if scr is None:
        say('Loading   : no %s beside the snapshot: builds without the loading screen' % LOAD_SCREEN)
    built = {}
    for tag, mk in sets:
        p = mk()
        sc = R.static_check(p.rom_code, 0x2200)
        f = os.path.join(out, '%s_%s.nex' % (name, tag))
        convert(start, f, mk())
        bad = R.boot_check(f, start, mk())
        lb = []
        if scr is not None:
            n, lb = loading_nex(open(f, 'rb').read(), scr)
            open(f, 'wb').write(n)
        ok = ok and not sc and not bad and not lb and p.regblock + 20 <= 0x3500
        say('%-10s: %s  %s  static %s, boot %s, hook code %d bytes (ends 0x%04X)%s' % (
            'Speed' if tag == 'speed' else 'Enhanced', os.path.basename(f), md5(f), 'PASS' if not sc else sc,
            'OK' if not bad else bad[:3], len(p.rom_code), p.regblock + 20,
            ', loading screen bank %d %s' % (LOAD_BANK, 'OK' if not lb else 'PROBLEM %s' % lb) if scr else ''))
        built[tag] = (f, mk)
    if getattr(a, 'decisions', None):
        say('Result    : %s (rebuild, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    jobs = [(tag, dz, start, r, clock, getattr(a, 'quick', None)) for tag in built for r in list(a.rzx or [])
            for clock in ((0, 3) if tag == 'speed' else (0,))]
    if jobs:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=len(jobs)) as ex:
            res = list(ex.map(_verify_job, jobs))
        for (tag, _, _, r, clock, _), (frames, plots, commits, pixels, fails) in zip(jobs, res):
            ok = ok and not fails
            say('Verify    : %s %s, hooks entered at NR 7 = %d: %d frames, %d plots, %d commits, %d sprite pixels, '
                'every hook gives back the speed it found -> %s' % (
                    tag, os.path.basename(r), clock, frames, plots, commits, pixels,
                    'IDENTICAL' if not fails else 'FAILED %s' % str(fails)[:300]))
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
