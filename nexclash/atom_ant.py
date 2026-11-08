"""Atom Ant (Hi-Tec, 1990): the 128K form of the tape, unchanged.

The play area is white on black: no colour clash to remove, so there are no hooks and the game's code runs as it is.
The tape's last block, the AY music, loads only on a 128K machine, so the .z80 in the archive (a 48K dump) has none: the start
state is the tape loaded on a 128K machine, stopped at 9FF4, the game's own start after the music has loaded.
"""
from pathlib import Path
import hashlib
from . import z80tonex as zt

TAPE_MD5 = '404e992b4edceb10ef8fae9dfaac364b'
START_MD5 = None                   # set by the review run: the start state is derived, never in this repo
START_PC = 0x9FF4
SIGNATURE = {0x9FF4: '31BF5D', 0x9E4A: 'CD71A7', 0xAB76: '3A5C5B', 0xA184: 'ED73F7A1'}
PUBLISHER = 'Hi-Tec, 1990'
DECISIONS = {'figures': 'none: white on black, as the original', 'scenery': 'as the original', 'pace': 'original; no hooks',
             'outline': 'none: figures have their own black masks', 'enhanced': 'waiting for the mock-up'}


def is_atom_ant(snap):
    """The tape's 128K start state: bank 2 holds the code, bank 3 the music."""
    if not getattr(snap, 'is128', False):
        return False
    try:
        if snap.banks[3][0xE75E - 0xC000:0xE75E - 0xC000 + 4] != bytes.fromhex('21000FCD'):
            return False
        return all(bytes(snap.banks[2][a - 0x8000:a - 0x8000 + len(v) // 2]) == bytes.fromhex(v) for a, v in SIGNATURE.items())
    except (KeyError, TypeError, IndexError):
        return False


class Patch:
    """No hooks, no changed bytes: the start state checked, then converted."""
    name = 'Atom Ant 128K: the original, with its AY music'
    uses_printer_buffer = False
    hook_page_data = b''
    setup_call = None
    stub_extra = b''
    extra_banks = {}

    def __init__(self, source=None):
        self.source = str(source) if source else None

    def apply(self, snap):
        if not is_atom_ant(snap):
            raise ValueError('Not the 128K start state of Atom Ant (tape MD5 %s)' % TAPE_MD5)


def build(source, destination):
    p = Patch(source)
    zt.convert(str(source), str(destination), patch=p, quiet=True)
    return p


def loading_nex(nex, screen):
    """A built .nex -> the same with the loading screen in the NEX file (header byte 10 = 2)."""
    if len(screen) != 6912 or nex[10] != 0:
        raise ValueError('Expected a .nex without a screen and a 6,912-byte loading screen')
    head = bytearray(nex[:512])
    head[10] = 2
    return bytes(head) + screen + nex[512:]
