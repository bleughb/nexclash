"""Cauldron (Palace Software, 1985; 48K) - engine `cauldron`.

Figures that become sprites (Dean, 2026-10-26/27, games/cauldron.md "Decisions"): every image the XOR
plotter 0x6357 draws (all 14 callers: the movers, the cauldron-spot image, the HUD item icon), in
front of everything (overlay: the ULA keeps the original's XOR pixels), colour = the image's cell
ink, with a black 4-neighbour outline (Q7); a figure that any other screen writer touches loses its
sprite at that moment and the ULA shows whatever the original left (Q6). The ULA keeps the
scenery's attributes: the figure-cell painting goes to a shadow the game reads instead (Q8).

    python nexclash.py auto GAME.z80 --rzx cauldron.rzx --no-record     (build + verify)
    python -m nexclash.cauldron extract cauldron.rzx -o OUT.z80        (the build input)

Build input (Q0): the snapshot embedded in cauldron.rzx (a different build of the game than the
delivered .z80: games/cauldron.md "Inputs"); `auto` extracts it and builds from it.

Build (games/cauldron.md "Build design"): hooks in alt ROM image 1 (0x386E-) at the plotter entry
0x6357 (the hook runs the plotter body itself: a DRAW shows the image's sprites before the body, an
ERASE hides them after it) and at every other screen writer (ROM PR-ALL / CL-LINE / CL-SCROLL via
alt ROM bytes below 0x2000, the game's clear, tile writer and the two bottom-third scrolls). A key
(graphic, x, y, rows, width) is live between the plot that draws it and the one that erases it;
another writer touching it taints it (no sprite until a clear holds it whole). Tables in Next page
26 at slot 6, mapped only inside the hooks. Verifier: differential at every site + an independent
model of the key table and the sprite layer; every screen write outside the plotter into a live
key's rectangle fails (the touch hooks must cover every writer).
"""
import collections
import hashlib
import json
import os
import struct
import zlib

_HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = 'cauldron'
RZX_Z80_MD5 = '2f0ef98e5c59552663b15d5eb1175236'   # the RZX's embedded snapshot (build input, Q0)
PALETTE = [0x00, 0x02, 0xA0, 0xA2, 0x14, 0x16, 0xB4, 0xB6, 0x00, 0x03, 0xE0, 0xE7, 0x1C, 0x1F, 0xFC, 0xFF]

PLOT, BODY, BODY_RET = 0x6357, 0x635A, 0x63DA
ROM_ORG = 0x386E                # alt ROM image 1: hooks 0x386E-, register block after them (< 0x3D00)
ALT_PAGE = 24                   # the patch image of 0x2000-0x3FFF (bank 12), copied by the stub
PG, PG_BANK = 26, 13            # tables + their code (0xC700-) at slot 6 inside the hooks
P26_OFF = 0x0700
TAIL_ADDR, TAIL_END = 0x5E00, 0x5FBA    # survey: 0x5D52-0x5FB9 free (whole RZX), lowest SP 0x5FBA
NSLOT, NTAB = 14, 128         # 9 sprites / patterns a slot (3 x 3: image + outline up to 34 x 34)
P27, GPG4 = 27, 4             # page 27 at slot 4 inside hooks (attribute shadow, canvases, code); the game's page 4
P27_OFF = 0x0A00              # page-27 code
OUTLINE = 8                   # outline nibble (palette 8 = black; Dean 2026-10-27 Q7)
V_N, V_OVF, V_NFREE, FREE, TAB = 0x0000, 0x0001, 0x0002, 0x0003, 0x0100   # page-26 offsets
# RAM sites: (original, hook symbol, kind)
SITES = {0x6357: ('5e2356', 'e_plot', 'plot'), 0xB2A0: ('210048', 'e_clr', 'clr'),
         0xB366: ('6f2600', 'e_tile', 'tile'), 0xDED2: ('210050', 'e_scl', 'scl'),
         0xDEEA: ('21ff57', 'e_scr', 'scr'),
         # attribute shadow (Q8): every reader / writer of the attribute file but the plotter's own
         0x61D8: ('6e18fa', 'e_peek', 'peek'), 0xC9DB: ('21005a', 'e_save', 'save'),
         0xC9E7: ('21f4c9', 'e_rest', 'rest'), 0xCE74: ('21e658', 'e_box', 'box'),
         0xB2AC: ('3a015b', 'e_rfil', 'rfil'), 0xDF04: ('21005a', 'e_sal', 'sal'),
         0xDF17: ('21ff5a', 'e_sar', 'sar'), 0xB33E: ('7ccbf7', 'e_tatt', 'tatt'),
         0xB361: ('1a2294', 'e_tard', 'tard')}
# ROM sites (alt ROM bytes below 0x2000, in patch.altrom_low): (original, jump symbol, kind)
ROM_SITES = {0x0B9B: ('3a915c', 'j_char', 'char'), 0x0E44: ('c5cd9b', 'j_cll', 'cll'),
             0x0E00: ('cd9b0e', 'j_csc', 'csc'), 0x0BE4: ('ed5b8f', 'j_poa', 'poa')}
# where the original and the patched code meet again after a site: (pc, SP change)
RESUME = {0x6357: None, 0xB2A0: (0xB2A3, 0), 0xB366: (0xB369, 0), 0xDED2: (0xDED5, 0),
          0xDEEA: (0xDEED, 0), 0x0B9B: (0x0B9E, 0), 0x0E44: None, 0x0E00: None, 0x0BE4: None,
          0x61D8: (0x61D5, 0), 0xC9DB: (0xC9E6, 0), 0xC9E7: (0xC9F2, 0), 0xCE74: (0xCE8D, 0),
          0xB2AC: (0xB2BB, 0), 0xDF04: (0xDF16, 0), 0xDF17: (0xDF29, 0), 0xB33E: (0xB342, 0),
          0xB361: (0xB365, 0)}           # None: to the caller's return (the hook runs the routine)
INTERIORS = tuple(a + k for a in list(SITES) + list(ROM_SITES) for k in (1, 2)) + (0x0BE7,)
# interior bytes the ORIGINAL reaches right after the site's own first (1-byte) instruction
SEQUELS = {0x6358: PLOT, 0x6359: PLOT, 0xB367: 0xB366, 0x0E45: 0x0E44, 0x61D9: 0x61D8,
           0xB33F: 0xB33E, 0xB362: 0xB361}
ATTR0, ATTR1 = 0x5800, 0x5B00
BUF = 51700                     # the game's bottom-third attribute buffer (0xC9DB saves, 0xC9E7 restores)
HOOK_RANGE = (ROM_ORG, 0x3D00)  # FF in the 48K ROM: the original never runs there (verify counts it)
TOUCH = {'clr': ((64, 191, 0, 31), 1), 'scl': ((128, 191, 0, 30), 0), 'scr': ((128, 191, 1, 31), 0),
         'csc': ((0, 191, 0, 31), 0)}
WHOLE = (0, 191, 0, 31)
ATTR_T, MASK_T, P_FLAG, TILEAT = 23695, 23696, 23697, 45972
CMP = list(range(0, 13)) + [14] + list(range(16, 25)) + [26, 27]   # all but R, T, MEMPTR
DECISIONS = {'engine': 'cauldron',
             'input': 'the snapshot embedded in cauldron.rzx (MD5 %s; Q0, Dean 2026-10-26)' % RZX_Z80_MD5,
             'strategy': 'overlay: the game still draws the ULA pixels; hooks in alt ROM image 1 (0x386E-, the '
                         'whole alt ROM image from the build) + page 26 at slot 6 + page 27 at slot 4 put a grid of '
                         '4-bit sprites on every live XOR image (key = graphic, x, y, rows, width) - shown at a '
                         'drawing plot\'s entry, hidden at an erasing plot\'s exit',
             'figures': 'every image of the plotter 0x6357 (all 14 callers; Q1)',
             'depth': 'sprites in front of everything (Q2)',
             'outline': 'every sprite: black (palette 8) on the left / right / up / down neighbours of its ink '
                        '(Q7, Dean 2026-10-27); up to 3 x 3 sprites a figure, 14 figures with sprites at once',
             'attributes': 'the ULA keeps the scenery colours: the plotter paints an attribute shadow (page 27) '
                           'instead (Q8, Dean 2026-10-27, reverses Q3); every game read of an attribute reads the '
                           'shadow, every other attribute writer writes both; a bottom-third restore gives the '
                           'ULA the colours of its save',
             'colour': 'the image\'s first cell ink after the plotter paints it (Q4, from the shadow); black -> palette 8',
             'other writers': 'ROM PR-ALL, CL-LINE, CL-SCROLL, the clear 0xB2A0, the tile writer 0xB366, the '
                              'scrolls 0xDED2 / 0xDEEA: a touched live image loses its sprite and is tainted; a '
                              'clear holding it whole forgets it (Q6)',
             'interrupts': 'left on (the ROM IM 1 handler touches slots 0 and 2 only)',
             'tail': '0x5E00 (0x5D52-0x5FB9 free in the whole RZX); printer buffer put back (the game reads '
                     '0x5B00 / 0x5B01)'}


def _profile_path():
    return os.path.join(_HERE, '..', 'docs', 'profiles', RECORD + '.json')


