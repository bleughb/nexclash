"""Target Renegade Enhanced colours (v1.1+, used by the opt-in rework renegade_v12): the sprite build (renegade.py)
with the hook-speed hooks assembled with ENH (asm/renegade_enh_speed_hooks.asm, profile target_renegade_enh_speed), a
per-level colour store, three palettes per level (enemies and objects, player 1, player 2) and the level found from
the level graphics in memory. Dean's default build is renegade.py's, unchanged.

The design (which colour each body pixel takes) is Jon Attree's paint, passed in as words {level: {mask byte address:
16-bit word}}, signatures {level: [(address, byte)]} and the 512 palette bytes (renegade_v12.load_design reads them
from target_renegade_enhanced.json beside the snapshot: it holds the game's graphic signatures, so never in this repo).
"""
import collections
import json
import os
from . import renegade as R

_HERE = os.path.dirname(os.path.abspath(__file__))
ENH_PROFILE = os.path.join(_HERE, '..', 'docs', 'profiles', 'target_renegade_enh_speed.json')
LO, HI = 0x7800, 0xC000                 # graphics entries with a word
LEVEL_BYTES = (HI - LO)                 # one word per entry (2 bytes): 18432 bytes per level
SIGT, LPAR = 0x1000, 0x1100             # in page H
STORE_BYTES = R.NSTORE * 8192


def load_profile():
    return json.load(open(ENH_PROFILE))


def lpar(level):
    lin = (level - 1) * LEVEL_BYTES
    return R.STORE + (lin >> 13), lin & 0x1FFF, (3 * (level - 1) + 1) << 4


def colour_index(word, b, code):
    """The hook's colour (palette index before the offset) of a pixel: word = the entry's word (0 = none), b = the
    pixel's stored bit (0 = left), code = its drawn code (1 ink, 2 body, 0 clear) -> index or None (transparent).
    Colour A = top nibble, colour B = next, selection = low byte: a selected opaque pixel takes B (0: INK, black),
    other body A (0: BODY), other ink INK. A selected clear pixel takes B too (speed5: the one silhouette exception,
    the bar bouncers' see-through holes filled; the painter selects no other clear pixel, and the silhouette guard
    in build_enh.py allows exactly the listed holes)."""
    ca, cb, sel = word >> 12, (word >> 8) & 15, word & 255
    if sel & (0x80 >> b):
        return cb or R.INK                  # colour B 0: black, drawn as ink
    if code == 0:
        return None
    return R.INK if code == 1 else (ca or R.BODY)


def sym_tables():
    """NIB0 / NIB1 of the Enhanced build: index graphic nibble << 4 | mask nibble -> the 4 pixels' symbols
    (0 clear, 1 ink, 2 body), a pair per byte as 4 s0 + s1."""
    t0, t1 = bytearray(256), bytearray(256)
    for i in range(256):
        g, m = i >> 4, i & 15
        px = [1 if g & (8 >> b) else (0 if m & (8 >> b) else 2) for b in range(4)]
        t0[i], t1[i] = 4 * px[0] + px[1], 4 * px[2] + px[3]
    return bytes(t0 + t1)


def sub_tables():
    """16 tables of 16 at SUB: colour c (0 = BODY), symbol pair 4 s0 + s1 -> pattern byte (clear 0, ink INK, body c)."""
    t = bytearray(256)
    for c in range(16):
        cc = c or R.BODY
        col = lambda s_: (0, R.INK, cc)[s_]
        for hi in range(3):
            for lo in range(3):
                t[16 * c + 4 * hi + lo] = col(hi) << 4 | col(lo)
    return bytes(t)


REV, SUB = 0x1200, 0x1400   # in page H


class EnhMap(dict):
    """The Enhanced colours as the verification models them (renegade.colour_of calls colour())."""
    enh = True

    def __init__(self, words, sigs):
        super().__init__({'enhanced': True})
        self.words, self.sigs = words, sigs
        self._last = (None, 0)

    def level(self, get):
        if self._last[0] is get:
            return self._last[1]
        lv = 0
        for L in sorted(self.sigs):
            if all(get(a) == v for a, v in self.sigs[L]):
                lv = L
                break
        self._last = (get, lv)
        return lv

    def colour(self, get, p, x, y, code):
        W = p['W']
        c = x - 8 * p['x']
        if p['mir']:
            c = 8 * W - 1 - c
        r = y - 8 - p['y']
        k, b = c >> 3, c & 7
        key = (p['gfx'] + 2 + 2 * R.stored_index(W, r, k)) & 0xFFFF
        L = self.level(get)
        w = self.words.get(L, {}).get(key, 0) if L and LO <= key < HI else 0
        if code == 0 and get(key) == 0xFF and get((key + 1) & 0xFFFF) == 0:
            return None                     # an all-clear byte: the hook draws nothing (pbyte's .zero path)
        ci = colour_index(w, b, code)
        if ci is None:
            return None
        return ci + (((3 * (L - 1) + 1 + p.get('cls', 0)) << 4) if L else 0)


