"""Wanted! Monty Mole (1984). Sprite overlay on the original bitmap and attributes."""
from array import array
from collections import Counter
import hashlib
import json
from pathlib import Path

from . import hooklib, nextboot, z80tonex as zt

RECORD = 'wanted_monty_mole'
ROM = 0x386E
SITES = {
    0x8f9f: ('f5c5d5', 'irq_mine'),
    0xcdef: ('f5c5d5', 'irq_outside'),
    0x9048: ('fde1dde1', 'irq_end_mine'),
    0xce0f: ('fde1dde1', 'irq_end_outside'),
    0xEC29: ('0603eb', 'e_pixels'),
    0xEC41: ('3adfec', 'e_end'),
    0xEC90: ('c521e4ec', 'e_right'),
    0xECCA: ('c52113ed', 'e_left'),
    0xEC15: ('11e4ec', 'e_plot'),
    0x8456: ('1160ea', 'e_erase_start'),
    0x9630: ('fd2137c5', 'e_pickup_start'),
    0x8477: ('772313', 'e_rows'),
    0x847d: ('772313', 'e_rows'),
    0x8483: ('772a9984', 'e_last_row'),
    0xC62A: ('2154cf', 'e_clear'),
    0x9092: ('cda390', 'e_floor'),
    0x90A8: ('0d0603', 'e_strip'),
    0xCAD1: ('210040', 'e_title'),
    0xF818: ('210040', 'e_title'),
    0xF804: ('210040', 'e_title'),
    0x8E2C: ('fd2127c5', 'e_crusher'),
    0x963b: ('121424', 'e_coal'),
}
SHIFT_END = {0xec90: 0xeca1, 0xecca: 0xecdb}
HOOK_END = {0xec29: 0xec36, **SHIFT_END}


INTERIORS = {a + i for a, (old, _) in SITES.items() for i in range(1, len(bytes.fromhex(old)))}
CMP = hooklib.CMP                         # no LD A,R in this release's RAM


def _profile_path():
    return Path(__file__).resolve().parents[1] / 'docs' / 'profiles' / (RECORD + '.json')


def load_profile():
    return json.loads(_profile_path().read_text())


def is_wanted_monty_mole(snap):
    sig = load_profile()['signature']
    a, data = sig['addr'], bytes.fromhex(sig['bytes'])
    return snap.machine == '48K' and bytes(snap.memory[a:a + len(data)]) == data


class Patch:
    name = 'Wanted! Monty Mole hardware sprites'
    keep_printer_buffer = uses_printer_buffer = True
    ram_slot1_after_alt = True
    setup_call = 0xD000
    hook_page_data = b''

    def __init__(self):
        h = load_profile()['hooks']
        self.syms = {k: int(v, 16) for k, v in h['syms'].items()}
        self.altrom = ROM, self.syms['rom_end'] + 20
        self.slot1 = 24, self.syms['rom_end']
        page = bytearray(zt.rom48()[8192:])
        code = bytes.fromhex(h['rom'])
        if ROM + len(code) != self.slot1[1] or any(b != 255 for b in zt.rom48()[ROM:self.altrom[1]]):
            raise ValueError('hook exceeds the unused ROM range')
        page[ROM-0x2000:self.slot1[1]-0x2000] = code
        self.page = bytes(page)
        self.stub_extra = bytes.fromhex(h['setup'])
        self.extra_banks = {12: self.page + bytes(8192), 13: bytes.fromhex(h['page']).ljust(16384, b'\0'),
                            14: bytes(16384), 15: bytes(16384), 16: bytes(16384)}
        # One 1K table per ink, four planes indexed by the game's source byte.
        self.extra_banks[17] = bytes(
            ink * (16 * ((bits >> (7-2*pair)) & 1) + ((bits >> (6-2*pair)) & 1))
            for ink in range(16) for pair in range(4) for bits in range(256))
        self.sites = []
        for a, (old, sym) in SITES.items():
            original = bytes.fromhex(old)
            self.sites.append((a, original, ((b'\xcd' if sym in ('e_title', 'e_floor', 'e_rows') else b'\xc3') + self.syms[sym].to_bytes(2, 'little')).ljust(len(original), b'\0')))

    def apply(self, snap):
        if snap.is128:
            raise ValueError('expected a 48K snapshot')
        ram = bytearray(snap.banks[5] + snap.banks[2] + snap.banks[0])
        for a, original, replacement in self.sites:
            i = a - 0x4000
            if ram[i:i+len(original)] != original:
                raise ValueError('unexpected game code at %04X' % a)
            ram[i:i+len(original)] = replacement
        for i, bank in enumerate((5, 2, 0)):
            snap.banks[bank] = bytes(ram[i*16384:(i+1)*16384])