def load_profile():
    return json.load(open(_profile_path()))


def is_cauldron(snap):
    try:
        sg = load_profile()['signature']
    except (FileNotFoundError, KeyError):
        return False
    if snap.machine != '48K':
        return False
    sig = bytes.fromhex(sg['bytes'])
    return bytes(snap.memory[sg['addr']:sg['addr'] + len(sig)]) == sig


def rzx_snapshot(rzx_path):
    """The .z80 bytes embedded in the RZX's first snapshot block (0x30; zlib when flags bit 1)."""
    d = open(rzx_path, 'rb').read()
    p = 10
    while p < len(d):
        bid, ln = d[p], struct.unpack('<I', d[p + 1:p + 5])[0]
        if bid == 0x30:
            flags, ext = struct.unpack('<I4s', d[p + 5:p + 13])
            body = d[p + 17:p + ln]
            if ext[:3].upper() != b'Z80':
                raise ValueError('RZX snapshot is not a .z80 (%r)' % ext)
            return zlib.decompress(body) if flags & 2 else body
        p += ln
    raise ValueError('no snapshot block in %s' % rzx_path)


def start_state(rzx_path, out_path):
    """Write the build input (the RZX's embedded snapshot) to out_path; refuse another recording's."""
    z = rzx_snapshot(rzx_path)
    md5 = hashlib.md5(z).hexdigest()
    if md5 != RZX_Z80_MD5:
        raise ValueError('the RZX\'s snapshot is not the one this engine was verified on (MD5 %s)' % md5)
    open(out_path, 'wb').write(z)
    return out_path


def _rom48():
    from .build import rom48
    return rom48()


class CauldronPatch:
    name = ('Cauldron: every XOR-plotted image -> hardware sprites (overlay; plotter + screen-writer '
            'hooks in alt ROM image 1, tables in page 26 at slot 6)')

    def __init__(self, prof=None, rom_code=None, p26=None, jmp=None, p27=None):
        self.prof = prof or load_profile()
        h = self.prof['hooks']
        self.rom_code = rom_code if rom_code is not None else bytes.fromhex(h['rom'])
        self.p26 = p26 if p26 is not None else bytes.fromhex(h['p26'])
        self.jmp = jmp if jmp is not None else bytes.fromhex(h['jmp'])
        self.p27 = p27 if p27 is not None else bytes.fromhex(h['p27'])
        if P27_OFF + len(self.p27) > 0x2000:
            raise ValueError('page-27 code too long')
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.stub_extra = bytes.fromhex(h['setup'])
        self.setup_call = 0xD000
        self.hook_page_data = b''
        self.uses_printer_buffer = True
        self.keep_printer_buffer = True          # the game reads 0x5B00 / 0x5B01: NEXLOAD overwrites them
        self.tail_addr = TAIL_ADDR
        self.max_tail = TAIL_END - TAIL_ADDR
        self.regblock = ROM_ORG + len(self.rom_code)
        if self.regblock + 20 > 0x3D00:
            raise ValueError('ROM hooks too long (0x3D00-0x3DFF: no code, DivMMC trap)')
        if P26_OFF + len(self.p26) > 0x2000:
            raise ValueError('page-26 code too long')
        rom = _rom48()
        if any(b != 0xFF for b in rom[ROM_ORG:self.regblock + 20]):
            raise ValueError('alt ROM hook range is not free ($FF) in the 48K ROM')
        self.slot1 = (ALT_PAGE, self.regblock)
        # The WHOLE alt ROM image comes from the build (Sinclair's 48K ROM + hooks): the Next copies
        # NextZXOS's ROM3 first, which is not Sinclair's (BRIEFING C2 #5; it has data at 0x3B00-,
        # where the hooks sit), and the game runs ROM KEY-SCAN, PRINT, CLS, PIXEL-ADD from it.
        self.altrom = (0x2000, 0x4000)
        page = bytearray(rom[0x2000:0x4000])
        page[ROM_ORG - 0x2000:ROM_ORG - 0x2000 + len(self.rom_code)] = self.rom_code
        self.page = bytes(page)                  # ROM 0x2000-0x3FFF + hooks (register block: the stub)
        low = bytearray(rom[0:0x2000])           # ROM 0x0000-0x1FFF + the JPs at the ROM sites
        j0 = self.syms['j_char']                 # the jump block as assembled (0x3000-; not in the image)
        for a, (old, sym, k) in ROM_SITES.items():
            if rom[a:a + 3] != bytes.fromhex(old):
                raise ValueError('48K ROM differs at 0x%04X' % a)
            jp = self.jmp[self.syms[sym] - j0:self.syms[sym] - j0 + 3]
            if jp[0] != 0xC3:
                raise ValueError('jump block: no JP at %s' % sym)
            low[a:a + 3] = jp
        self.altrom_low = (ALT_PAGE + 1, bytes(low))
        self.sites = [(a, bytes.fromhex(old), b'\xC3' + self.syms[sym].to_bytes(2, 'little'))
                      for a, (old, sym, k) in SITES.items()]
        self.extra_banks = {12: self.page + bytes(low), PG_BANK: page26(self.p26) + page27(bytes(768), self.p27)}

    def rom_image(self):
        """The alt ROM image the patched game reads at 0x0000-0x3FFF (the stub adds the register
        block at self.regblock; the game never reads it)."""
        return bytearray(self.altrom_low[1] + self.page)

    def apply(self, snap):
        if snap.is128:
            raise ValueError('Cauldron patch expects the 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at 0x%04X (%s, expected %s)' % (a, cur.hex(), old.hex()))
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        # page 27 starts with the snapshot's attribute file as the shadow (the ULA and the original agree)
        self.extra_banks[PG_BANK] = page26(self.p26) + page27(bytes(ram[0x1800:0x1B00]), self.p27)


def page27(attrs, code=None):
    """Page 27 as the build loads it: the attribute shadow (= the snapshot's attribute file) at 0, the
    save pairs / canvases empty, the code at 0x0A00."""
    p = bytearray(8192)
    p[0:768] = attrs
    code = bytes.fromhex(load_profile()['hooks']['p27']) if code is None else code
    p[P27_OFF:P27_OFF + len(code)] = code
    return bytes(p)


def page26(code=None):
    """Page 26 as the build loads it: empty table, free slot stack 27..0 (slot 0 is taken first),
    the table code at 0x0700."""
    p = bytearray(8192)
    p[V_NFREE] = NSLOT
    for i in range(NSLOT):
        p[FREE + i] = NSLOT - 1 - i
    code = bytes.fromhex(load_profile()['hooks']['p26']) if code is None else code
    p[P26_OFF:P26_OFF + len(code)] = code
    return bytes(p)


# ---------------------------------------------------------------------------------------------
# Next-side state of the patched machine
# ---------------------------------------------------------------------------------------------

class NextState:
    """NEXTREG, sprite attributes, pattern RAM, page 26 (the hooks' tables)."""

    def __init__(self, pages):
        self.nr = {0x54: GPG4, 0x56: 0, 0x57: 1}
        self.u = bytearray(768)               # the patched machine's ULA attribute file
        self.attr = [[0, 0, 0, 0, 0] for _ in range(128)]
        self.pat = bytearray(16384)
        self.pidx = 0
        self.pages = {k: bytearray(v) for k, v in pages.items()}
        self.bad = []

    def copy(self):
        n = NextState({})
        n.nr = dict(self.nr)
        n.attr = [list(a) for a in self.attr]
        n.pat = bytearray(self.pat)
        n.pidx = self.pidx
        n.pages = {k: bytearray(v) for k, v in self.pages.items()}
        n.u = bytearray(self.u)
        return n

    def nextreg(self, reg, val):
        self.nr[reg] = val
        if 0x35 <= reg <= 0x39:
            self.attr[self.nr.get(0x34, 0) & 0x7F][reg - 0x35] = val
        elif reg == 0x56:
            if val not in (0, PG) or (val == PG and PG not in self.pages):
                self.bad.append(('MMU6 set to page %d' % val,))
        elif reg == 0x54:
            if val not in (GPG4, P27) or (val == P27 and P27 not in self.pages):
                self.bad.append(('MMU4 set to page %d' % val,))
        elif reg not in (0x34, 0x07):
            self.bad.append(('NEXTREG 0x%02X' % reg,))

    def port(self, port, v):
        if port == 0x303B:
            self.pidx = (v & 0x3F) * 256 + (128 if v & 0x80 else 0)
        elif port & 0xFF == 0x5B:
            self.pat[self.pidx % 16384] = v
            self.pidx += 1
        else:
            self.bad.append(('OUT 0x%04X' % port,))

    def layer(self):
        """Visible sprite pixels -> {(x, y): nibble} in ULA coordinates, higher sprite on top."""
        out = {}
        for i in range(128):
            a0, a1, a2, a3, a4 = self.attr[i]
            if not a3 & 0x80:
                continue
            if a2 & 0xFE or not a3 & 0x40 or not a4 & 0x80 or a4 & 0x3F:
                self.bad.append(('sprite %d: unexpected attribute bits' % i,))
                continue
            x = a0 + (a2 & 1) * 256 - 32
            y = a1 - 32
            base = (a3 & 0x3F) * 256 + (128 if a4 & 0x40 else 0)
            for j in range(16):
                row = self.pat[base + j * 8:base + j * 8 + 8]
                for k in range(16):
                    b = row[k >> 1]
                    n = (b >> 4) if not k & 1 else (b & 15)
                    if n and 0 <= x + k < 256 and 0 <= y + j < 192:
                        out[(x + k, y + j)] = n
        return out


