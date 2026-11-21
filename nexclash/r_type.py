"""R-Type (Electric Dreams, 1988, 128K): Layer 2 scroll, hardware sprites and glide (engine 'r_type').

The game's own logic runs unchanged. Hooks (asm/r_type_hooks.asm) take over the display: the play area scrolls on
Layer 2, the figures the game plots become hardware sprites painted from colour tables, the ship glides between the
game's 4-pixel steps, and level 3's battleship is a tilemap. See games/r_type.md.

Nothing copied from the game is stored here. The level graphics are unpacked at build time from the player's snapshot
by the game's own unpacker (run in the simulator); docs/profiles/r_type_catalogue.json.gz holds only where each
graphic is (level, address, ink, geometry), never its bytes. The owner's start-up picture and the tape's loading
screen are side inputs beside the snapshot, checked by MD5.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path

from . import hooklib, simpool, z80tonex as Z

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs' / 'profiles' / 'r_type.json'
CATALOGUE = ROOT / 'docs' / 'profiles' / 'r_type_catalogue.json.gz'
BEHIND = ROOT / 'docs' / 'profiles' / 'r_type_behind.json'
SOURCE_MD5 = '5a2179b4006d7888a1f7f821a4316bf5'      # Rtype.z80, the 128K snapshot the build is made from
DECODED_SHA256 = 'b70b5d3e4cb8b022190cb8fdbcb65e071925764914b1eb0d69b39482fac9aeb2'
UNPACK_LEVELS = [49, 50, 51, 52, 53, 54, 55, 56, 49]  # the level digits the loader asks for: 1-8, then 1 again
UNPACK_IX = 0xC4AE
PUBLISHER = 'Electric Dreams, 1988'
CMP = tuple(hooklib.CMP_R)
VERIFIED = False                                      # emulator evidence only; the simulator proof is a later stage


def load_profile():
    return json.loads(PROFILE.read_text())


def is_r_type(snap):
    """The 128K game at its display code: zt.Z80Snapshot (banks) or skoolkit's Snapshot (memory)."""
    sig = load_profile()['signature']
    banks = getattr(snap, 'banks', None)
    try:
        if banks is None:
            if getattr(snap, 'machine', '48K') == '48K':
                return False
            return all(bytes(snap.memory[int(a, 16):int(a, 16) + len(v) // 2]) == bytes.fromhex(v) for a, v in sig.items())
        if not getattr(snap, 'is128', False):
            return False
        return all(bytes(banks[2][int(a, 16) - 0x8000:int(a, 16) - 0x8000 + len(v) // 2]) == bytes.fromhex(v)
                   if int(a, 16) < 0xC000 else
                   bytes(banks[0][int(a, 16) - 0xC000:int(a, 16) - 0xC000 + len(v) // 2]) == bytes.fromhex(v)
                   for a, v in sig.items())
    except (KeyError, TypeError, IndexError):
        return False


# ---------------------------------------------------------------- level graphics, by the game's own unpacker

class Memory:
    """64K view over the snapshot's 8 banks (8K pages) with an MMU, ROM in pages 255."""
    def __init__(self, banks):
        from skoolkit import ROM128
        self.pages = {2 * i + j: bytearray(b[8192 * j:8192 * (j + 1)]) for i, b in enumerate(banks) for j in (0, 1)}
        self.rom = Path(ROM128[1]).read_bytes()
        self.mmu = [255, 255, 10, 11, 4, 5, 0, 1]

    def __len__(self):
        return 65536

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(65536))]
        p = self.mmu[a >> 13]
        return self.rom[a] if p == 255 else self.pages[p][a & 8191]

    def __setitem__(self, a, v):
        p = self.mmu[a >> 13]
        if p != 255:
            self.pages[p][a & 8191] = v


class Model(hooklib.NextModel):
    def nextreg(self, n, v):
        super().nextreg(n, v)
        if 0x50 <= n <= 0x57:
            self.sim.memory.mmu[n - 0x50] = v

    def write_port(self, regs, port, value, *args):
        if port & 0x8002 == 0:
            self.sim.memory.mmu[6] = (value & 7) * 2
            self.sim.memory.mmu[7] = (value & 7) * 2 + 1
        return super().write_port(regs, port, value, *args)

    def read_port(self, regs, port):
        if port == 0x243B:
            return self.sel
        if port == 0x253B and 0x50 <= self.sel <= 0x57:
            return self.sim.memory.mmu[self.sel - 0x50]
        if port & 1 == 0:
            return 0xFF
        return super().read_port(regs, port)


def _until(sim, pc, limit):
    for _ in range(limit):
        if sim.registers[24] == pc:
            return
        sim.opcodes[sim.memory[sim.registers[24]]]()
    raise RuntimeError('unpacker did not return (PC %04X)' % sim.registers[24])


def unpack(snap, level, previous=None):
    """The game's level unpacker (8F31..8F4E) for level digit `level`, as its loader calls it. -> (64K image with
    the gameplay bank 0 at C000, the 8 banks after it)."""
    from .dizzy6 import _rw_simulator
    mem = Memory(previous or [bytes(snap.banks[i]) for i in range(8)])
    mem[0x600D] = level                 # the loader's filename digit, written by its low-IX call
    mem[0x719C] = level
    regs = [0] * 30
    regs[8:10] = [UNPACK_IX >> 8, UNPACK_IX & 255]
    regs[12] = 0xF000
    regs[24] = 0x8F31
    sim = simpool.machine(_rw_simulator(), mem, regs, slot='r_type-unpack')
    Model(sim, speed=0)
    _until(sim, 0x8F4E, 10000000)
    mem.mmu[6:] = [0, 1]                # the caller restores 7FFD = 10: gameplay bank 0 at C000
    return bytes(mem[a] for a in range(65536)), [bytes(mem.pages[2 * i]) + bytes(mem.pages[2 * i + 1]) for i in range(8)]


_IMAGES = {}


def images(snap):
    """[the snapshot's 64K, then each UNPACK_LEVELS level unpacked]: 10 images (cached per snapshot)."""
    key = hashlib.md5(b''.join(bytes(snap.banks[i]) for i in range(8))).hexdigest()
    if key not in _IMAGES:
        out = [bytes(snap.read(a) or 0 for a in range(65536))]
        prev = None
        for lv in UNPACK_LEVELS:
            data, prev = unpack(snap, lv, prev)
            out.append(data)
        if hashlib.sha256(b''.join(out)).hexdigest() != DECODED_SHA256:
            raise ValueError('the unpacked levels differ from the original game (not the R-Type snapshot this build knows)')
        _IMAGES[key] = out
    return _IMAGES[key]


def image_of(level):
    """Which images() entry a corpus level byte's graphics are read from (0x30 = text, 0x39 = level 9 (the 8th unpack))."""
    return {0x30: 0, 0x39: 8}.get(level, level - 0x30)


# ---------------------------------------------------------------- the figure corpus, without graphics

def catalogue_from(corpus):
    """The corpus (capture_assets / normalize_assets output) -> the committed catalogue: cells keep level, address
    and ink only; plots point at cells by index. Run by the maintainer from the intake corpus."""
    cells = list(corpus['cells'])
    index = {k: i for i, k in enumerate(cells)}
    return {'schema': 1, 'game': 'r_type',
            'note': 'R-Type figure geometry (games/r_type.md): per cell level byte, graphics address, ink; the attribute '
                    'and bits are read from the player\'s snapshot (images()), never stored here.',
            'levels': corpus['levels'], 'normalization': corpus['normalization'],
            'cells': [[c['level'], c['address'], c['ink']] for c in corpus['cells'].values()],
            'plots': [[k, p['level'], p['address'], p['w'], p['h'], [[x, y, index[c]] for x, y, c in p['cells']]]
                      for k, p in corpus['plots'].items()],
            'figures': corpus['figures']}


def corpus(snap, catalogue=None):
    """The figure corpus as the colour build reads it, cells' attribute and bits from the snapshot's levels."""
    cat = catalogue or json.loads(gzip.decompress(CATALOGUE.read_bytes()))
    imgs = images(snap)
    cells, keys = {}, []
    for lv, addr, ink in cat['cells']:
        im = imgs[image_of(lv)]
        bits = list(im[addr + 1:addr + 9])
        k = '%02x:%04x:%x:%s' % (lv, addr, ink, bytes(bits).hex())
        cells[k] = {'level': lv, 'address': addr, 'ink': ink, 'attribute': im[addr], 'bits': bits}
        keys.append(k)
    plots = {k: {'level': lv, 'address': addr, 'w': w, 'h': h, 'cells': [[x, y, keys[i]] for x, y, i in cl]}
             for k, lv, addr, w, h, cl in cat['plots']}
    return {'levels': cat['levels'], 'normalization': cat['normalization'], 'cells': cells, 'plots': plots,
            'figures': cat['figures']}


def catalogue_md5():
    return hashlib.md5(CATALOGUE.read_bytes()).hexdigest()


# ---------------------------------------------------------------- the snapshot the colour tools read

_SOURCE = None


def set_source(z80):
    """The player's R-Type snapshot (path or zt.Z80Snapshot) for corpus() / the colour tools."""
    global _SOURCE
    snap = Z.Z80Snapshot(str(z80)) if isinstance(z80, (str, Path)) else z80
    if not is_r_type(snap):
        raise ValueError('not the R-Type 128K snapshot this engine knows')
    _SOURCE = snap
    return snap


def source():
    if _SOURCE is None:
        path = os.environ.get('NEXCLASH_R_TYPE_Z80')
        if not path:
            raise ValueError('R-Type colour tools need the snapshot: set NEXCLASH_R_TYPE_Z80 to the .z80')
        set_source(path)
    return _SOURCE


# ---------------------------------------------------------------- side inputs (game data, never in this repo)

LOAD_SCREEN = 'r_type_loading.scr'            # the tape's 6,912-byte loading screen
LOAD_MD5 = 'acab5a1b9643d14c02284e057bc16854'
SHOWPIECE = 'r_type_showpiece.png'             # the owner's neon-glow 320x256 picture of the specification screen
SHOWPIECE_MD5 = '3023611302798e3bb5998fa42a77b2e3'


def side_input(z80, name, md5):
    """A file beside the snapshot, or None. A different file under that name is refused."""
    path = Path(z80).resolve().parent / name
    if not path.is_file():
        return None
    if hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise ValueError('%s is not the expected file (MD5 %s)' % (name, md5))
    return path


# ---------------------------------------------------------------- the build

SLOT1_BANK = 24                 # hook page (bank 12 low half), slot 1 while the game runs
PACE = 4                        # 8690: the game's frame-count compare (original 3)
# The level unpack (8F40) writes 7FFD, which on the Next maps ROM over slots 0-1 and hides the hook page until
# something maps it back; its return (8F4E) jumps to a copy in 5C4C..5C59 (printer-buffer bytes the game never
# touches) that maps bank 24 back before EI.
RAMFIX = [(0x5C4C, None, '01fd7f3e10ed79ed9151%02x37fbc9' % SLOT1_BANK),
          (0x8F4E, '01fd7f', 'c34c5c')]
# FE03 without its tape prompts (REWIND SIDE 2, LOADING R TYPE LEVEL n, LOADED OK, STOP TAPE and their key
# waits). The 128K game unpacks each level from its own memory (8F1F), so the loads stay.
NOTAPE = [(0xFE22, '200e', '180e'),            # JR NZ,FE32 -> JR FE32: no REWIND SIDE 2 + key
          (0xFE39, '0e01', '1820'),            # LD C,1 -> JR FE5B: no LOADING ... + key, no tape text
          (0xFE76, 'cdc5c2', '181000'),        # CALL C2C5 -> JR FE88: no level text
          (0xFE96, 'cd', 'c9'),                # CALL C2C5 -> RET: no LOADED OK, STOP TAPE + key
          (0xFE16, 'cd4d8a', '000000')]        # CALL 8A4D -> nothing: the title plays the logo animation again


def hooks():
    """{'code', 'glide', 'ship': bytes, 'syms': {name: address}} from the profile."""
    h = load_profile()['hooks']
    return {'code': bytes.fromhex(h['code']), 'glide': bytes.fromhex(h['glide']), 'ship': bytes.fromhex(h['ship']),
            'syms': {k: int(v, 16) if isinstance(v, str) else v for k, v in h['syms'].items()}}


def sites():
    """[(address, original bytes, opcode, hook symbol)] for every hook site."""
    return [(int(a, 16), bytes.fromhex(o), int(op, 16), lab) for a, o, op, lab in load_profile()['sites']]


def scenery_banks():
    """Banks 16-23: per level 1-8 the scenery see-through masks (r_type_masks): page 2n-2 of the bank pair = count +
    sorted 9-byte keys (attribute with the scenery bit, 8 bytes as drawn), next page the 8-byte masks in the same
    order (r_type_l2scroll.asm mask_find); key page 8190 = the level's first paint record (r_type_scenery)."""
    from . import r_type_masks as SM
    out, first = {}, 0
    for level, (table, stats) in sorted(SM.all_levels().items()):
        keys = sorted(table)
        assert len(keys) <= (8192 - 4) // 9 and len(keys) <= 1024, (level, len(keys))
        kp, mp = bytearray(8192), bytearray(8192)
        kp[0:2] = bytes([len(keys) & 255, len(keys) >> 8])
        kp[8190:8192] = bytes([first & 255, first >> 8])
        first += len(keys)
        for n, k in enumerate(keys):
            kp[2 + 9 * n:11 + 9 * n] = bytes([k[0]]) + bytes(k[1])
            mp[8 * n:8 * n + 8] = bytes(table[k])
        out[15 + level] = bytes(kp + mp)
    return out


def behind_flags():
    """Bank 13 low page: (level, graphic lo, hi) per figure drawn behind the scenery (docs/profiles/r_type_behind.json)."""
    out = bytearray()
    for f in json.loads(BEHIND.read_text())['flags']:
        if f['on']:
            g = int(f['graphic'], 16)
            out += bytes([int(f['level'], 0), g & 255, g >> 8])
    assert len(out) < 8192, 'too many behind-scenery flags'
    return bytes(out + bytes(8192 - len(out)))


class Plain:
    """The converter's patch interface; restores the snapshot's printer buffer (the converter's tail uses it)."""
    name = 'R-Type plain printer restoration'
    uses_printer_buffer = False
    hook_page_data = b''
    extra_banks = {}
    sites = []
    slot1 = None
    setup_call = Z.STUB_ORG + 0x1000
    stub_extra = b''

    def apply(self, snap):
        printer = bytes(snap.read(a) for a in range(0x5B00, 0x5C00))
        self.stub_extra = (b'\x21' + Z.w16(self.setup_call + 12) + b'\x11\x00\x5B'
                           + b'\x01\x00\x01\xED\xB0\xC9' + printer)
        assert len(self.stub_extra) == 268


class Patch(Plain):
    """The full build: hooks, colour tables, scenery masks, behind flags, glide, ship, showpiece."""
    name = 'R-Type Layer 2 scroll and sprites (not verified)'
    slot1 = (SLOT1_BANK, 0x3E00)

    def __init__(self, z80, colours=None, showpiece=True):
        from . import r_type_colour as RC
        snap = set_source(z80)
        h = hooks()
        self.syms = h['syms']
        self.hook_page_data = h['code']
        banks = {12: h['code']}
        cbanks, self.colour_info = RC.tables(RC.load_colours() if colours is None else colours)
        banks.update(cbanks)
        glide = h['glide']
        banks[13] = behind_flags() + bytes(0x100) + glide + bytes(8192 - 0x100 - len(glide))
        ship = h['ship']
        banks[63] = bytes(8192) + bytes(0x100) + ship + bytes(8192 - 0x100 - len(ship))
        banks.update(scenery_banks())
        self.showpiece = False
        if showpiece:
            src = side_input(z80, SHOWPIECE, SHOWPIECE_MD5)
            if src:
                from . import r_type_intro as I, r_type_showpiece as SP
                SP.SOURCE, SP.ORIGINAL = src, I.spec_image(snap)
                sp = SP.build()[0]
                cop = sp.pop(SP.COPPER_BANK)[:2049]     # mode byte, then the palette (glide page at 1800, COPPER_AT)
                banks.update(sp)
                b13 = bytearray(banks[13])
                b13[8192 + 0x17FF:8192 + 0x2000] = cop
                banks[13] = bytes(b13)
                self.showpiece = True
        self.extra_banks = banks

    def apply(self, snap):
        super().apply(snap)
        backup = self.stub_extra[12:]
        setup = bytearray(self.stub_extra[:11] + Z.nextreg(0x51, SLOT1_BANK) + b'\xCD'
                          + Z.w16(self.syms['hook_setup']) + b'\xC9')
        setup[1:3] = Z.w16(self.setup_call + len(setup))
        self.stub_extra = bytes(setup) + backup

        def patch(addr, old, new):
            bank, base = (5, 0x4000) if addr < 0x8000 else (2, 0x8000) if addr < 0xC000 else (0, 0xC000)
            data = bytearray(snap.banks[bank])
            if old is not None:
                assert bytes(data[addr - base:addr - base + len(old)]) == old, 'R-Type site %04X' % addr
            data[addr - base:addr - base + len(new)] = new
            snap.banks[bank] = bytes(data)
        for addr, old, op, label in sites():
            patch(addr, old, bytes([op]) + Z.w16(self.syms[label]))
        patch(0x868F, bytes([0xFE, 3]), bytes([0xFE, PACE]))
        for addr, old, new in RAMFIX:
            patch(addr, old and bytes.fromhex(old), bytes.fromhex(new))
        for addr, old, new in NOTAPE:
            patch(addr, bytes.fromhex(old), bytes.fromhex(new))


def build(z80, nex, colours=None, showpiece=True):
    """The game .nex (no intro, no loading screen). -> the Patch used."""
    p = Patch(z80, colours, showpiece)
    Z.convert(str(z80), str(nex), tail_req=0x5B00, force50=True, quiet=True, patch=p)
    return p


# ---------------------------------------------------------------- engine contract

def _profile_path():
    return PROFILE


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """No simulator proof yet (games/r_type.md "Next session"): the hooks own the display and the Layer 2 / sprite
    model for them is the next stage."""
    raise NotImplementedError('R-Type: no differential verifier yet; the build is emulator-tested only (games/r_type.md)')


def unit_tests(patch, states, neg=True):
    raise NotImplementedError('R-Type: no unit tests yet (games/r_type.md)')


# colour sheets and recolour work on the game build (NAME_game.nex): the intro build carries the game's banks as data
from .r_type_colour import (RECOLOUR, COLOURS, load_colours, colour_identity, nex_peek,  # noqa: E402
                            recolour, sheets)


def auto(a, z80, name, out, say):
    """nexclash.py auto: NAME_game.nex (the game: Layer 2 scroll, sprites, glide, battleship tilemap, the showpiece when
    its picture is beside the snapshot) and NAME_sprites.nex (the intro in front of it: the animated R-9 specification
    screen, the tape's loading screen when it is beside the snapshot). Not verified: no recording is replayed."""
    from . import r_type_intro as I
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not getattr(a, 'publisher', None):
        a.publisher = PUBLISHER
    if hashlib.md5(Path(z80).read_bytes()).hexdigest() != SOURCE_MD5:
        say('Snapshot  : not the snapshot this build was made from (MD5 %s); building anyway' % SOURCE_MD5)
    say('Game      : R-Type (Electric Dreams, 1988, 128K)')
    say('Engine    : r_type; play area on Layer 2 (scroll, scenery colours), figures as hardware sprites, ship glide, '
        'level 3 battleship tilemap; the original logic unchanged')
    game = out / (name + '_game.nex')
    p = build(z80, game)
    say('Game      : %s  %s' % (game.name, hashlib.md5(game.read_bytes()).hexdigest()))
    say('Colours   : %s' % ', '.join('%s %s' % kv for kv in p.colour_info.items()))
    say('Showpiece : %s' % ('the owner\'s picture (%s)' % SHOWPIECE if p.showpiece else
                            'no %s beside the snapshot: the original specification screen only' % SHOWPIECE))
    screen = side_input(z80, LOAD_SCREEN, LOAD_MD5)
    say('Loading   : %s' % ('the tape\'s loading screen (%s)' % LOAD_SCREEN if screen else
                            'no %s beside the snapshot: the intro starts on a black screen' % LOAD_SCREEN))
    say('Intro     : rendering the R-9 (about 2 minutes)')
    files = I.data(source(), say)
    full = out / (name + '_sprites.nex')
    full.write_bytes(I.combine(game.read_bytes(), files, screen.read_bytes() if screen else None))
    say('Sprites   : %s  %s  (intro + game)' % (full.name, hashlib.md5(full.read_bytes()).hexdigest()))
    (out / (name + '_outputs.json')).write_text(json.dumps({'default': full.name}, indent=1) + '\n')
    say('Boot      : not simulated (128K intro + game; emulator smoke test, games/r_type.md)')
    say('Verify    : none: not verified (emulator evidence only; games/r_type.md "Evidence")')
    say('Result    : BUILT, NOT VERIFIED')
    return True
