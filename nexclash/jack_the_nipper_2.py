"""Jack the Nipper II - In Coconut Capers (Gremlin Graphics, 1987, 48K) engine 'jack_the_nipper_2'. Additive module:
reachable only through is_jack_the_nipper_2().

Game facts (games/jack_the_nipper_2.md): per object, 0xBAF9 gives each cell the figure covers a slot in a cell buffer
at 0xE900 (the dirty map 0xFB00-0xFD7F points at it) and copies the cell's background tile in; one of 16 blit paths
masks the figure into the slots through IY; the copier 0xBC62 writes each dirty cell to the screen, its attribute from
the slot's colour list 0xBD68 (the object's colour: the clash).

Hooks (asm/jack_the_nipper_2_hooks.asm, Next page JTN_PAGE at MMU slot 1 for the whole game): at each blit's
LD (0xBDE8),SP the hook records the figure and moves IY to a scratch buffer at 0x2900-0x2CFF, so the blit runs
unchanged (the same work) and the cell buffer keeps the background; at the copier's entry the commit puts the
scenery's attribute back into each slot's colour list entry (the tile colour table 0xED00) and turns the figures into
4-bit sprites in the object's own ink and paper. The slot-1 page, the tail restore and the Next model are Jack the
Nipper's (nexclash/jack_the_nipper.py).
"""
import json
import os

from . import jack_the_nipper as J1
from .hooklib import CMP as _CMP

CMP = _CMP                  # every register but R, T, MEMPTR (R: no LD A,R in the code)
JTN_PAGE = J1.JTN_PAGE
CODE_ORG = 0x3000           # hook code (asm ORG); its state sits below the scratch buffer, 0x2000-0x28FF
REGBLOCK = J1.REGBLOCK
TAIL_ADDR = 0xBF00          # the start-up tail; restore_tail puts its bytes back before the game starts
BUFFER = (0xE900, 0xED00)   # the cell buffer the blits draw into (128 slots of 8 bytes)
SCRATCH = (0x2900, 0x2D50)  # where they draw instead (IY high byte AND 0x3F; offsets up to +0x4F)
STATE = (0x2000, 0x2900)    # the page's hook state and stack
DIRTY, TILEMAP, TILEATTR, SLOTCOL = 0xFB00, 0xF800, 0xED00, 0xBD68
BLITS = (0xB34B, 0xB39B, 0xB3FD, 0xB471, 0xB579, 0xB5C1, 0xB618, 0xB679, 0xB727, 0xB75F, 0xB799, 0xB816, 0xB903,
         0xB931, 0xB960, 0xB9B3)
COPIER = 0xBC62
V_NFIG, V_SHOWN, MAXFIG = 0x21C0, 0x21C1, 24   # the hook state's figure count and sprites shown (asm)
SITES_ORIG = {**{a: 'ed73e8bd' for a in BLITS}, COPIER: '2180fd'}
SITE_SYM = {**{a: 'e_b%d' % i for i, a in enumerate(BLITS)}, COPIER: 'e_cmt'}
INTERIORS = tuple(a + k for a in BLITS for k in (1, 2, 3)) + (COPIER + 1, COPIER + 2)
X_DRAWN = 0xB2D5            # the draw's x (stored at 0xB2B3)
PLAY = (256, 160)           # the play area: 32 x 20 cells

_HERE = os.path.dirname(os.path.abspath(__file__))


def _profile_path():
    for p in (os.path.join(_HERE, '..', 'docs', 'profiles', 'jack_the_nipper_2.json'),
              os.path.join(_HERE, 'jack_the_nipper_2.json')):
        if os.path.exists(p):
            return p
    raise FileNotFoundError('jack_the_nipper_2.json profile not found')


def load_profile():
    return json.load(open(_profile_path()))


def is_jack_the_nipper_2(snap):
    """True only for Jack the Nipper II: 48K and the draw 0xB28B's first bytes."""
    try:
        sg = load_profile()['signature']
    except FileNotFoundError:
        return False
    if snap.machine != '48K':
        return False
    a, sig = int(sg['addr']), bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[a:a + len(sig)]) == sig


class _Page(J1._PagePatch):
    tail_addr = TAIL_ADDR
    code_org = CODE_ORG