def _machine(Sim, mem, regs, ns, slot='o'):
    from skoolkit.simulator import R2
    from .simpool import machine
    sim = machine(Sim, mem, regs, slot)
    R, ed = sim.registers, sim.after_ED

    def nn():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], mem[(p + 3) % 65536])
        R[15] = R2[R[15]]; R[24] = (p + 4) % 65536; R[25] += 20

    def na():
        p = R[24]
        ns.nextreg(mem[(p + 2) % 65536], R[0])
        R[15] = R2[R[15]]; R[24] = (p + 3) % 65536; R[25] += 17
    ed[0x91], ed[0x92] = nn, na

    class Tr:
        def read_port(s, regs_, port):
            ns.bad.append(('IN 0x%04X' % port,))
            return 0xFF

        def write_port(s, regs_, port, value, *x):
            ns.port(port, value)
    sim.set_tracer(Tr())
    return sim


def _overlays(get, alt, psite, ns):
    class O:
        def __init__(s):
            s.ov = {}

        def __getitem__(s, a):
            v = s.ov.get(a)
            return v if v is not None else get(a)

        def __setitem__(s, a, v):
            if a >= 0x4000:
                s.ov[a] = v

        def __len__(s):
            return 65536

    class P(O):
        def __getitem__(s, a):
            if a < 0x4000:
                return alt[a]
            if 0xC000 <= a < 0xE000 and ns.nr.get(0x56, 0) == PG:
                return ns.pages[PG][a - 0xC000]
            if 0x8000 <= a < 0xA000 and ns.nr.get(0x54, GPG4) == P27:
                return ns.pages[P27][a - 0x8000]
            if ATTR0 <= a < ATTR1:
                return ns.u[a - ATTR0]
            v = psite.get(a)
            if v is not None:
                return v
            return O.__getitem__(s, a)

        def __setitem__(s, a, v):
            if a < 0x4000:
                s.romw = getattr(s, 'romw', 0) + 1
            elif 0xC000 <= a < 0xE000 and ns.nr.get(0x56, 0) == PG:
                ns.pages[PG][a - 0xC000] = v
            elif 0x8000 <= a < 0xA000 and ns.nr.get(0x54, GPG4) == P27:
                ns.pages[P27][a - 0x8000] = v
            elif ATTR0 <= a < ATTR1:
                ns.u[a - ATTR0] = v
            else:
                s.ov[a] = v
    return O, P


def _run(sim, stop, limit=1000000, check=None):
    R, ops, mem = sim.registers, sim.opcodes, sim.memory
    n = 0
    while not stop(R):
        ops[mem[R[24]]]()
        if check:
            check()
        n += 1
        if n > limit:
            return False
    return True


ISAFE = {'checked': 0}
COST = {'extra': 0}     # last event: patched - original T at 3.5 MHz (28 MHz T / 8)
SP_FLOOR = 0x5D52 + 24  # the ROM IM 1 handler needs 18 bytes below SP (survey); free RAM from 0x5D52


def _isafe(sim, regs0, ns, err):
    """Interrupt safety at every patched instruction with interrupts on: the ROM IM 1 handler reads
    IY, pushes up to 18 bytes and runs in slots 0 and 2 (MMU7 must stay page 1; MMU6 may hold page 26:
    the handler never reads 0xC000-0xFFFF); I and the alternate set unchanged; no fetch in 0x3D00-0x3DFF."""
    R = sim.registers
    iy, i, alt0 = (regs0[10], regs0[11]), regs0[14], regs0[16:24]

    def chk():
        pc = R[24]
        if 0x3D00 <= pc < 0x3E00 and not err:
            err.append(('instruction fetch in 0x3D00-0x3DFF', hex(pc)))
        if not R[26]:
            return
        ISAFE['checked'] += 1
        bad = None
        if (R[10], R[11]) != iy:
            bad = 'IY'
        elif R[14] != i or R[16:24] != alt0:
            bad = 'I / alternate set'
        elif R[12] < SP_FLOOR:
            bad = 'SP below 0x%04X' % SP_FLOOR
        elif ns.nr.get(0x57, 1) != 1:
            bad = 'MMU7 mapped'
        if bad and not err:
            err.append(('interrupt-unsafe hook: %s' % bad, hex(pc)))
    return chk


def event(patch, site, get, R, ns, alt, Sim, at_body=None):
    """Original and patched code from one state to where they meet again. -> (failures, original
    overlay, final original registers). ns (the patched machine's Next state) is updated in place;
    at_body(ns) is called when the patched plot hook reaches the plotter body."""
    psite = {a + k: v for a, old, new in patch.sites for k, v in enumerate(new)}
    sp0 = R[12]
    if RESUME[site] is None:                      # the hook runs the routine: meet at the caller's return
        ret = get(sp0) | get(sp0 + 1) << 8
        stop = lambda r: r[24] == ret and r[12] == sp0 + 2
    else:
        pc_, dsp = RESUME[site]
        stop = lambda r: r[24] == pc_ and r[12] == sp0 + dsp
    O, P = _overlays(get, alt, psite, ns)
    o, p = O(), P()
    ns.bad = []
    so = _machine(Sim, o, list(R), NextState({}))
    sp_ = _machine(Sim, p, list(R), ns, 'p')
    if not _run(so, stop):
        return ['original did not return'], o, so.registers
    err = []
    chk = _isafe(sp_, R, ns, err)
    rp_, tm = sp_.registers, {'prev': R[25], 'slow': 0, 'fast': 0, 'body': at_body is None}
    body = patch.syms['body2']

    def check():
        chk()
        if not tm['body'] and rp_[24] == body:
            tm['body'] = True
            at_body(ns)
        d = rp_[25] - tm['prev']
        tm['prev'] = rp_[25]
        tm['fast' if ns.nr.get(0x07, 0) == 3 else 'slow'] += d
    if not _run(sp_, stop, check=check):
        return ['patched code did not return'], o, so.registers
    COST['extra'] = tm['slow'] + tm['fast'] / 8.0 - (so.registers[25] - R[25])
    f = list(err)
    if not tm['body']:
        f.append(('patched plot never reached the body',))
    ro, rp = so.registers, sp_.registers
    diff = [i for i in CMP if ro[i] != rp[i]]
    if diff:
        f.append(('registers differ', diff, [ro[i] for i in diff], [rp[i] for i in diff]))
    if getattr(p, 'romw', 0):
        f.append(('patched code wrote ROM',))
    f += ns.bad
    if ns.nr.get(0x56, 0) or ns.nr.get(0x57, 1) != 1 or ns.nr.get(0x54, GPG4) != GPG4:
        f.append(('MMU4 / MMU6 / MMU7 left mapped',))
    if ns.nr.get(0x07, 0):
        f.append(('CPU speed left at %d' % ns.nr[0x07],))
    dead = range(ro[12] - 64, ro[12])             # below the final SP: dead stack
    keys = set(o.ov) | set(p.ov)
    md = [a for a in keys if a not in dead and not ATTR0 <= a < ATTR1 and o[a] != p[a]]
    if md:
        f.append(('memory differs', len(md), [hex(a) for a in sorted(md)[:4]]))
    return f, o, ro


# ---------------------------------------------------------------------------------------------
# Model: what the build must show (a re-implementation of the rule, from the original's state)
# ---------------------------------------------------------------------------------------------

def screen_addr(x8, y):
    return 0x4000 | (y & 0xC0) << 5 | (y & 7) << 8 | (y & 0x38) << 2 | x8


def y_of(a):
    return (a >> 5 & 0xC0) | (a >> 2 & 0x38) | (a >> 8 & 7)


def cell_rect(a):
    """Screen address of a character cell's top line -> its rectangle (else the whole screen)."""
    if a >> 8 & 7:
        return WHOLE
    y = y_of(a)
    return (y, y + 7, a & 31, a & 31)


def read_desc(get, hl):
    d = [get((hl + i) & 0xFFFF) for i in range(8)]
    return {'g': d[0] | d[1] << 8, 'x': d[2], 'y': d[3], 'rows': d[4], 'w': d[5], 't': d[6], 'v': d[7]}


def plot_ink(get, d, y0, c0):
    """The colour rule (Q4): ink of the image's first cell after the plotter's first paint of it."""
    old = get(0x5800 + (y0 >> 3) * 32 + c0)
    at = get(ATTR_T)
    if d['t'] == 2:
        e, m = at, get(MASK_T)
        a = ((old ^ e) & m) ^ e
        pf = get(P_FLAG)
        if pf & 0x40:
            a &= 0xC7
            if not a & 4:
                a ^= 0x38
        if pf & 0x10:
            a &= 0xF8
            if not a & 0x20:
                a ^= 7
    elif d['t'] == 0:
        a = d['v'] if old == at else old
    else:
        a = at if old == d['v'] else old
    ink = a & 7
    if not ink:
        return 8
    return ink | (8 if a & 0x40 else 0)