def store_bytes(words):
    st = bytearray(STORE_BYTES)
    for L, ws in words.items():
        pg, of, _ = lpar(L)
        base = (pg - R.STORE) * 8192 + of
        for a, w in ws.items():
            if not LO <= a < HI or a & 1:
                raise ValueError('word for %04X outside the store' % a)
            i = base + (a - LO)
            st[i], st[i + 1] = w >> 8, w & 255
    return bytes(st)


def hook_page(sigs):
    p = bytearray(R.hook_page({'x': 1}))           # V_COL = 1
    at = SIGT
    for L in sorted(sigs):
        n = len(sigs[L])
        if not 1 <= n <= 255:
            raise ValueError('signature length')
        p[at] = n
        at += 1
        for a, v in sigs[L]:
            p[at:at + 3] = bytes((a & 255, a >> 8, v))
            at += 3
    p[at] = 0
    if at >= LPAR:
        raise ValueError('signature table too long')
    p[REV:REV + 256] = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))
    p[SUB:SUB + 256] = sub_tables()
    for L in sorted(sigs):
        pg, of, pb = lpar(L)
        p[LPAR + 4 * L:LPAR + 4 * L + 4] = bytes((pg, of & 255, of >> 8, pb))
    return bytes(p)


class EnhPatch(R.RenegadePatch):
    name = ('Target Renegade figures -> hardware sprites, Enhanced colours (per-level colour store, three palettes '
            'per level; alt ROM images 0 + 1, page 26 at slot 2, copy into page 27)')

    def __init__(self, words, sigs, palette, prof=None, rom_code=None):
        prof = prof or load_profile()
        super().__init__(prof=prof, colours={}, rom_code=rom_code)
        if len(palette) != 512:
            raise ValueError('the palette is 256 entries of 2 bytes')
        self.words, self.sigs, self.palette = words, sigs, bytes(palette)
        self.colours = EnhMap(words, sigs)
        self.hpage = bytearray(hook_page(sigs))
        self.store = store_bytes(words)
        self.page[0:512] = sym_tables()
        self.stub_extra = bytes.fromhex(prof['hooks']['setup']) + self.palette
        self._banks()


def palette_writes(patch):
    """Run the set-up's palette part (setup.back to its RET) in the simulator -> the 256 9-bit entries it loads
    into sprite palette 0 (NextReg 0x43 = 0x20, 0x40 = 0, then 0x44 pairs)."""
    syms = patch.syms
    back = int(load_profile()['hooks']['syms']['setup.back'], 16) if 'setup.back' not in syms else syms['setup.back']
    mem = bytearray(65536)
    mem[0xD000:0xD000 + len(patch.stub_extra)] = patch.stub_extra
    mem[0xBFFE:0xC000] = b'\x00\xC0'                  # return address 0xC000 (a HALT)
    mem[0xC000] = 0x76
    ns = R._NS(R._Dummy)
    regs = [0] * 28
    regs[12], regs[24] = 0xBFFE, back
    s = R._machine(R._sim_class(), _Flat(mem), regs, ns, 'setup')
    R._run_until(s, lambda r: r[24] == 0xC000, limit=200000)
    sel, idx, half, first, out = None, None, 0, 0, {}
    for e in ns.events:
        if e[0] != 'nr':
            continue
        reg, v = e[1], e[2]
        if reg == 0x43:
            sel = v
        elif reg == 0x40:
            idx, half = v, 0
        elif reg == 0x44 and sel == 0x20:
            if half == 0:
                first, half = v, 1
            else:
                out[idx] = first << 1 | (v & 1)
                idx, half = (idx + 1) & 255, 0
    return [out.get(i) for i in range(256)]


class _Flat:
    def __init__(self, m):
        self.m = m

    def __getitem__(self, a):
        return self.m[a & 0xFFFF]

    def __setitem__(self, a, v):
        self.m[a & 0xFFFF] = v

    def __len__(self):
        return 65536


