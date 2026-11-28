"""Moley Christmas (48K). Resident 4-bit figures over the original OR plotter."""
from collections import Counter, deque
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from . import coloursheet as cs, recolour as rc
from . import hooklib, nextboot, rzx, simpool, z80n, z80tonex as zt
from . import auf_wiedersehen_monty as monty
from .build import rom48

PROFILE = Path(__file__).resolve().parents[1] / 'docs/profiles/moley_christmas.json'
CMP = hooklib.CMP_R
FIG, INIT, CYCLE, TAKE, ROOM, CLEAR, OVER = 0x8931, 0x8627, 0x8659, 0x8697, 0x854a, 0xa2a8, 0x8292
SITES = {
    FIG: ('figure', 'cd118a', 0x8952), INIT: ('pickup_init', 'dd23dd23', 0x862b),
    CYCLE: ('pickup_cycle', '77dd5e00', 0x865d), TAKE: ('collected', 'dd360200', 0x869b),
    ROOM: ('room', '320781', 0x854d), CLEAR: ('clear', '210040', 0xa2ab),
    OVER: ('gameover', 'cdd982', 0x82d9),
}
FIGURES, ITEMS, GFX = 0x8121, 0x86d5, 0xc000
ROM_ORG = 0x386e


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_moley_christmas(snap):
    sig = load_profile()['signature']
    data = bytes.fromhex(sig['bytes'])
    return snap.machine == '48K' and bytes(snap.memory[sig['addr']:sig['addr'] + len(data)]) == data


class Patch:
    name = 'Moley Christmas figures and cycling pickups'
    uses_printer_buffer = False
    keep_printer_buffer = True
    tail_addr, max_tail = 0x5c00, 192
    hook_page_data = b''
    setup_call = 0xd000

    def __init__(self):
        hooks = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in hooks['syms'].items()}
        self.code = bytes.fromhex(hooks['rom'])
        self.setup = bytes.fromhex(hooks['setup'])
        end = self.syms['rom_end']
        self.altrom = (ROM_ORG, end + 20)
        self.slot1 = (24, end)
        self.sites = []
        for a, (label, old, _) in SITES.items():
            old = bytes.fromhex(old)
            op = 0xcd if a == OVER else 0xc3
            self.sites.append((a, old, bytes([op]) + zt.w16(self.syms[label]) + bytes(len(old) - 3)))

    def apply(self, snap, cmap=None):
        if snap.is128:
            raise ValueError('Build from the 48K title snapshot')
        prefix = bytes.fromhex('dd7e00e60787327a8932e28932578add7e026f260029292929291100c019')
        if snap.banks[2][0x934:0x952] != prefix:
            raise ValueError('Unexpected plotter setup at 8934')
        b = bytearray(snap.banks[2])
        for a, old, new in self.sites:
            i = a - 0x8000
            if b[i:i + len(old)] != old:
                raise ValueError('Unexpected original bytes at %04X' % a)
            b[i:i + len(old)] = new
        if snap.read(38302) != 0x35 or snap.read(38352) != 0x35:
            # both DEC (HL) on the life counter, as on the clean covertape (a poked copy has NOP at 38302)
            raise ValueError('Unexpected life-counter instruction (build from the clean TOSEC snapshot)')
        snap.banks[2] = bytes(b)
        self.raw = {}
        self.patterns = {}
        assets = {}
        mapping = bytearray(256)
        sources = bytearray()
        for frame in range(192):
            raw = bytes(snap.banks[0][frame * 32:frame * 32 + 32])
            if raw not in assets:
                pattern = len(assets)
                if pattern >= 124:
                    raise ValueError('Figure bank exceeds the 124 resident patterns')
                assets[raw] = pattern
                sources.extend((pattern, frame))
                self.raw[pattern] = raw
                self.patterns[pattern] = art(raw)
            mapping[frame] = assets[raw]
        self.blank = assets[bytes(32)]
        mapping[192:] = bytes([self.blank]) * 64
        for tile in range(4):
            base = 0x1800 + (235 + tile) * 8
            raw = bytes(snap.banks[0][base:base + 8])
            sources.extend((124 + tile, 192 + tile))
            self.raw[124 + tile] = raw
            self.patterns[124 + tile] = art(raw)
        self.mapping = bytes(mapping)
        page = bytearray(rom48()[0x2000:])
        page[ROM_ORG - 0x2000:self.syms['rom_end'] - 0x2000] = self.code
        offset = self.syms['frames'] - 0x2000
        page[offset:offset + 256] = mapping
        self.page = bytes(page)
        self.extra_banks = {12: self.page + bytes(8192)}
        self.stub_extra = self.setup + sources + b'\xff'
        self.default_setup = self.stub_extra
        self.edited = {}
        if cmap is None:
            cmap = cs.load(rc.build_colours_path(PROFILE.with_name('moley_christmas_colours.json')))
        if cmap:
            apply_colours(self, cmap)