def image_pixels(g, w, rows, x, y0):
    """Ink pixels of an image drawn unshifted at pixel x, top line y0 -> [(x, y)] (no clipping)."""
    out = []
    for r in range(rows):
        for c in range(w):
            b = g[r * w + c]
            for k in range(8):
                if b >> (7 - k) & 1:
                    out.append((x + 8 * c + k, y0 + r))
    return out


def outline(pix):
    """Ink pixels -> the outline: their left / right / up / down neighbours that are not ink (Q7)."""
    p = set(pix)
    out = set()
    for x, y in p:
        for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if q not in p:
                out.add(q)
    return out


def po_attr(old, get):
    """ROM PO-ATTR (0x0BE4-0x0C08) on one attribute value with the system variables of get."""
    e, m = get(ATTR_T), get(MASK_T)
    a = ((old ^ e) & m) ^ e
    pf = get(P_FLAG)
    if pf & 0x40:
        a &= 0xC7
        if not a & 4:
            a ^= 0x38
    if pf & 0x10:
        a &= 0xF8
        if not a & 0x20:
            a ^= 7
    return a


def image_bytes(get, d):
    """{screen address: XOR mask} the plotter changes for descriptor d (addresses as it computes
    them: PIXEL-ADD per line, then consecutive bytes)."""
    out = {}
    g = d['g']
    sh = d['x'] & 7
    for r in range(d['rows']):
        y = 175 - (d['y'] - r)
        a = screen_addr(d['x'] >> 3, y)
        for c in range(d['w']):
            v = get((g + r * d['w'] + c) & 0xFFFF)
            if sh:
                v16 = v << (8 - sh)
                out[a + c] = out.get(a + c, 0) ^ (v16 >> 8)
                out[a + c + 1] = out.get(a + c + 1, 0) ^ (v16 & 255)
            else:
                out[a + c] = out.get(a + c, 0) ^ v
    return {k: v for k, v in out.items() if v}


class Model:
    """The key table, the free sprite-slot stack and the sprites shown - in the order the hooks keep
    them (the slot a key gets decides which sprite is on top), the rule as games/cauldron.md
    "Build design" states it."""

    def __init__(self):
        self.tab = []                         # [key, state, rect]
        self.free = [NSLOT - 1 - i for i in range(NSLOT)]
        self.ovf = 0
        self.shown = {}                       # slot: (pixels {(x, y): ink or OUTLINE})
        self.u = bytearray(768)               # the ULA attribute file the build must show (Q8)
        self.usv = bytearray(384)             # (ULA, original) pairs at the last bottom-third save

    def copy(self):
        m = Model()
        m.tab = [[k, s, r] for k, s, r in self.tab]
        m.free = list(self.free)
        m.ovf = self.ovf
        m.shown = dict(self.shown)
        m.u = bytearray(self.u)
        m.usv = bytearray(self.usv)
        return m

    def attrs(self, kind, get, R, after):
        """The ULA attributes after an attribute event (games/cauldron.md "Build design", Q8): the
        plotter's painting never reaches the ULA; every other writer writes it; a restore of the
        bottom third gives back the ULA colours of the save where the buffer still holds that save.
        get = the original before the event, after = the original after it."""
        u = self.u
        if kind == 'poa':
            a = (R[6] << 8 | R[7]) - ATTR0
            if 0 <= a < 768:
                u[a] = po_attr(u[a], get)
        elif kind == 'cll':
            b = R[2]
            lo = (24 - b) * 32 if 1 <= b <= 24 else 0
            for a in range(lo, 768):
                u[a] = after(ATTR0 + a)
        elif kind == 'csc':
            for a in range(768):
                u[a] = after(ATTR0 + a)
        elif kind == 'save':
            for i in range(192):
                self.usv[2 * i] = u[0x200 + i]
                self.usv[2 * i + 1] = get(ATTR0 + 0x200 + i)
        elif kind == 'rest':
            for i in range(192):
                b = get(BUF + i)
                u[0x200 + i] = self.usv[2 * i] if b == self.usv[2 * i + 1] else b
        elif kind == 'box':
            for r in range(5):
                for c in range(6):
                    a = 0xE6 + 32 * r + c
                    u[a] = after(ATTR0 + a)
        elif kind == 'rfil':
            for a in range(0x80, 0x300):
                u[a] = after(ATTR0 + a)
        elif kind in ('sal', 'sar'):
            for r in range(8):
                row = u[0x200 + 32 * r:0x220 + 32 * r]
                row = row[1:] + row[31:] if kind == 'sal' else row[:1] + row[:31]
                u[0x200 + 32 * r:0x220 + 32 * r] = row
        elif kind == 'tatt':
            a = (R[4] << 8 | R[5]) - ATTR0
            if 0 <= a < 768:
                u[a] = R[6] | 0x40

    def _hide(self, s):
        self.shown.pop(s, None)
        self.free.append(s)

    def taint_all(self):
        for e in self.tab:
            if e[1] < NSLOT:
                self._hide(e[1])
            e[1] = 0xFF

    def _remove(self, i):
        last = self.tab.pop()
        if i < len(self.tab):
            self.tab[i] = last

    def plot(self, get, d):
        """At the plotter entry. -> (slot hidden at the exit or None, slot shown now or None)."""
        y, rows, w, x = d['y'], d['rows'], d['w'], d['x']
        if y > 175 or not rows or y + 1 < rows or not w:
            self.taint_all()
            self.ovf = 1
            return None, None
        y0 = 175 - y
        c0 = x >> 3
        c1 = c0 + w - 1 + (1 if x & 7 else 0)
        rect = (y0, y0 + rows - 1, c0, c1)
        nospr = 0
        if c1 > 31:
            rect, nospr = WHOLE, 1
        elif w > 4 or rows > 32:
            nospr = 2
        key = (d['g'] & 255, d['g'] >> 8, x, y, rows, w)
        for i, e in enumerate(self.tab):
            if e[0] == key:
                s = e[1]
                if s == 0xFF:
                    return None, None
                self._remove(i)
                if s < NSLOT:
                    self.free.append(s)
                    return s, None
                return None, None
        if self.ovf:
            return None, None
        if len(self.tab) >= NTAB:
            self.ovf = 1
            return None, None
        s = 0xFE if nospr or not self.free else self.free.pop()
        self.tab.append([key, s, rect])
        if s >= NSLOT:
            return None, None
        g = bytes(get((d['g'] + i) & 0xFFFF) for i in range(rows * w))
        ink = plot_ink(get, d, y0, c0)
        pix = image_pixels(g, w, rows, x, y0)
        sh = {p: OUTLINE for p in outline(pix)}
        sh.update({p: ink for p in pix})
        self.shown[s] = sh
        return None, s

    def exit(self, s):
        if s is not None:
            self.shown.pop(s, None)

    def touch(self, rect, kind):
        y0, y1, c0, c1 = rect
        i = 0
        while i < len(self.tab):
            e = self.tab[i]
            a0, a1, b0, b1 = e[2]
            if a1 < y0 or y1 < a0 or b1 < c0 or c1 < b0:
                i += 1
                continue
            if e[1] < NSLOT:
                self._hide(e[1])
            if kind and y0 <= a0 and a1 <= y1 and c0 <= b0 and b1 <= c1:
                self._remove(i)
                continue
            e[1] = 0xFF
            i += 1
        if kind and rect == WHOLE:
            self.ovf = 0

    def layer(self):
        out = {}
        for s in sorted(self.shown):              # higher sprite (slot) on top
            for (x, y), n in self.shown[s].items():
                if 0 <= x < 256 and 0 <= y < 192:
                    out[(x, y)] = n
        return out

    def live_bytes(self):
        """Screen addresses inside a live key's rectangle -> key."""
        out = {}
        for k, s, (y0, y1, c0, c1) in self.tab:
            if s == 0xFF:
                continue
            for y in range(y0, y1 + 1):
                for c in range(c0, min(c1, 31) + 1):
                    out[screen_addr(c, y)] = k
        return out

    def table_bytes(self):
        """The page-26 bytes the hooks must hold for this model (entries, count, flags, free stack)."""
        p = {V_N: len(self.tab), V_OVF: self.ovf, V_NFREE: len(self.free)}
        for i, s in enumerate(self.free):
            p[FREE + i] = s
        for i, (k, s, r) in enumerate(self.tab):
            for j, v in enumerate(list(k) + [s] + list(r) + [0]):
                p[TAB + 12 * i + j] = v
        return p


def touch_rect(site, get, R):
    """The rectangle and kind (1 clear, 0 taint) a writer site touches, from the state at the site;
    None: no screen touch."""
    k = SITES[site][2] if site in SITES else ROM_SITES[site][2]
    if k in TOUCH:
        return TOUCH[k]
    if k not in ('char', 'tile', 'cll'):
        return None
    if k == 'char':
        a = R[6] << 8 | R[7]
    elif k == 'tile':
        a = get(TILEAT) | get(TILEAT + 1) << 8
    else:                                         # cll: B lines from the bottom
        b = R[2]
        if 1 <= b <= 24:
            return ((24 - b) * 8, 191, 0, 31), 1
        return WHOLE, 0
    if not 0x4000 <= a < 0x5800:
        return None
    return cell_rect(a), 0


