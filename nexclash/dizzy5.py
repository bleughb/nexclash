"""'dizzy5' engine (Spellbound Dizzy / Dizzy V): masked 24-pixel sprite with an XOR undo buffer,
drawn and erased by the IM2 interrupt handler on request (req/state flags), frames in a
3-byte table (height, pointer), 4-pixel horizontal steps, mirroring via a bit-reverse table.

Patch design (PLAYBOOK step 4, from the Dizzy V analysis):
  * plotter and eraser run unchanged except their 8 screen writes (NOPs), so the undo buffer
    and all game state evolve exactly as before;
  * plot hook (at the plotter's 'LD (state),A'): shows 4 hardware sprites at the new frame,
    position and mirror state; erase hook (same instruction in the eraser): hides them.
    Erase and plot run in different interrupts, so the visibility is the original's;
  * no virtual read, no box/wipe hook (analysis: no logic reads the player's pixels, and all
    wipes run with the player erased);
  * hook code and pattern table live in RAM page 24 at MMU slot 1, which is a copy of ROM
    0x2000-0x3FFF (the game prints with the ROM font at 0x3D00), so the hooks must sit in
    ROM bytes the game never reads; the start-up tail goes in the undo buffer (every plot
    writes the rows the next erase reads, so its start-up content is never used).
Loader-stage snapshots (engine not yet relocated) are started from loader.prerun().
Hook source: asm/dizzy5_hooks.asm (sjasmplus output == hook_code() bytes for Dizzy V)."""
import collections
from .identify import _find, _p, w
from .sprites import build_patterns
from . import build as B

PAGE = 24
ORG = 0x3800                      # hook code + table + register block: ROM 0x3800-0x3CFF


def identify5(mem):
    """Profile dict (engine 'dizzy5'), a 'dizzy5_like' hint dict, or None. A copy of the engine
    only counts if the interrupt handler dispatches to it (AND A / JP Z,plotter / JP eraser):
    a relocating loader leaves an inert source copy in memory as well."""
    m = bytes(mem)
    core = _find(m, _p('7E D9 A1 B0 D9 47 AE 12 70'))
    if not core:
        return None
    hint = None
    for X in core:
        prof = _derive(m, X)
        if prof.get('engine') == 'dizzy5':
            return prof
        hint = hint or prof
    return hint


