"""Jilly's Farm Volume 1 - SokoBAArn! (Bob's Stuff, 2017, 48K): the original game on the Next, no figures moved.

Every level's play area is one colour on black (bright white), so the game has no colour clash there. The default is the
original picture. The build owns the ROM (Sinclair's 48K ROM as the whole alt ROM) so the game runs the same on any
NextZXOS. No hook, no site, not one game byte changes. See games/jillys_farm.md.
"""
from pathlib import Path
import json
from . import z80tonex as zt

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'docs/profiles/jillys_farm.json'
SOURCE_MD5 = '86a5e1dc43e4cfe45582e91eb7cd1cf3'
REGBLOCK = 0x3C00
REGS_LEN = 20
PAGE = 25
SIGNATURE = {0x8200: '31C0FEF33E80ED47ED5EFB', 0x8181: 'F5E5218FA134', 0x83A8: 'C34C83'}
DECISIONS = {'figures': 'unchanged: monochrome play area', 'scenery': 'unchanged', 'pace': 'original: no hook', 'outline': 'none',
             'enhanced': 'waiting for the mock-up'}
CMP = ()


def _profile_path():
    return PROFILE


def load_profile():
    return json.loads(PROFILE.read_text())


def is_jillys(snap):
    try:
        mem = snap.memory if hasattr(snap, 'memory') else (bytes(16384) + snap.banks[5] + snap.banks[2] + snap.banks[0])
        return all(bytes(mem[a:a + len(bytes.fromhex(v))]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (AttributeError, KeyError, TypeError, IndexError):
        return False


class Patch:
    name = "Jilly's Farm: the original game, Sinclair ROM as the whole alt ROM"
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
        if not is_jillys(snap):
            raise ValueError("Not the supported Jilly's Farm release (MD5 %s)" % SOURCE_MD5)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


def verify(patch, rzx_path, stop=None, collect=0, progress=None):
    """No hook: what can differ is the ROM and the tail; nextboot.rom_paths replays the original against the .nex."""
    from collections import Counter
    c = Counter(hooks=0)
    if patch.sites:
        c['a site in a no-hook build!'] += 1
    return (c, {}, []) if collect else (c, {})


def unit_tests(patch, states, neg=True):
    from collections import Counter
    return Counter()
