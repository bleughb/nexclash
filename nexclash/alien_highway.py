"""Alien Highway renderer. Keep the game's mask/OR buffers and publish its visible figures on sprites."""
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from . import hooklib, jnext, nextboot, runchecks, rzx
from . import z80tonex as zt
from .machine import Machine

CMP = tuple(hooklib.CMP_R)

ROOT = Path(__file__).resolve().parents[1]
START_MD5 = 'cd9b4a722898c9f31f959b5b2767635f'
FIGURES = 0xB6B0
SITES = {
    0x8C42: ('2100fd', 'scene_open'),
    0x8F6C: ('210083', 'draw_open'),
    0x8FD5: ('69603e18', 'plot_right'),
    0x9073: ('60693e18', 'plot_left4'),
    0x90C8: ('60693e18', 'plot_left2'),
    0x9112: ('60690618', 'plot_even'),
    0x9CD4: ('21ff5a', 'clear_hud'),
    0xA36D: ('21ff5a', 'clear_end'),
    0xA6EA: ('af320ba9', 'clear_menu'),
    0xA954: ('210040', 'clear_title'),
    0x913D: ('210087', 'copy_open'),
    0x919A: ('3a0b88', 'publish'),
}


def load_profile():
    return json.loads((ROOT / 'docs/profiles/alien_highway.json').read_text())


def mask_pages(memory):
    """One byte per destination byte, set for both black paper and coloured ink."""
    pages = []
    for shift in (2, -4, -2, 0):
        data = bytearray()
        for addr in range(FIGURES, 0xD900, 6):
            mask = int.from_bytes(memory[addr:addr + 3], 'big')
            ink = int.from_bytes(memory[addr + 3:addr + 6], 'big')
            if shift > 0:
                if mask & 0x800000:
                    mask -= 1 << 24
                mask >>= shift
                ink >>= shift
            else:
                carry = 1
                for _ in range(-shift):
                    mask, carry = (mask << 1) | carry, (mask >> 23) & 1
                ink <<= -shift
            solid = (~mask | ink) & (0xFFFF00 if shift == -4 else 0xFFFFFF)
            data.extend(solid.to_bytes(3, 'big'))
        pages.append(bytes(data).ljust(8192, b'\0'))
    return pages