def _derive(m, X):
    ent = [a for a in _find(m, _p('3A ?? ?? A7 C0 32 ?? ?? 21 ?? ?? ED 5B ?? ?? 16 00 3A ?? ?? A7 20 02 1E'))
           if X - 400 < a < X]
    if len(ent) != 1:
        return {'engine': 'dizzy5_like', 'hint': 'Dizzy V plot loop at %d, plotter entry not recognised' % X}
    P = ent[0]
    state = w(m, P + 6)
    er = [a for a in _find(m, [0x3A, state & 255, state >> 8, 0xA7, 0xC0, 0x3D, 0x32, state & 255, state >> 8])
          if X < a < X + 200]
    if len(er) != 1:
        return {'engine': 'dizzy5_like', 'hint': 'Dizzy V plotter at %d, eraser not found' % P}
    E = er[0]
    if not _find(m, [0xA7, 0xCA, P & 255, P >> 8, 0xC3, E & 255, E >> 8]):
        return {'engine': 'dizzy5_like', 'hint': 'Dizzy V engine copy at %d is not called (relocating loader?)' % P}

    def one(pat, lo, hi):
        r = [a for a in _find(m, _p(pat)) if lo <= a < hi]
        return r[0] if len(r) == 1 else None
    nf, yv, fv, xv = one('D6 ?? 38', P, P + 60), one('3A ?? ?? 91 32', P, X), \
        one('3A ?? ?? 21 ?? ?? 07 38', P, X), one('3A ?? ?? CB 3F 32', P, X)
    und = one('31 ?? ?? 3A', E, E + 20)
    prof = {
        'engine': 'dizzy5', 'plotter': P, 'eraser': E, 'player_end': E + 62,
        'req': w(m, P + 1), 'state': state, 'frame_table': w(m, P + 9), 'frame_var': w(m, P + 13),
        'frame_flag': w(m, P + 18), 'frame_default': m[P + 24],
        'num_frames': m[nf + 1] if nf else None,
        'y_var': w(m, yv + 1) if yv else None, 'flip_var': w(m, fv + 1) if fv else None,
        'x_var': w(m, xv + 1) if xv else None, 'undo_buffer': w(m, und + 1) if und else None,
        'plot_site': P + 5, 'plot_cont': P + 8, 'erase_site': E + 6, 'erase_cont': E + 9,
        'plotter_writes': [a for a in range(X, X + 60) if m[a] == 0x70 and m[a - 1] == 0x12 and m[a - 2] == 0xAE],
        'eraser_writes': [a for a in range(E, E + 62) if m[a] == 0x12 and m[a - 1] in (0xA8, 0xA9) and m[a - 2] == 0x1A],
    }
    notes = []
    for k in ('num_frames', 'y_var', 'flip_var', 'x_var', 'undo_buffer'):
        if prof[k] is None:
            notes.append('%s not found uniquely' % k)
    if len(prof['plotter_writes']) != 4 or len(prof['eraser_writes']) != 4:
        notes.append('screen-write sites: %d plotter, %d eraser (expected 4 and 4)'
                     % (len(prof['plotter_writes']), len(prof['eraser_writes'])))
    if not notes:
        try:
            prof['undo_size'] = 4 * max(h for h, px in read_frames(lambda a: m[a], prof))
        except ValueError as e:
            notes.append(str(e))
    prof['notes'] = notes
    prof['ok'] = not notes
    return prof


def read_frames(peek, prof):
    """(height, {(x, y): 'T'|'K'|'W'}) per frame; row = 3 x (mask, graphic); out = scr&mask|gfx."""
    frames = []
    t = prof['frame_table']
    for n in range(prof['num_frames']):
        h = peek(t + 3 * n)
        a = peek(t + 3 * n + 1) | peek(t + 3 * n + 2) << 8
        if not 1 <= h <= 32:
            raise ValueError('frame %d has height %d - not the expected game data' % (n, h))
        px = {}
        for r in range(h):
            for bx in range(3):
                mk, gf = peek(a + 6 * r + 2 * bx), peek(a + 6 * r + 2 * bx + 1)
                for bit in range(8):
                    g = (gf >> (7 - bit)) & 1
                    px[(bx * 8 + bit, r)] = 'W' if g else ('T' if (mk >> (7 - bit)) & 1 else 'K')
        frames.append((h, px))
    return frames


# ---------------------------------------------------------------------------------------------
# Hook code (hand-assembled; source listing in HOOKS_ASM below, checked against sjasmplus)
# ---------------------------------------------------------------------------------------------

def _w(v):
    return bytes([v & 255, (v >> 8) & 255])


