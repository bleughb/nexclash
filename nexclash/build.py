"""Build .nex files: generic TID-engine patch (three memory strategies), dedicated builders, plain."""
import json, os
from . import z80tonex as zt
from .sprites import patterns_for

T = json.load(open(os.path.join(os.path.dirname(__file__), 'templates.json')))
SETUP = bytes.fromhex(T['setup'])
SETUP_ORG = 0xD000
SETUP_NBLOCKS2_OFF = len(SETUP) - 1
STRATEGIES = ('altrom', 'printer', 'slot1')      # default preference order for new builds (then the old rule)
ALTROM_END = 0x3D00                              # hooks + table + register block end below the ROM font


def rom48():
    """The real 48K ROM (Snapshot.memory holds ZEROS below 0x4000 for .z80 files)."""
    try:
        from skoolkit import ROM48, read_bin_file
    except ImportError:
        raise ImportError('nexclash needs SkoolKit 10.x: pip install -r requirements.txt '
                          '(add --break-system-packages on a managed Python)') from None
    return bytes(read_bin_file(ROM48, 16384))


def altrom_image(rom, org, body, regs_len=20):
    """8K image of 0x2000-0x3FFF for the alt ROM: ROM bytes + body at org + register block after it.
    Returns (page, regblock, (lo, hi)); the bytes outside lo..hi are the ROM's."""
    regblock = org + len(body)
    if regblock + regs_len > ALTROM_END:
        raise ValueError('hook code + table (0x%04X-0x%04X) does not fit below the ROM font' % (org, regblock + regs_len))
    if any(b != 0xFF for b in rom[org:regblock + regs_len]):
        raise ValueError('alt ROM hook range 0x%04X-0x%04X is not the 48K ROM\'s unused block' % (org, regblock + regs_len))
    page = bytearray(rom[0x2000:0x4000])
    page[org - 0x2000:regblock - 0x2000] = body
    return bytes(page), regblock, (org, regblock + regs_len)


def _w(v):
    return bytes([v & 255, v >> 8])


def _reloc(code, fix, prof):
    vals = {'PLOTTER': prof['plotter'], 'ERASER_CONT': prof['eraser_cont'], 'ERASER_SPSAVE': prof['eraser_spsave'],
            'WIPE_CONT': prof['wipe_cont'], 'WIPE_IX': prof['wipe_ix'], 'SOUND_TICK': prof['sound_tick'],
            'BOX_CONT': prof.get('box_cont', 0), 'BOX_VAR': prof.get('box_var', 0)}
    b = bytearray(code)
    for sym, positions in fix.items():
        for p in positions:
            b[p:p + 2] = _w(vals[sym])
    return bytes(b)


def tid_sites(prof, t):
    op = 0xC3 if prof['plot_site_kind'] == 'JP' else 0xCD
    s = [(prof['plot_site'], bytes([op]) + _w(prof['plotter']), bytes([op]) + _w(t['T_PLOT'])),
         (prof['eraser'], b'\xF3\xED\x73', b'\xC3' + _w(t['T_ERASE'])),
         (prof['wipe'], b'\xDD\x21' + _w(prof['wipe_ix']), b'\xC3' + _w(t['T_WIPE']) + b'\x00'),
         (prof['isr_hide_call'], b'\xCD' + _w(prof['sound_tick']), b'\xCD' + _w(t['T_ISR']))]
    if prof.get('box'):
        s.append((prof['box'], b'\x3A' + _w(prof['box_var']), b'\xC3' + _w(t['T_BOX'])))
    s += [(a, b'\x70', b'\x00') for a in prof['plotter_writes']]
    s += [(a, b'\x77', b'\x00') for a in prof['eraser_writes']]
    return s