# ---------------------------------------------------------------------------------------------
# Differential verification against the RZX (the replay runs the ORIGINAL game)
# ---------------------------------------------------------------------------------------------

_SIM = []


def _rw():
    if not _SIM:
        from .dizzy6 import _rw_simulator
        _SIM.append(_rw_simulator())
    return _SIM[0]


def _sync(ns, m):
    """Make the patched machine's page-26 tables and visible sprites those of model m (unit cases:
    a model changed from a captured one; sprites may only be removed)."""
    pg = ns.pages[PG]
    for a, v in m.table_bytes().items():
        pg[a] = v
    for s in range(NSLOT):
        if s not in m.shown:
            for k in range(9):
                ns.attr[9 * s + k][3] = 0
    ns.u[:] = m.u
    if P27 in ns.pages:
        ns.pages[P27][0x300:0x480] = m.usv


def compare(ns, m, fail, what, c=None, orig=None):
    """Patched Next state vs the model: the sprite layer, the hooks' tables, the ULA attribute file
    and (orig = the original's memory) the attribute shadow."""
    if ns.u != m.u:
        d = [i for i in range(768) if ns.u[i] != m.u[i]]
        fail('%s: ULA attributes differ from the model' % what, (len(d), [(hex(ATTR0 + i), ns.u[i], m.u[i]) for i in d[:3]]))
    if orig is not None:
        sh = ns.pages[P27]
        d = [i for i in range(768) if sh[i] != orig(ATTR0 + i)]
        if d:
            fail('%s: attribute shadow differs from the original' % what,
                 (len(d), [(hex(ATTR0 + i), sh[i], orig(ATTR0 + i)) for i in d[:3]]))
        if c is not None:
            c['attribute bytes compared'] += 1536
    exp, got = m.layer(), ns.layer()
    if ns.bad:
        fail('%s: %s' % (what, ns.bad[0][0]))
        ns.bad = []
    if got != exp:
        go, eo = set(got.items()) - set(exp.items()), set(exp.items()) - set(got.items())
        fail('%s: sprite layer differs from the model' % what,
             ('sprites only', len(go), sorted(go)[:3], 'model only', len(eo), sorted(eo)[:3]))
    pg = ns.pages[PG]
    tb = m.table_bytes()
    bad = [a for a, v in tb.items() if pg[a] != v]
    if bad:
        fail('%s: hook tables differ from the model' % what, (len(bad), [(hex(a), pg[a], tb[a]) for a in bad[:4]]))
    if c is not None:
        c['sprite pixels compared'] += len(exp)
        c['table bytes compared'] += len(tb)


def verify(patch, rzx_path, stop=None, collect=0, progress=None, shots=None):
    """Replay the RZX (original game, Python simulator); at every site run the original and the
    patched code from the same state and compare; check the sprite layer, the hooks' tables, the ULA
    attribute file (model) and the attribute shadow (= the original's) after every event and at a
    plot's body start, each plot's screen change against its image, every screen write outside the
    plotter against the live rectangles, and every attribute access outside the hooked routines
    (none may write; none may read a cell whose ULA value differs from the original's).
    shots: frames at which to keep what the Next shows (ULA pixels, ULA attributes, sprite layer):
    -> (Counter, examples, states, shots) then.
    -> (Counter, examples[, states])."""
    import skoolkit.rzxplay as rzxplay
    from skoolkit.simulator import Simulator
    G, S = list.__getitem__, list.__setitem__
    c = collections.Counter()
    ex = collections.defaultdict(list)
    alt = patch.rom_image()
    Sim = _rw()
    site_bytes = {a + k for a, old, new in patch.sites for k in range(len(new))}
    ns = NextState({PG: page26(patch.p26)})
    model = Model()
    st = {'frame': 0, 'on': False, 'R': None, 'live': {}, 'plot': None, 'gfx': set(), 'span': None,
          'diff': set()}
    cnt = collections.Counter()
    fcost = collections.Counter()
    states = []
    hook_pcs = set(range(*HOOK_RANGE))
    WATCH = set(SITES) | set(ROM_SITES) | set(INTERIORS) | {BODY_RET} | hook_pcs

    def fail(k, info=()):
        c[k + '!'] += 1
        if len(ex[k]) < 5:
            ex[k].append((st['frame'],) + tuple(info))

    class Mem(list):
        def __getitem__(s, a):
            if a in st['diff'] and st['span'] is None and st['on']:
                fail('attribute read outside the hooks of a cell the ULA shows differently',
                     (hex(st['R'][24]), hex(a)))
            return G(s, a)

        def __setitem__(s, a, v):
            if st['on']:
                if a in site_bytes:
                    fail('game wrote a patch site', (hex(a), hex(st['R'][24])))
                if a in st['gfx']:
                    fail('game wrote a graphic a plot used (the sprite keeps the old shape)', (hex(a),))
                if 0x4000 <= a < 0x5800:
                    pc = st['R'][24]
                    d = G(s, a) ^ v
                    if BODY <= pc <= BODY_RET:
                        pl = st['plot']
                        if pl is not None and d:
                            pl['delta'][a] = pl['delta'].get(a, 0) ^ d
                    elif d and a in st['live']:
                        fail('screen write into a live image\'s rectangle with no touch hook', (hex(pc), hex(a)))
                elif ATTR0 <= a < ATTR1 and st['span'] is None:
                    fail('attribute write outside the hooks', (hex(st['R'][24]), hex(a)))
            S(s, a, v)

    def snap(get):
        return bytes(get(a) for a in range(65536))

    class Sm(Simulator):
        def __init__(self, memory, registers=None, state_=None, config=None):
            super().__init__(Mem(memory), registers, state_, config)
            R, mem, ops = self.registers, self.memory, self.opcodes
            get = lambda a: G(mem, a)
            at0 = bytes(get(ATTR0 + i) for i in range(768))
            ns.pages[P27] = bytearray(page27(at0, patch.p27))
            ns.u[:] = at0
            model.u[:] = at0
            st['on'] = True
            st['R'] = R
            st['mem'] = mem

            def keep(label, pc):
                if collect and c['collected ' + label] < collect:
                    c['collected ' + label] += 1
                    states.append((label, pc, list(R), snap(get), ns.copy(), model.copy()))

            def span(pc):
                r = RESUME[pc]
                if r is None:
                    st['span'] = (get(R[12]) | get(R[12] + 1) << 8, (R[12] + 2) & 0xFFFF)
                else:
                    st['span'] = (r[0], (R[12] + r[1]) & 0xFFFF)

            def diff():
                st['diff'] = {ATTR0 + i for i in range(768) if model.u[i] != G(mem, ATTR0 + i)}

            def run(pc, label, at_body=None):
                COST['extra'] = 0
                fl, o, ro = event(patch, pc, get, R, ns, alt, Sim, at_body)
                c[label] += 1
                fcost[st['frame']] += COST['extra']
                for k in fl:
                    fail('%s: %s' % (label, k[0] if isinstance(k, tuple) else k),
                         k[1:] if isinstance(k, tuple) else ())
                return o

            def mk(fn):
                def g():
                    pc = R[24]
                    sp_ = st['span']
                    if sp_ is not None and pc == sp_[0] and R[12] == sp_[1]:
                        st['span'] = None
                        diff()
                    if pc not in WATCH:
                        fn()
                        return
                    cnt[pc] += 1
                    if st['span'] is not None and pc != BODY_RET:
                        fn()
                        return
                    if pc == PLOT:
                        d = read_desc(get, R[6] << 8 | R[7])
                        m1 = model.copy()
                        hide, show = m1.plot(get, d)
                        label = 'draw' if show is not None else ('erase' if hide is not None else 'plot, no sprite')
                        keep(label, pc)
                        model.plot(get, d)
                        mb = model.copy()

                        def at_body(ns_):
                            compare(ns_, mb, fail, '%s at the body start' % label, None, get)
                            c['transient checks'] += 1
                        o = run(pc, label, at_body)
                        model.exit(hide)
                        compare(ns, model, fail, label, c, o.__getitem__)
                        span(pc)
                        st['plot'] = {'d': d, 'delta': {}, 'sp': R[12]}
                        g0 = d['g']
                        for i in range(d['rows'] * d['w']):
                            st['gfx'].add((g0 + i) & 0xFFFF)
                        st['live'] = model.live_bytes()
                        if show is not None:
                            st['ink'] = plot_ink(get, d, 175 - d['y'], d['x'] >> 3)
                        c['max live keys'] = max(c['max live keys'], sum(1 for e in model.tab if e[1] != 0xFF))
                        c['max table entries'] = max(c['max table entries'], len(model.tab))
                    elif pc == BODY_RET:
                        pl = st['plot']
                        if pl is not None and R[12] == pl['sp']:
                            want = image_bytes(get, pl['d'])
                            got = {k: v for k, v in pl['delta'].items() if v}
                            if want != got:
                                fail('plot: screen change is not the image', (len(set(want.items()) ^ set(got.items())),))
                            c['plot screen bytes compared'] += len(want)
                            st['plot'] = None
                            if st.get('ink') is not None:
                                y0 = 175 - pl['d']['y']
                                a_ = get(0x5800 + (y0 >> 3) * 32 + (pl['d']['x'] >> 3))
                                k_ = (a_ & 7) | (8 if a_ & 0x40 else 0) if a_ & 7 else 8
                                c['colour: rule = first cell ink at the plot exit' if k_ == st['ink']
                                  else 'colour: rule != first cell ink at the plot exit'] += 1
                                st['ink'] = None
                    elif pc in INTERIORS:
                        pass
                    elif pc in hook_pcs:
                        fail('original ran in the alt ROM hook range', (hex(pc),))
                    else:
                        tr = touch_rect(pc, get, R)
                        label = SITES[pc][2] if pc in SITES else ROM_SITES[pc][2]
                        keep(label, pc)
                        o = run(pc, label)
                        if tr:
                            model.touch(*tr)
                        model.attrs(label, get, R, o.__getitem__)
                        compare(ns, model, fail, label, c, o.__getitem__)
                        st['live'] = model.live_bytes()
                        span(pc)
                    fn()
                return g
            for i in range(256):
                ops[i] = mk(ops[i])

    _nf = rzxplay.RZXTracer.next_frame

    shot = []

    def next_frame(self):
        st['frame'] += 1
        if shots and st['frame'] in shots and st.get('mem') is not None:
            shot.append((st['frame'], bytes(G(st['mem'], a) for a in range(0x4000, 0x5800)), bytes(ns.u), ns.layer()))
        if progress and st['frame'] % 1000 == 0:
            progress(st['frame'], c)
        return _nf(self)
    old = (rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator)
    rzxplay.RZXTracer.next_frame = next_frame
    rzxplay.Simulator = Sm
    rzxplay.CSimulator = None
    try:
        rzxplay.main(['--python', '--quiet', '--no-screen', '--fps', '0'] +
                     (['--stop', str(stop)] if stop else []) + [rzx_path])
    except SystemExit:
        pass
    finally:
        rzxplay.RZXTracer.next_frame, rzxplay.Simulator, rzxplay.CSimulator = old
    for a in INTERIORS:
        if a in SEQUELS:
            if cnt[a] != cnt[SEQUELS[a]]:
                c['0x%04X reached other than from 0x%04X!' % (a, SEQUELS[a])] += 1
        elif cnt[a]:
            c['jump into a patched instruction (0x%04X)!' % a] += 1
    c['frames'] = st['frame']
    c['interrupt-safety points'] = ISAFE['checked']
    if fcost:
        v = sorted(fcost.values())
        c['speed: hook T per game frame, mean'] = int(sum(v) / max(1, st['frame']))
        c['speed: hook T per game frame, max'] = int(v[-1])
    if shots:
        return c, dict(ex), states, shot
    return (c, dict(ex), states) if collect else (c, dict(ex))