def build_pair(start_z80, out_default, out_enh, words, sigs, palette, say=print):
    """The default sprite build and the Enhanced one from the same start snapshot."""
    import hashlib
    from . import z80tonex as zt
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    zt.convert(start_z80, out_default, quiet=True, patch=R.RenegadePatch(colours={}))
    p = EnhPatch(words, sigs, palette)
    sc = R.static_check(p.rom_code, 0x2200)
    zt.convert(start_z80, out_enh, quiet=True, patch=EnhPatch(words, sigs, palette))
    bad = R.boot_check(out_enh, start_z80, EnhPatch(words, sigs, palette))
    say('default %s  enhanced %s  static %s  boot %s' % (md5(out_default), md5(out_enh), 'PASS' if not sc else sc,
                                                          'OK' if not bad else bad[:3]))
    return not sc and not bad


# ---------------------------------------------------------------------------------------------
# Unit tests of the Enhanced build (the default build keeps renegade.unit_tests)
# ---------------------------------------------------------------------------------------------

def cls_of(obj):
    return 1 if obj == 0x0A else (2 if obj == 0x20 else 0)


def capture_states(cap_dir, log_path):
    """JNext captures of the ORIGINAL game in play (pilot runs/target_renegade_enh/jn/cap: a .sna at the copy
    62565 of a game frame and every plot call of that frame, with the object being drawn) -> commit states
    {R, mem, log, level, tag} for run_commit."""
    import re
    caps, cur, obj = {}, None, None
    for ln in open(log_path, errors='replace'):
        m = re.search(r'CAP (\S+) F=(\d+) lvl=(\d+)', ln)
        if m:
            cur = m.group(1)
            caps[cur] = dict(frame=int(m.group(2)), level=int(m.group(3)), log=[])
            continue
        if re.search(r'END (\S+)', ln):
            cur = None
            continue
        m = re.search(r'OB ([0-9A-F]{2})[0-9A-F]{2}', ln)
        if m and cur:
            obj = int(m.group(1), 16)
            continue
        if 'OB EXTRA' in ln and cur:
            obj = None
            continue
        m = re.search(r'PL (\d) ([0-9A-F]{4}) ([0-9A-F]{4})', ln)
        if m and cur:
            mir, hl, de = int(m.group(1)), int(m.group(2), 16), int(m.group(3), 16)
            caps[cur]['log'].append((hl, de >> 8, de & 255, mir | cls_of(obj) << 1))
    out = []
    for tag, c in sorted(caps.items()):
        # JNext writes the snapshot later in the frame than the trigger (mid draw-all for _a), so the state is
        # built: the memory of _a (the level's graphics, records, mirror table), registers for an entry to the
        # copy 62565 as the main loop makes it (CALL from 0xD7E3: return address 0xD7E6 on a stack at 0xFF60)
        d = open(os.path.join(cap_dir, tag + '_a.sna'), 'rb').read()
        p7 = d[49181]
        if p7 & 7:
            raise ValueError('%s: bank %d at 0xC000' % (tag, p7 & 7))
        mem = bytearray(bytes(16384) + d[27:27 + 49152])
        mem[0xFF60], mem[0xFF61] = 0xE6, 0xD7
        Rg = [0] * 30
        Rg[12], Rg[24], Rg[27], Rg[14] = 0xFF60, 62565, 2, 0x9F
        out.append(dict(R=Rg, mem=bytes(mem), log=c['log'], level=c['level'], tag=tag, frame=c['frame']))
    return out