def hook_code(prof, org=ORG):
    """Returns (code bytes incl. pattern table placeholder offset, syms)."""
    c = bytearray()
    NR = lambda r, v: b'\xED\x91' + bytes([r, v])          # NEXTREG r,v
    NA = lambda r: b'\xED\x92' + bytes([r])                # NEXTREG r,A
    fix = {}
    # T_PLOT: registers AF BC DE HL BC' DE' HL' are dead here (the plotter assigns them all
    # before use); EXX count is even and AF' is untouched, so the ISR's restore is unaffected.
    syms = {'T_PLOT': org}
    c += b'\x32' + _w(prof['state'])                      # ld (state),a      (original)
    c += b'\x3A' + _w(prof['frame_flag'])                 # ld a,(flag)
    c += b'\xA7'                                          # and a
    c += b'\x3A' + _w(prof['frame_var'])                  # ld a,(frame)
    c += b'\x20\x02'                                      # jr nz,+2
    c += b'\x3E' + bytes([prof['frame_default']])         # ld a,default
    c += b'\xFE' + bytes([prof['num_frames']])            # cp nframes
    hide_jr = len(c)
    c += b'\xD2\x00\x00'                                  # jp nc,hide (patched)
    c += b'\x6F\x26\x00\x29\x29\x29'                      # ld l,a / ld h,0 / add hl,hl x3
    fix['TABLE'] = len(c) + 1
    c += b'\x11\x00\x00'                                  # ld de,table
    c += b'\x19'                                          # add hl,de
    c += b'\xD9'                                          # exx
    c += b'\x3A' + _w(prof['x_var'])                      # ld a,(x)
    c += b'\x6F\x26\x00\x29\x29'                          # ld l,a / ld h,0 / add hl,hl x2  (x*4)
    c += b'\x11\x20\x00\x19'                              # ld de,32 / add hl,de
    c += b'\x3A' + _w(prof['flip_var'])                   # ld a,(flip)
    c += b'\x07'                                          # rlca
    c += b'\x30\x07'                                      # jr nc,mir
    c += b'\x0E\x00\x11\x10\x00\x18\x09'                  # ld c,0 / ld de,16 / jr go
    c += b'\x0E\x08\x11\x08\x00\x19\x11\xF0\xFF'          # mir: ld c,8 / ld de,8 / add hl,de / ld de,-16
    c += b'\xEB\x19'                                      # go: ex de,hl / add hl,de  -> DE'=left x, HL'=right x

    def sprite(n, right, dy):
        s = bytearray(NR(0x34, n))
        s += b'\x7D' if right else b'\x7B'                # ld a,l / ld a,e
        s += NA(0x35)
        s += b'\x3A' + _w(prof['y_var'])                  # ld a,(y)
        if dy:
            s += b'\xC6' + bytes([dy])                    # add a,dy
        s += NA(0x36)
        s += b'\x7C' if right else b'\x7A'                # ld a,h / ld a,d
        s += b'\xE6\x01\xB1'                              # and 1 / or c
        s += NA(0x37)
        s += b'\xD9\x7E\x23' + NA(0x38) + b'\x7E\x23' + NA(0x39) + b'\xD9'   # exx / attr3,4 / exx
        return bytes(s)
    c += sprite(0, False, 0) + sprite(1, True, 0) + sprite(2, True, 16) + sprite(3, False, 16)
    c += b'\xD9'                                          # exx (back: even count)
    c += NR(0x15, 0x01)                                   # sprites on
    c += b'\xC3' + _w(prof['plot_cont'])                  # jp plotter+8
    c[hide_jr + 1:hide_jr + 3] = _w(org + len(c))
    c += NR(0x15, 0x00)                                   # hide: sprites off
    c += b'\xC3' + _w(prof['plot_cont'])
    syms['T_ERASE'] = org + len(c)
    c += b'\x32' + _w(prof['state'])                      # ld (state),a      (original)
    c += NR(0x15, 0x00)                                   # sprites off
    c += b'\xC3' + _w(prof['erase_cont'])                 # jp eraser+9
    syms['table'] = org + len(c)
    c[fix['TABLE']:fix['TABLE'] + 2] = _w(syms['table'])
    return bytes(c), syms


def sites(prof, syms):
    st = _w(prof['state'])
    s = [(prof['plot_site'], b'\x32' + st, b'\xC3' + _w(syms['T_PLOT'])),
         (prof['erase_site'], b'\x32' + st, b'\xC3' + _w(syms['T_ERASE']))]
    s += [(a, b'\x70', b'\x00') for a in prof['plotter_writes']]
    s += [(a, b'\x12', b'\x00') for a in prof['eraser_writes']]
    return s