def word(mem, a):
    return mem[a] | mem[(a+1) & 65535] << 8


def build(z80, out, name, say=print):
    patch = Patch()
    ok = True
    for label, suffix, pt in [('Plain', '', None), ('Sprites', '_sprites', patch)]:
        path = Path(out) / (name + suffix + '.nex')
        _, addr, tail, _ = zt.convert(z80, str(path), None, True, quiet=True, patch=pt, keep_printer_buffer=True)
        path.write_bytes(zt.automap_off(path.read_bytes()))
        failures = nextboot.check(str(path), z80, pt, (addr, addr+len(tail)), nexload=True)
        failures += nextboot.automap_check(str(path))
        say('%-10s: %s %s; NEXLOAD boot %s, tail %04X+%d' % (
            label, path.name, hashlib.md5(path.read_bytes()).hexdigest(), failures or 'OK', addr, len(tail)))
        ok &= not failures
    return ok, patch


class Hardware:
    """Real hook instructions write ports and NextRegs. Keep their RAM across replay events."""
    def __init__(self, patch):
        from skoolkit import CSimulator
        from skoolkit.simulator import Simulator
        from . import z80n, simpool
        self.patch = patch
        self.native = CSimulator(bytearray(65536), {}) if CSimulator else None
        self.mem = self.native.memory if self.native else bytearray(65536)
        self.sim = simpool.machine(Simulator, self.mem, slot='wanted')
        self.sim.set_tracer(self)
        if self.native:
            self.native.set_tracer(self)
        z80n.install(self.sim, self.nextreg)
        self.alt = nextboot.rom_view(patch)
        self.cursor = patch.syms['last_src']
        self.pages = {bank*2+i: bytearray(data[i*8192:(i+1)*8192])
                      for bank, data in patch.extra_banks.items() for i in range(2)}
        self.default = {0: 255, 2: 10, 3: 11, 4: 4, 5: 5, 6: 0}
        self.mapping = self.default.copy()
        self.attrs = [bytearray(5) for _ in range(128)]
        self.pattern = bytearray(16384)
        self.speed = self.select = self.slot = self.pointer = 0
        self.changed = set()
        self.base_ticks = 0
        self.last_t = 0
        self.fast = {patch.syms[a]: patch.syms[b] for a, b in
                     [('rectangle', 'flush'), ('upload_bytes', 'upload_done')]}

    def nextreg(self, reg, v):
        if reg == 0x50 or 0x52 <= reg <= 0x56:
            slot = reg - 0x50
            section = slice(slot*8192, (slot+1)*8192)
            if self.mapping[slot] == self.default[slot]:
                self.backup[slot] = self.mem[section]
            else:
                self.pages[self.mapping[slot]][:] = self.mem[section]
            self.mapping[slot] = v
            self.mem[section] = (self.backup[slot] if v == self.default[slot] else self.pages[v])
        elif reg == 7:
            self.clock()
            self.speed = v
        elif reg == 0x34:
            self.slot = v & 127
        elif 0x35 <= reg <= 0x39:
            self.attrs[self.slot][reg-0x35] = v
            self.changed.add(self.slot)
        else:
            raise ValueError('unexpected NextReg %02x' % reg)

    def clock(self):
        t = self.sim.registers[25]
        self.base_ticks += (t - self.last_t) / (1 << self.speed)
        self.last_t = t

    def read_port(self, regs, port):
        if port != 0x253b or self.select != 7:
            raise ValueError('unexpected IN %04x' % port)
        return self.speed

    def write_port(self, regs, port, value, *args):
        if port == 0x243b:
            self.select = value
        elif port == 0x303b:
            self.uploads += 1
            self.pointer = (value & 63)*256 + (value >> 7)*128
        elif port & 255 == 0x5b:
            self.pattern[self.pointer] = value
            self.pointer = (self.pointer+1) & 16383
        else:
            raise ValueError('unexpected OUT %04x' % port)

    def step(self):
        r = self.sim.registers
        pc = r[24]
        if self.native and pc in self.fast:
            self.native.registers[:] = array(self.native.registers.typecode, r)
            self.native.run(pc, self.fast[pc])
            r[:] = self.native.registers
        else:
            # SkoolKit models the bottom 16K as ROM. MMU1 on this build
            # is RAM. Honour the real store operand and source registers.
            opcode = self.mem[pc]
            if opcode in (0x22, 0x32) or (opcode == 0xed and self.mem[pc+1] in (0x43, 0x53)):
                dest = word(self.mem, pc+(2 if opcode == 0xed else 1))
                if self.cursor <= dest < self.patch.syms['rom_end']:
                    if opcode == 0x32:
                        self.mem[dest] = r[0]
                    else:
                        hi = 6 if opcode == 0x22 else (2 if self.mem[pc+1] == 0x43 else 4)
                        self.mem[dest:dest+2] = bytes((r[hi+1], r[hi]))
                        if opcode == 0xed and dest == self.cursor:
                            self.publications.append(word(self.mem, dest))
            self.sim.opcodes[opcode]()

    def event(self, addr, orig, regs, observe=None):
        self.publications = []
        self.backup = {}
        self.uploads = 0
        self.mem[:] = orig
        self.mem[:16384] = self.alt
        for a, old, new in self.patch.sites:
            self.mem[a:a+len(old)] = new
        self.changed.clear()
        self.base_ticks = self.last_t = 0
        r = self.sim.registers
        r[:] = regs
        r[25] = 0
        end = HOOK_END.get(addr, addr + len(bytes.fromhex(SITES[addr][0])))
        steps = 0
        while r[24] != end:
            if observe:
                observe(self, r[24])
            self.step()
            steps += 1
            if steps > 250000:
                raise ValueError('hook %04X ran away at %04X' % (addr, r[24]))
        self.alt[self.cursor:self.patch.syms['rom_end']] = self.mem[self.cursor:self.patch.syms['rom_end']]
        self.clock()
        return self.base_ticks

    def tile(self, slot):
        x, y, hi, pattern, mode = self.attrs[slot]
        if not pattern & 128:
            return None
        if not pattern & 64 or mode & 0xbf != 0x80 or hi & 0xfe:
            raise ValueError('unexpected sprite mode')
        x += 256*(hi & 1) - 32
        y -= 32
        if x % 16 or y % 16 or not (0 <= x < 256 and 0 <= y < 192):
            raise ValueError('invalid tile coordinates')
        p = 256*(pattern & 63) + 2*(mode & 64)
        return (x // 16, y // 16), self.pattern[p:p+128]


def screen_cell(address):
    a = address - 0x4000
    x = (a & 31) * 8
    y = ((a >> 5) & 0xc0) | ((a >> 2) & 0x38) | ((a >> 8) & 7)
    return (x // 16, y // 16), (y % 16)*8 + (x % 16)//2


class Oracle:
    """Assign ink from the original game's individual stores, independently of tile allocation."""
    def __init__(self):
        self.tiles = {}
        self.colour = 15
        self.packed = [[bytes((((n >> (7-j)) & 1)*16 + ((n >> (6-j)) & 1))*ink
                              for j in range(0, 8, 2)) for n in range(256)] for ink in range(16)]

    def write(self, addr, bits, ink):
        if 0x4000 <= addr < 0x5800:
            key, offset = screen_cell(addr)
            if bits or key in self.tiles:
                tile = self.tiles.setdefault(key, bytearray(128))
                tile[offset:offset+4] = self.packed[ink][bits]

    def check(self, hw, c, fail):
        actual = {}
        for slot in range(128):
            tile = hw.tile(slot)
            if tile:
                key, data = tile
                if key in actual:
                    fail('duplicate tile', key)
                actual[key] = data
        want = {key: data for key, data in self.tiles.items() if any(data)}
        if actual != want:
            diff = [k for k in actual.keys() | want.keys() if actual.get(k) != want.get(k)]
            fail('sprite layer differs', (len(diff), diff[:4]))
        c['layer checks'] += 1
        c['peak sprites'] = max(c['peak sprites'], len(actual))


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    from . import rzx, simpool
    from skoolkit.simulator import Simulator
    hw, oracle = Hardware(patch), Oracle()
    c, ex, states = Counter(), {}, {}
    # Row stores restore old scenery. Other writers can replace figure pixels before their next plot.
    stores = {0x90a6, 0x90b1, 0x90b5, 0xEC2E, 0x8477, 0x847D, 0x8483, 0x8E6C, 0x963B, 0xF82A}
    ends = {0xEC41, 0x848B, 0x8E76, 0x9642, 0xC640, 0x90bc}
    active = []
    in_update, idle, extra, transfer = False, 0, 0, 0

    def fail(kind, detail):
        c[kind+'!'] += 1
        ex.setdefault(kind, (hex(pc_now[0]), detail))
        if kind == 'sprite layer differs':
            c['layer failures at %04X' % pc_now[0]] += 1

    pc_now = [0]
    expected_interiors = Counter()
    room19_recording = hashlib.md5(Path(rzx_path).read_bytes()).hexdigest() == 'b000db958867bcd4b873b6cbc18701d1'
    row_samples = set()
    shifting = set()
    shift_costs = {}

    def hit(pc, sim):
        nonlocal in_update, idle, extra, transfer
        pc_now[0] = pc
        if pc == 0x943c:
            idle += 4
            return
        if pc == 0x943d:
            if in_update and idle:
                c['paced intervals'] += 1
                if extra > idle:
                    c['update exceeds HALT slack!'] += 1
                    c['worst deficit T'] = max(c['worst deficit T'], round(extra-idle))
                if extra-transfer > idle:
                    c['deficits even with free transfers'] += 1
            in_update, idle, extra, transfer = True, 0, 0, 0
            oracle.check(hw, c, fail)
            if room19_recording and sim.tracer.context.frame_count == 26433:
                # The original enemy at x=118 ends at x=133. The scenery pixel
                # immediately to its right was white before FC13 painted the cell.
                m = sim.memory
                if m[0x9649] != 19 or not m[0x43d0] & m[0xd630] & 2:
                    fail('room 19 witness input differs', m[0x9649])
                ink = m[0x58d0] & 7 | (m[0x58d0] >> 3 & 8)
                for slot in range(128):
                    tile = hw.tile(slot)
                    if tile and tile[0] == (8, 3):
                        ink = (tile[1][3*8+3] >> 4) or ink
                c['room 19 scenery checks'] += 1
                if ink != 15:
                    fail('scenery colour changed', (134, 51, 'expected 15', ink))
        m, r = sim.memory, sim.registers
        if pc in (0x8477, 0x847d, 0x963b):
            expected_interiors[pc+1] += 1
            expected_interiors[pc+2] += 1
        elif pc == 0x8483:
            expected_interiors[pc+1] += 1
        if pc in (0x8f9f, 0xcdef):
            expected_interiors[pc+1] += 1
            expected_interiors[pc+2] += 1
        elif pc in (0x9048, 0xce0f):
            expected_interiors[pc+2] += 1
        if pc in SHIFT_END:
            expected_interiors[pc+1] += 1
        if pc == 0xec29:
            expected_interiors[0xec2b] += 3  # the original 3-byte loop
        elif pc == 0x90a8:
            expected_interiors[0x90a9] += 1  # fall-through after DEC C
        if pc in INTERIORS:
            if expected_interiors[pc]:
                expected_interiors[pc] -= 1
            else:
                fail('unexpected interior entry', pc)
        if pc == 0x9254:
            addr = r[4]*256+r[5]
            c['point tests'] += 1
            c['figure dependent'] += bool((m[addr] ^ m[(addr+0x9260) & 65535]) & r[2])
        if pc == 0xec29:
            # A fixed-length path. Test complete rows against the original subroutine.
            # Original cost is input-independent. Reconcile the measured saving on every row.
            addr = r[6]*256+r[7]
            key = (addr & 255, m[addr], r[26]) if 0x4000 <= addr < 0x5800 else (addr,)
            if key in row_samples and 'row saving T' in c:
                extra -= c['row saving T']
                c['row calls'] += 1
                return
            row_samples.add(key)
        if pc in SHIFT_END.values():
            shifting.discard(pc)
        if pc in SHIFT_END:
            end = SHIFT_END[pc]
            if end in shifting:
                return
            shifting.add(end)
            shift_key = (pc, r[2])
            if shift_key in shift_costs:
                extra += shift_costs[shift_key]
                c['shift calls'] += 1
                return
        if pc in SITES:
            c[SITES[pc][1]] += 1
            orig = bytes(m)
            old, label = SITES[pc]
            if orig[pc:pc+len(bytes.fromhex(old))] != bytes.fromhex(old):
                fail('patch site overwritten', hex(pc))
            if collect and len(states.setdefault(pc, [])) < collect:
                states[pc].append((orig, list(r)))
            cursor_before = bytes(hw.alt[hw.cursor:hw.cursor+2])
            ticks = hw.event(pc, orig, list(r))
            if pc == 0xec29:
                dest = r[4]*256+r[5]+2
                if hw.publications != [dest-2, dest-1, dest]:
                    fail('shifted source cursor differs', dest)
                # The recorded ISR can split this row. Replay the three cursor
                # stores at their individual visible writes below.
                hw.alt[hw.cursor:hw.cursor+2] = cursor_before
            so = simpool.machine(Simulator, bytearray(orig), list(r), slot='wanted-original', copy=True)
            end = HOOK_END.get(pc, pc + len(bytes.fromhex(old)))
            while so.registers[24] != end:
                so.opcodes[so.memory[so.registers[24]]]()
            delta = ticks - (so.registers[25]-r[25])
            if ticks >= 69888 and hw.sim.registers[14] == 0xc7 and r[26]:
                fail('mapped hook exceeds interrupt period', (pc, ticks))
            if pc in SHIFT_END:
                shift_costs[shift_key] = delta
                c['shift calls'] += 1
            extra += delta
            transfer += hw.uploads*128*16/8
            c['pattern uploads'] += hw.uploads
            if pc == 0xec29:
                if 'row saving T' in c and c['row saving T'] != -delta:
                    fail('row cost differs', delta)
                c['row saving T'] = -delta
                c['row calls'] += 1
            if any(so.registers[i] != hw.sim.registers[i] for i in CMP):
                fail('registers differ', [(i, so.registers[i], hw.sim.registers[i]) for i in CMP
                                          if so.registers[i] != hw.sim.registers[i]])
            if hw.speed or hw.mapping != hw.default:
                fail('clock or MMU differs', hw.mapping)
            if hw.mem[0x4000:0x5b00] != so.memory[0x4000:0x5b00]:
                fail('ULA differs', pc)
            # Exclude guarded site bytes and the dead call stack below the restored SP.
            for a, old_bytes, _ in patch.sites:
                hw.mem[a:a+len(old_bytes)] = orig[a:a+len(old_bytes)]
            sp = r[12]
            depth = 10 if label in ('e_title', 'e_floor') else 8
            if label in ('irq_mine', 'irq_outside'):
                depth = 20  # saved interrupt pairs, queue dispatch and its private-stack switch
            elif label in ('e_coal', 'e_last_row', 'e_rows'):
                depth = 12
            live_sp = min(sp, so.registers[12])
            hw.mem[sp-depth:live_sp] = so.memory[sp-depth:live_sp]
            if hw.mem[0x4000:] != so.memory[0x4000:]:
                fail('live RAM differs', next(i for i in range(16384,65536) if hw.mem[i] != so.memory[i]))
            c['ULA checks'] += 1
            c['worst hook T'] = max(c['worst hook T'], round(ticks))
            c['total hook T'] += round(ticks)
            if pc == 0xec15:
                ret = word(m, sp)
                ix = r[8]*256+r[9]
                ink = (10 if m[0xece1] == 0x62 else 8) if m[0x9649] == 44 else 15
                if ret == 0x8843 and m[ix] == 0 and m[0x9649] != 44:
                    v = m[ix+9]
                    ink = (v & 7 | ((v >> 3) & 8)) if v & 7 else 8
                active.append(ink)
            if pc in (0xc62a, 0xf804, 0xf818, 0xcad1):
                oracle.tiles.clear()
        if pc in stores:
            if pc == 0xec2e:
                # e_pixels publishes BC (the shifted source pointer) immediately
                # after each raw ULA store. DE holds that pointer in the original.
                hw.alt[hw.cursor:hw.cursor+2] = bytes((r[5], r[4]))
                addr = r[6]*256+r[7]
                oracle.write(addr, r[0], active[-1] if active else 15)
                c['figure ink bits'] += r[0].bit_count()
            elif pc == 0x963b:
                addr = r[4]*256+r[5]
                attr = m[0x5800+((addr>>3)&0x300)+(addr&255)]
                bits = 0 if m[0xc537] == 255 else 255-r[0]
                oracle.write(addr, bits, ((attr>>3)&15) or 8)
            elif pc == 0x90a6:
                addr = r[6]*256+r[7]
                if 0x4000 <= addr < 0x5800:
                    key, offset = screen_cell(addr)
                    tile = oracle.tiles.get(key)
                    if tile is not None and m[0x90a4] == 0x2f:
                        mask = oracle.packed[15][255 ^ r[3]]
                        for j in range(4):
                            tile[offset+j] &= mask[j]
            elif pc in (0x90b1, 0x90b5):
                idx = 4 if pc == 0x90b5 else 6
                oracle.write(r[idx]*256+r[idx+1], 0, 0)
            elif pc in (0x8477, 0x847d, 0x8483):
                oracle.write(r[6]*256+r[7], 0, 0)
            elif pc == 0x8e6c:
                oracle.write(r[4]*256+r[5], r[0], 15)
            elif pc == 0xf82a and tuple(r[2:4]) == (0x1a,0xff):
                oracle.tiles.clear()
            c['original bitmap stores'] += 1
        if pc in ends:
            oracle.check(hw, c, fail)
        if pc == 0xec41 and active:
            active.pop()

    c['frames'], err = rzx.trace(str(rzx_path), SITES.keys() | set(SHIFT_END.values()) | stores | ends | INTERIORS | {0x9254, 0x943c, 0x943d}, hit, stop=stop)
    if err:
        fail('recording desync', err)
    return (c, ex, states) if collect else (c, ex)


def negative_patch(patch):
    """Drop the first OUTI in the upload. The slot then receives shifted, incomplete data."""
    import copy
    broken = copy.deepcopy(patch)
    page = bytearray(broken.extra_banks[13])
    i = patch.syms['upload_bytes'] - 0x6000
    assert page[i:i+2] == b'\xed\xa3'
    page[i:i+2] = b'\x23\x00'       # INC HL / NOP, one packed byte omitted
    broken.extra_banks[13] = bytes(page)
    return broken


def interrupt_row_tests(patch, sample):
    """Inject each handler at every assembled row instruction boundary, at all caller speeds."""
    c = Counter()
    m, regs = sample
    original_cursor = regs[4]*256 + regs[5] - 1
    for speed in range(4):
        for vector, epilogue in ((0x8f9f, 0x9048), (0xcdef, 0xce0f)):
            hw = Hardware(patch)
            hw.speed = speed
            hw.alt[patch.syms['game_speed']] = speed
            hw.alt[hw.cursor:hw.cursor+2] = original_cursor.to_bytes(2, 'little')
            r = list(regs)
            r[26] = 1
            next_source = original_cursor
            def interrupt(state, pc):
                nonlocal next_source
                regs = state.sim.registers
                before = list(regs)
                incoming = state.speed
                sp = regs[12] - 2
                state.mem[sp:sp+2] = pc.to_bytes(2, 'little')
                regs[12], regs[24], regs[26] = sp, vector, 0
                # Both original prologues have saved all six register pairs here.
                saved = 0x8fa7 if vector == 0x8f9f else 0xcdf7
                while regs[24] != saved:
                    state.step()
                if state.speed != speed or word(state.mem, state.cursor) != next_source:
                    c['interrupted speed or published byte differs!'] += 1
                regs[24] = epilogue
                while regs[24] != pc:
                    state.step()
                if state.speed != incoming or any(regs[i] != before[i] for i in CMP):
                    c['resumed row differs!'] += 1
                # The first LD (HL),A uses A from (BC); the second uses the
                # merged ULA byte. Only the first advances the source cursor.
                if state.mem[pc:pc+3] == bytes((0x77, 0xed, 0x43)):
                    next_source += 1
                c['row interrupt boundaries'] += 1
            hw.event(0xec29, m, r, observe=interrupt)
            if hw.speed != speed or word(hw.alt, hw.cursor) != original_cursor+3:
                c['completed interrupted row differs!'] += 1
    return c


def deferred_interrupt_tests(patch, sample):
    """Inject IM2 during rendering. Run the game's vector from restored RAM at dispatch exit."""
    c = Counter()
    memory, regs = sample
    for mark in ('rectangle', 'flush', 'upload_bytes'):
        hw = Hardware(patch)
        data = bytearray(memory)
        # Stand-in for the game's 5B5B vector, incrementing a counter in live RAM.
        data[0x5b5b:0x5b67] = bytes.fromhex('f53a705b3c32705bf1fbc9').ljust(12, b'\0')
        data[0x5b70] = 0
        data[0xece4:0xed14] = bytes([0xaa])*48
        inputs = list(regs)
        inputs[14], inputs[26], inputs[27] = 0xc7, 1, 2
        hw.event(0xec15, bytes(data), inputs)
        hw.alt[hw.cursor:hw.cursor+2] = (0xed13).to_bytes(2, 'little')
        inputs[24] = 0xec41
        fired = serviced = False
        def inject(state, pc):
            nonlocal fired, serviced
            r = state.sim.registers
            if pc == 0x5b5b:
                serviced = True
                if state.mapping != state.default or state.speed != 0 or r[14] != 0xc7:
                    c['deferred handler saw private state!'] += 1
            if fired or pc != patch.syms[mark]:
                return
            fired = True
            if not r[26] or r[27] != 2:
                c['interrupt blocked during mapped work!'] += 1
                return
            vector = word(state.mem, (r[14] << 8) | 255)
            if vector != patch.syms['deferred_irq']:
                c['private interrupt vector differs!'] += 1
                return
            r[12] -= 2
            state.mem[r[12]:r[12]+2] = pc.to_bytes(2, 'little')
            r[24], r[26] = vector, 0
            while r[24] != pc:
                state.step()
            if not state.mem[patch.syms['irq_pending']] or state.mem[0x5b70]:
                c['interrupt not deferred!'] += 1
        ticks = hw.event(0xec41, bytes(data), inputs, observe=inject)
        if not fired or not serviced or hw.mem[0x5b70] != 1 or ticks >= 69888:
            c['deferred interrupt lost or duplicated!'] += 1
        c['deferred interrupt injections'] += 1
    return c


def secondary_interrupt_tests(patch, states):
    """Interrupt every coal row and eraser byte, immediately after its physical ULA store."""
    c = Counter()
    hw, expected = Hardware(patch), Oracle()
    # Fixtures use the original row table, coordinates and screen format.
    base_mem, base_regs = states[0xec15][0]
    memory = bytearray(base_mem)
    memory[0xc537:0xc53f] = bytes((0x81, 0x42, 0x24, 0x18, 0xff, 0x33, 0x66, 0x99))
    memory[0x5c7b] = 32
    memory[0x5804:0x5807] = bytes([0x78])*3
    def checked_irq(state, pc):
        r = state.sim.registers
        origin = list(r)
        sp = r[12]-2
        state.mem[sp:sp+2] = pc.to_bytes(2, 'little')
        r[12], r[24], r[26] = sp, 0x8f9f, 0
        while r[24] != 0x8fa7:
            state.step()
        expected.check(state, c, lambda kind, detail: c.update([kind+'!']))
        r[24] = 0x9048
        while r[24] != pc:
            state.step()
        if any(r[i] != origin[i] for i in CMP):
            c['secondary IRQ register mismatch!'] += 1
        c['secondary interrupt boundaries'] += 1

    def enter(site, addr, count, value, source_row=0):
        r = list(base_regs)
        r[24], r[26], r[27], r[14] = site, 1, 2, 0xc7
        r[0], r[2] = value, count
        r[4], r[5] = divmod(addr, 256)
        r[6:8] = r[4:6]
        r[10], r[11] = divmod(0xc537+source_row, 256)
        def observe(state, pc):
            # LD (small_cursor),HL or LD (small_cursor),DE immediately follows
            # the visible store in all three entry points.
            if site in (0x8477,0x847d,0x8483,0x963b):
                op = state.mem[pc]
                if op == 0x22 and word(state.mem,pc+1) == patch.syms['small_cursor'] or (
                        op == 0xed and state.mem[pc+1] == 0x53 and word(state.mem,pc+2) == patch.syms['small_cursor']):
                    checked_irq(state, pc)
        hw.event(site, bytes(memory), r, observe)
    for col in range(4, 7):
        enter(0x9630, 0x4000+col, 8, 0)
        for row, bits in enumerate(memory[0xc537:0xc53f]):
            addr = 0x4000+col+row*256
            expected.write(addr, bits, 15)
            enter(0x963b, addr, 8-row, 255-bits, row)
    row_table = 0xea60 + 2*100
    memory[row_table-2:row_table+2] = bytes((0,0x41,0,0x40))
    enter(0x8456, 200, 2, 100)
    for row in range(2):
        for col,site in enumerate((0x8477, 0x847d, 0x8483),4):
            addr = 0x4000+col+256*row
            expected.write(addr,0,0)
            enter(site,addr,2-row,0)
    return c


def unit_tests(patch, states):
    """Static-only caller contexts use the common entry, including blank patterns and overlapping tiles."""
    c = Counter()
    if 0xec15 not in states or not states[0xec15]:
        c['no plot state!'] += 1
        return c
    from . import simpool
    from skoolkit.simulator import Simulator
    mem, regs = states[0xec15][0]
    callers = [i for i in range(0x6000, 65533) if mem[i:i+3] == b'\xcd\xe0\xeb']
    hw, model = Hardware(patch), Oracle()
    for i, caller in enumerate(callers):
        data = bytearray(mem)
        r = list(regs)
        r[24] = caller
        data[0x9649] = 44
        data[0xecde] = (0, 1, 7, 8, 249, 255)[i % 6]
        data[0xecdf] = 79
        data[0xece0:0xece2] = (0x7780 if i%3 == 1 else 0x849c).to_bytes(2, 'little')
        sim = simpool.machine(Simulator, data, r, slot='caller', copy=True)
        for _ in range(3000):
            pc = sim.registers[24]
            if pc == 0xec15:
                break
            sim.opcodes[sim.memory[pc]]()
        else:
            c['caller missed hook!'] += 1
            continue
        m, r = sim.memory, sim.registers
        if word(m, r[12]) != caller+3:
            c['wrong caller return!'] += 1
        hw.event(0xec15, bytes(m), list(r))
        row = word(m, 0xece2)
        for j in range(16):
            start = word(m, row-2*j) + word(m, 0xed14)
            for k in range(3):
                model.write(start+k, m[0xece4+3*j+k], 8)
        hw.alt[hw.cursor:hw.cursor+2] = (0xed13).to_bytes(2, 'little')
        finish = list(r)
        finish[24] = 0xec41
        hw.event(0xec41, bytes(m), finish)
        model.check(hw, c, lambda kind, detail: c.update([kind+'!']))
    c['static caller contexts'] = len(callers)
    if len(callers) != 30:
        c['caller count!'] += 1

    for speed in range(4):
        for iff in (0, 1):
            state = Hardware(patch)
            state.speed = speed
            inputs = list(r)
            inputs[26] = iff
            state.event(0xec15, bytes(m), inputs)
            if state.speed != speed or state.sim.registers[26] != iff or state.mapping != state.default:
                c['speed, IFF or paging restoration!'] += 1
            c['clock and IFF cases'] += 1

    c.update(secondary_interrupt_tests(patch, states))
    c.update(deferred_interrupt_tests(patch, states[0xec15][0]))
    if states.get(0xec29):
        c.update(interrupt_row_tests(patch, states[0xec29][0]))

    # Break the actual port-writing code in the candidate's own hook bank.
    # Keep the broken code between events. Only the captured game's state is loaded.
    broken = negative_patch(patch)
    bad = Hardware(broken)
    bad.event(0xec15, bytes(m), list(r))
    bad.alt[bad.cursor:bad.cursor+2] = (0xed13).to_bytes(2, 'little')
    bad.event(0xec41, bytes(m), finish)
    expected = Oracle()
    for j in range(16):
        start = word(m, row-2*j) + word(m, 0xed14)
        for k in range(3):
            expected.write(start+k, m[0xece4+3*j+k], 8)
    caught = []
    expected.check(bad, Counter(), lambda kind, detail: caught.append(kind))
    c['negative control caught' if caught else 'negative missed!'] += 1
    return c


def auto(a, z80, name, out, say):
    say('Engine    : wanted_monty_mole (original ULA and a sparse hardware sprite overlay)')
    ok, patch = build(z80, out, name, say)
    for recording in a.rzx or []:
        c, ex, states = verify(patch, recording, stop=getattr(a, 'quick', None), collect=1)
        u = unit_tests(patch, states)
        say('Verify    : %s %s %s' % (Path(recording).name, dict(c), ex))
        say('Unit      : %s' % dict(u))
        ok &= bool(c['layer checks']) and not any(k.endswith('!') for k in c.keys() | u.keys())
    result = 'PASSED' if a.rzx else 'diagnostic rebuild only'
    say('Result    : %s' % (result if ok else 'FAILED'))
    return ok
