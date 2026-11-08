"""Scooby Doo in the Castle Mystery (Elite, 1986, 48K): the original game on the Next, no figures moved.

Its play area is one colour pair throughout, so the game never had colour clash; figures carry their own masks.
The default is the original picture. The build owns the ROM (Sinclair's 48K ROM as the whole alt ROM) so the
game and its BASIC loader run the same on any NextZXOS. No hook, no site, not one game byte changes. See
games/scooby_doo.md.
"""
from pathlib import Path
import json
from . import z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/scooby_doo.json'
SOURCE_MD5 = '8a82e06f6829a2a1c30781491cfbc42e'
REGBLOCK = 0x3C00                  # in Sinclair's unused 0x386E-0x3CFF: the stub writes the start-up registers here
REGS_LEN = 20
PAGE = 25
SIGNATURE = {0x73AB: '21B961', 0x75B1: '21C06C35C0', 0x7320: 'ED73DD703AB861'}
DECISIONS = {'figures': 'unchanged: monochrome play area, figures have their own masks', 'scenery': 'unchanged',
             'pace': 'original: no hook', 'outline': 'none', 'enhanced': 'waiting for the mock-up'}
CMP = ()                           # no hook: nothing runs instead of the game's code


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_scooby_doo(snap):
    try:
        mem = snap.memory if hasattr(snap, 'memory') else (bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0])
        return all(bytes(mem[a:a + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class Patch:
    name = 'Scooby Doo: the original game, Sinclair ROM as the whole alt ROM'
    uses_printer_buffer = False
    keep_printer_buffer = True
    hook_page_data = b''
    stub_extra = b''
    setup_call = None
    sites = ()

    def __init__(self, source=None):
        self.source = str(source) if source else None
        rom = zt.rom48()
        self.page = bytearray(rom[0x2000:0x4000])
        self.slot1 = (PAGE, REGBLOCK)
        self.altrom = (REGBLOCK, REGBLOCK + REGS_LEN)
        self.extra_banks = {PAGE // 2: bytes(8192) + bytes(self.page)}

    def apply(self, snap):
        if not is_scooby_doo(snap):
            raise ValueError('Not the supported Scooby Doo release (MD5 %s)' % SOURCE_MD5)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """No hook: what can differ is the ROM and the tail. nextboot.rom_paths replays the original and compares every ROM
    byte it runs or reads, and the tail bytes it reads, against the .nex (work/replay.py); here the game's bytes."""
    from collections import Counter
    c = Counter(hooks=0)
    if patch.sites:
        c['a site in a no-hook build!'] += 1
    return (c, {}, []) if collect else (c, {})


def unit_tests(patch, states, neg=True):
    from collections import Counter
    return Counter()