def render(pixels, attrs, layer, scale=2):
    """What the Next shows: the ULA (pixels + attributes) with the sprite layer in front -> PIL image."""
    from PIL import Image
    pal = [(0, 0, 0), (0, 0, 0xD7), (0xD7, 0, 0), (0xD7, 0, 0xD7), (0, 0xD7, 0), (0, 0xD7, 0xD7),
           (0xD7, 0xD7, 0), (0xD7, 0xD7, 0xD7), (0, 0, 0), (0, 0, 0xFF), (0xFF, 0, 0), (0xFF, 0, 0xFF),
           (0, 0xFF, 0), (0, 0xFF, 0xFF), (0xFF, 0xFF, 0), (0xFF, 0xFF, 0xFF)]
    img = Image.new('RGB', (256, 192))
    px = img.load()
    for y in range(192):
        for c in range(32):
            b = pixels[screen_addr(c, y) - 0x4000]
            a = attrs[(y >> 3) * 32 + c]
            br = 8 if a & 0x40 else 0
            for k in range(8):
                px[c * 8 + k, y] = pal[(a & 7 if b >> (7 - k) & 1 else a >> 3 & 7) + br]
    for (x, y), n in layer.items():
        px[x, y] = pal[n]
    return img.resize((256 * scale, 192 * scale), Image.NEAREST)


# ---------------------------------------------------------------------------------------------
# Unit tests (paths the RZX does not reach) and negative controls
# ---------------------------------------------------------------------------------------------

def _ns_for(pt, ns0):
    """The patched machine's Next state for patch pt from a captured one: the run-time bytes of page
    26 (tables, 0x0000-0x06FF) from the capture, pt's OWN code (CLAUDE.md: negative controls)."""
    ns = ns0.copy()
    ns.pages[PG][P26_OFF:] = page26(pt.p26)[P26_OFF:]
    ns.pages[P27][P27_OFF:] = page27(bytes(768), pt.p27)[P27_OFF:]
    return ns


def _entry_only(pt, R, mem, ns, alt, Sim):
    """Patched plot hook from the entry to the body (a plot the original cannot finish)."""
    psite = {a + k: v for a, old, new in pt.sites for k, v in enumerate(new)}
    O, P = _overlays(mem.__getitem__, alt, psite, ns)
    sim = _machine(Sim, P(), list(R), ns, 'p')
    body = pt.syms['body2']
    ok = _run(sim, lambda r: r[24] == body)
    return [] if ok else ['patched hook never reached the body']


def _dummy(i, s=0xFF, rect=(0, 0, 0, 0)):
    return [(i & 255, 0x01, i >> 8, 200, 1, 1), s, rect]


def unit_cases(states):
    """[(name, state, mutate(R, mem, model) or None, mode)] - mode 'run' (to the meeting point) or
    'body' (plot entry to the body only)."""
    by = collections.defaultdict(list)
    for stt in states:
        by[stt[0]].append(stt)
    cases = []
    draw = by['draw'][-1] if by['draw'] else None
    erase = by['erase'][-1] if by['erase'] else None
    if draw:
        def dset(off, v):
            def f(R, mem, m):
                mem[(R[6] << 8 | R[7]) + off] = v
            return f

        def both(*fs):
            def f(R, mem, m):
                for g in fs:
                    g(R, mem, m)
            return f

        def full(R, mem, m):
            m.tab += [_dummy(i) for i in range(NTAB - len(m.tab))]

        def ovf(R, mem, m):
            m.ovf = 1

        def nofree(R, mem, m):
            m.free = []

        def taint_key(R, mem, m):
            d = read_desc(mem.__getitem__, R[6] << 8 | R[7])
            m.tab.append([(d['g'] & 255, d['g'] >> 8, d['x'], d['y'], d['rows'], d['w']), 0xFF, (0, 0, 0, 0)])

        def nospr_key(R, mem, m):
            d = read_desc(mem.__getitem__, R[6] << 8 | R[7])
            m.tab.insert(0, [(d['g'] & 255, d['g'] >> 8, d['x'], d['y'], d['rows'], d['w']), 0xFE, (0, 0, 0, 0)])

        def cell(v, at=None, pf=None, mt=None):
            def f(R, mem, m):
                d = read_desc(mem.__getitem__, R[6] << 8 | R[7])
                y0 = 175 - d['y']
                mem[0x5800 + (y0 >> 3) * 32 + (d['x'] >> 3)] = v
                if at is not None:
                    mem[ATTR_T] = at
                if pf is not None:
                    mem[P_FLAG] = pf
                if mt is not None:
                    mem[MASK_T] = mt
            return f
        cases += [('draw', draw, None, 'run'),
                  ('draw: table full -> overflow, no entry', draw, full, 'run'),
                  ('draw in overflow: not recorded', draw, ovf, 'run'),
                  ('draw with no free slot: live, no sprite', draw, nofree, 'run'),
                  ('draw past column 31: no sprite, whole-screen rectangle', draw, dset(2, 250), 'run'),
                  ('draw 5 bytes wide: no sprite', draw, dset(5, 5), 'run'),
                  ('plot of a tainted key: nothing', draw, taint_key, 'run'),
                  ('plot of a live key with no sprite: forgotten', draw, nospr_key, 'run'),
                  ('plot y 176: all tainted, overflow', draw, dset(3, 176), 'body'),
                  ('plot of 0 rows: all tainted, overflow', draw, dset(4, 0), 'body'),
                  ('plot y + 1 < rows: all tainted, overflow', draw, both(dset(3, 3), dset(4, 8)), 'body'),
                  ('plot width 0: all tainted, overflow', draw, dset(5, 0), 'body')]
        for t in (0, 1, 2):
            cases += [('colour type %d, cell = ATTR-T' % t, draw, both(dset(6, t), dset(7, 0x45), cell(0x38, 0x38, 0, 0)), 'run'),
                      ('colour type %d, cell = value' % t, draw, both(dset(6, t), dset(7, 0x45), cell(0x45, 0x38, 0, 0)), 'run'),
                      ('colour type %d, black' % t, draw, both(dset(6, t), dset(7, 0x40), cell(0x40, 0x40, 0, 0)), 'run')]
        for pf in (0x10, 0x40, 0x50):
            cases.append(('colour type 2, P-FLAG 0x%02X' % pf, draw,
                          both(dset(6, 2), cell(0x0D, 0x22, pf, 0x00)), 'run'))
        cases.append(('colour type 2, MASK-T 0xFF', draw, both(dset(6, 2), cell(0x0D, 0x22, 0, 0xFF)), 'run'))
    if erase:
        cases.append(('erase', erase, None, 'run'))

        def at(pc, regs=None, mem_=None, model_=None):
            def f(R, mem, m):
                R[24] = pc
                for k, v in (regs or {}).items():
                    R[k] = v
                for a, v in (mem_ or {}).items():
                    mem[a] = v
                if model_:
                    model_(R, mem, m)
            return f

        def live_cell(m):
            """A cell inside the first live key with a sprite (its screen address), or None."""
            for k, s, (y0, y1, c0, c1) in m.tab:
                if s < NSLOT:
                    return screen_addr(c0, y0 & 0xF8)
            return None
        m0 = erase[5]
        lc = live_cell(m0)
        if lc is not None:
            cases += [('PR-ALL on a live image', erase, at(0x0B9B, {6: lc >> 8, 7: lc & 255}), 'run'),
                      ('tile on a live image', erase, at(0xB366, {0: 0x41}, {TILEAT: lc & 255, TILEAT + 1: lc >> 8}), 'run')]
        lower = lambda R, mem, m: [e.__setitem__(2, (130, 140, e[2][2], e[2][3])) for e in m.tab]
        lowcol = lambda col: lambda R, mem, m: [e.__setitem__(2, (130, 140, col, col)) for e in m.tab]
        cases += [('PR-ALL to the printer buffer: no touch', erase, at(0x0B9B, {6: 0x5B, 7: 0x00}), 'run'),
                  ('PR-ALL off a cell\'s top line: whole screen', erase, at(0x0B9B, {6: 0x43, 7: 0x00}), 'run'),
                  ('tile off the screen: no touch', erase, at(0xB366, {0: 0x41}, {TILEAT: 0, TILEAT + 1: 0x60}), 'run'),
                  ('clear 64-191 with every image inside', erase, at(0xB2A0, model_=lower), 'run'),
                  ('clear 64-191, images straddle line 64', erase,
                   at(0xB2A0, model_=lambda R, mem, m: [e.__setitem__(2, (60, 70, 0, 3)) for e in m.tab]), 'run'),
                  ('clear 64-191 in overflow: overflow stays', erase, at(0xB2A0, model_=ovf), 'run'),
                  ('scroll left, images in the bottom third', erase, at(0xDED2, model_=lower), 'run'),
                  ('scroll left, image in column 31 only: untouched', erase, at(0xDED2, model_=lowcol(31)), 'run'),
                  ('scroll right, image in column 0 only: untouched', erase, at(0xDEEA, model_=lowcol(0)), 'run'),
                  ('scroll right, images in the bottom third', erase, at(0xDEEA, model_=lower), 'run'),
                  ('CL-LINE 24 (CLS) in overflow: all forgotten, overflow ends', erase, at(0x0E44, {2: 24}, model_=ovf), 'run'),
                  ('CL-LINE 2: lower lines only', erase, at(0x0E44, {2: 2}, model_=lower), 'run'),
                  ('CL-SCROLL (0x0E00, B 23): all tainted', erase, at(0x0E00, {2: 23}), 'run')]
    # attribute shadow (Q8): each hooked reader / writer as captured, and with every ULA cell
    # different from the original's (as under painted figures)
    def paint(R, mem, m):
        m.u[:] = bytes(b ^ 0x3F for b in mem[ATTR0:ATTR1])

    def regs(**kw):
        idx = {'A': 0, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'H': 6, 'L': 7}
        def f(R, mem, m):
            for k, v in kw.items():
                R[idx[k]] = v
        return f

    def both2(*fs):
        def f(R, mem, m):
            for g in fs:
                g(R, mem, m)
        return f
    for kind in ('peek', 'poa', 'save', 'rest', 'box', 'rfil', 'sal', 'sar', 'tatt', 'tard', 'cll'):
        if by[kind]:
            stt = by[kind][-1]
            cases += [('%s as captured' % kind, stt, None, 'run'),
                      ('%s, every ULA cell differs' % kind, stt, paint, 'run')]
    if by['peek']:
        stt = by['peek'][-1]
        cases += [('PEEK of an attribute, ULA differs', stt, both2(paint, regs(H=0x59, L=0x23)), 'run'),
                  ('PEEK of the screen', stt, both2(paint, regs(H=0x48, L=0x23)), 'run'),
                  ('PEEK of 0x5B00', stt, both2(paint, regs(H=0x5B, L=0x00)), 'run')]
    if by['rest']:
        stt = by['rest'][-1]

        def bufchg(R, mem, m):
            paint(R, mem, m)
            for i in range(0, 192, 7):
                mem[BUF + i] ^= 0x11
        cases.append(('restore with the buffer changed since the save', stt, bufchg, 'run'))

        def saved(R, mem, m):
            paint(R, mem, m)
            for i in range(192):
                m.usv[2 * i + 1] = mem[BUF + i]
                m.usv[2 * i] = mem[BUF + i] ^ 0x3F
        cases.append(('restore right after its save, every ULA cell different', stt, saved, 'run'))
    if by['box']:
        def boxchg(R, mem, m):
            paint(R, mem, m)
            for r in range(5):
                for c_ in range(6):
                    mem[ATTR0 + 0xE6 + 32 * r + c_] ^= 0x3F
        cases.append(('box over cells holding other colours', by['box'][-1], boxchg, 'run'))
    if by['tard']:
        cases.append(('room cell read off the attributes', by['tard'][-1], both2(paint, regs(D=0x40)), 'run'))
    if by['tatt']:
        cases.append(('room cell write off the attributes', by['tatt'][-1], both2(paint, regs(D=0x40)), 'run'))
    if by['poa']:
        stt = by['poa'][-1]

        def mask(R, mem, m):
            paint(R, mem, m)
            mem[MASK_T] = 0xFF
            mem[P_FLAG] = 0x50
        cases.append(('PO-ATTR with MASK-T 0xFF, INK / PAPER 9, ULA differs', stt, mask, 'run'))
    if erase:
        # CL-LINE with B 0 or > 24 never returns in the original (it clears over the stack): no case
        cases += [('CL-LINE 3 with every ULA cell different', erase, both2(paint, at(0x0E44, {2: 3})), 'run'),
                  ('CL-SCROLL with every ULA cell different', erase, both2(paint, at(0x0E00, {2: 23})), 'run')]
    if draw:
        cases.append(('draw with every ULA cell different', draw, paint, 'run'))
    return cases


def run_case(pt, stt, mut, mode, fail, c=None):
    label, pc, R, mem, ns0, m0 = stt
    R, mem, m = list(R), bytearray(mem), m0.copy()
    if mut:
        mut(R, mem, m)
    ns = _ns_for(pt, ns0)
    _sync(ns, m)
    ns.pages[P27][0:768] = mem[ATTR0:ATTR1]       # the shadow = the original's attributes (a mutated case too)
    alt = pt.rom_image()
    Sim = _rw()
    get = mem.__getitem__
    pc = R[24]
    if pc == PLOT:
        d = read_desc(get, R[6] << 8 | R[7])
        hide, show = m.plot(get, d)
        if mode == 'body':
            for k in _entry_only(pt, R, mem, ns, alt, Sim):
                fail(k)
            compare(ns, m, fail, 'at the body', c)
            return
        mb = m.copy()
        fl, o, ro = event(pt, pc, get, R, ns, alt, Sim,
                          lambda ns_: compare(ns_, mb, fail, 'at the body start', c, get))
        m.exit(hide)
    else:
        tr = touch_rect(pc, get, R)
        fl, o, ro = event(pt, pc, get, R, ns, alt, Sim)
        if tr:
            m.touch(*tr)
        k_ = SITES[pc][2] if pc in SITES else ROM_SITES[pc][2]
        m.attrs(k_, get, R, o.__getitem__)
    for k in fl:
        fail(k[0] if isinstance(k, tuple) else k, k[1:] if isinstance(k, tuple) else ())
    compare(ns, m, fail, 'after', c, o.__getitem__)


def unit_tests(patch, states, negs=None):
    """Every case with the real patch must pass; every negative patch must fail at least one."""
    c = collections.Counter()
    cases = unit_cases(states)
    for name, stt, mut, mode in cases:
        bad = []
        run_case(patch, stt, mut, mode, lambda k, info=(): bad.append((k, info)), c)
        c['cases'] += 1
        if bad:
            c['%s: %s!' % (name, bad[0][0])] += 1
            c['  %s: %s %s' % (name, bad[0][0], str(bad[0][1])[:160])] += 1
    for what, npt in (negs or {}).items():
        caught = 0
        for name, stt, mut, mode in cases:
            bad = []
            try:
                run_case(npt, stt, mut, mode, lambda k, info=(): bad.append(k))
            except Exception as e:              # a broken build may crash the run: caught
                bad.append(repr(e))
            if bad:
                caught += 1
        c['negative controls'] += 1
        if not caught:
            c['negative control not caught: %s!' % what] += 1
        else:
            c['  negative control %s: caught by %d of %d cases' % (what, caught, len(cases))] += 1
    if not states:
        c['no captured states!'] += 1
    return c