class PlainPatch(_Page):
    name = 'Jack the Nipper II plain conversion'


class JtnPatch(_Page):
    name = 'Jack the Nipper II figures -> hardware sprites (slot-1 page, scratch-buffer redirect)'

    def __init__(self, prof=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        if self.syms['code_start'] != self.code_org:
            raise ValueError('hook code assembled at 0x%04X, not 0x%04X' % (self.syms['code_start'], self.code_org))
        super().__init__(bytes.fromhex(h['page']))
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = self.syms['setup']
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[SITE_SYM[a]].to_bytes(2, 'little'))
                      for a, old in SITES_ORIG.items()]


def build(z80, out, name, say=print):
    """Both builds with their boot checks. -> (plain path, sprites path, problems)"""
    import hashlib
    from . import z80tonex as zt
    from .nextboot import check
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    bad, paths = [], []
    for label, patch, suffix in (('Plain', PlainPatch(), ''), ('Sprites', JtnPatch(), '_sprites')):
        path = os.path.join(out, name + suffix + '.nex')
        conv = zt.convert(z80, path, None, True, quiet=True, patch=patch, keep_printer_buffer=True)
        b = check(path, z80, patch, (conv[1], conv[1] + len(conv[2])))
        say('%-10s: %s  %s  boot %s  (tail 0x%04X, %d bytes, put back)' % (
            label, os.path.basename(path), md5(path), 'OK' if not b else 'MISMATCH %s' % str(b[:3])[:200],
            conv[1], len(conv[2])))
        bad += b
        paths.append(path)
    return paths[0], paths[1], bad


# ---------------------------------------------------------------------------------------------
# Verify (PLAYBOOK 6)
# ---------------------------------------------------------------------------------------------

DRAW = (0xB28B, 0xBC62)     # the draw and its blits: a blit run ends back in the object loop
COPY = (0xBC62, 0xBD70)     # the copier
SITE_KIND = {**{a: 'blit' for a in BLITS}, COPIER: 'copy'}


def figure_of(regs, get):
    """The figure a blit is about to draw, from the original's state at its site."""
    ix = regs[8] << 8 | regs[9]
    t = get(ix + 2)
    for bit, (w, rows) in ((1, (2, 16)), (2, (2, 24)), (4, (3, 24)), (8, (3, 32)), (16, (2, 24))):
        if t & bit:
            break
    else:
        w, rows = 3, 32
    col = get(ix + 9)
    return dict(gfx=regs[6] << 8 | regs[7], rows=rows, width=w, x=get(X_DRAWN), y=get(ix + 1),
                mirror=bool(get(ix + 5) & 2), ink=col & 7, paper=col >> 3 & 7, bright=bool(col & 0x40))


def figure_pixels(f, get):
    """{(x, y): 1 ink / 2 paper} on the screen (rows top first: the mask bytes, then the graphics bytes)."""
    out = {}
    w, w8 = f['width'], f['width'] * 8
    for r in range(f['rows']):
        row = f['gfx'] + r * 2 * w
        for b in range(w):
            m, g = get((row + b) & 0xFFFF), get((row + w + b) & 0xFFFF)
            for bit in range(8):
                gb, mb = g >> (7 - bit) & 1, m >> (7 - bit) & 1
                v = 1 if gb else 2 if not mb else 0
                if v:
                    c = b * 8 + bit
                    out[f['x'] + (w8 - 1 - c if f['mirror'] else c), f['y'] + r] = v
    return out


def code(attr, v):
    """The sprite pixel value of an attribute's ink (v = 1) or paper (v = 2): 1-8 normal black .. white, 9-15 bright
    blue .. white, bright black = 1 (asm `codes`; one palette bank)."""
    c = attr & 7 if v == 1 else attr >> 3 & 7
    return (8 + c if c else 1) if attr & 0x40 else 1 + c