class D5Patch:
    """Hook page = ROM 0x2000-0x3FFF + hooks at ORG; flag-free (NextReg $15). strategy 'altrom'
    (default): the page's hook bytes go into alt ROM image 1 (ROM3 copy) - same memory as the game
    sees with 'slot1', where the page is RAM page 24 mapped at slot 1."""

    def __init__(self, prof, tail_addr, max_tail, rom=None, strategy='altrom'):
        if strategy not in ('altrom', 'slot1'):
            raise ValueError('Dizzy V builder supports --strategy altrom or slot1')
        self.prof = prof
        self.name = 'Dizzy V engine hardware sprite (%s)' % strategy
        self.strategy = strategy
        self.altrom = None
        self.stub_extra = b''
        self.setup_call = B.SETUP_ORG
        self.hook_page_data = b''
        self.extra_banks = {}
        self.uses_printer_buffer = True
        self.code, self.syms = hook_code(prof)
        self.sites = sites(prof, self.syms)
        if rom is None:                   # the real 48K ROM (Snapshot.memory holds ZEROS below 0x4000)
            from skoolkit import ROM48, read_bin_file
            rom = read_bin_file(ROM48, 16384)
        self.rom = bytes(rom[0x2000:0x4000])
        if not any(self.rom[0x1D00:0x2000]):
            raise ValueError('ROM copy for the slot-1 page is empty (font missing)')
        self.tail_addr, self.max_tail = tail_addr, max_tail
        self.regblock = None
        self.slot1 = None
        self.num_patterns = 0

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for 48K snapshots')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        pats, table, n = build_patterns(read_frames(lambda a: ram[a - 0x4000], self.prof))
        self.num_patterns = n
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        body = self.code + table
        self.regblock = ORG + len(body)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('hook code does not fit below the ROM font')
        self.slot1 = (PAGE, self.regblock)
        if self.strategy == 'altrom':
            self.altrom = (ORG, self.regblock + 20)
        page = bytearray(self.rom)
        page[ORG - 0x2000:ORG - 0x2000 + len(body)] = body
        self.page = bytes(page)
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = pats + bytes(-len(pats) % 256)
        if len(pats) < 8192:
            pats = pats + bytes(8192 - len(pats))
        setup = bytearray(B.SETUP)
        setup[B.SETUP_NBLOCKS2_OFF] = (len(pats) - 8192) // 256
        self.stub_extra = bytes(setup)
        self.extra_banks = {11: pats, 12: self.page + bytes(8192)}


# ---------------------------------------------------------------------------------------------
# Analysis: one pass from the first plot (player not on screen there)
# ---------------------------------------------------------------------------------------------

def analyse5(prof, rzx_path, z80_sp, stop=None):
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .analyse import classify, apply_write
    G = list.__getitem__
    lo, hi = prof['plotter'], prof['player_end']
    PS, ES = prof['plot_cont'], prof['erase_cont']
    U = prof['undo_buffer']
    sites_ = {a + k for a, old, new in sites(prof, {'T_PLOT': 0, 'T_ERASE': 0}) for k in range(len(old))}
    st = {'P': None, 'drawn': False}
    c = collections.Counter(); dw = collections.Counter(); dr = collections.Counter(); fr = collections.Counter()
    FA = bytearray(65536)       # first access after sync: 1 = read, 2 = write
    RD = bytearray(65536)
    FA0 = bytearray(65536); RD0 = bytearray(65536); WR0 = bytearray(65536)   # whole recording
    cc = {}
    REG = [None]

    class Mem(list):
        def __getitem__(s, a):
            R = REG[0]
            if R is not None and type(a) is int:
                pc = R[24]
                RD0[a] = 1
                if not FA0[a]:
                    FA0[a] = 1
                if st['P'] is None:
                    if a == PS and pc == a:
                        st['P'] = [G(s, x) for x in range(0x4000, 0x5800)]
                        st['sp0'] = R[12]
                if st['P'] is not None:
                    RD[a] = 1
                    if not FA[a]:
                        FA[a] = 1
                    if pc == a:
                        if a == PS:
                            c['plot (%s)' % ('DRAWN' if st['drawn'] else 'not drawn')] += 1
                            e = G(s, prof['frame_var']) if G(s, prof['frame_flag']) else prof['frame_default']
                            fr[e] += 1
                            if e >= prof['num_frames']:
                                c['PLOTS WITH A FRAME OUTSIDE THE TABLE'] += 1
                            st['drawn'] = True
                        elif a == ES:
                            c['erase (%s)' % ('drawn' if st['drawn'] else 'NOT DRAWN')] += 1
                            st['drawn'] = False
                    elif 0x4000 <= a < 0x5800 and not (lo <= pc < hi) and G(s, a) != st['P'][a - 0x4000]:
                        dr[pc] += 1
                    elif U <= a < U + prof['undo_size'] and not (lo <= pc < hi):
                        c['UNDO BUFFER READ OUTSIDE THE PLAYER ROUTINES'] += 1
            return G(s, a)

        def __setitem__(s, a, v):
            R = REG[0]
            if R is not None and type(a) is int:
                WR0[a] = 1
                if not FA0[a]:
                    FA0[a] = 2
            if R is not None and type(a) is int and st['P'] is not None:
                if not FA[a]:
                    FA[a] = 2
                if a in sites_:
                    c['WRITES TO PATCH SITES'] += 1
                if 0x4000 <= a < 0x5800:
                    pc = R[24]
                    if not (lo <= pc < hi):
                        old = G(s, a)
                        key = (pc, G(s, (pc - 1) & 0xFFFF))
                        cls = cc.get(key) or cc.setdefault(key, classify(s, pc))
                        if st['P'][a - 0x4000] != old:
                            dw[(pc, cls[0], 'drawn' if st['drawn'] else 'erased')] += 1
                        apply_write(st['P'], a, old, v, cls)
            list.__setitem__(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(Mem(memory), registers, state, config)
            REG[0] = self.registers
            st['P'], st['drawn'] = None, False      # new RZX segment = new state: resync at its first plot

    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else [])
    try:
        rzxplay.main(args + [rzx_path])
    except SystemExit:
        pass
    REG[0] = None
    low, a, gap = z80_sp, z80_sp - 1, 0
    while a > z80_sp - 1024 and gap < 8:
        if WR0[a]:
            low, gap = a, 0
        else:
            gap += 1
        a -= 1
    return {'events': dict(c), 'frames': dict(fr), 'diff_writes': dw.most_common(10), 'diff_reads': dr.most_common(10),
            'fa_game': FA, 'rd_game': RD, 'synced': st['P'] is not None,
            # generic access-scan keys (whole recording), as analyse.analyse(None, ...) returns
            'rd': RD0, 'wr': WR0, 'fa': FA0, 'rom_used': any(RD0[1:0x4000]),
            'printer_buffer_touched': any(RD0[x] or WR0[x] for x in range(0x5B00, 0x5C00)),
            'stack_low_water': low}


def refusals(prof, an, mem):
    """Reasons the patch would not be proven safe by this analysis (empty list = OK)."""
    ev, why = an['events'], []
    if not an['synced']:
        why.append('the recording never plots the player')
    for k in ('plot (DRAWN)', 'erase (NOT DRAWN)'):
        if ev.get(k):
            why.append('%d x %s (double draw/erase: needs a parity model)' % (ev[k], k))
    for k in ('PLOTS WITH A FRAME OUTSIDE THE TABLE', 'UNDO BUFFER READ OUTSIDE THE PLAYER ROUTINES',
              'WRITES TO PATCH SITES'):
        if ev.get(k):
            why.append('%s: %d' % (k.lower(), ev[k]))
    lr = logic_readers(mem, an['diff_reads'])
    if lr:
        why.append('game logic reads the player\'s pixels at %s (needs a virtual read)' % lr[:3])
    return why


def logic_readers(mem, diff_reads):
    """Screen reads (while the screens differ) that are not 'XOR (HL)' followed by 'LD (HL),A'."""
    return [(pc, n) for pc, n in diff_reads if not (mem[pc] == 0xAE and mem[(pc + 1) & 0xFFFF] == 0x77)]


# ---------------------------------------------------------------------------------------------
# Differential verification
# ---------------------------------------------------------------------------------------------

def verify5(prof, patch, rzx_path, stop=None):
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    from .analyse import classify, apply_write
    from .verify import _M, REGS
    G = list.__getitem__
    lo, hi = prof['plotter'], prof['player_end']
    excl = set()
    for a, old, new in patch.sites:
        excl.update(range(a, a + len(new)))
    pats = patch.extra_banks[11]
    A, Bm = _M(True, [0] * 8192), _M(False, [0] * 8192)
    A.mem.lo, A.mem.hi = lo, hi
    st = {'P': None, 'nr15': 0, 'attrs': {}}
    stats = collections.Counter()
    log = []
    slog = []

    def sprite_px(m):
        out = {}
        if not (m.nr.get(0x15, 0) & 1):
            return out
        for n in range(4):
            a = m.attrs[n]
            if not a[3] & 0x80:
                continue
            x = a[0] | ((a[2] & 1) << 8); y = a[1]; p = ((a[3] & 0x3F) << 1) | ((a[4] >> 6) & 1)
            mir = a[2] & 8
            pat = pats[p * 128:(p + 1) * 128]
            for yy in range(16):
                for xx in range(16):
                    b = pat[yy * 8 + xx // 2]
                    col = (b >> 4) if xx % 2 == 0 else (b & 15)
                    if col:
                        out[(x + (15 - xx if mir else xx) - 32, y + yy - 32)] = col
        return out

    def check(kind, mm, R):
        ret_pc, ret_sp = G(mm, R[12]) | G(mm, R[12] + 1) << 8, R[12] + 2
        snap, regs, P0 = list(mm), list(R), list(st['P'])
        A.load(snap, regs); A.mem.P = list(P0)
        Bm.load(snap, regs)
        for a, old, new in patch.sites:
            list.__setitem__(Bm.mem, slice(a, a + len(new)), list(new))
        list.__setitem__(Bm.mem, slice(0x2000, 0x4000), list(patch.page))
        list.__setitem__(Bm.mem, slice(0x4000, 0x5800), P0)
        Bm.nr[0x15] = st['nr15']
        Bm.attrs = collections.defaultdict(lambda: [0] * 5, {k: list(v) for k, v in st['attrs'].items()})
        A.run(ret_pc, ret_sp); Bm.run(ret_pc, ret_sp)
        bad = [i for i in REGS if A.R[i] != Bm.R[i]]
        md = [a for a in range(0x5800, 65536) if A.mem[a] != Bm.mem[a] and a not in excl]
        sd = [a for a in range(0x4000, 0x5800) if Bm.mem[a] != A.mem.P[a - 0x4000]]
        U = prof['undo_buffer']
        if bad and not md and not sd and _converges(A, Bm):
            stats[kind + ' ok (registers differ at return, overwritten before use)'] += 1
            bad = []
        elif bad or md or sd:
            ghost = kind == 'plot' and not bad and not sd and all(U <= a < U + prof['undo_size'] for a in md) \
                and any(snap[a] != P0[a - 0x4000] for a in range(0x4000, 0x5800))
            if ghost:
                stats['plot: undo buffer differs (original ghost pixels, harmless)'] += 1
            else:
                stats[kind + ' MISMATCH'] += 1
                if len(log) < 6:
                    log.append((kind, R[24], 'regs', bad, 'mem', md[:6], 'screen', sd[:6]))
        else:
            stats[kind + ' ok'] += 1
        st['nr15'] = Bm.nr.get(0x15, 0)
        st['attrs'] = {k: list(v) for k, v in Bm.attrs.items()}
        if kind == 'plot':
            spx = sprite_px(Bm)
            bad_px = 0
            for y in range(192):
                for x in range(256):
                    a = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)
                    o = (A.mem[a] >> (7 - (x & 7))) & 1
                    # transparent sprite pixels: the original plot left the pixel as it was (ghost
                    # pixels of the original stay out of the comparison); K -> 0, W -> 1
                    before = (snap[a] >> (7 - (x & 7))) & 1
                    col = spx.get((x, y))
                    want = before if col is None else (1 if col == 2 else 0)
                    if o != want:
                        bad_px += 1
            stats['sprite pixel-perfect' if not bad_px else 'SPRITE PIXEL MISMATCH'] += 1
            if bad_px and len(slog) < 6:
                slog.append(('sprite', 'frame', G(snap, prof['frame_var']) if G(snap, prof['frame_flag'])
                             else prof['frame_default'], 'x', G(snap, prof['x_var']), 'y', G(snap, prof['y_var']),
                             'flip', G(snap, prof['flip_var']), bad_px, 'pixels'))
        else:
            stats['erase hides sprite' if not st['nr15'] & 1 else 'ERASE LEAVES SPRITE VISIBLE'] += 1

    def _converges(a, b, limit=400):
        # step both from the return point; the difference must vanish before any I/O
        # instruction (or memory write difference) can observe it
        ra, rb = a.R, b.R
        for _ in range(limit):
            if all(ra[i] == rb[i] for i in REGS):
                return True
            pc = ra[24]
            if pc != rb[24]:
                return False
            op, op2 = a.mem[pc], a.mem[(pc + 1) & 0xFFFF]
            if op in (0xD3, 0xDB) or (op == 0xED and ((0x40 <= op2 < 0x80 and op2 & 6 == 0) or op2 in
                                                     (0xA2, 0xA3, 0xAA, 0xAB, 0xB2, 0xB3, 0xBA, 0xBB))):
                if any(ra[i] != rb[i] for i in range(0, 13) if i != 1):   # only F may differ at I/O
                    return False
            sa, sb = ra[12], rb[12]
            a.sim.opcodes[op](); b.sim.opcodes[b.mem[pc]]()
            for q in {sa - 2, sa - 1, sb - 2, sb - 1}:        # pushes are the only writes that could differ
                if a.mem[q & 0xFFFF] != b.mem[q & 0xFFFF]:
                    return False
        return False

    ev = {prof['plot_site']: 'plot', prof['erase_site']: 'erase'}
    REG = [None]

    class Mem(list):
        def __getitem__(s, a):
            R = REG[0]
            if type(a) is int and R is not None and a in ev and R[24] == a:
                if st['P'] is None and ev[a] == 'plot':
                    st['P'] = [G(s, x) for x in range(0x4000, 0x5800)]
                if st['P'] is not None:
                    check(ev[a], s, R)
            return G(s, a)

        def __setitem__(s, a, v):
            R = REG[0]
            if R is not None and st['P'] is not None and type(a) is int and 0x4000 <= a < 0x5800 \
                    and not (lo <= R[24] < hi):
                apply_write(st['P'], a, G(s, a), v, classify(s, R[24]))
            list.__setitem__(s, a, v)

    class S(Simulator):
        def __init__(self, memory, registers=None, state=None, config=None):
            super().__init__(Mem(memory), registers, state, config)
            REG[0] = self.registers
            st['P'], st['nr15'], st['attrs'] = None, 0, {}   # new RZX segment: resync at its first plot

    rzxplay.Simulator = S
    rzxplay.CSimulator = None
    args = ['--python', '--quiet', '--no-screen', '--fps', '0'] + (['--stop', str(stop)] if stop else [])
    try:
        rzxplay.main(args + [rzx_path])
    except SystemExit:
        pass
    REG[0] = None
    failed = any('MISMATCH' in k or 'VISIBLE' in k for k in stats)
    return {'passed': not failed and sum(stats.values()) > 0, 'stats': dict(stats), 'examples': log[:3] + slog[:3]}