def _neg(patch, old, new, what, block='rom', nth=None):
    """Copy of the patch with one hook byte sequence changed (exactly once in the block, or its nth
    occurrence)."""
    o, n = bytes.fromhex(old), bytes.fromhex(new)
    blk = bytearray({'rom': patch.rom_code, 'p26': patch.p26, 'p27': patch.p27}[block])
    hits = [i for i in range(len(blk)) if blk[i:i + len(o)] == o]
    if nth is None and len(hits) != 1:
        raise ValueError('negative control %s: pattern %s found %d times' % (what, old, len(hits)))
    i = hits[nth or 0]
    blk[i:i + len(o)] = n
    kw = {'rom_code': patch.rom_code, 'p26': patch.p26, 'p27': patch.p27}
    kw[{'rom': 'rom_code', 'p26': 'p26', 'p27': 'p27'}[block]] = bytes(blk)
    return CauldronPatch(patch.prof, jmp=patch.jmp, **kw)


def negative_patches(patch):
    return {'sprite X one pixel off': _neg(patch, '6f2600112000', '6f2600112100', 'X'),
            'erase never hides its sprite': _neg(patch, 'e3f57dfe0e', 'e3f57dfe00', 'exit'),
            'left scroll touches nothing': _neg(patch, '01bf80111e00', '01bfc0111e00', 'scl'),
            'clear 0xB2A0 forgets nothing (taints)': _neg(patch, '01bf40111f003e01', '01bf40111f003e00', 'clr'),
            'PR-ALL hook only for 0x4000-0x40FF': _neg(patch, 'fe5830', 'fe4130', 'char', nth=0),
            'tainted key plotted again gets a sprite': _neg(patch, 'feffca', 'fefdca', 'taint', 'p26'),
            'table full not detected': _neg(patch, 'fe8038', 'fe8138', 'full', 'p26'),
            'full clear keeps the overflow': _neg(patch, 'af3201c0c9', '003201c0c9', 'ovf', 'p26'),
            'type 2 colour ignores INK 9': _neg(patch, 'cb66', 'cb6e', 'pflag', 'p26'),
            'plotter paints the ULA': _neg(patch, 'e603f680', 'e603f658', 'body', 'p27'),
            'no outline (top pixel of a pair)': _neg(patch, '3e082001af', '3e002001af', 'outline', 'p27', nth=0),
            'PEEK reads the ULA': _neg(patch, 'c628', 'c600', 'peek', nth=0),
            'PO-ATTR twice on the ULA': _neg(patch, 'c628', 'c600', 'poa', nth=1),
            'restore ignores the save': _neg(patch, 'ddbe01', 'ddbe00', 'rest', 'p27'),
            'left attribute scroll skips the shadow': _neg(patch, '210082cd', '21005acd', 'sal', 'p27'),
            'box skips the shadow': _neg(patch, '21e680cd', '21e658cd', 'box', 'p27'),
            'CL-LINE rows not into the shadow': _neg(patch, '110028', '110000', 'cll', 'p27')}


# ---------------------------------------------------------------------------------------------
# auto: plain + sprite build from the RZX's snapshot, verify, unit tests
# ---------------------------------------------------------------------------------------------

def rom3_independent(nex, src, patch, conv):
    """Boot with a system ROM3 that differs from Sinclair's in every byte: the alt ROM must still
    be exactly patch.rom_image() (+ the register block). -> list of problems."""
    from .nextboot import check
    foreign = bytes(b ^ 0x5A for b in _rom48())
    bad = check(nex, src, patch, (conv[1], conv[1] + len(conv[2])), nexload=True, sysrom=foreign)
    from .nextboot import boot
    import copy
    from . import z80tonex as zt
    s = zt.Z80Snapshot(src)
    st = boot(nex, s.pc, nexload=True, sysrom=foreign)
    img = patch.rom_image()
    view = bytes(st['mem'][a] for a in range(0x4000))
    rb = patch.regblock
    d = [a for a in range(0x4000) if view[a] != img[a] and not rb <= a < rb + 20]
    if d:
        bad.append(('alt ROM differs from rom_image()', len(d), [hex(x) for x in d[:6]]))
    return bad


def auto(a, z80, name, out, say):
    from . import z80tonex as zt
    from .nextboot import check
    say('Game      : %s' % name)
    say('Engine    : cauldron (every XOR-plotted image -> sprites; overlay, plotter + screen-writer hooks)')
    md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
    rzxs = list(a.rzx or [])
    if not rzxs:
        say('Result    : FAILED (the build input is the snapshot inside cauldron.rzx: give --rzx)')
        return False
    src = start_state(rzxs[0], os.path.join(out, name + '_rzx_start.z80'))
    say('Input     : %s -> %s (MD5 %s; the delivered %s is a different build, Q0)' % (
        os.path.basename(rzxs[0]), os.path.basename(src), RZX_Z80_MD5, os.path.basename(z80)))
    plain = os.path.join(out, name + '.nex')
    conv = zt.convert(src, plain, TAIL_ADDR, True, quiet=True, keep_printer_buffer=True)
    bad = check(plain, src, None, (conv[1], conv[1] + len(conv[2])), nexload=True)
    say('Plain     : %s  %s  boot %s  (tail 0x%04X; printer buffer put back)' % (
        os.path.basename(plain), md5(plain), 'OK' if not bad else 'MISMATCH %s' % str(bad[:3])[:200], TAIL_ADDR))
    patch = CauldronPatch()
    spr = os.path.join(out, name + '_sprites.nex')
    conv = zt.convert(src, spr, None, True, quiet=True, patch=patch)
    bad2 = check(spr, src, patch, (conv[1], conv[1] + len(conv[2])), nexload=True)
    # the Next copies NextZXOS's ROM3, not Sinclair's: boot again with a ROM3 that differs in every
    # byte; slots 0/1 must still show exactly the image the verify runs on (BRIEFING C2 #5)
    bad2 += ['foreign ROM3: %s' % x for x in rom3_independent(spr, src, patch, conv)]
    say('Sprites   : %s  %s  boot %s' % (os.path.basename(spr), md5(spr),
                                         'OK (also with a foreign ROM3)' if not bad2 else
                                         'MISMATCH %s' % str(bad2[:3])[:200]))
    ok = not bad and not bad2
    json.dump(DECISIONS, open(os.path.join(out, name + '_decisions.json'), 'w'))
    if getattr(a, 'decisions', None):
        say('Result    : %s (rebuild from stored decisions, no verification)' % ('PASSED' if ok else 'FAILED'))
        return ok
    states = []
    for r in rzxs:
        c, ex, st = verify(patch, r, stop=getattr(a, 'quick', None), collect=3,
                           progress=lambda f, c_: say('            ... frame %d, plots %d' % (
                               f, c_['draw'] + c_['erase'] + c_['plot, no sprite'])) if f % 5000 == 0 else None)
        states += st
        fails = {k: v for k, v in c.items() if k.endswith('!')}
        ok = ok and not fails
        say('Verify    : %s  %d frames, plots %d (draw %d, erase %d, no sprite %d), touches: PR-ALL %d, tile %d, '
            'scroll %d / %d, clear %d, CL-LINE %d, CL-SCROLL %d; %d sprite pixels, %d table bytes, %d transient '
            'checks, %d plot screen bytes, %d interrupt-safety points, max %d live keys / %d entries -> %s' % (
                os.path.basename(r), c['frames'], c['draw'] + c['erase'] + c['plot, no sprite'], c['draw'],
                c['erase'], c['plot, no sprite'], c['char'], c['tile'], c['scl'], c['scr'], c['clr'], c['cll'],
                c['csc'], c['sprite pixels compared'], c['table bytes compared'], c['transient checks'],
                c['plot screen bytes compared'], c['interrupt-safety points'], c['max live keys'],
                c['max table entries'], 'IDENTICAL' if not fails else 'FAILED %s' % fails))
        say('Attributes: PEEK %d, PO-ATTR %d, save %d, restore %d, box %d, room fill %d, room cell %d / %d, '
            'scroll %d / %d; %d shadow + ULA bytes compared, no unhooked attribute access (Q8)' % (
                c['peek'], c['poa'], c['save'], c['rest'], c['box'], c['rfil'], c['tatt'], c['tard'],
                c['sal'], c['sar'], c['attribute bytes compared']))
        for k, v in ex.items():
            say('            %s: %s' % (k, str(v)[:300]))
        say('Colour    : rule = first cell ink at the plot exit %d, differs %d (informative)' % (
            c['colour: rule = first cell ink at the plot exit'], c['colour: rule != first cell ink at the plot exit']))
        say('Speed     : hook cost per game frame (69888 T): mean %d T, max %d T (28 MHz parts as T / 8)' % (
            c['speed: hook T per game frame, mean'], c['speed: hook T per game frame, max']))
    if states and 'unit_tests' in globals():
        u = unit_tests(patch, states, negative_patches(patch))
        uf = {k: v for k, v in u.items() if k.endswith('!')}
        ok = ok and not uf
        say('Unit      : %s -> %s' % (', '.join('%s %d' % (k, v) for k, v in sorted(u.items())
                                                if not k.startswith('  ')), 'PASS' if not uf else 'FAIL'))
        for k, v in u.items():
            if k.startswith('  '):
                say('          %s' % k.strip())
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog='python -m nexclash.cauldron')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('extract', help='cauldron.rzx -> its embedded snapshot (the build input)')
    p.add_argument('rzx')
    p.add_argument('-o', '--out', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'extract':
        print(start_state(a.rzx, a.out))


if __name__ == '__main__':
    main()
