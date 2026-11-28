"""Batman (Ocean, 1986, 48K). Original ULA picture and optional trainers."""
import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from . import hooklib, nextboot, rzx, simrun, z80tonex
from .green_beret import PlainPatch
from .jack_the_nipper import restored_boot_check


SUPPORTED_STARTS = {
    'af9f1a6fb79c47bdf9a3ac15a5fef9c7',  # Ocean archive snapshot
    '9730b0dd1ac81ed2aa18545e921547cf',  # batman1.rzx start
}
CMP = hooklib.CMP_R + [24]  # include the current PC at each RZX boundary


def load_profile():
    return json.loads((Path(__file__).resolve().parents[1] / 'docs/profiles/batman.json').read_text())


def is_batman(snap):
    if snap.machine != '48K' or snap.memory[0x8E1D] != 0xE9:
        return False
    return all(bytes(snap.memory[s['addr']:s['addr'] + len(s['bytes']) // 2]).hex() == s['bytes']
               for s in load_profile()['signature'])

# Each indirect target at 8E1D selects a clipped width and source stride.
BLITS = {
    0x86A4: (1, 3), 0x86B9: (2, 3), 0x86D5: (3, 3),
    0x86F8: (1, 4), 0x870F: (2, 4), 0x872D: (3, 4), 0x8752: (4, 4),
    0x877D: (1, 5), 0x8796: (2, 5), 0x87B6: (3, 5), 0x87DD: (4, 5), 0x880A: (5, 5),
}
BLIT_RETURNS = {0x86B8, 0x86D4, 0x86F7, 0x870E, 0x872C, 0x8751,
                0x877C, 0x8795, 0x87B5, 0x87DC, 0x8809, 0x883C}
SCREEN_COPIES = {0x8324, 0x8342, 0x8344, 0x8362, 0x8364, 0x8366,
                 0x8384, 0x8386, 0x8388, 0x838A, 0x83A9, 0x83AB, 0x83AD, 0x83AF, 0x83B1}
OTHER_COPY_CALLERS = {0x7EDA, 0x7EE3, 0x7F17, 0x8421}
PLAYER_NODES = {0x8F1A, 0x8F2C}


def check_plots(recording, stop=None):
    """Measure unchanged masked plots and two proposed player overlays on the 48K game."""
    segments = rzx.read_segments(str(recording))
    if not segments or segments[0][0].machine != '48K':
        raise ValueError('Expected a 48K Batman recording')
    memory = segments[0][0].memory
    if any(memory[pc] != opcode for pc, opcode in ((0x8D35, 0xED), (0x8E1D, 0xE9), (0x86A4, 0xD9))):
        raise ValueError('Recording does not start with the Ocean Batman renderer')
    counts = Counter()
    expected = {}
    # Unlike a hardware sprite placed over the ULA, the original can paint over
    # individual black or ink pixels of either player piece later in the list.
    visible, silhouette, ink = (bytearray(256) for _ in range(3))
    object_addresses, graphics, heights = set(), set(), set()
    scene_copy = False

    def observe(pc, sim):
        nonlocal scene_copy
        m, regs = sim.memory, sim.registers
        if pc == 0x8D35:
            visible[:] = bytes(256)
            silhouette[:] = bytes(256)
            scene_copy = False
        elif pc == 0x8D9A:
            scene_copy = True
        elif pc in OTHER_COPY_CALLERS:
            scene_copy = False
        elif pc in SCREEN_COPIES:
            if scene_copy:
                source = regs[6] * 256 + regs[7]
                if source >> 8 != 0xA0:
                    raise ValueError('Unexpected source for room screen copy')
                i = source & 255
                differing = ink[i] ^ m[source]
                hidden = silhouette[i] & ~visible[i]
                counts['visible player pixel samples'] += visible[i].bit_count()
                counts['opaque black player samples'] += (visible[i] & ~ink[i]).bit_count()
                counts['covered player samples'] += hidden.bit_count()
                counts['wrong unclipped pixels'] += (differing & hidden).bit_count()
                counts['false ownership by equal colour'] += (hidden & ~differing).bit_count()
                counts['wrong clipped player pixels'] += (visible[i] & differing).bit_count()
        elif pc == 0x8E1D:
            if expected:
                raise ValueError('Next dispatch reached before previous blit returned')
            width, stride = BLITS[regs[6] * 256 + regs[7]]
            node = m[0x8DAA] + 256 * m[0x8DAB]
            player = node in PLAYER_NODES
            object_addresses.add(node)
            graphics.add(m[0x9692] & 127)
            height = regs[2] or 256
            if player:
                heights.add(height)
                counts['player dispatches'] += 1
            counts['dispatches'] += 1
            dest = regs[18] * 256 + regs[19]
            source = regs[20] * 256 + regs[21]
            mask = regs[22] * 256 + regs[23]
            if dest >> 8 != 0xA0:
                raise ValueError('Unexpected masked plot destination')
            for y in range(height):
                for x in range(width):
                    i = (dest + 6 * y + x) & 255
                    bits = m[(source + y * stride + x) & 65535]
                    keep = m[(mask + y * stride + x) & 65535]
                    opaque = bits | (255 ^ keep)
                    address = 0xA000 + i
                    expected[address] = (m[address] & keep) | bits
                    visible[i] &= 255 ^ opaque
                    if player:
                        ink[i] = (ink[i] & ~opaque) | bits
                        visible[i] |= opaque
                        silhouette[i] |= opaque
        elif pc in BLIT_RETURNS and expected:
            counts['returns checked'] += 1
            counts['bytes checked'] += len(expected)
            counts['wrong masked bytes'] += sum(m[a] != b for a, b in expected.items())
            expected.clear()

    watch = SCREEN_COPIES | OTHER_COPY_CALLERS | BLIT_RETURNS | {0x8D35, 0x8D9A, 0x8E1D}
    frames, desync = rzx.trace(str(recording), watch, observe, stop=stop)
    return dict(frames=frames, desync=desync, counts=dict(counts), pending_bytes=len(expected),
                object_addresses=len(object_addresses), graphics=len(graphics), player_heights=sorted(heights))


def build_plain(source, destination):
    """Restore all game RAM before the original IM 2 entry at 0xFFFF."""
    source, destination = Path(source), Path(destination)
    if destination.suffix.lower() != '.nex':
        raise ValueError('The plain output must be a .nex file')
    if hashlib.md5(source.read_bytes()).hexdigest() not in SUPPORTED_STARTS:
        raise ValueError('Unsupported Batman snapshot')
    # The plotter reads Sinclair ROM byte 2 via an empty object pointer.
    # This bootstrap provides that ROM and restores both the NEXLOAD workspace
    # and the temporary tail. Its upper-ROM working span misses vector 0x39FF.
    patch = PlainPatch()
    patch.name = 'Batman original display'
    patch.tail_addr = 0x7BFF
    with TemporaryDirectory(dir=destination.parent) as work:
        output = Path(work) / 'plain.nex'
        z80tonex.convert(str(source), str(output), patch=patch, quiet=True)
        output.write_bytes(z80tonex.automap_off(output.read_bytes()))
        output.replace(destination)
    return patch


def game_entry(nex, source, nexload):
    snap = z80tonex.Z80Snapshot(str(source))
    state = nextboot.boot(str(nex), snap.pc, nexload=nexload, sysrom=nextboot.system_rom3()[0],
                          nr={0x0A: 0x11, 0x15: 1, 0x07: 3})
    if (state['bad'] or state['R'][15] != snap.r or state['mem'][2] != 0x11
            or state['nr'][0x0A] & 0x10 or state['nr'][0x15] or state['nr'][0x07]):
        raise ValueError('Batman boot did not restore the expected ROM, R, automap, ULA or CPU speed')
    return state


def unit_tests(nex, source, patch):
    for loader in (False, True):
        problems = nextboot.check(str(nex), str(source), patch,
                                  (patch.tail_addr, patch.tail_addr + patch.tail_restore_bytes), nexload=loader)
        problems += restored_boot_check(str(nex), str(source), patch, nexload=loader)
        if problems:
            raise ValueError(f'Batman boot (NEXLOAD {loader}): {problems}')
        game_entry(nex, source, loader)


def negative_tail(nex, source, patch):
    """Damage the backup in the NEX, then require the game-entry check to see that byte in RAM."""
    from . import nxc
    raw = bytearray(nex.read_bytes())
    banks = list(nxc.nex_banks(raw))
    bank, slot = divmod(patch.slot1[0], 2)
    offset = 512 + len(nxc.nex_screen(raw)) + banks.index(bank) * 16384 + slot * 8192
    raw[offset + (patch.slot1[1] & 8191) + 20] ^= 1
    with TemporaryDirectory() as work:
        broken = Path(work) / 'tail.nex'
        broken.write_bytes(raw)
        problems = restored_boot_check(str(broken), str(source), patch, nexload=True)
    if problems != [('RAM at the game start differs (the tail too)', 1, [f'{patch.tail_addr:04X}'])]:
        raise ValueError(f'Corrupt Batman tail was not identified: {problems}')


def verify(entry, rzx_path, stop=None):
    """Compare each boundary with the stock replay, starting the second from the actual NEX boot."""
    memory = bytes(entry['mem'][a] for a in range(65536))
    expected = []
    total, _ = simrun.rzx_frames(rzx_path)
    boundaries = min(total, stop or total) + 1

    class Replay:
        frame_only = True

        def __init__(self, built):
            self.built = built

        def on_sim(self, sim):
            self.sim = sim
            if self.built:
                sim.memory[:] = memory
                for i in CMP:
                    sim.registers[i] = entry['R'][i]

        def on_frame(self, n):
            ram = hashlib.blake2b(bytes(self.sim.memory[0x4000:]), digest_size=16).digest()
            sample = (ram, tuple(self.sim.registers[i] for i in CMP))
            if not self.built:
                expected.append(sample)
            elif n > len(expected) or sample != expected[n - 1]:
                raise ValueError(f'{rzx_path}: game RAM or registers differ at boundary {n}')

        def on_desync(self, n, message):
            raise ValueError(f'{rzx_path}: desync at frame {n}: {message}')

    for built in (False, True):
        seen = simrun.play_rzx(rzx_path, Replay(built), stop=stop)
        if seen != boundaries:
            raise ValueError(f'{rzx_path}: replay visited {seen} of {boundaries} boundaries')
    return boundaries


def trainer_pok(source, trainers):
    snap = z80tonex.Z80Snapshot(str(source))
    lines = []
    for t in trainers:
        if snap.read(t['address']) != t['original']:
            raise ValueError(f"Unexpected original byte for {t['name']}")
        lines.extend(['N' + t['name'], 'Z 8 {address} {value} {original}'.format(**t)])
    return '\n'.join(lines + ['Y', ''])


def collision_units(recording, work, trainers):
    """Branch from the archive contact with no keys held, once per menu combination."""
    from skoolkit.snapshot import Snapshot
    from .machine import Machine
    cut = str(work / 'contact.rzx')
    if rzx.cut(recording, 29373, 200, cut) != 200:
        raise ValueError('Batman collision segment incomplete')
    start, _ = rzx.extract(cut)
    for lives, immune in product((False, True), repeat=2):
        snap = Snapshot.get(start)
        for enabled, t in zip((lives, immune), trainers):
            if snap.memory[t['address']] != t['original']:
                raise ValueError('Unexpected trainer site at collision')
            if enabled:
                snap.memory[t['address']] = t['value']
        m = Machine(snap)
        initial = m.sim.memory[0x8F01]
        timers = []
        for _ in range(200):
            m.frame()
            timers.append(m.sim.memory[0x9B06])
        observed = initial, m.sim.memory[0x8F01], max(timers), sum(bool(v) for v in timers)
        expected = 0x10, 0x10 if lives or immune else 0x09, 0 if immune else 12, 0 if immune else 122
        if observed != expected:
            raise ValueError(f'Batman collision, lives={lives} immunity={immune}: {observed} != {expected}')


def auto(a, z80, name, out, say):
    from .hard_drivin import with_screen
    source, out = Path(z80), Path(out)
    profile = load_profile()
    a.publisher = getattr(a, 'publisher', None) or 'Ocean, 1986'
    a.fix_label = getattr(a, 'fix_label', None) or 'Next compatibility'
    a.display_model = profile['display_model']
    a.nxc_rom = 2
    plain = out / (name + '.nex')
    patch = build_plain(source, plain)
    say('Game      : Batman (Ocean, 1986), original display')
    unit_tests(plain, source, patch)
    negative_tail(plain, source, patch)
    say(f'Plain     : {plain.name}  {hashlib.md5(plain.read_bytes()).hexdigest()}  boot OK')
    screen = source.with_name('batman.scr')
    loading = None
    if screen.is_file():
        data = screen.read_bytes()
        if hashlib.md5(data).hexdigest() != '8605b0815d9a3378997df5df8ba843e5':
            raise ValueError('Expected the Ocean Batman loading screen in batman.scr')
        loading = out / (name + '_loading.nex')
        with_screen(plain, loading, data)
        unit_tests(loading, source, patch)
        say(f'Loading   : {loading.name}, 6912 bytes of original tape screen, boot OK')
    else:
        say('Loading   : batman.scr absent, building without the tape picture')

    pok = trainer_pok(source, profile['trainers'])
    if getattr(a, 'pok', None):
        supplied = Path(a.pok)
        if (supplied.read_text() != pok and
                hashlib.md5(supplied.read_bytes()).hexdigest() != 'c1cbcd956050cdca8f9e6e58cb419f3a'):
            raise ValueError('Expected the Ocean archive POK or the two verified Batman trainers')
    pok_path = out / (name + '_verified.pok')
    pok_path.write_text(pok)
    a.pok = str(pok_path)
    (out / (name + '_outputs.json')).write_text(json.dumps(
        dict(default=plain.name, plain=plain.name, loading=loading.name if loading else None), indent=1))

    for recording in a.rzx or []:
        with TemporaryDirectory() as work:
            start = Path(work) / 'start.z80'
            _, ext = rzx.extract(recording, str(start))
            digest = hashlib.md5(start.read_bytes()).hexdigest()
            play, src = loading or plain, source
            if ext == 'z80' and digest in SUPPORTED_STARTS and digest != hashlib.md5(source.read_bytes()).hexdigest():
                play, src = Path(work) / 'recorded.nex', start
                other = build_plain(src, play)
                unit_tests(play, src, other)
            samples = verify(game_entry(play, src, True), recording, a.quick)
            say(f'Verify    : {Path(recording).name}, {samples - 1} frames, {samples} boundaries, '
                f'49152 RAM bytes and {len(CMP)} register fields each: IDENTICAL')
            if samples > 29573 and hashlib.md5(Path(recording).read_bytes()).hexdigest() == '68b2492b14d871ea925ba989d2a88bcd':
                collision_units(recording, Path(work), profile['trainers'])
                say('Unit      : all four trainer combinations at archive contact, 200 frames each: PASS')
    say('Unit      : boot with and without NEXLOAD, wrong tail byte detected: PASS')
    say('Result    : PASSED')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--plain', nargs=2, metavar=('SNAPSHOT', 'OUTPUT'),
                        help='build the original-display NEX')
    action.add_argument('--check-plots', metavar='RZX', help='measure original plots and player clipping')
    args = parser.parse_args()
    if args.plain:
        build_plain(*args.plain)
    else:
        result = check_plots(args.check_plots)
        print(json.dumps(result, indent=2))
        counts = result['counts']
        if (result['desync'] or result['pending_bytes'] or not counts.get('visible player pixel samples')
                or counts.get('wrong masked bytes') or counts.get('wrong clipped player pixels')):
            raise SystemExit(1)