def road_tiles(memory):
    """18 strips copied by 913D, each from its rightmost byte to its leftmost."""
    cells = set()
    for p in range(0x8700, 0x877E, 7):
        length = memory[p]
        source = int.from_bytes(memory[p + 1:p + 3], 'little') - 0xE900
        y, x = divmod(source, 32)
        cells.update((x - i, y // 8) for i in range(length))
    if len(cells) != 363:
        raise ValueError('Alien Highway road cell map differs')
    tiles = bytearray()
    for y in range(0, 144, 16):
        for x in range(0, 256, 16):
            flags = sum(1 << i for i in range(4) if (x // 8 + i % 2, y // 8 + i // 2) in cells)
            if flags:
                tiles.extend(zt.w16(0x300 + y * 32 + x // 8))
                tiles.extend(((32 + x) & 255, 32 + y, flags | (128 if x >= 224 else 0)))
    if len(tiles) != 98 * 5:
        raise ValueError('Alien Highway road tile map differs')
    return tiles


class Patch:
    name = 'Alien Highway hardware sprites'
    tail_addr = 0x6EB0
    max_tail = 339
    uses_printer_buffer = True
    keep_printer_buffer = True
    setup_call = 0xD000
    slot1 = (28, 0x3F40)
    altrom_whole = True
    hook_page_data = b''

    def __init__(self):
        h = load_profile()['hooks']
        symbols = {k: int(v, 16) for k, v in h['syms'].items()}
        self.page = bytearray(zt.rom48()[0x2000:])
        start = symbols['rom_start']
        end = symbols['rom_end']
        self.page[start - 0x2000:end - 0x2000] = bytes.fromhex(h['rom'])
        self.altrom = (start, 0x3F60)
        self.altrom0 = (start, end)
        self.stub_extra = bytes.fromhex(h['setup'])
        self.page[0x1C00:] = bytes(1024)
        self.page[0x1C07] = 98
        self.page[0x1C20:0x1C82] = bytes(range(98))
        for mask in range(16):
            for ink in range(16):
                pixels = [(2 if ink & bit else 1) if mask & bit else 0 for bit in (8, 4, 2, 1)]
                index = 16 * mask + ink
                self.page[0x1400 + index] = 16 * pixels[0] + pixels[1]
                self.page[0x1500 + index] = 16 * pixels[2] + pixels[3]
        self.sites = []
        for address, (old_hex, label) in SITES.items():
            old = bytes.fromhex(old_hex)
            self.sites.append((address, old, b'\xc3' + zt.w16(symbols[label]) + bytes(len(old) - 3)))
        self.extra_banks = {}

    def apply(self, snap):
        ram = bytearray(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0]
        tiles = road_tiles(ram)
        self.page[0x1800:0x1800 + len(tiles)] = tiles
        masks = mask_pages(ram)
        self.extra_banks = {14: bytes(self.page) + bytes(8192), 15: bytes(16384),
                            16: masks[0] + masks[1], 17: masks[2] + masks[3]}
        for address, old, new in self.sites:
            if bytes(ram[address:address + len(old)]) != old:
                raise ValueError('Alien Highway original bytes differ at %04X' % address)
            ram[address:address + len(old)] = new
        for bank, addr in ((5, 0x4000), (2, 0x8000), (0, 0xC000)):
            snap.banks[bank] = bytes(ram[addr:addr + 16384])


def build(source, destination, *, checkpoint=None):
    if hashlib.md5(Path(source).read_bytes()).hexdigest() != START_MD5:
        raise ValueError('Use the Alien Highway RZX start snapshot')
    patch = Patch()
    patch.source = Path(source).resolve()
    conv = zt.convert(str(checkpoint or source), str(destination), patch=patch, quiet=True)
    path = Path(destination)
    path.write_bytes(zt.automap_off(path.read_bytes()))
    return patch, conv


def build_plain(source, destination):
    """Use the original 48K ROM, including the two bytes the recording reads."""
    from .build import _PlainCompact
    plain = _PlainCompact(Patch.tail_addr, Patch.max_tail)
    plain.keep_printer_buffer = True
    plain.altrom = (0x3FE0, 0x4000)
    plain.page = bytes(8192)
    conv = zt.convert(str(source), str(destination), patch=plain, quiet=True)
    path = Path(destination)
    path.write_bytes(zt.automap_off(path.read_bytes()))
    return plain, conv


def is_alien_highway(snap):
    if getattr(snap, 'is128', False) or getattr(snap, 'machine', '48K') != '48K':
        return False
    signature = load_profile()['signature']
    address = int(signature['address'], 16)
    expected = bytes.fromhex(signature['hex'])
    if hasattr(snap, 'memory'):
        return bytes(snap.memory[address:address + len(expected)]) == expected
    return snap.banks[2][address - 0x8000:address - 0x8000 + len(expected)] == expected


def pixel_errors(frame):
    """Count hardware pixels that cover a different native ULA colour."""
    layer = frame.layer()
    errors = 0
    for (x, y), colour in layer.items():
        address = (y & 7) * 256 + (y & 56) * 4 + (y & 192) * 32 + x // 8
        ink = frame.ula[address] & (128 >> (x % 8))
        attr = frame.ula[6144 + (y // 8) * 32 + x // 8]
        index = ((attr >> 3) & 8) | ((attr if ink else attr >> 3) & 7)
        errors += colour != frame.upal[index]
    return len(layer), errors


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """Replay site reachability and measure the assembled overlay at native frame boundaries."""
    counts = Counter()
    examples = []
    states = {}
    seen = set()

    def hit(pc, sim):
        counts['site hits'] += 1
        if pc in SITES and pc not in seen:
            old = bytes.fromhex(SITES[pc][0])
            if bytes(sim.memory[pc:pc + len(old)]) != old:
                counts['site bytes!'] += 1
            seen.add(pc)
        if pc == 0x8935 and pc not in states:
            states[pc] = (bytes(sim.memory[:65536]), list(sim.registers), 0)

    frames, error = rzx.trace(rzx_path, set(SITES) | {0x8935}, hit, stop=stop)
    counts['RZX frames'] = frames
    counts['sites reached'] = len(seen)
    if error or not states:
        counts['replay or gameplay checkpoint!'] += 1
        examples.append(str(error or 'Timer update was not reached'))
    elif not stop and len(seen) != len(SITES):
        counts['unreached patch sites!'] += len(SITES) - len(seen)
    elif not os.environ.get('NEXCLASH_JNEXT_CARD'):
        counts['native display unmeasured!'] += 1
        examples.append('Set NEXCLASH_JNEXT_CARD to a readable NextZXOS card image')
    else:
        with tempfile.TemporaryDirectory(prefix='alien_display_') as tmp:
            folder = Path(tmp)
            machine = Machine(str(patch.source))
            machine.load(states[0x8935])
            checkpoint = folder / 'gameplay.z80'
            checkpoint.write_bytes(machine.z80_bytes())
            program = folder / 'gameplay.nex'
            build(patch.source, program, checkpoint=checkpoint)
            script = jnext.Script(jnext.start_frame(str(program)))
            script.var('u')
            script.rule('on execute 0x8935 do\n  set u = u + 1\nend\n')
            script.rule('on frame when u >= 3 and u < 43 do\n  save_snapshot "f${FRAME}.jns"\nend\n')
            script.rule('on execute 0x8935 when u == 44 do\n  log "DONE u=${u}"\n  exit 0\nend\n')
            script.exit_at(1000)
            job = (str(program), script.text(), str(folder), 1100, jnext.card(), str(folder/'home'))
            if jnext.run_all([job]) != [0] or 'DONE u=44' not in (folder/'run.log').read_text():
                counts['native run incomplete!'] += 1
            captures = sorted(folder.glob('f*.jns'), key=lambda p: int(p.stem[1:]))
            ids = [int(p.stem[1:]) for p in captures]
            if ids and len(ids) != ids[-1] - ids[0] + 1:
                counts['missing intermediate captures!'] += 1
            for path in captures:
                frame = jnext.Frame(str(path))
                pixels, errors = pixel_errors(frame)
                counts['native frames'] += 1
                counts['hardware pixels'] += pixels
                if not pixels:
                    counts['copy hidden frames' if not frame.on else 'empty enabled layer!'] += 1
                if errors:
                    counts['stale frames!'] += 1
                    counts['stale pixels!'] += errors
                    if len(examples) < 3:
                        examples.append(f'{path.stem}: {errors} differing pixels')
            if not counts['hardware pixels'] or not counts['copy hidden frames']:
                counts['native publication unmeasured!'] += 1
            if not counts['native frames']:
                counts['missing frame captures!'] += 1
            # Independent native replay consumes every recorded IN and observes the beam during copies.
            from .alien_highway_replay import run
            frozen = folder/'start.nex'
            build(patch.source, frozen)
            try:
                results = run(patch.source, frozen, rzx_path, stop)
                for mode, result in results.items():
                    for key, value in result.items():
                        counts[f'{mode} {key}'] = int(value)
            except (ValueError, OSError, KeyError, RuntimeError) as exc:
                counts['whole recording comparison!'] += 1
                examples.append(str(exc))
    return (counts, examples, states) if collect else (counts, examples)


def unit_tests(patch, source):
    """A one-bit change in any guarded site must fail before modifying snapshot RAM."""
    counts = Counter()
    for address, old, _ in patch.sites:
        snap = zt.Z80Snapshot(str(source))
        bank = 2 if address < 0xC000 else 0
        offset = address & 0x3FFF
        mutated = bytearray(snap.banks[bank])
        mutated[offset + len(old) - 1] ^= 1
        snap.banks[bank] = bytes(mutated)
        before = snap.banks.copy()
        try:
            patch.apply(snap)
        except ValueError as exc:
            if f'{address:04X}' in str(exc) and snap.banks == before:
                counts['mutated site refused'] += 1
                continue
        counts['mutated site accepted or RAM changed!'] += 1
    machine = Machine(str(source))
    bottom = 0x7800
    sim = machine.sim
    for phase, entry in enumerate((0x8FD5, 0x9073, 0x90C8, 0x9112)):
        bank = patch.extra_banks[16 + phase // 2]
        page = bank[(phase % 2) * 8192:((phase % 2) + 1) * 8192]
        for address in range(FIGURES, 0xD900, 144):
            # On zeros we get the ink. On ones we also see which bits pass through.
            rows = []
            for fill in (0, 255):
                sim.memory[0x7500:0x7900] = bytes([fill]) * 1024
                registers = sim.registers
                registers[2], registers[3] = divmod(bottom, 256)
                registers[4], registers[5] = divmod(address, 256)
                registers[12] = 0xFF00
                sim.memory[0xFF00:0xFF02] = bytes((0, 0x82))
                sim.run(entry, 0x8200)
                rows.append(b''.join(bytes(sim.memory[p:p + 3]) for p in range(bottom, bottom - 768, -32)))
            expected = bytes(a | (b ^ 255) for a, b in zip(*rows))
            index = (address - FIGURES) // 2
            got = page[index:index + 72]
            counts['mask records compared'] += 1
            if got != expected:
                counts['original plotter mask mismatch!'] += 1
            if address == FIGURES:
                broken = bytearray(got)
                broken[0] ^= 1
                key = 'mask fault detected' if got == expected and bytes(broken) != expected else 'mask fault missed!'
                counts[key] += 1
    return counts


def negative_palette():
    """A wrong hardware ink in a synthetic paper cell must trip the native pixel comparator."""
    from types import SimpleNamespace
    black, ink = (0, 0, 0), (192, 192, 192)
    bitmap = bytearray(6912)
    bitmap[0], bitmap[6144] = 128, 7
    frame = SimpleNamespace(ula=bitmap, upal=[black]*7 + [ink],
                            layer=lambda: {(0, 0): ink, (1, 0): black})
    good = pixel_errors(frame)
    frame.layer = lambda: {(0, 0): black, (1, 0): black}
    return good == (2, 0) and pixel_errors(frame) == (2, 1)


def auto(a, z80, name, out, say):
    """Build the two Next executables and register the tape-target package recipe."""
    a.tape_packager = package_tape
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    plain = folder / (name + '.nex')
    sprite = folder / (name + '_sprites.nex')
    patch, (_, start, tail, _) = build(z80, sprite)
    plain_patch, (_, pstart, ptail, _) = build_plain(z80, plain)
    ok = True
    for label, path, obj, address, code in (('Plain', plain, plain_patch, pstart, ptail),
                                           ('Sprites', sprite, patch, start, tail)):
        for loader in (False, True):
            errors = nextboot.check(str(path), z80, obj, (address, address + len(code)), nexload=loader)
            ok &= not errors
            say(f'{label}     : {path.name} NEXLOAD={int(loader)} boot ' + (str(errors) if errors else 'OK'))
    units = unit_tests(patch, z80)
    palette_detected = negative_palette()
    units_ok = not any(k.endswith('!') for k in units) and palette_detected
    ok &= units_ok
    runchecks.add(runchecks.RUN, 'alien_highway_units', 'pass' if units_ok else 'fail', str(dict(units)))
    say(f'Unit      : {dict(units)}, palette fault detected={palette_detected}')
    for path in getattr(a, 'rzx', None) or []:
        counts, examples = verify(patch, path, stop=getattr(a, 'quick', None))
        say(f'Verify    : {dict(counts)} {examples}')
        faults = {k: v for k, v in counts.items() if k.endswith('!')}
        runchecks.add(runchecks.RUN, 'alien_highway_display', 'fail' if faults else 'pass',
                      f"{counts['native frames']} native frames, {dict(faults)}")
        ok &= not faults
    if not getattr(a, 'rzx', None):
        say('Rebuild   : no recording supplied.')
    say('Result    : ' + (('PASSED' if getattr(a, 'rzx', None) else 'rebuild OK') if ok else 'FAILED'))
    return ok


TAPE = 'Alien Highway (1986)(Vortex)[aka Encounter 2].tap'
POK = 'Alien Highway - Encounter 2 (1986)(Vortex Software).pok'


def package_tape(a, z80, out, name, spr, rep, say, colours, toggles, checks):
    """Use the player's tape and the two verified POK entries on both menu paths."""
    from itertools import combinations
    from . import nxc, nxcout
    src = Path(z80)
    reference = os.environ.get('NEXCLASH_REFERENCE')
    def asset(explicit, filename, digest):
        paths = [Path(explicit)] if explicit else [src.parent/filename]
        if not explicit and reference:
            paths.append(Path(reference)/'alien_highway'/filename)
        for path in paths:
            if path.is_file() and nxcout.md5(path) == digest:
                return path
        raise ValueError('Expected ' + filename + ' with MD5 ' + digest)
    tapes = getattr(a, 'tape', None) or []
    if len(tapes) > 1 or colours or toggles:
        raise ValueError('Alien Highway 1.0 uses one TAP and two trainers')
    tape = asset(tapes[0] if tapes else None, TAPE, 'deb9dc45642681d6e218c08e2f9930f2')
    pok = asset(getattr(a, 'pok', None), POK, '4169c19afa59bc954c6d9dbdbf850489')
    nxc.ZX0_DIR = nxcout.zx0_dir()
    proof = nxcout.proof(rep, nxcout.md5(src), nxcout.md5(spr), getattr(a, 'quick', None), checks)
    proof['hardware'] = 'Untested on a physical Next.'
    info = dict(version='1.0', publisher='Vortex, 1986', build='Alien Highway 1.0',
                fix_label='Hardware sprites', build_screen='1989',
                trainers_played='Timer and damage checked in play. Both trainers start off.')
    packed, *_ = nxc.make(str(tape), str(spr), dict(file=TAPE, title='Alien Highway'), info,
                          start=str(src), proof=proof)
    packed = nxc.import_pok(packed, str(tape), pok.read_text(), only=['Infinite Time', 'Infinite Energy'])
    game, default = tape.read_bytes(), Path(spr).read_bytes()
    original = nxc.snapshot_of(src.read_bytes(), nxc.KIND_Z80).banks
    if nxc.apply(packed, game=game, chosen=()) != default:
        raise ValueError('Default package differs from sprite NEX')
    cheats = {'Infinite time': (0x0935, 0x2B, 0x00), 'Infinite energy': (0x19F3, 0xC8, 0xC9)}
    for n in range(3):
        for chosen in combinations(cheats, n):
            patched = nxc.apply(packed, game=game, chosen=chosen)
            restored = nxc.snapshot_of(nxc.original_with_pokes(packed, game, chosen), nxc.KIND_Z80).banks
            for before, after in ((nxc.nex_banks(default), nxc.nex_banks(patched)), (original, restored)):
                bank = bytearray(before[2])
                for cheat in chosen:
                    offset, old, new = cheats[cheat]
                    if bank[offset] != old:
                        raise ValueError(f'{cheat}: unexpected game byte')
                    bank[offset] = new
                if {**before, 2: bytes(bank)} != after:
                    raise ValueError(f'Trainer reconstruction differed: {chosen}')
    destination = Path(out)/(name+'.nxc')
    destination.write_bytes(packed)
    say(f'NXC       : {destination.name}, four trainer combinations on both menu paths')
    return str(destination)