class TidPatch:
    """Generic TID-engine patch. strategy 'printer' (trampolines at 0x5B00, hook page paged into
    slot 0), 'slot1' (everything in RAM page 24 at 0x2000-0x3FFF, flag in NextReg $7F) or 'altrom'
    (the slot1 hook code + table + register block in alt ROM image 1 = ROM3 copy, flag in $7F; the
    stub fills it from RAM page 24, the compact tail enables it). low_water = tail address for
    slot1/altrom (dead stack low-water mark, or 0x5B00 for altrom when the printer buffer is free)."""

    def __init__(self, prof, strategy, low_water=None):
        self.prof, self.strategy = prof, strategy
        self.name = 'TID-engine hardware sprite (%s)' % strategy
        self.altrom = None
        self.stub_extra = b''
        self.setup_call = SETUP_ORG
        self.hook_page_data = b''
        self.extra_banks = {}
        self.uses_printer_buffer = True
        if strategy == 'printer':
            t = T['printer']
            self.code = _reloc(bytes.fromhex(t['tramp']), t['fix'], prof)
            self.syms = t['syms']
        else:
            t = T['slot1']
            self.code = _reloc(bytes.fromhex(t['patch']), t['fix'], prof)
            self.syms = t['syms']
            self.slot1 = (t['page'], t['regblock'])
            self.tail_addr = low_water
            self.max_tail = None
            if strategy == 'altrom':
                self.uses_printer_buffer = low_water != 0x5B00
        self.sites = tid_sites(prof, self.syms)

    def apply(self, snap):
        if snap.is128:
            raise ValueError('this patch is for 48K snapshots')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, old, new in self.sites:
            cur = bytes(ram[a - 0x4000:a - 0x4000 + len(old)])
            if cur != old:
                raise ValueError('unexpected code at %d (%s, expected %s)' % (a, cur.hex(), old.hex()))
        if self.strategy == 'printer' and any(ram[0x1B00:0x1B00 + len(self.code)]):
            raise ValueError('printer buffer at 0x5B00 is not empty in this snapshot')
        if self.strategy == 'altrom' and self.tail_addr == 0x5B00:
            self.max_tail = 256
            if any(ram[0x1B00:0x1C00]):
                raise ValueError('printer buffer at 0x5B00 is not empty in this snapshot')
        elif self.strategy in ('slot1', 'altrom'):
            self.max_tail = snap.sp - self.tail_addr
            if self.max_tail < 54:
                raise ValueError('only %d bytes of dead stack below SP 0x%04X for the start-up tail'
                                 % (self.max_tail, snap.sp))
        pats, table, n = patterns_for(lambda a: ram[a - 0x4000], self.prof['frame_table'], self.prof['frame_base'])
        self.num_patterns = n
        for a, old, new in self.sites:
            ram[a - 0x4000:a - 0x4000 + len(new)] = new
        if self.strategy == 'printer':
            ram[0x1B00:0x1B00 + len(self.code)] = self.code
            t = T['printer']
            self.hook_page_data = bytes.fromhex(t['hooks']) + table
        elif self.strategy == 'altrom':
            self.page, regblock, self.altrom = altrom_image(rom48(), T['slot1']['org'], self.code + table)
            self.slot1 = (T['slot1']['page'], regblock)
        else:
            page = bytearray(8192)
            org = T['slot1']['org']
            page[org - 0x2000:org - 0x2000 + len(self.code) + len(table)] = self.code + table
            self.page = bytes(page)
        snap.banks[5] = bytes(ram[0:16384])
        snap.banks[2] = bytes(ram[16384:32768])
        snap.banks[0] = bytes(ram[32768:49152])
        pats = pats + bytes(-len(pats) % 256)
        if len(pats) < 8192:
            pats = pats + bytes(8192 - len(pats))
        setup = bytearray(SETUP)
        setup[SETUP_NBLOCKS2_OFF] = (len(pats) - 8192) // 256
        self.stub_extra = bytes(setup)
        self.extra_banks = {11: pats}
        if self.strategy in ('slot1', 'altrom'):
            self.extra_banks[12] = self.page + bytes(8192)


class _PlainCompact:
    name = 'none (compact start-up: register block in RAM page 24 at slot 1)'
    uses_printer_buffer = True
    stub_extra = b''
    setup_call = None
    hook_page_data = b''

    def __init__(self, tail_addr, max_tail):
        self.tail_addr, self.max_tail, self.slot1 = tail_addr, max_tail, (24, 0x3FE0)
        self.extra_banks = {12: bytes(16384)}

    def apply(self, snap):
        pass


ALTROM_HOOKS = (0x386E, ALTROM_END)     # the slot1 template's alt ROM range (48K ROM: all $FF)


def choose_tid_strategy(snap, an, strategy=None):
    """-> (strategy, reason, tail address or None). strategy None = default preference
    (altrom, then the old rule printer / slot1); a named strategy is checked, not substituted."""
    pb_zero = not any(snap.banks[5][0x1B00:0x1B00 + 80])
    pb_free = pb_zero and not an['printer_buffer_touched']
    dead = snap.sp - an['stack_low_water']
    rd = an.get('rd')
    hooks_unread = rd is not None and not any(rd[ALTROM_HOOKS[0]:ALTROM_HOOKS[1]])
    ok = {
        'altrom': (hooks_unread and (pb_free or dead >= 54),
                   'alt ROM (ROM3 copy + hooks at 0x386E; game never reads 0x%04X-0x%04X); compact tail in %s'
                   % (ALTROM_HOOKS[0], ALTROM_HOOKS[1] - 1, 'the printer buffer' if pb_free else 'dead stack'),
                   0x5B00 if pb_free else an['stack_low_water']),
        'printer': (pb_free, 'printer buffer empty and never used', None),
        'slot1': (not an['rom_used'] and dead >= 54, 'no free RAM; ROM never used -> patch in RAM page at slot 1',
                  an['stack_low_water']),
    }
    for st in ([strategy] if strategy else STRATEGIES):
        good, why, tail = ok[st]
        if good:
            return st, why, tail
    if strategy:
        return None, '--strategy %s is not proven safe for this game' % strategy, None
    return None, 'no safe place for the patch (printer buffer used, ROM hook area read or no dead stack)', None


def plain(z80, out, an=None, log=print):
    """Plain conversion with a tail location proven safe by the analysis (if given)."""
    from skoolkit.snapshot import Snapshot
    s = Snapshot.get(z80)
    sp = s.sp if hasattr(s, 'sp') else None
    if an is None:
        zt.convert(z80, out, None, True, quiet=True)
        return 'default tail (no recording to check it against)'
    rd, wr = an['rd'], an['wr']
    mem = s.memory
    pb_zero = not any(mem[0x5B00:0x5B50])
    pb_free = not any(rd[a] or wr[a] for a in range(0x5B00, 0x5B50))
    default = 0x5B00 if pb_zero else sp - 96
    if (default == 0x5B00 and pb_free) or (default != 0x5B00 and default >= an['stack_low_water']):
        zt.convert(z80, out, None, True, quiet=True)
        return 'tail at 0x%04X (converter default, checked safe)' % default
    if pb_free:
        zt.convert(z80, out, 0x5B00, True, quiet=True)
        return 'tail at 0x5B00 (printer buffer never used by the game)'
    low = an['stack_low_water']
    if not an['rom_used'] and sp - low >= 54:
        zt.convert(z80, out, None, True, quiet=True, patch=_PlainCompact(low, sp - low))
        return 'compact tail at 0x%04X (dead stack) + register block in RAM page at slot 1' % low
    zt.convert(z80, out, None, True, quiet=True)
    return 'WARNING: no proven-safe tail location; converter default used'