@lru_cache(maxsize=256)
def art(raw):
    """Independent host oracle: exterior is four-connected to an edge, holes are black."""
    pixels = bytearray([2] * 256)
    rows = len(raw) // 2 if len(raw) == 32 else 8
    for y in range(rows):
        word = raw[y] << 8 | (raw[y + 16] if rows == 16 else 0)
        for x in range(16):
            if word & (0x8000 >> x):
                pixels[16 * y + x] = 1
    edge = deque(i for i in range(256) if i % 16 in (0, 15) or i // 16 in (0, 15))
    while edge:
        i = edge.popleft()
        if pixels[i] != 2:
            continue
        pixels[i] = 0
        for j in (i - 16, i + 16, i - 1, i + 1):
            if 0 <= j < 256 and abs(i % 16 - j % 16) <= 1 and pixels[j] == 2:
                edge.append(j)
    return bytes((a << 4) | b for a, b in zip(pixels[::2], pixels[1::2]))


def boot_patterns(path, z80, patch):
    """Observe the real setup's pattern ports and NextRegs, including dirty sprite RAM."""
    from unittest.mock import patch as replace
    ns = monty.NextState()
    ns.pat[:] = bytes([0xab]) * len(ns.pat)
    for attr in ns.attr:
        attr[3] = 0x80
    class Ports(nextboot.NextPorts):
        def write_port(self, regs, port, value, *args):
            ns.port(port, value)
            super().write_port(regs, port, value, *args)
    with replace.object(nextboot, 'NextPorts', Ports):
        st = nextboot.boot(path, zt.Z80Snapshot(z80).pc, nexload=True)
    selected, index, palette = 0, 0, {}
    for reg, val in st['nrlog']:
        ns.nextreg(reg, val)
        if reg == 0x43:
            selected = val
        elif reg == 0x40:
            index = val
        elif reg == 0x41 and selected & 0x70 == 0x20:
            palette[index] = val
            index = (index + 1) & 255
    if patch.edited:
        expected_colours = dict(enumerate(patch.stub_extra[-256:]))
    else:
        expected_colours = {16 * i + n: c for i, ink in enumerate(SPECTRUM)
                            for n, c in ((1, ink), (2, 0))}
    if any(palette.get(i) != val for i, val in expected_colours.items()):
        raise ValueError('Sprite palette differs from its source colours')
    if any(ns.visible(i) for i in range(128)):
        raise ValueError('Dirty sprite left visible at boot')
    for index, expected in patch.patterns.items():
        if ns.pat[128 * index:128 * (index + 1)] != expected:
            raise ValueError('Boot pattern %d differs from source art' % index)
    return bytes(ns.pat)


def build(z80, out, name, say):
    patch = Patch()
    ok = True
    for suffix, p in [('', None), ('_sprites', patch)]:
        path = Path(out) / (name + suffix + '.nex')
        _, addr, tail, _ = zt.convert(z80, str(path), patch=p, quiet=True)
        bad = nextboot.check(str(path), z80, p, (addr, addr + len(tail)))
        say('%-10s: %s  %s  boot %s' % ('Sprites' if p else 'Plain', path.name,
                                         hashlib.md5(path.read_bytes()).hexdigest(), bad or 'OK'))
        ok &= not bad
    patch.resident = boot_patterns(str(path), z80, patch)
    say('Patterns  : %d preloaded patterns match, 128 dirty slots hidden' % len(patch.patterns))
    screen = Path(z80).with_name('moley_loading.scr')
    if screen.exists():
        from .booty import loading_nex
        scr = screen.read_bytes()
        if hashlib.md5(scr).hexdigest() != 'b4b6127c7c6a9bdf8a57ad81ff5d686d':
            raise ValueError('Unexpected tape loading screen')
        loaded = path.with_name(name + '_sprites_loading.nex')
        loaded.write_bytes(loading_nex(path.read_bytes(), scr))
        say('Loading   : original tape display, 6912 bytes')
    return ok, patch


def expected_sprite(pc, get, regs, patch):
    ix = regs[8] * 256 + regs[9]
    if pc == FIG:
        index = 8 + (ix - FIGURES) // 4
        frame = get(ix + 2)
        raw = bytes(get(GFX + frame * 32 + i) for i in range(32))
        flags = 0xf0 | (0 if get(ix + 3) & 128 else 8)
        pattern = patch.mapping[frame]
    else:
        index = (ix - ITEMS) // 4
        ptr = get(ix + 2) + 256 * get(ix + 3)
        cell = ptr - 0x5800
        base = get(0x8103) + get(0x8104) * 256
        tile = get(base + cell)
        start = 0xd800 + (tile - 1) * 8
        raw = bytes(get(start + i) for i in range(8))
        pattern = 124 + tile - 236
        flags = ((regs[0] if pc == CYCLE else get(ptr)) & 7) << 4
    x, y = get(ix) + 32, get(ix + 1) + 32
    attr = [x & 255, y & 255, flags | (x >> 8), 0xc0 | pattern // 2,
            0x80 | ((pattern & 1) << 6) | (y >> 8)]
    return index, attr, patch.edited.get(pattern, art(raw))


def event(patch, pc, get, regs, ns, speed=0):
    """Compare up to the first untouched instruction. Both sides then run identical game code."""
    from .dizzy6 import _rw_simulator
    simclass = _rw_simulator()
    orig = monty._Ov(get)
    mod = monty._OvP(get, patch.alt, patch.sitebytes)
    end = SITES[pc][2]
    problems = []
    a = simpool.machine(simclass, orig, list(regs), 'mc-o')
    if not monty._run(a, end, limit=96):
        return ['original resume'], 0
    b = simpool.machine(simclass, mod, list(regs), 'mc-p')
    z80n.install(b, ns.nextreg)
    b.set_tracer(monty._Ports(ns=ns))
    ns.nr[7] = speed
    before = [row[:] for row in ns.attr]
    entry_sp = regs[12]
    for _ in range(240):
        r = b.registers
        if r[24] == end:
            break
        # IX advances in the two original INC IXs; IY, I, IFF and stack
        # headroom must stay valid even inside a hook, not just at return.
        if ((r[8:10] != regs[8:10] and pc != INIT) or r[10:12] != regs[10:12]
                or r[14] != regs[14] or r[26] != regs[26]
                or not 0x5c00 + 192 + 42 <= r[12] <= entry_sp):
            problems.append('interrupt context')
            break
        b.opcodes[b.memory[r[24]]]()
    if b.registers[24] != end:
        problems.append('patched resume')
    for i in CMP:
        if a.registers[i] != b.registers[i]:
            problems.append('register %d (%d vs %d)' % (i, a.registers[i], b.registers[i]))
    if mod.romw or ns.nr[7] != speed or ns.ports:
        problems.append('ROM, speed or ports')
    for addr in set(orig.ov) | set(mod.ov):
        if entry_sp - 16 <= addr < a.registers[12]:
            continue                # dead pushes only, never the live return address
        if orig.ov.get(addr, get(addr)) != mod.ov.get(addr, get(addr)):
            problems.append('RAM %04x' % addr)
    if pc in (FIG, INIT, CYCLE):
        i, row, pixels = expected_sprite(pc, get, regs, patch)
        before[i] = row
        attr = ns.attr[i]
        offset = 256 * (attr[3] & 63) + 128 * bool(attr[4] & 64)
        if patch.resident[offset:offset + 128] != pixels:
            problems.append('sprite pixels')
    elif pc == TAKE:
        before[(regs[8] * 256 + regs[9] - ITEMS) // 4][3] = 0
    else:
        for row in before[:16]:
            row[3] = 0
    if ns.attr != before:
        problems.append('sprite attributes')
    return problems, b.registers[25] - a.registers[25]


def original_plot(get, regs):
    """Predict every written back-buffer byte from its value before the original CALL."""
    ix = 256 * regs[8] + regs[9]
    x, y, frame, flags = [get(ix + i) for i in range(4)]
    src = GFX + frame * 32
    plain = get(0x8107) == 5
    writes = {}
    for j in range(16):
        left, right = get(src + j), get(src + 16 + j)
        if not flags & 128:
            left, right = REVERSE[right], REVERSE[left]
        bits = ((left << 8) | right) << (8 - x % 8)
        sy = (y & 127) + j
        addr = 0xe000 + ((sy & 0xc0) << 5) + ((sy & 7) << 8) + ((sy & 56) << 2) + x // 8
        for dx, shift in enumerate((16, 8, 0)):
            target = (addr & 0xff00) | ((addr + dx) & 255)
            old = get(target)
            mask = 255 if plain else get(0xff00 + old)
            writes[target] = old | ((bits >> shift) & mask & 255)
    return writes


REVERSE = bytes(int(f'{i:08b}'[::-1], 2) for i in range(256))


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    c, examples, states = Counter(), [], {}
    ns = monty.NextState()
    pending = {}
    interior = {addr + i for addr, old, _ in patch.sites for i in range(1, len(old))}
    expected_interior = set()
    initialized = set()
    def hit(pc, sim):
        nonlocal pending
        m, regs = sim.memory, sim.registers
        if pc in interior:
            if pc not in expected_interior:
                c['interior entry!'] += 1
            expected_interior.discard(pc)
            return
        if pc == 0x888e:
            if pending:
                c['original plot bytes'] += len(pending)
                if any(m[a] != v for a, v in pending.items()):
                    c['original plot bytes!'] += 1
                pending = {}
            return
        if pc in (0x8627, 0x8659):
            expected_interior.add(0x8629 if pc == INIT else 0x865a)
        if pc in (INIT, CYCLE):
            slot, row, _ = expected_sprite(pc, m.__getitem__, regs, patch)
            if pc == CYCLE and slot not in initialized:
                # A death branch can start after a pickup was placed. Seed
                # only its entry state, once, with the previous cell colour.
                if c['room'] or c['clear']:
                    c['pickup missing init!'] += 1
                row[2] = (row[2] & 1) | ((m[regs[6] * 256 + regs[7]] & 7) << 4)
                ns.attr[slot] = row
            initialized.add(slot)
        if pc in (CLEAR, ROOM, OVER):
            initialized.clear()
        failures, extra = event(patch, pc, m.__getitem__, list(regs), ns)
        c[SITES[pc][0]] += 1
        c['max extra T ' + SITES[pc][0]] = max(extra, c['max extra T ' + SITES[pc][0]])
        if pc == FIG:
            pending = original_plot(m.__getitem__, regs)
        if failures:
            c['differential!'] += 1
            if len(examples) < 5:
                examples.append((hex(pc), failures[:4]))
        if collect and pc not in states:
            states[pc] = (bytes(m[i] for i in range(65536)), list(regs))
    c['frames'], desync = rzx.trace(str(rzx_path), set(SITES) | interior | {0x888e}, hit, stop=stop)
    if desync:
        c['desync!'] += 1
        examples.append(desync)
    if not c['figure'] or not c['original plot bytes']:
        c['no completed figure!'] += 1
    return c, examples, states


def unit_tests(patch, states):
    counts = Counter()
    def check(pc, mem, regs, speed=0):
        ns = monty.NextState()
        for row in ns.attr:
            row[3] = 0x80
        if pc == CYCLE:
            slot, row, _ = expected_sprite(pc, mem.__getitem__, regs, patch)
            row[2] ^= 16
            ns.attr[slot] = row
        problems, _ = event(patch, pc, mem.__getitem__, regs, ns, speed)
        counts['cases'] += 1
        if problems:
            counts['unit!'] += 1
    for pc, (mem, r) in states.items():
        for speed in hooklib.CLOCKS:
            check(pc, mem, r, speed)
    if FIG not in states:
        counts['missing figure!'] += 1
        return counts
    mem, r = states[FIG]
    for frame in range(192):
        for x, y in [(0, 0), (1, 7), (7, 65), (240, 127)]:
            for mirror in (0, 128):
                m = bytearray(mem)
                ix = FIGURES + (frame % 8) * 4
                r = list(r)
                r[8], r[9] = divmod(ix, 256)
                m[ix:ix + 4] = bytes((x, y, frame, mirror))
                check(FIG, m, r)
    # Mutate the actual executable or lookup table, leaving the oracle alone.
    import copy
    for pc, (mem, r) in states.items():
        q = copy.copy(patch)
        q.sitebytes = dict(patch.sitebytes)
        a, old, _ = next(s for s in patch.sites if s[0] == pc)
        q.sitebytes.update({a + i: v for i, v in enumerate(old)})
        ns = monty.NextState()
        for row in ns.attr:
            row[3] = 0x80
        failures, _ = event(q, pc, mem.__getitem__, r, ns)
        counts['negatives'] += 1
        if not failures:
            counts['missed negative!'] += 1
    mem, r = states[FIG]
    q = copy.copy(patch)
    q.alt = bytearray(patch.alt)
    f = mem[r[8] * 256 + r[9] + 2]
    q.alt[patch.syms['frames'] + f] ^= 1
    failures, _ = event(q, FIG, mem.__getitem__, r, monty.NextState())
    counts['negatives'] += 1
    if not failures:
        counts['missed negative!'] += 1
    # Detect a transient IY change even when the hook restores it by return,
    # and a one-M1 refresh error even when the pixels are still correct.
    for old, new in [(bytes.fromhex('3cfe10'), None), (bytes.fromhex('c62a'), bytes.fromhex('c62b'))]:
        q = copy.copy(patch)
        q.alt = bytearray(patch.alt)
        if new is None:
            # Replace two harmless register saves with INC IY. Its immediate
            # instruction-boundary check must fire before stack use differs.
            at = patch.syms['figure']
            q.alt[at:at + 2] = bytes.fromhex('fd23')
            reason = 'interrupt context'
        else:
            for at in range(patch.syms['figure'], patch.syms['place']):
                if patch.alt[at:at + 2] == old:
                    q.alt[at:at + 2] = new
            reason = 'register 15'
        failures, _ = event(q, FIG, mem.__getitem__, r, monty.NextState())
        counts['negatives'] += 1
        if not any(reason in msg for msg in failures):
            counts['missed negative!'] += 1
    return counts


def auto(a, z80, name, out, say):
    say('Game      : Moley Christmas')
    say('Engine    : moley_christmas')
    if not getattr(a, 'publisher', None):
        a.publisher = 'Gremlin Graphics / Your Sinclair'
    if not getattr(a, 'pok', None):
        trainer = Path(out) / (name + '_checked.pok')
        trainer.write_text('NInfinite Lives\nM 8 38302 0 53\nZ 8 38352 0 53\nY\n')
        a.pok = str(trainer)
    ok, patch = build(z80, out, name, say)
    patch.alt = nextboot.alt_image(patch)
    patch.sitebytes = {addr + i: b for addr, _, data in patch.sites for i, b in enumerate(data)}
    states = {}
    for rec in a.rzx or []:
        c, errors, got = verify(patch, rec, stop=a.quick, collect=1)
        states.update(got)
        failed = {k: v for k, v in c.items() if k.endswith('!')}
        say('Verify    : %s, %d frames, %d figure plots, %d original back-buffer bytes -> %s' %
            (Path(rec).name, c['frames'], c['figure'], c['original plot bytes'], failed or 'IDENTICAL'))
        say('            %s' % dict(c))
        if errors:
            say('            %s' % errors)
        ok &= not failed
    if a.rzx:
        if OVER not in states and CLEAR in states:
            # Unreached game-over CALL: its real instruction and code under
            # live stack/IRQ conditions, including a screen full of sprites.
            mem, regs = states[CLEAR]
            regs = list(regs)
            regs[24] = OVER
            states[OVER] = (mem, regs)
        units = unit_tests(patch, states)
        say('Unit      : %s' % dict(units))
        ok &= not any(k.endswith('!') for k in units)
    say('Result    : %s' % ('PASSED' if ok else 'FAILED'))
    return ok

SPECTRUM = bytes.fromhex('0002a0a21416b4b60003e0e31c1ffcff')
RECOLOUR = dict(game='moley_christmas', output='sprites',
                colours='docs/profiles/moley_christmas_colours.json', clear=True,
                note='Resident pattern, source row and half. Pickup ink cycles unless painted.')


def colour_identity(peek):
    raw = bytes(peek(a) for a in range(0xc000, 0xd800))
    tiles = bytes(peek(a) for a in range(0xdf58, 0xdf78))
    return dict(schema=1, game='moley_christmas', engine='moley_christmas',
                keys='pattern:row:half, pickup phase suffix v1', geometry=None,
                inputs={'graphics': hashlib.md5(raw + tiles).hexdigest()})


def sheet_part(pattern, raw, group, phase=None):
    size = 16 if len(raw) == 32 else 8
    encoded = art(raw)
    pixels, entries = [], {}
    for y in range(size):
        for x in range(size):
            key = '%d:%d:%d' % (pattern, y, x // 8)
            if phase is not None:
                key += ':%d' % phase
            entries[key] = [raw[y + 16 * (x // 8)], size]
            value = encoded[y * 8 + x // 2]
            code = value & 15 if x % 2 else value >> 4
            ink = 15 if phase is None else phase or 8
            pixels.append((x, y, key, x % 8, code, (0, ink, 8)[code]))
    return dict(id=(pattern, phase), size=size, w=size, h=size, x=0, y=0, mir=0,
                group=group, pixels=pixels, entries=entries)


def write_sheets(snapshot, recordings, directory):
    patch = Patch()
    snap = zt.Z80Snapshot(str(snapshot))
    patch.apply(snap, {})
    seen = {}
    def hit(pc, sim):
        mem, regs = sim.memory, sim.registers
        ix = regs[8] * 256 + regs[9]
        if pc == FIG:
            pattern = patch.mapping[mem[ix + 2]]
            group = 'PLAYER' if ix == FIGURES else 'ROOM%d' % (1 + mem[0x8107])
            phase = None
        else:
            ptr = mem[ix + 2] + 256 * mem[ix + 3]
            base = mem[0x8103] + 256 * mem[0x8104]
            pattern = 124 + mem[base + ptr - 0x5800] - 236
            phase = (regs[0] if pc == CYCLE else mem[ptr]) & 7
            group = 'PICKUPS'
        if pattern != patch.blank:
            seen.setdefault((group, pattern, phase), None)
    for path in recordings:
        frames, desync = rzx.trace(str(path), {FIG, INIT, CYCLE}, hit)
        if desync or not frames:
            raise ValueError('Incomplete sheet recording %s: %s' % (path, desync))
    groups = {}
    for group, pattern, phase in sorted(seen):
        collector = groups.setdefault(group, cs.Collector())
        collector.add_frame([sheet_part(pattern, patch.raw[pattern], group, phase)])
    identity = colour_identity(snap.read)
    cmap = cs.load(rc.build_colours_path(PROFILE.with_name('moley_christmas_colours.json')))
    for group, collector in groups.items():
        for suffix, comps in [('PAINTING_SPRITES', collector.composites()),
                              ('REFERENCE_ALL_SPRITES', list(collector.comps.values()))]:
            prefix = Path(directory) / ('Moley_Christmas_' + group + '_' + suffix)
            cs.write(comps, str(prefix) + '.png', str(prefix) + '_layout.json', cs.palette_rgb(SPECTRUM),
                     cmap, paint_clear=True, identity=identity)
    return {group: len(c.comps) for group, c in groups.items()}


def paint_pixel(part, pixel, cmap, used):
    x, y, key, bit, code, default = pixel
    if key not in cmap:
        return default
    row = cmap[key]
    if list(row[:2]) != part['entries'][key] or len(row[2]) != 8:
        raise ValueError('Wrong source byte for ' + key)
    used.add(key)
    if len(row) > 3 and row[3] & (128 >> bit):
        return 0
    colour = row[2][bit] or default
    if not 0 <= colour < 16:
        raise ValueError('Colour outside the Spectrum palette for ' + key)
    return colour


def apply_colours(patch, cmap):
    # Each pickup pixel occupies the same pattern nibble through its eight
    # colour phases. Share a nibble when the eight displayed colours match.
    pal = bytearray(256)
    pal[240:] = SPECTRUM
    vectors = {}
    used = set()
    data = bytearray(16384)
    for pattern, raw in patch.raw.items():
        phases = range(8) if pattern >= 124 else [None]
        parts = [sheet_part(pattern, raw, None, phase) for phase in phases]
        packed = bytearray(128)
        for pixels in zip(*(part['pixels'] for part in parts)):
            x, y = pixels[0][:2]
            shades = tuple(paint_pixel(part, px, cmap, used) for part, px in zip(parts, pixels))
            nibble = shades[0]
            if len(shades) == 8 and any(shades):
                if 0 in shades:
                    raise ValueError('A pickup pixel must share transparency across all eight phases')
                if shades not in vectors:
                    index = len(vectors) + 1
                    if index > 15:
                        raise ValueError('Pickup painting needs more than 15 distinct eight-phase colours')
                    vectors[shades] = index
                    for phase, shade in enumerate(shades):
                        pal[phase * 16 + index] = SPECTRUM[shade]
                nibble = vectors[shades]
            packed[y * 8 + x // 2] |= nibble << (0 if x % 2 else 4)
        patch.edited[pattern] = bytes(packed)
        data[pattern * 128:(pattern + 1) * 128] = packed
    if used != set(cmap):
        raise ValueError('Unknown paint keys: %s' % sorted(set(cmap) - used))
    patch.patterns.update(patch.edited)
    patch.extra_banks[13] = bytes(data)
    at = patch.syms['enable'] - patch.setup_call
    dest = patch.syms['painted']
    code = bytearray(patch.default_setup)
    code[at:at + 3] = b'\xc3' + zt.w16(dest)
    patch.stub_extra = code.ljust(dest - patch.setup_call, b'\0') + bytes.fromhex(load_profile()['hooks']['paint']) + pal


def recolour(nex, cmap):
    from types import SimpleNamespace
    banks = rc.banks(nex)
    if set(banks) - {13} != {0, 2, 5, 10, 12, 47}:
        raise ValueError('Expected the Moley Christmas sprite build')
    peek = rc.nex_peek(nex)
    if colour_identity(peek)['inputs']['graphics'] != '792f461935cd79bae6e3ad79f9c48032':
        raise ValueError('Unexpected Moley graphics')
    p = Patch()
    original = bytearray(banks[2])
    for addr, old, new in p.sites:
        off = addr - 0x8000
        if original[off:off + len(new)] != new:
            raise ValueError('Missing Moley hook at %04x' % addr)
        original[off:off + len(old)] = old
    snap = SimpleNamespace(is128=False, banks={0: banks[0], 2: bytes(original)}, read=peek)
    p.apply(snap, cmap)
    if banks[12] != p.extra_banks[12]:
        raise ValueError('Unrecognised figure table or hooks')
    stub = bytearray(banks[10])
    start = 0x1000
    expected = bytearray(p.default_setup)
    if 13 in banks:
        off = p.syms['enable'] - p.setup_call
        expected[off:off + 3] = b'\xc3' + zt.w16(p.syms['painted'])
    if stub[start:start + len(expected)] != expected:
        raise ValueError('Unrecognised Moley setup')
    optional = p.syms['painted'] - 0xc000
    routine = bytes.fromhex(load_profile()['hooks']['paint'])
    if 13 in banks and stub[optional:optional + len(routine)] != routine:
        raise ValueError('Unrecognised painted setup')
    end = optional + len(routine) + 256
    if 13 not in banks and any(stub[start + len(expected):end]):
        raise ValueError('Paint storage already in use')
    stub[start:end] = p.stub_extra.ljust(end - start, b'\0')
    before = dict(banks)
    banks[10] = bytes(stub)
    banks.pop(13, None)
    if cmap:
        banks[13] = p.extra_banks[13]
    header = bytearray(nex[:512])
    header[9], header[18 + 13] = len(banks), int(bool(cmap))
    changed = [b for b in sorted(before.keys() | banks.keys()) if before.get(b) != banks.get(b)]
    return bytes(header) + b''.join(banks[b] for b in zt.BANK_FILE_ORDER if b in banks), {'banks changed': changed}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Capture Moley Christmas colour sheets')
    parser.add_argument('snapshot')
    parser.add_argument('recordings', nargs='+')
    parser.add_argument('-o', '--out', required=True)
    args = parser.parse_args()
    print(write_sheets(args.snapshot, args.recordings, args.out))