def enh_unit_tests(patch, states, later, words, sigs, palette):
    """-> (Counter, fails). Cases as renegade.unit_tests (captured, cache hit, guard edges, log full, the plot
    hook's log, patterns full) for the Enhanced build, the commit on JNext captures of every level, and negative
    controls (each must be detected)."""
    import random
    rng = random.Random(7)
    u = collections.Counter()
    fails = collections.defaultdict(list)

    def chk(name, st, log, mem_edit=None, p=None, model=None, nmax=None, want_drop=None, expect_fail=False):
        p = p or patch
        ns, H, err = R.run_commit(p, st, log, mem_edit)
        exp, conv = R.expected_parts(patch, st, log, mem_edit, model or patch.colours, nmax)
        lay = ns.sprite_layer()
        bad = lay != exp or bool(err) or (want_drop is not None and H[R.V_DROP] != want_drop)
        u['cases'] += 1
        u['converted parts'] += conv
        if expect_fail:
            u['negative cases'] += 1
            u['negative detected'] += bad
            u['neg %s detected' % name] += bad
            return lay, exp
        if bad:
            u[name + '!'] += 1
            if len(fails[name]) < 3:
                d = [k for k in set(lay) | set(exp) if lay.get(k) != exp.get(k)]
                fails[name].append((len(d), sorted(d)[:3], [(lay.get(k), exp.get(k)) for k in sorted(d)[:3]], err[:2], H[R.V_DROP]))
        else:
            u['pixels compared'] += len(exp)
        return lay, exp

    offs = set()
    for st in states:
        log = R._log_of(st['H'])
        lay, exp = chk('captured (RZX)', st, log)
        offs |= {v >> 4 for v in exp.values()}
        ns, H, err = R.run_commit(patch, st, log)
        ns2, H2, err2 = R.run_commit(patch, st, log, ns=ns, H=R._relog(H, log))
        u['cache hit cases'] += 1
        if ns2.sprite_layer() != exp or err2:
            u['cache hit!'] += 1
    per_level = collections.Counter()
    for st in later:
        lay, exp = chk('capture L%d' % st['level'], st, st['log'])
        per_level[st['level']] += 1
        offs |= {v >> 4 for v in exp.values()}
        found = patch.colours.level(st['mem'].__getitem__)
        if found != st['level']:
            u['level found wrong!'] += 1
            fails['level'].append((st['tag'], found, st['level']))
    u['captures per level'] = dict(per_level)
    u['palette offsets used'] = sorted(offs)
    st = states[0]
    for W in (0, 1, 2, 6, 7):
        for Rr in (0, 1, 17, 64, 65):
            for kind in (0, 1, 2, 3, 5):
                for x, y in ((14, 70), (-1, 60), (31, 60), (0, 127)):
                    ed = R._synthetic(rng, W, Rr, q58=True)
                    d = (y + 40) & 255
                    e = (x + 1) & 255 if not kind & 1 else (x - 1 - 1 + W) & 255
                    chk('guard W%d R%d' % (W, Rr), st, [(0xB000, d, e, kind)], ed)
    for rec, g, nm in ((0x5E00, 0xB010, 'record below 0x6000'), (0xB000, 0x5E10, 'graphic below 0x6000'),
                       (0x6002, 0x6010, 'at 0x6000'), (0xB000, 0xE110, 'graphic in bank 0'), (0x7700, 0x7710, 'below 0x7800')):
        ed = R._synthetic(rng, 3, 20, at=rec, gat=g)
        chk(nm, st, [(rec, 80, 12, 2), (rec, 80, 20, 5)], ed)
    ed = R._synthetic(rng, 1, 8)
    log = [(0xB000, (40 + 8 * (i // 30)) & 255, 1 + i % 30, (i & 1) | (i % 3) << 1) for i in range(65)]
    chk('log full', st, log, ed)
    for n0 in (R.MAXLOG - 1, R.MAXLOG):
        for pc in (R.PLOT, R.PLOT_M):
            for obj in (0x0A, 0x20, 0x62):
                H = bytearray(patch.hpage)
                H[R.V_N] = n0
                ns = R._NS(patch)
                ns.H = H
                mem = bytearray(st['mem'])
                mem[0xDCA9] = obj
                get = mem.__getitem__
                Rg = list(st['R'])
                Rg[24], Rg[6], Rg[7], Rg[4], Rg[5] = pc, 0x9F, 0x12, 0x50, 0x0E
                err = []
                psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
                pv = R._PatchedView(get, ns, patch.alt_view(get), psite, {}, patch.store, err)
                ov = R._OrigView(get)
                so = R._machine(R._sim_class(), ov, list(Rg), R._NS(R._Dummy), 'o')
                R._run_until(so, lambda r: r[24] == pc + 3)
                sp_ = R._machine(R._sim_class(), pv, list(Rg), ns, 'p')
                R._run_until(sp_, lambda r: r[24] == pc + 3, each=lambda r, b=[]: R._safe(r, Rg, ns, err, b, 4))
                u['plot hook cases'] += 1
                kind = int(pc == R.PLOT_M) | cls_of(obj) << 1
                ok = not err and all(so.registers[i] == sp_.registers[i] for i in R.CMP) and ov.ov == pv.ov
                if n0 < R.MAXLOG:
                    ok = ok and H[R.V_N] == R.MAXLOG and H[R.V_DROP] == 0 and \
                        bytes(H[R.LOG + 5 * n0:R.LOG + 5 * n0 + 5]) == bytes([0x12, 0x9F, 0x0E, 0x50, kind])
                else:
                    ok = ok and H[R.V_N] == R.MAXLOG and H[R.V_DROP] == 1
                if not ok:
                    u['plot hook log!'] += 1
    ed, log = {}, []
    for i in range(40):
        a = 0x9000 + 0x110 * i
        ed.update(R._synthetic(rng, 4, 32, at=a, gat=a + 0x10))
        log.append((a, 70, (i * 3) % 28 + 1, (i % 3) << 1))
    chk('patterns full', st, log, ed, nmax=32, want_drop=8)
    # negative controls: each a broken Enhanced build, checked against the real design's model
    allst = [(s_, R._log_of(s_['H'])) for s_ in states] + [(s_, s_['log']) for s_ in later]

    def neg(name, p, sts=allst):
        hit = 0
        for s_, lg in sts:
            ns, H, err = R.run_commit(p, s_, lg)
            exp, _ = R.expected_parts(patch, s_, lg, None, patch.colours)
            hit |= ns.sprite_layer() != exp or bool(err)
            if hit:
                break
        u['negative cases'] += 1
        u['negative detected'] += hit
        u['neg %s detected' % name] = hit
    later_only = [(s_, s_['log']) for s_ in later]
    neg('store left out', EnhPatch({}, sigs, palette))
    p = EnhPatch(words, sigs, palette)
    code = bytearray(p.rom_code)
    i = code.find(bytes.fromhex('3A5240'))          # emit's LD A,(V_CLS) -> XOR A, NOP, NOP: class ignored
    code[i:i + 3] = bytes.fromhex('AF0000')
    neg('palette class ignored (P1 / P2 / enemies on one palette)', EnhPatch(words, sigs, palette, rom_code=bytes(code)))
    shifted = {L: {a + 2: w for a, w in ws.items() if a + 2 < HI} for L, ws in words.items()}
    neg('store shifted by one entry', EnhPatch(shifted, sigs, palette))
    bad_sig = {L: [(a, (v + 1) & 255) for a, v in s] for L, s in sigs.items()}
    neg('level signatures wrong (no level found)', EnhPatch(words, bad_sig, palette))
    swap = {1: words.get(2, {}), 2: words.get(1, {}), 3: words.get(4, {}), 4: words.get(3, {}), 5: words.get(5, {})}
    neg('levels 1-4 colour tables swapped', EnhPatch(swap, sigs, palette), later_only)
    # one graphic's painted entries changed (each run's colour moved on by one), in a graphic level 3's captures draw
    s3 = [s_ for s_ in later if s_['level'] == 3][0]
    g3 = s3['mem'].__getitem__
    gfx = next(R.guard(g3, rec, k) for rec, d, e, k in s3['log'] if R.guard(g3, rec, k) is not None)
    one = {L: dict(ws) for L, ws in words.items()}
    for j in range(g3(gfx) * g3(gfx + 1)):
        a = gfx + 2 + 2 * j
        w0 = one[3].get(a, 0)
        one[3][a] = (w0 & 0x0FFF) | ((((w0 >> 12) % 15) + 1) << 12)     # colour A moved on by one
    neg('one graphic\'s painted entries changed (level 3)', EnhPatch(one, sigs, palette), [(s3, s3['log'])])
    ip = EnhPatch(words, sigs, palette)
    a = ip.syms['e_cm'] - 0x2000
    ip.page[a:a + 4] = bytes.fromhex('FD210000')
    ns, H, err = R.run_commit(ip, st, R._log_of(st['H']))
    u['negative cases'] += 1
    u['negative detected'] += any(e[0] == 'interrupt-unsafe hook' for e in err)
    u['neg IY written in a hook detected'] = any(e[0] == 'interrupt-unsafe hook' for e in err)
    # the palette the set-up loads: the design's; a palette byte changed is seen
    want = [palette[2 * i] << 1 | (palette[2 * i + 1] & 1) for i in range(256)]
    u['palette entries loaded'] = sum(1 for x in palette_writes(patch) if x is not None)
    if palette_writes(patch) != want:
        u['palette loaded differs from the design!'] += 1
    badp = bytearray(palette)
    badp[2 * (16 * 2 + 3)] ^= 0x24                  # level 1, player 1's trousers (offset 2, index 3)
    u['negative cases'] += 1
    hit = palette_writes(EnhPatch(words, sigs, bytes(badp))) != want
    u['negative detected'] += hit
    u['neg palette byte changed detected'] = hit
    return u, fails