def slot_cells(get):
    """{slot: (cell column, cell row)} from the dirty map."""
    out = {}
    for i in range(640):
        v = get(DIRTY + i)
        if v >= 3:
            out[v] = (i % 32, i // 32)
    return out


RUN_ON = 400000
DEAD_FIRST, DEAD_EVERY = 300, 100  # dead_regs on the first 300 blits, then every 100th (every blit: ~40 h on the whole recording)


def dead_regs(base, writes, ro, rp, n=RUN_ON):
    """Whether the registers in which the patched run ended differently are dead: the original machine run on from
    its end state, once as it is and once with the patched values, in lockstep (the same PC at every step) until every
    register agrees and memory agrees too, apart from popped bytes below SP (a pushed copy may be popped and reloaded
    on the way: 0x9D91 pushes IY, the next object pops it, then loads IY afresh). A different path: live; no agreement
    within n: live."""
    from skoolkit.simulator import Simulator
    mem = bytearray(base)
    for a, v in writes.items():
        mem[a] = v
    sims = []
    for r in (list(ro), [rp[i] if i in CMP else ro[i] for i in range(len(ro))]):
        sim = Simulator(bytearray(mem), {})
        sim.registers[:] = r
        sims.append(sim)
    A, B = sims
    ra, rb = A.registers, B.registers
    ma, mb = A.memory, B.memory
    for _ in range(n):
        A.opcodes[ma[ra[24]]]()
        B.opcodes[mb[rb[24]]]()
        if ra[24] != rb[24]:
            return False                    # the value changed the game's path: live
        if ra == rb or all(ra[i] == rb[i] for i in CMP):
            if ma == mb:
                return True
            sp = ra[12]
            if all(sp - 0x100 <= x < sp for x in range(65536) if ma[x] != mb[x]):
                return True                 # only popped bytes below SP differ
    return False


_BLITS_SEEN = [0]


def pair(patch, regs, base, vpage, vns, span):
    """One site from one state, original and patched. -> (failures, allowed, details, original writes, page writes)"""
    import collections
    from skoolkit.simulator import Simulator
    from .simpool import machine
    from . import z80n
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    O, P = J1._overlays(base, vpage, psite, STATE, SCRATCH)
    o, p = O(), P()
    so = machine(Simulator, o, list(regs), 'j2o')
    sp = Simulator(p, {})
    sp.registers[:] = list(regs)
    p.R = sp.registers
    J1._writable_slot1(sp, p.__setitem__)
    z80n.install(sp, vns.nextreg)
    sp.set_tracer(vns)
    vns.events = []
    speed0 = vns.nr.get(0x07, 0)
    bad, ok, det = collections.Counter(), collections.Counter(), []
    sp0 = regs[12]

    def ran(sim):
        R, ops, mem = sim.registers, sim.opcodes, sim.memory
        for _ in range(5000000):
            pc = R[24]
            if span is DRAW and not 0x2000 <= pc < 0x4000 and pc in BLITS:      # the next blit of this object, or
                if R[12] == sp0 and sim is not sp and False:
                    return True
            if not span[0] <= pc < span[1] and not 0x2000 <= pc < 0x4000 and R[12] > sp0:
                return True
            ops[mem[pc]]()
        return False
    if not (ran(so) and ran(sp)):
        bad['did not return!'] += 1
        return bad, ok, det, o.w, p.pw
    jb = patch.syms['j_back'] + 1
    for e in p.err:
        k = e[0]
        if k == 'write to the page outside state and scratch' and e[1] in (jb, jb + 1):
            continue                        # the scratch buffer, and the shared blit body's way back (its JP operand)
        bad[k + '!'] += 1
        det.append(e)
    if vns.events:
        bad['port access outside the Next side!'] += 1
        det.append(('ports', vns.events[:4]))
    if vns.nr.get(0x07, 0) != speed0:
        bad['CPU speed not given back!'] += 1
    ro, rp = so.registers, sp.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff and span is DRAW and 10 in diff and rp[10] == ro[10] & 0x3F:
        # IY moved to the scratch buffer, and what the blit read back from there (A, the flags): dead if the game sets
        # them before it reads them (the next object loads IY afresh); proved on a sample (DEAD_FIRST, DEAD_EVERY)
        n = _BLITS_SEEN[0] = _BLITS_SEEN[0] + 1
        if n > DEAD_FIRST and n % DEAD_EVERY:
            ok['IY moved (not sampled)'] += 1
        elif dead_regs(base, o.w, ro, rp):
            ok['IY moved, and values read from the scratch (dead)'] += 1
        else:
            bad['moved IY or scratch values read later!'] += 1
            det.append(('registers', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    elif diff and span is COPY and set(diff) <= {21}:
        # E' holds the last copied cell's colour, the scenery's here: dead if the game sets it before reading it
        if dead_regs(base, o.w, ro, rp):
            ok["E' cell colour (dead)"] += 1
        else:
            bad["E' cell colour read later!"] += 1
    elif diff:
        bad['registers differ!'] += 1
        det.append(('registers', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    rest_o = {a: v for a, v in o.w.items() if not BUFFER[0] <= a < BUFFER[1]} if span is DRAW else dict(o.w)
    rest_p = dict(p.w)
    if span is COPY:
        # the intended difference: the colour list holds the scenery's colour, so the figure cells' attributes do
        cells = slot_cells(base.__getitem__)
        for s, (cx, cy) in cells.items():
            want = base[TILEATTR + base[TILEMAP + cy * 32 + cx]]
            if rest_p.get(SLOTCOL + s, base[SLOTCOL + s]) != want:
                bad['colour list not the scenery\'s!'] += 1
            rest_o.pop(SLOTCOL + s, None)
            rest_p.pop(SLOTCOL + s, None)
            a = 0x5800 + cy * 32 + cx
            if a in rest_p and rest_p[a] != want:
                bad['figure cell attribute not the scenery\'s!'] += 1
            rest_o.pop(a, None)
            rest_p.pop(a, None)
    buf_p = {a for a in p.w if BUFFER[0] <= a < BUFFER[1]} if span is DRAW else set()
    if buf_p:
        bad['patched blit wrote the cell buffer!'] += 1
    stack = {a for a in set(rest_o) | set(rest_p) if ro[12] - 0x100 <= a < ro[12] and rest_o.get(a) != rest_p.get(a)}
    for a in stack:                         # popped bytes below the caller's SP
        rest_o.pop(a, None)
        rest_p.pop(a, None)
    if stack:
        ok['stack below SP (dead)'] += 1
    if rest_o != rest_p:
        bad['memory differs!'] += 1
        ks = sorted(set(rest_o) ^ set(rest_p) | {a for a in rest_o if rest_p.get(a) != rest_o[a]})
        det.append(('memory', ['%04X' % a for a in ks[:8]]))
    if span is DRAW:
        moved = {a - 0xC000 for a in o.w if BUFFER[0] <= a < BUFFER[1]}
        scratch = {a for a in p.pw if SCRATCH[0] <= a < SCRATCH[1]}
        if moved != scratch:
            bad['scratch writes are not the buffer writes moved by 0xC000!'] += 1
            det.append(('scratch', len(moved), len(scratch), sorted(moved ^ scratch)[:6]))
    return bad, ok, det, o.w, p.pw


def _snap64(sim):
    m = sim.memory
    try:
        return bytes(m[:65536])
    except TypeError:                       # a 128K recording's paging memory
        return bytes(m[a] for a in range(65536))


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Differential test (PLAYBOOK 6). Blits: the redirect. Copier entry: the commit (the colour list holds the
    scenery's colour), then the picture: the figures blitted since the last copy, modelled from their graphics, must
    give the original's buffer slots over the background tiles they were drawn on, and be the visible sprites pixel for
    pixel (the object's ink and paper, mirror, later on top). -> (Counter, examples, states)"""
    import collections
    from . import rzx as RZ
    c = collections.Counter()
    ex = collections.defaultdict(list)
    states = []
    vpage = bytearray(patch.page)
    vns = J1.NextSide()
    upd = {'figs': [], 'pre': {}}
    _BLITS_SEEN[0] = 0

    def fail(k, info):
        c[k] += 1
        if len(ex[k]) < 5:
            ex[k].append(info)

    def on(pc, sim):
        regs, base = list(sim.registers), _snap64(sim)
        get = base.__getitem__
        c[SITE_KIND[pc]] += 1
        if pc in BLITS:
            upd['figs'].append(figure_of(regs, get))
            bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, DRAW)
            for a in ow:
                if BUFFER[0] <= a < BUFFER[1]:
                    upd['pre'].setdefault(a, base[a])
                    c['figure bytes redirected'] += 1
        else:
            bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, COPY)
            picture(get)
        for k, n in ok.items():
            c[k] += n
        for k, n in bad.items():
            for _ in range(n):
                fail(k, (hex(pc), det))
        if collect and sum(1 for x in states if x[0] == pc) < collect:
            states.append((pc, regs, base))

    def picture(get):
        figs, pre = upd['figs'], upd['pre']
        exp = {}
        for f in figs:
            col = (f['ink'], f['paper'], f['bright'])
            for xy, v in figure_pixels(f, get).items():
                exp[xy] = (v, col)
        cells = slot_cells(get)
        for a, b0 in pre.items():
            s, k = (a - BUFFER[0]) // 8, (a - BUFFER[0]) % 8
            if s not in cells:
                continue
            cx, cy = cells[s]
            want = 0
            for bit in range(8):
                v = exp.get((cx * 8 + bit, cy * 8 + k))
                pb = b0 >> (7 - bit) & 1 if v is None else (1 if v[0] == 1 else 0)
                want |= pb << (7 - bit)
            if want != get(a):
                fail('figure model differs from the original drawing!', ('%04X' % a, want, get(a)))
        c['picture bytes checked'] += len(pre)
        got, bad = J1.render(vns)
        for b in bad:
            fail('sprite attributes!', b)
        want = {}
        for (x, y), (v, _) in exp.items():   # each pixel in its cell's colour, from the original's own colour list
            if 0 <= x < PLAY[0] and 0 <= y < PLAY[1]:
                s = get(DIRTY + (y >> 3) * 32 + (x >> 3))
                if s < 3:
                    fail('figure pixel on a cell with no slot!', (x, y))
                    continue
                want[(x + 32, y + 32)] = (code(get(SLOTCOL + s), v), 0)
        have = {k: v for k, v in got.items() if 32 <= k[0] < 32 + PLAY[0] and 32 <= k[1] < 32 + PLAY[1]}
        if want != have:
            d = sorted(set(want) ^ set(have) | {k for k in want if have.get(k) != want[k]})
            fail('SPRITE PIXEL difference!', (len(d), d[:4], [(want.get(k), have.get(k)) for k in d[:4]]))
        c['sprite pixels compared'] += len(want)
        upd['figs'], upd['pre'] = [], {}

    frames, err = RZ.trace(rzx_path, set(SITE_KIND), on, stop=stop)
    c['frames'] = frames
    if err:
        fail('replay desync!', err)
    return c, dict(ex), states


def _sym(patch, name):
    return patch.syms[name] - 0x2000


def negative_patches(patch=None):
    """Broken builds the verifier must catch: {name: patch}."""
    import copy
    base = patch or JtnPatch()
    out = {}

    def make(name, edits):
        p = copy.deepcopy(base)
        pg = bytearray(p.page)
        for off, b in edits:
            pg[off:off + len(b)] = b
        p.page = bytes(pg)
        p.extra_banks = {J1.JTN_PAGE // 2: p.page + bytes(8192)}
        out[name] = p
    make('no redirect (AND 0xFF)', [(_sym(base, 'blit.n_red') + 1, b'\xFF')])
    make('colour list not put back', [(_sym(base, 'rest.n_col') + 6, b'\x00')])
    make('one colour for every figure', [(_sym(base, 'fcolour.n_multi') + 3, b'\x01')])
    make('multi-colour cache ignores the colours', [(_sym(base, 'sigeq.n_sig'), b'\x00\x00')])
    make('never mirrored', [(_sym(base, 'attrs.n_mir') + 1, b'\x00')])
    make('wrong palette bank', [(_sym(base, 'attrs.n_bank') + 1, b'\x01')])
    make('leftover sprites not hidden', [(_sym(base, 'commit.n_hide'), b'\x7A\x00\x00')])
    make("caller's speed not given back", [(_sym(base, 'e_cmt.n_spd') + 4, b'\x00\x00\x00')])
    return out


def unit_tests(patch, states, negs=(), rzx=None, neg_frames=1500):
    """Every site at the four CPU speeds (hooklib.every_site); the copy as a hide (hooklib.hide_cases: every sprite
    shown, no figure recorded: all hidden); a blit with the figure table full (refused, the table untouched); the
    negative controls on the first neg_frames of rzx. -> Counter"""
    import collections
    from . import hooklib
    c = collections.Counter()
    first = {}
    for pc, regs, base in states:
        first.setdefault(pc, (regs, base))

    def run_at(pc, clock):
        regs, base = first[pc]
        vpage, vns = bytearray(patch.page), J1.NextSide()
        vns.nr[0x07] = clock
        bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, COPY if pc == COPIER else DRAW)
        state = (tuple(sorted(bad)), tuple(sorted(ow.items())), bytes(vns.attr), bytes(vns.pat))
        return vns.nr.get(0x07, 0), state
    cs, rows = hooklib.every_site(list(first), run_at)
    for k, v in cs.items():
        c['every site: ' + k] += v

    def hide_run(pc, st, speed):
        regs, base = st[1], st[2]
        vpage, vns = bytearray(patch.page), J1.NextSide()
        vns.nr[0x07] = speed
        for n in range(16):                 # sprites on show from an earlier update
            vns.attr[5 * n:5 * n + 5] = bytes([40 + n, 40, 0, 0xC0, 0x80])
        vpage[V_SHOWN - 0x2000] = 16
        bad, ok, det, ow, pw = pair(patch, regs, base, vpage, vns, COPY)
        shown = [n for n in range(128) if vns.attr[5 * n + 3] & 0x80]
        return [k for k in bad], shown
    copies = [s for s in states if s[0] == COPIER]
    if copies:
        for k, v in hooklib.hide_cases(copies, {COPIER: 'copy with no figure'}, hide_run).items():
            c[k] += v
    for pc, regs, base in [s for s in states if s[0] in BLITS][:4]:
        vpage, vns = bytearray(patch.page), J1.NextSide()      # the table full: the record refused, nothing written
        vpage[V_NFIG - 0x2000] = MAXFIG
        before = bytes(vpage[:V_NFIG - 0x2000 + 1])
        pair(patch, regs, base, vpage, vns, DRAW)
        c['figure table full ' + ('ok' if bytes(vpage[:V_NFIG - 0x2000 + 1]) == before else 'FAIL!')] += 1
    if rzx:
        for name, np_ in (negs or negative_patches(patch)).items():
            cc, ex, _ = verify(np_, rzx, stop=neg_frames)
            caught = [k for k in cc if k.endswith('!')]
            c['negative %s: %s' % (name, 'DETECTED' if caught else 'MISSED!')] += 1
    return c


def auto(a, z80, name, out, say):
    """The whole run: plain + sprite builds with boot checks, verify each recording, unit tests + negative controls."""
    import os as _os
    say('Game      : %s' % name)
    say("Engine    : jack_the_nipper_2 (the game's own blits into a scratch buffer; figures as 4-bit sprites)")
    plain, spr, bad = build(z80, out, name, say)
    ok = not bad
    patch = JtnPatch()
    from . import z80tonex as zt
    patch.apply(zt.Z80Snapshot(z80))
    states, first_rzx = [], None
    for r in list(getattr(a, 'rzx', None) or []):
        first_rzx = first_rzx or r
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=12)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails and c.get('copy', 0) > 0
        say('Verify    : %s  %d frames, blits %d, copies %d, figure bytes redirected %d, picture bytes %d, '
            'sprite pixels %d -> %s' % (
                _os.path.basename(r), c['frames'], c['blit'], c['copy'], c['figure bytes redirected'],
                c['picture bytes checked'], c['sprite pixels compared'],
                'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Allowed   : %s  %s' % (_os.path.basename(r),
                                    {k: v for k, v in c.items() if '(dead)' in k or 'sampled' in k}))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:200]))
    if states:
        u = unit_tests(patch, states, rzx=first_rzx)
        ufail = [k for k in u if k.endswith('!')]
        ok = ok and not ufail
        say('Unit      : %s -> %s' % (', '.join('%s %d' % kv for kv in sorted(u.items())), 'FAIL' if ufail else 'PASS'))
    elif getattr(a, 'rzx', None):
        ok = False                          # a verify run that reached no site covers nothing
        say('Unit      : no states from the recordings: FAIL')
    else:
        say('Unit      : not run (no recording: a rebuild)')
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok
