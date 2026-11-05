#!/usr/bin/env python3
"""Make and apply .nxc v1 files; the reference the Z80 loader (firmware/nexclash.asm) must match
byte for byte. See spec/NXC-FORMAT.md.

    nxc.py PATCH [GAME] [-o OUT] [--trainer NAME_OR_NUMBER ...] [--original] [--colours NAME]
    nxc.py make NEX GAME -o OUT [--zxdb ENTRY] [--title T] [--publisher "Ocean, 1986"] [--patch-by N] [--colours-by N]
                 [--fix-label TEXT] [--patch-version V] [--rom 0|1|2] [--highest-bank N] [--proof KEY=VALUE ...] [--proof-file F] [--colours NAME=NEX ...] [--language NAME=NEX ...]
    nxc.py make NEX TAPE --start START.z80 -o OUT [--tape-bank N ...] [--residual-max N] [as above]
    nxc.py add-dump PATCH KNOWN_GAME NEW_DUMP -o OUT [--file NAME] [--zxdb ENTRY] [--title TITLE]   (also add-target)
    nxc.py import-pok PATCH POK GAME -o OUT [--publisher "Ocean, 1986"] [--only "Name,Name"] [--top-bank 0-7]
    nxc.py credit PATCH GAME -o OUT [--patch-by NAME] [--colours-by NAME]
    nxc.py version PATCH GAME VERSION -o OUT   (the patch's own version, such as 1.0, shown as v1.0; '' removes it)
    nxc.py help PATCH GAME -o OUT --line KEY=TEXT ...   (the menu's help: fix, colours, language, trainer_N, toggle_N)
    nxc.py handoff-bas -o NXCHAND.BAS

Applying writes a .nex that carries its menu: it shows the menu when it starts, with any choices given here already on,
and applies what is chosen then. --bare writes one without it, with the choices given here fixed in it.

Applying, listing, adding a target, importing cheats and crediting need only Python 3's standard library. Making a
patch, or anything else that compresses, needs the zx0 compressor: set NXC_ZX0_DIR to its folder.
"""
import hashlib, os, re, struct, subprocess, sys, tempfile, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
ZX0_DIR = os.environ.get('NXC_ZX0_DIR', os.path.join(HERE, 'zx0bin'))
MAGIC = b'NXC1'; ORDER = [5, 2, 0, 1, 3, 4, 6, 7] + list(range(8, 112)); BANK = 16384; DROP = 256
HEADER = 38; NONCE_AT = 6; CHECK_AT = 22; CHECK_SIZE = 16; MASTER_SIZE = 16
WRAP_CHECK = b'NXC1-KEY'; WRAP_SIZE = 24; TARGET_FIXED = 30; KEY_ROUNDS = 16
KIND_Z80 = 1; KIND_SNA = 2; KIND_TAP = 3; KIND_TZX = 4
KIND_NAMES = {KIND_Z80: 'z80', KIND_SNA: 'sna', KIND_TAP: 'tap', KIND_TZX: 'tzx'}
SNAPSHOT_KINDS = (KIND_Z80, KIND_SNA); TAPE_KINDS = (KIND_TAP, KIND_TZX)
LOADER_LEVEL = 3                                   # this tool does all there is; the Z80 loader is level 2
OPT_TAPE = 1; OPT_TAPE_SET = 2; LOADER_FLAGS = OPT_TAPE | OPT_TAPE_SET   # OPT1 byte 1: what a patch needs besides its level; this tool reads tapes and sets of them
KIND_SET = 0x80; SET_FILES_MAX = 8; FILE_SHIFT = 12; BLOCK_MASK = 0x03FF   # a target of several tape files; a copy's file index, above its block
TAPE_TAG = b'TAP1'; TAPE_TABLE_MAX = 24576; RESIDUAL_MAX = 8192; TAPE_BLOCKS_MAX = 1024   # a tape table, and the data blocks it may name
START_SIZE = 55; COPY_SIZE = 10; TAPE_FIXED = 2; MIN_RUN = 16        # a .z80 v2 header; one copy; a TAP1's clear head
SCREEN_SIZES = ((1, 49152), (2, 6912), (4, 12288), (8, 12288), (16, 12288)); SCREEN_MAX = 92928; SCREEN_CHUNK = BANK
TARGETS_MAX = 32; FILE_NAME_MAX = 127
SITE_TABLE_MAX = 24576  # what a Next loader holds: three 8K pages
TRAINER_NAME_MAX = 25; TRAINER_POKES_MAX = 255; TRAINERS_SHOWN = 8; POKES_HELD = 128
SET_NAME_MAX = 25; SETS_MAX = 256
SET_TAG = b'SET2'; SET_STREAM = b'SEB'; SET_CRC_INDEX = 255   # a set's streams: tag SEB and its index; index its bank, or 255 for its CRC
BITMAP = BANK // 8; SET_CHUNK_MAX = BITMAP + BANK; SET_CHUNK_HEAD = 3   # a bank's chunk: a bit for each byte, then the bytes whose bits are set
KIND_COLOURS = 1; KIND_LANGUAGE = 2; KIND_TOGGLE = 3; KIND_TOGGLE_LOGIC = 4; TOGGLES_MAX = 4
KIND_NAMES_SET = {KIND_COLOURS: 'colours', KIND_LANGUAGE: 'language', KIND_TOGGLE: 'toggle', KIND_TOGGLE_LOGIC: 'toggle'}
TOGGLE_KINDS = (KIND_TOGGLE, KIND_TOGGLE_LOGIC)
BASE_SPRITE = 1; BASE_PLAIN = 2                    # the sprite build; the plain game, reserved
SET_FIXED = 5; SET_CRC = 4
TEXT_READ = 252; CREDIT_NAME = 32  # what a loader reads of INF1, and keeps of a name
FIX_LABEL = 'Colour clash fix'; FIX_LABEL_MAX = 25; MENU_KEYS = ('publisher', 'patch_by', 'colours_by', 'fix_label', 'version')   # the main line's name without INF1's fix_label
VERSION_MAX = 8; DESC_FIXED = 1; DESC_VERSION = 2   # INF1's version, shown as v and it; the description's flags
CREDIT = "Built with NexClash by Dean Woodyatt (Bleugh.biz, bleughb/nexclash, GPL-3.0-or-later)"
PROOF_KEYS = ('replay', 'replay_when', 'emulator', 'emulator_when', 'hardware', 'hardware_when', 'coverage', 'coverage_when',
              'display_samples', 'display_exact', 'display_misses', 'display_approved', 'display_model', 'display_when',
              'timing', 'timing_when')

class Wrong(ValueError):
    """The file cannot be applied to this snapshot."""

def absorb(state, data):
    """The one mixing step. state: [s, i, j]."""
    s, i, j = state
    for b in data:
        i = (i + 1) & 255; j = (j + s[i] + b) & 255; s[i], s[j] = s[j], s[i]
    state[1], state[2] = i, j

class Stream:
    """An RC4-style state and the streams made from it. The base is keyed by dump_state or key_state. Each use has its
    own tag and index absorbed into a copy of the base, so a loader can skip a block it does not know."""
    def __init__(self, base):
        self.base = base
    def start(self, tag, index=0):
        """A copy of the base with tag and index absorbed: [s, i, j]."""
        st = [list(self.base[0]), self.base[1], self.base[2]]
        absorb(st, tag + bytes((index,)))
        return st
    @staticmethod
    def output(st, data):
        """data XORed with the state's next output bytes."""
        s, i, j = st; out = bytearray(len(data))
        for n, b in enumerate(data):
            i = (i + 1) & 255; j = (j + s[i]) & 255; s[i], s[j] = s[j], s[i]
            out[n] = b ^ s[(s[i] + s[j]) & 255]
        st[1], st[2] = i, j
        return bytes(out)
    def block(self, tag, index=0):
        """The xor function for one use: tag and index absorbed, 256 bytes dropped."""
        st = self.start(tag, index)
        self.output(st, bytes(DROP))
        return lambda data: self.output(st, data)

def fresh_state():
    return [list(range(256)), 0, 0]

def dump_state(nonce, game):
    """Keyed by one whole dump: nonce, the file (a set's files in order), nonce."""
    st = fresh_state(); absorb(st, nonce + keyed_bytes(game) + nonce)
    return Stream(st)

def key_state(nonce, master):
    """Keyed by the patch's master key: nonce, key, nonce, 16 times. One pass of 48 bytes would leave about 173 of the
    256 entries at their starting values, measured; 8 passes reach what a random permutation shows, and 16 is double that."""
    st = fresh_state(); absorb(st, (nonce + master + nonce) * KEY_ROUNDS)
    return Stream(st)

def check_value(f, st):
    """The file's keyed check: all of it but the check field, absorbed after CHK1 and index 0 under the master state."""
    s = st.start(b'CHK1')
    absorb(s, f[:CHECK_AT]); absorb(s, f[HEADER:])
    Stream.output(s, bytes(DROP))
    return Stream.output(s, bytes(CHECK_SIZE))

def zx0(data):
    if not os.path.exists(os.path.join(ZX0_DIR, 'zx0')):
        raise Wrong('making a patch needs the zx0 compressor: set NXC_ZX0_DIR to its folder')
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, 'i'), os.path.join(d, 'o')
        open(a, 'wb').write(data)
        subprocess.run([os.path.join(ZX0_DIR, 'zx0'), '-f', a, b], check=True, capture_output=True)
        return open(b, 'rb').read()

def unzx0(src, limit=BANK):
    """Decode a ZX0 (version 2) stream, as firmware/nexclash.asm does, with the same checks: at most limit bytes
    out, no copy from before the start of the output, no read past the input, and the input used up exactly."""
    out = bytearray(); i = 0; a = 0x80; last = 1
    def byte():
        nonlocal i
        if i >= len(src): raise Wrong('compressed block is damaged')
        i += 1
        return src[i - 1]
    def bit():
        nonlocal a
        carry = a >> 7; a = a << 1 & 255
        if a == 0:
            b = byte(); carry = b >> 7; a = (b << 1 | 1) & 255
        return carry
    def elias(n=1):
        while not bit():
            n = n << 1 | bit()
            if n > 0xFFFF: raise Wrong('compressed block is damaged')
        return n
    def copy(n):
        if last > len(out) or len(out) + n > limit: raise Wrong('compressed block is damaged')
        for _ in range(n): out.append(out[-last])
    while True:
        n = elias()                                 # literals
        if len(out) + n > limit or i + n > len(src): raise Wrong('compressed block is damaged')
        out += src[i:i + n]; i += n
        if not bit():
            copy(elias())                           # the last offset again
            if not bit(): continue
        while True:                                 # a new offset
            c = 0xFE
            while not bit():
                c = (c << 1 | bit()) & 255
            c = (c + 1) & 255
            if c == 0:
                if i != len(src): raise Wrong('compressed block is damaged')
                return bytes(out)
            low = byte(); last = 0x10000 - (0x8000 | c >> 1 << 8 | (c & 1) << 7 | low >> 1)
            n = (1 if low & 1 else elias(1 << 1 | bit())) + 1
            if n > 0xFFFF: raise Wrong('compressed block is damaged')
            copy(n)
            if not bit(): break

def sna_places(data):
    """(is128, 7FFD, {bank: its offsets in the file}) of a .sna: 27 bytes of registers, then 48K as banks 5, 2 and the one
    paged at 0xC000. A 128K file adds PC, 7FFD and a TR-DOS byte, then the banks in rising order other than 5, 2 and the
    paged one. A paged bank 5 or 2 is in the file twice, which is why there are two 128K lengths."""
    if len(data) == 27 + 3 * BANK:
        return False, 0, {5: [27], 2: [27 + BANK], 0: [27 + 2 * BANK]}
    if len(data) not in (131103, 147487): raise ValueError('a .sna is 49179, 131103 or 147487 bytes, not %d' % len(data))
    port = data[27 + 3 * BANK + 2]; top = port & 7; places = {5: [27], 2: [27 + BANK]}
    places.setdefault(top, []).append(27 + 2 * BANK)
    rest = [b for b in range(8) if b not in (2, 5, top)]
    if 27 + 3 * BANK + 4 + len(rest) * BANK != len(data): raise ValueError('a .sna of this length cannot page bank %d' % top)
    for n, b in enumerate(rest): places[b] = [27 + 3 * BANK + 4 + n * BANK]
    return True, port, places

def unpack_z80(src):
    """A .z80's packing: ED ED n v is n copies of v (n may be 0); an ED with fewer than three bytes after it in the
    stream, or not followed by ED, is itself."""
    out = bytearray(); i = 0; n = len(src)
    while i < n:
        if src[i] == 0xED and i + 3 < n and src[i + 1] == 0xED:
            out += bytes((src[i + 3],)) * src[i + 2]; i += 4
        else:
            out.append(src[i]); i += 1
    return bytes(out)

class Z80Snapshot:
    """A .z80 snapshot, as the spec's "Snapshots" reads it: version 1 (48K, one stream from offset 30), version 2 (an
    extended header of 23) or 3 (any other length), packed or not; banks 0 to 7 of a 128K game, or 5, 2 and 0 of a 48K
    one. Gives the same banks, version, is128 and port7ffd as the reader in Dean Woodyatt's NexClash
    (bleughb/nexclash, nexclash/z80tonex.py), which this replaces so that applying a patch needs no NexClash checkout;
    tests/test_snapshot_reader.py compares the two where NexClash is at hand."""
    def __init__(self, data):
        if isinstance(data, (str, os.PathLike)):
            with open(data, 'rb') as g: data = g.read()
        data = bytes(data)
        if len(data) < 30: raise ValueError('a .z80 is at least 30 bytes')
        h = data[:30]
        self.a, self.f, self.bc, self.hl = h[0], h[1], h[2] | h[3] << 8, h[4] | h[5] << 8
        pc = h[6] | h[7] << 8; self.sp = h[8] | h[9] << 8; self.i = h[10]
        flags12 = h[12] if h[12] != 255 else 1
        self.r = (h[11] & 0x7F) | (flags12 & 1) << 7; self.border = flags12 >> 1 & 7
        self.de, self.bc_, self.de_, self.hl_ = (h[13] | h[14] << 8, h[15] | h[16] << 8, h[17] | h[18] << 8, h[19] | h[20] << 8)
        self.a_, self.f_, self.iy, self.ix = h[21], h[22], h[23] | h[24] << 8, h[25] | h[26] << 8
        self.iff1, self.iff2, self.im = int(h[27] != 0), int(h[28] != 0), h[29] & 3
        self.is128 = False; self.port7ffd = 0; self.port1ffd = 0; self.ay_regs = [0] * 16; self.ay_last = 0; self.banks = {}
        if pc != 0:
            self.version = 1; self.pc = pc; body = data[30:]
            if flags12 & 0x20:
                if body.endswith(b'\x00\xED\xED\x00'): body = body[:-4]
                body = unpack_z80(body)
            if len(body) < 3 * BANK: raise ValueError('48K block is too short (%d bytes)' % len(body))
            self.banks = {5: body[:BANK], 2: body[BANK:2 * BANK], 0: body[2 * BANK:3 * BANK]}
            return
        if len(data) < 32: raise ValueError('the extended header is cut off')
        ext_len = data[30] | data[31] << 8; ext = data[32:32 + ext_len]
        if len(ext) < 23: raise ValueError('the extended header is cut off')
        self.version = 2 if ext_len == 23 else 3; self.pc = ext[0] | ext[1] << 8; hw = ext[2]
        self.is128 = hw in (3, 4) if self.version == 2 else hw in (4, 5, 6, 7, 9, 12, 13)
        if self.version == 3 and hw in (7, 12, 13) and ext_len >= 55: self.port1ffd = ext[54]
        if self.is128: self.port7ffd = ext[3]; self.ay_last = ext[6]; self.ay_regs = list(ext[7:23])
        j = 32 + ext_len
        while j < len(data):
            if j + 3 > len(data): raise ValueError('a page header is cut off')
            size = data[j] | data[j + 1] << 8; page = data[j + 2]; j += 3
            if size == 0xFFFF: block = data[j:j + BANK]; j += BANK
            else: block = unpack_z80(data[j:j + size]); j += size
            if len(block) != BANK: raise ValueError('page %d decompressed to %d bytes' % (page, len(block)))
            if self.is128:
                if 3 <= page <= 10: self.banks[page - 3] = block
            else:
                bank = {8: 5, 4: 2, 5: 0}.get(page)
                if bank is not None: self.banks[bank] = block
        missing = [b for b in (range(8) if self.is128 else (5, 2, 0)) if b not in self.banks]
        if missing: raise ValueError('snapshot is missing RAM banks %s' % missing)

class SnaSnapshot:
    """The banks of a .sna, with the same attributes as Z80Snapshot."""
    version = 0
    def __init__(self, data):
        self.is128, self.port7ffd, places = sna_places(data)
        self.banks = {b: data[at[0]:at[0] + BANK] for b, at in places.items()}

class FileSet(tuple):
    """A tape target of several files, in order: their bytes, with .kinds (each KIND_TAP or KIND_TZX). A single file is bytes."""
    def __new__(cls, files, kinds):
        self = super().__new__(cls, [bytes(x) for x in files]); self.kinds = tuple(kinds)
        if not 2 <= len(self) <= SET_FILES_MAX or len(self.kinds) != len(self) or any(k not in TAPE_KINDS for k in self.kinds):
            raise Wrong('a set of files is 2 to %d tapes, .tap or .tzx' % SET_FILES_MAX)
        return self

def files_of(game, kind=None):
    """[(bytes, kind)] of a game: one file, or each of a FileSet."""
    if isinstance(game, FileSet): return list(zip(game, game.kinds))
    return [(game, kind)]

def keyed_bytes(game):
    """What dump_base absorbs between the nonces: the file, or a set's files one after another, in order."""
    return b''.join(game) if isinstance(game, FileSet) else game

def kind_of_name(name):
    ext = os.path.splitext(name)[1].lower()
    for kind, n in KIND_NAMES.items():
        if ext == '.' + n: return kind
    raise Wrong('%s: a game file is .z80, .sna, .tap or .tzx' % name)

def snapshot_of(game, kind):
    """The snapshot object for a dump's bytes, of the kind its target entry names."""
    try:
        if kind == KIND_SNA: return SnaSnapshot(game)
        return Z80Snapshot(game)
    except (ValueError, IndexError) as e:
        raise Wrong('the game file is damaged: %s' % e)

def snapshot_banks(path):
    with open(path, 'rb') as g:
        return {k: bytes(v) for k, v in snapshot_of(g.read(), kind_of_name(path)).banks.items()}

# ---------------------------------------------------------------- tapes

# The TZX blocks a tape target may hold. A data block: (its head, where in the head its length is, the length's size); its
# bytes follow the head. Any other: (its head, where a count is or None, the count's size, bytes per count), skipped.
TZX_DATA = {0x10: (4, 2, 2), 0x11: (18, 15, 3), 0x14: (10, 7, 3)}
TZX_SKIP = {0x12: (4, None, 0, 0), 0x13: (1, 0, 1, 2), 0x15: (8, 5, 3, 1), 0x18: (4, 0, 4, 1), 0x19: (4, 0, 4, 1),
            0x20: (2, None, 0, 0), 0x21: (1, 0, 1, 1), 0x22: (0, None, 0, 0), 0x23: (2, None, 0, 0), 0x24: (2, None, 0, 0),
            0x25: (0, None, 0, 0), 0x26: (2, 0, 2, 2), 0x27: (0, None, 0, 0), 0x28: (2, 0, 2, 1), 0x2A: (4, 0, 4, 1),
            0x2B: (4, 0, 4, 1), 0x30: (1, 0, 1, 1), 0x31: (2, 1, 1, 1), 0x32: (2, 0, 2, 1), 0x33: (1, 0, 1, 3),
            0x35: (20, 16, 4, 1), 0x5A: (9, None, 0, 0)}
TZX_MAGIC = b'ZXTape!\x1a'

def tape_blocks(tape, kind, limit=None):
    """[(where its bytes start in the file, how many)] for a tape's data blocks, in the order the file stores them, or Wrong.
    A .tap's blocks are all data blocks, empty ones too, each 2 bytes of length then its bytes. A .tzx is TZX_MAGIC, major
    version 1, any minor, then blocks: 0x10, 0x11 and 0x14 are data, the other IDs in TZX_SKIP are skipped, any other ID is
    refused. A block's bytes are as stored: on a standard block the flag byte first and the checksum last. limit: stop once
    that many data blocks are found."""
    out = []; i = 0; end = len(tape)
    def take(at, size):
        if at + size > end: raise Wrong('the tape is damaged: a block runs past its end')
        return int.from_bytes(tape[at:at + size], 'little')
    if kind == KIND_TAP:
        while i < end and (limit is None or len(out) < limit):
            n = take(i, 2); i += 2
            if i + n > end: raise Wrong('the tape is damaged: a block runs past its end')
            out.append((i, n)); i += n
        return out
    if kind != KIND_TZX: raise Wrong('that is not a tape')
    if end < 10 or tape[:8] != TZX_MAGIC or tape[8] != 1: raise Wrong('the tape is not a TZX file of major version 1')
    i = 10
    while i < end and (limit is None or len(out) < limit):
        bid = tape[i]; i += 1
        if bid in TZX_DATA:
            head, at, size = TZX_DATA[bid]
            n = take(i + at, size)
            if i + head + n > end: raise Wrong('the tape is damaged: a block runs past its end')
            out.append((i + head, n)); i += head + n
        elif bid in TZX_SKIP:
            head, at, size, unit = TZX_SKIP[bid]
            n = 0 if at is None else take(i + at, size) * unit
            if i + head + n > end: raise Wrong('the tape is damaged: a block runs past its end')
            i += head + n
        else:
            raise Wrong('the tape has a TZX block of ID 0x%02X, which a tape target cannot hold' % bid)
    return out

def machine_banks(is128):
    return list(range(8)) if is128 else [5, 2, 0]

def start_header(start):
    """The 55-byte .z80 version 2 header TAP1 carries, from a .z80 of the state the build starts from: its registers, IM,
    border, machine (hardware mode 0 for 48K or 3 for 128K), 7FFD and AY registers, and nothing else."""
    snap = snapshot_of(start, KIND_Z80)
    head = bytearray(start[:30]); head[12] = (1 if head[12] == 255 else head[12]) & ~0x20 & 255
    ext = bytearray(23)
    if snap.version == 1:
        ext[0:2] = start[6:8]
    else:
        ext[:] = start[32:55]; ext[4] = 0; ext[5] &= 4
        if not snap.is128: ext[3] = ext[5] = ext[6] = 0; ext[7:23] = bytes(16)
    head[6:8] = b'\0\0'; ext[2] = 3 if snap.is128 else 0
    return bytes(head) + struct.pack('<H', 23) + bytes(ext)

def start_snapshot(header, banks, pokes=()):
    """The .z80 a loader writes for a tape target with the clash fix off: the start header, then the machine's banks as
    whole pages, with the POKEs in place."""
    is128 = header[34] == 3; out = bytearray(header)
    for b, o, v in pokes:
        if b not in machine_banks(is128): raise Wrong('a trainer POKE is in a bank the game does not have')
    pages = ((3 + b, b) for b in range(8)) if is128 else ((8, 5), (4, 2), (5, 0))
    for page, b in pages:
        data = bytearray(banks[b])
        for pb, o, v in pokes:
            if pb == b: data[o] = v
        out += b'\xff\xff' + bytes((page,)) + data
    return bytes(out)

def tape_table(header, crc, copies, sites):
    """A TAP1 table's plain bytes. copies: (block, source offset, length, bank, offset); sites: (bank, offset, bytes)."""
    out = bytearray(header) + struct.pack('<IH', crc, len(copies))
    for k, s, n, b, o in copies: out += struct.pack('<H', k) + s.to_bytes(3, 'little') + struct.pack('<HBH', n, b, o)
    out += struct.pack('<H', len(sites))
    for b, o, d in sites: out += struct.pack('<BHH', b, o, len(d)) + d
    return bytes(out)

def parse_tape_table(table, blocks):
    """A TAP1 table's parts, or Wrong: every rule of the format checked against the tape's data blocks. blocks: a list of
    them, or (tape, kind) to walk it only as far as the highest data block a copy names, as a reader does."""
    if len(table) < START_SIZE + 8: raise Wrong('a tape table is damaged')
    header = table[:START_SIZE]
    if header[6:8] != b'\0\0' or header[30:32] != b'\x17\0' or header[34] not in (0, 3): raise Wrong('a tape table is damaged')
    crc, count = struct.unpack_from('<IH', table, START_SIZE); i = START_SIZE + 6; copies = []; last = (-1, 0)
    if isinstance(blocks, tuple):                     # (tape, kind) or (FileSet, kind): walk each file as far as needed
        files = files_of(*blocks)
        named = [struct.unpack_from('<H', table, i + COPY_SIZE * n)[0] for n in range(count) if i + COPY_SIZE * (n + 1) <= len(table)]
        blocks = []; last_file = max([k >> FILE_SHIFT for k in named], default=0)
        for fi, (tape, kind) in enumerate(files):
            if fi < last_file:                        # a file before the last one named: walked to its end
                blocks.append(tape_blocks(tape, kind))
                if len(blocks[-1]) > TAPE_BLOCKS_MAX: raise Wrong('a tape of a set has more data blocks than a reader walks')
                continue
            mine = [k & BLOCK_MASK for k in named if k >> FILE_SHIFT == fi]
            blocks.append(tape_blocks(tape, kind, min(max(mine, default=-1), TAPE_BLOCKS_MAX - 1) + 1))
    elif blocks and not isinstance(blocks[0], list):
        blocks = [blocks]                             # one file's blocks
    def ordered(b, o, n):
        nonlocal last
        if b >= 112 or n < 1 or o + n > BANK: raise Wrong('a tape table is out of range')
        here = ORDER.index(b)
        if here < last[0] or (here == last[0] and o < last[1]): raise Wrong('a tape table is out of order')
        last = (here, o + n)
    for _ in range(count):
        if i + COPY_SIZE > len(table): raise Wrong('a tape table is damaged')
        k = struct.unpack_from('<H', table, i)[0]; s = int.from_bytes(table[i + 2:i + 5], 'little')
        n, b, o = struct.unpack_from('<HBH', table, i + 5); i += COPY_SIZE
        fi, kb = k >> FILE_SHIFT, k & BLOCK_MASK
        if k & ~(BLOCK_MASK | 7 << FILE_SHIFT) or fi >= len(blocks): raise Wrong('a tape table names a file the target does not have')
        if kb >= len(blocks[fi]) or kb >= TAPE_BLOCKS_MAX or s + n > blocks[fi][kb][1]: raise Wrong('a tape table names bytes the tape does not have')
        ordered(b, o, n); copies.append((k, s, n, b, o))
    if i + 2 > len(table): raise Wrong('a tape table is damaged')
    count = struct.unpack_from('<H', table, i)[0]; i += 2; sites = []; last = (-1, 0)
    for _ in range(count):
        if i + 5 > len(table): raise Wrong('a tape table is damaged')
        b, o, n = struct.unpack_from('<BHH', table, i); i += 5
        if i + n > len(table): raise Wrong('a tape table is damaged')
        ordered(b, o, n); sites.append((b, o, table[i:i + n])); i += n
    if i != len(table): raise Wrong('a tape table is damaged')
    return dict(header=header, crc=crc, copies=copies, sites=sites, is128=header[34] == 3)

class TapeSnapshot:
    """The banks a tape target supplies, from its TAP1 table, as the same attributes NexClash's Z80Snapshot has: the machine's
    banks as the start state has them, and any other bank the table writes. Every byte nothing writes is 0."""
    version = 2
    def __init__(self, tape, kind, table):
        t = parse_tape_table(table, (tape, kind)); files = files_of(tape, kind)
        blocks = [tape_blocks(x, xk, max([c[0] & BLOCK_MASK for c in t['copies'] if c[0] >> FILE_SHIFT == fi], default=-1) + 1)
                  for fi, (x, xk) in enumerate(files)]
        self.header, self.crc, self.is128 = t['header'], t['crc'], t['is128']
        self.port7ffd = self.header[35] if self.is128 else 0
        banks = {b: bytearray(BANK) for b in machine_banks(self.is128)}
        for k, s, n, b, o in t['copies']:
            fi = k >> FILE_SHIFT; at = blocks[fi][k & BLOCK_MASK][0] + s; data = files[fi][0]
            banks.setdefault(b, bytearray(BANK))[o:o + n] = data[at:at + n]
        for b, o, d in t['sites']:
            banks.setdefault(b, bytearray(BANK))[o:o + len(d)] = d
        self.banks = {b: bytes(v) for b, v in banks.items()}
        self.extra = sorted(set(self.banks) - set(machine_banks(self.is128)))
        if zlib.crc32(start_snapshot(self.header, self.banks)) != self.crc: raise Wrong('the game rebuilt from the tape fails its checksum')

def tape_index(tape, blocks, fi=0, index=None):
    """{MIN_RUN bytes: [(block, offset)]} over the tape's data blocks, at most 16 places for each. A block is named with its
    file's index above FILE_SHIFT: file 0's are the block numbers themselves."""
    index = {} if index is None else index
    for k, (at, n) in enumerate(blocks[:TAPE_BLOCKS_MAX]):
        for o in range(n - MIN_RUN + 1):
            places = index.setdefault(tape[at + o:at + o + MIN_RUN], [])
            if len(places) < 16: places.append((fi << FILE_SHIFT | k, o))
    return index

def tape_copies(want, bank, tape, blocks, index, built):
    """Copies taking from the tape every run of MIN_RUN bytes or more of want, a bank's bytes, longest first from each place,
    grown back over bytes not yet taken. Runs of zeros are not looked for: a bank starts as zeros. built gets them.
    tape and blocks: one file's, or lists of them for a set, indexed by the file index in a copy's block field."""
    if not isinstance(tape, list): tape, blocks = [tape], [blocks]
    out = []; i = 0; taken = 0; zero = bytes(MIN_RUN)
    while i <= BANK - MIN_RUN:
        key = bytes(want[i:i + MIN_RUN])
        if key == zero or key not in index: i += 1; continue
        best = None
        for k, o in index[key]:
            t = tape[k >> FILE_SHIFT]; at, n = blocks[k >> FILE_SHIFT][k & BLOCK_MASK]; m = MIN_RUN
            while i + m < BANK and o + m < n and t[at + o + m] == want[i + m]: m += 1
            if best is None or m > best[2]: best = (k, o, m)
        k, o, m = best; t = tape[k >> FILE_SHIFT]; at = blocks[k >> FILE_SHIFT][k & BLOCK_MASK][0]
        while i > taken and o > 0 and t[at + o - 1] == want[i - 1]: i -= 1; o -= 1; m += 1
        out.append((k, o, m, bank, i)); built[i:i + m] = want[i:i + m]; i += m; taken = i
    return out

def residual_sites(want, built, bank):
    """The sites making built into want, joining two that are 4 bytes apart or less."""
    out = []; i = 0
    while i < BANK:
        if want[i] == built[i]: i += 1; continue
        last = i; j = i + 1
        while j < BANK and j - last <= 4:
            if want[j] != built[j]: last = j
            j += 1
        out.append((bank, i, bytes(want[i:last + 1]))); i = last + 1
    return out

def make_tape_table(tape, kind, start, extra=None):
    """(the TAP1 table, a summary) for a tape target: the start state's banks, from start (a .z80), taken from the tape
    wherever it holds them and carried as sites where it does not; and each bank of extra, {bank: its bytes}, taken from
    the tape alone, as a build that keeps a multiload's blocks in memory wants them. What the tape does not hold of an extra
    bank is for SIT1, as any change the build makes."""
    return build_tape_table(tape, kind, start_header(start), snapshot_of(start, KIND_Z80).banks, extra)

def build_tape_table(tape, kind, header, banks, extra=None):
    """make_tape_table, from the start header and the machine's banks as the state the build starts from has them."""
    files = files_of(tape, kind); tapes = [x for x, _ in files]; blocks = [tape_blocks(x, xk) for x, xk in files]; index = {}
    for fi, (x, b_) in enumerate(zip(tapes, blocks)): tape_index(x, b_, fi, index)
    copies = []; sites = []; extra = extra or {}; machine = machine_banks(header[34] == 3)
    for b in extra:
        if b in machine or not 0 <= b < 112: raise Wrong('bank %d cannot be an extra bank of a %s game' % (b, '128K' if header[34] == 3 else '48K'))
    for b in ORDER:
        if b in machine: want = banks[b]
        elif b in extra: want = extra[b]
        else: continue
        built = bytearray(BANK)
        copies += tape_copies(want, b, tapes, blocks, index, built)
        if b in machine: sites += residual_sites(want, built, b)
    crc = zlib.crc32(start_snapshot(header, banks))
    table = tape_table(header, crc, copies, sites)
    held = sum(len(d) for _, _, d in sites)
    return table, dict(copies=len(copies), sites=len(sites), residual=held, table=len(table),
                       from_tape=sum(c[2] for c in copies if c[3] in machine), blocks=sum(len(x) for x in blocks),
                       from_files=[sum(c[2] for c in copies if c[0] >> FILE_SHIFT == fi) for fi in range(len(files))])

# ---------------------------------------------------------------- trainers

def parse_pok(text):
    """The trainers of a .pok: [(name, [(bank field, address, value, original)])]. Y ends the file."""
    out = []; name = None; pokes = []
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if line[0] == 'Y': break
        if line[0] == 'N':
            name = line[1:].strip(); pokes = []
        elif line[0] in 'MZ':
            f = line[1:].split()
            if name is None or len(f) != 4: raise ValueError('bad .pok line: %r' % line)
            pokes.append(tuple(int(x) for x in f))
            if line[0] == 'Z':
                out.append((name, pokes)); name = None
        else:
            raise ValueError('bad .pok line: %r' % line)
    return out

def sentence_case(name):
    """"Infinite Lives" as the menu shows it: "Infinite lives". All-capital words stay."""
    words = name.split(' ')
    return ' '.join(w if i == 0 or w.isupper() else w.lower() for i, w in enumerate(words))

def poke_bank(bank, address, snap, top=None):
    """(16K bank, offset) for a .pok line. Bank field 0 to 7: that bank paged at 0xC000. 8: no paging, so 0x4000 to
    0xBFFF are banks 5 and 2, and 0xC000 up is bank 0 on a 48K game. On a 128K game 8 does not say which bank is at
    0xC000 when the game reads the byte: the snapshot's 7FFD gives the bank paged when it was saved, which can be another
    (Rainbow Islands is saved with bank 1 there and runs its code from bank 0). So that needs top, the bank paged there in
    play, and is refused without it."""
    if not 0x4000 <= address <= 0xFFFF: raise Wrong('a POKE at %d is not in RAM' % address)
    if address < 0x8000: return 5, address - 0x4000
    if address < 0xC000: return 2, address - 0x8000
    if bank == 8 and not snap.is128: bank = 0
    elif bank == 8:
        if top is None:
            raise Wrong('a POKE at %d (0x%04X) has .pok bank 8 on a 128K game: the bank paged at 0xC000 in play need not be '
                        'bank %d, which the snapshot pages; name it in the .pok, or give it with --top-bank'
                        % (address, address, snap.port7ffd & 7))
        bank = top
    if not 0 <= bank <= 7: raise Wrong('a POKE names bank %d' % bank)
    return bank, address - 0xC000

def trn1(name, pokes):
    """One TRN1 block's data, flags 0. pokes: (bank, offset, value)."""
    label = name.encode('ascii')
    if not 1 <= len(label) <= TRAINER_NAME_MAX: raise ValueError('trainer name %r must be 1 to %d characters' % (name, TRAINER_NAME_MAX))
    if not 1 <= len(pokes) <= TRAINER_POKES_MAX: raise ValueError('trainer %r must have 1 to %d POKEs' % (name, TRAINER_POKES_MAX))
    return bytes((0, len(label))) + label + bytes((len(pokes),)) + b''.join(struct.pack('<BHB', *p) for p in pokes)

def parse_trn1(d):
    """(flags, name, [(bank, offset, value)]) from a TRN1 block's data, or Wrong."""
    if len(d) < 3: raise Wrong('a trainer block is damaged')
    size = d[1]
    if size < 1 or size > TRAINER_NAME_MAX or len(d) < 3 + size: raise Wrong('a trainer block is damaged')
    if d[0]: raise Wrong('a trainer block has flags this reader does not know')
    name = d[2:2 + size].decode('ascii', 'replace'); n = d[2 + size]
    if n < 1 or len(d) != 3 + size + 4 * n: raise Wrong('a trainer block is damaged')
    pokes = [struct.unpack_from('<BHB', d, 3 + size + 4 * k) for k in range(n)]
    for b, o, _ in pokes:
        if b >= 112 or o >= BANK: raise Wrong('a trainer POKE is out of range')
    return d[0], name, pokes

def trainers(f):
    """The patch's trainers, readable without the game: [(flags, name, pokes)]."""
    return [parse_trn1(d) for t, d in blocks(f)[1] if t == b'TRN1']

def chosen_pokes(f, chosen):
    """The POKEs of the chosen trainers (their 1-based numbers or names), in the order of the file."""
    every = trainers(f); out = []; want = []
    for c in chosen or ():
        numbers = [k for k, t in enumerate(every) if t[1] == c or str(k + 1) == str(c)]
        if not numbers: raise Wrong('this patch has no trainer %s' % c)
        want += numbers
    for k, t in enumerate(every):
        if k in want: out += t[2]
    return out

def patched_bytes(f, game):
    """What the patch itself decides in the finished build: {bank: None for a whole bank, or the set of offsets}."""
    st, bl = check_key(f, game)[:2]; out = {}
    sit = dict(bl)[b'SIT1']
    if sit:
        table = unzx0(st.block(b'SIT1')(sit), SITE_TABLE_MAX); i = 2
        for _ in range(struct.unpack_from('<H', table)[0]):
            b, o, l = struct.unpack_from('<BHH', table, i); i += 5 + l
            out.setdefault(b, set()).update(range(o, o + l))
    for t, body in bl:
        if t == SET_TAG:
            for b, chunk in read_set(st, parse_set(body))[1]:
                out.setdefault(b, set()).update(chunk_offsets(chunk))
    for t, body in bl:
        if t == b'BNK1': out[body[0]] = None
    return out

def select_trainers(entries, only):
    """The entries of a .pok named in only, a list of names as the .pok or the menu spells them, in the .pok's order.
    It selects and orders nothing else. A name it does not have, or cannot use, is an error."""
    usable = [e for e in entries if not any(v == 256 for _, _, v, _ in e[1])]
    for name in only:
        if not any(name in (e[0], sentence_case(e[0])) for e in entries):
            raise Wrong('this .pok has no trainer called %r' % name)
        if not any(name in (e[0], sentence_case(e[0])) for e in usable):
            raise Wrong('trainer %r asks the player for a value, which a patch cannot hold' % name)
    return [e for e in entries if e[0] in only or sentence_case(e[0]) in only]

def import_pok(f, game_path, pok_text, publisher=None, skipped=None, only=None, top_bank=None):
    """The patch with the trainers of a .pok added and INF1's publisher set: the same nonce and encrypted blocks, with
    a new check value. Refuses a POKE that lands on a byte the patch changes, or on a bank the patch supplies: its target
    there is not the game's own code. Original values in the .pok are not stored.
    only: names of the trainers to import; none: all of them. top_bank: the bank paged at 0xC000 in play, for .pok lines
    with bank 8 there on a 128K game, which are refused without it (see poke_bank)."""
    game = game_path if isinstance(game_path, (bytes, FileSet)) else read_file(game_path)   # a path, or the game itself
    opened = check_key(f, game); st, bl = opened[:2]
    snap = game_snapshot(opened, game)
    header = unzx0(st.block(b'NEX1')(dict(bl)[b'NEX1']), 512); touched = patched_bytes(f, game)
    made = []; entries = parse_pok(pok_text)
    for name, lines in (entries if only is None else select_trainers(entries, only)):
        if any(v == 256 for _, _, v, _ in lines):
            if skipped is not None: skipped.append((name, 'asks the player for a value'))
            continue
        pokes = []
        for bank_field, address, value, original in lines:
            try: b, o = poke_bank(bank_field, address, snap, top_bank)
            except Wrong as e: raise Wrong('%s: %s' % (name, e))
            if not header[18 + b]: raise Wrong('%s: POKE %d is in bank %d, which the build does not have' % (name, address, b))
            if b in touched and (touched[b] is None or o in touched[b]):
                raise Wrong('%s: POKE %d lands on a byte the patch changes' % (name, address))
            have = snap.banks[b][o]
            if original not in (0, have) and skipped is not None:
                skipped.append((name, 'POKE %d: .pok expects %d, this file has %d' % (address, original, have)))
            pokes.append((b, o, value))
        made.append(trn1(sentence_case(name)[:TRAINER_NAME_MAX], pokes))
    names = [parse_trn1(m)[1] for m in made]
    if len(set(names)) != len(names): raise Wrong('two trainers would have one name on the menu')
    out = []
    for t, body in bl:
        if t == b'TRN1': continue
        if t == b'OUT1': out += [[b'TRN1', m] for m in made]
        if t == b'INF1' and publisher:
            text_ = b''.join(l + b'\n' for l in body.split(b'\n') if l and not l.startswith(b'publisher='))
            body = b'publisher=%s\n' % publisher.encode() + text_
            label = next((l[10:] for l in body.split(b'\n') if l.startswith(b'fix_label=')), b'')
            if not fix_label_seen(body, label.decode()): raise Wrong('fix_label must end within the first %d bytes of INF1' % TEXT_READ)
            ver = next((l[8:] for l in body.split(b'\n') if l.startswith(b'version=')), b'')
            if not fix_label_seen(body, ver.decode(), b'version'): raise Wrong('version must end within the first %d bytes of INF1' % TEXT_READ)
        out.append([t, body])
    return seal(f[:CHECK_AT], out, st)

def original_with_pokes(f, game, chosen, path=None):
    """The player's game with the chosen trainers applied; what the loader writes with the clash fix off. With no trainer it
    is the game file itself, unchecked, as the format says. With one, the game must unlock the patch, and a .z80 becomes
    version 2 or 3 with its pages stored whole, under its own header (a version 1 file becomes version 2, 48K; pages other
    than the RAM banks are not kept), and a .sna keeps its layout. A tape, trainer or not, must unlock the patch, and
    becomes the start state's .z80, as its TAP1 has it."""
    if not chosen and not isinstance(game, FileSet) and not any(is_tape(t) and matches(t, game) for t in targets(f)): return game
    opened = check_key(f, game); kind = opened.target['kind'] & ~KIND_SET
    if kind in TAPE_KINDS:
        snap = game_snapshot(opened, game)
        return start_snapshot(snap.header, snap.banks, chosen_pokes(f, chosen))
    if not chosen: return game
    snap = snapshot_of(game, kind)
    banks = {k: bytearray(v) for k, v in snap.banks.items()}
    pokes = chosen_pokes(f, chosen)
    for b, o, v in pokes:
        if b not in banks: raise Wrong('a trainer POKE is in a bank the game does not have')
        banks[b][o] = v
    if kind == KIND_SNA: return sna_with(game, snap, pokes)
    if snap.version == 1:
        head = bytearray(game[:30]); pc = game[6:8]; head[6:8] = b'\0\0'
        head[12] = (1 if head[12] == 255 else head[12]) & ~0x20 & 255
        head += struct.pack('<H', 23) + pc + bytes(21)
    else:
        head = bytearray(game[:32 + (game[30] | game[31] << 8)])
    out = bytes(head)
    pages = ((3 + b, b) for b in range(8)) if snap.is128 else ((8, 5), (4, 2), (5, 0))
    for page, b in pages:
        out += b'\xff\xff' + bytes((page,)) + bytes(banks[b])
    return out

def sna_with(game, snap, pokes):
    """A .sna with POKEs in place, in every place a bank is held."""
    out = bytearray(game); places = sna_places(game)[2]
    for b, o, v in pokes:
        for at in places[b]: out[at + o] = v
    return bytes(out)

def screen_size(flags):
    """The bytes between a .nex's header and its banks, from its byte 10, as .nexload reads them: a palette of 512 unless
    bit 7 is set or a ULA, hi-res or hi-colour screen is there; then each screen listed. Bits 5 and 6 are V1.3's screens."""
    if not flags: return 0
    if flags & 0x60: raise Wrong('a .nex loading screen of V1.3 (byte 10 has bit 5 or 6 set) cannot be packaged')
    return (0 if flags & 0x9A else 512) + sum(n for bit, n in SCREEN_SIZES if flags & bit)

def check_nex(d):
    """What a patch can hold: a .nex V1.0 to V1.2 with, between its header and banks, a loading screen and nothing else."""
    if len(d) < 512 or d[:4] != b'Next' or d[4:8] not in (b'V1.0', b'V1.1', b'V1.2'): raise ValueError('not a .nex V1.0 to V1.2')
    screen_size(d[10])
    if any(v > 1 for v in d[18:130]): raise ValueError('a .nex bank flag must be 0 or 1')
    if sum(d[18:130]) != d[9]: raise ValueError('a .nex must count the banks it lists')

def nex_screen(d):
    return d[512:512 + screen_size(d[10])]

def nex_banks(d):
    off = 512 + screen_size(d[10]); out = {}
    for b in ORDER:
        if d[18 + b]:
            out[b] = d[off:off + BANK]; off += BANK
    if off != len(d):
        raise ValueError('.nex has %d bytes past its banks' % (len(d) - off))
    return out

def block(tag, data):
    return tag + struct.pack('<I', len(data)) + data

def text(fields):
    made = ''.join('%s=%s\n' % kv for kv in fields.items() if kv[1] not in (None, ''))
    for line in made.split('\n'):
        if not line.isascii() or not (line.isprintable() or not line): raise ValueError('text must be printable ASCII: %r' % line)
    return made.encode()

def check_file_name(name):
    """A target's file: a bare name, or Wrong. name: bytes. It is never a path, so it can never open another path."""
    if not 1 <= len(name) <= FILE_NAME_MAX: raise Wrong('a game file name must be 1 to %d bytes' % FILE_NAME_MAX)
    if any(c < 32 or c > 126 or c in b'/\\:*?"<>|' for c in name) or b'..' in name or name[:1] == b' ' or name[-1:] in (b' ', b'.'):
        raise Wrong('a game file name must be a bare name, not %r' % name)

def target_block(index, kind, game, nonce, master, fields):
    """One TGT1 block's data for one accepted dump, or for a FileSet, one accepted set of tape files: fields['file'] is then
    a list of their names, in order."""
    if kind not in KIND_NAMES: raise ValueError('unknown container kind')
    names = fields.get('file'); names = list(names) if isinstance(names, (list, tuple)) else [str(names or '')]
    files = files_of(game, kind)
    if len(names) != len(files): raise Wrong('a set of files needs a name for each')
    for n in names: check_file_name(n.encode('latin-1', 'replace'))
    if len({n.lower() for n in names}) != len(names): raise Wrong('two files of a set have one name')
    lines = dict(file=names[0])
    for k, n in enumerate(names[1:], 2): lines['file_%d' % k] = n
    lines.update(title=fields.get('title'), zxdb_entry=fields.get('zxdb_entry'), md5=hashlib.md5(files[0][0]).hexdigest())
    for k, (x, _) in enumerate(files[1:], 2): lines['md5_%d' % k] = hashlib.md5(x).hexdigest()
    body = text(lines)
    found = parse_target_text(body, len(files))
    if not found[0] or any(n is None for n in found[2]): raise Wrong('the file names must end within the first %d bytes' % TEXT_READ)
    wrap = dump_state(nonce, game).block(b'TGT1', index)(WRAP_CHECK + master)
    if len(files) == 1: return struct.pack('<BBI', index, kind, len(game)) + wrap + body
    rest = b''.join(struct.pack('<BI', k_, len(x)) for x, k_ in files[1:])
    return struct.pack('<BBI', index, files[0][1] | KIND_SET, len(files[0][0])) + wrap + bytes((len(files),)) + rest + body

def parse_target_text(body, files=1):
    """(file, title, [file_2 .. file_n]) from a TGT1 block's text as a reader takes them: within TEXT_READ bytes, ended by a
    newline. files: how many the entry names."""
    window = body[:TEXT_READ]; found = {}
    for line in window.split(b'\n')[:-1]:
        k, _, v = line.partition(b'=')
        found.setdefault(k, v)
    more = [found.get(b'file_%d' % k) for k in range(2, files + 1)]
    return found.get(b'file'), found.get(b'title'), more

def parse_target(d):
    """A TGT1 block's fields, or Wrong: index, kind, length, wrap, file, title and its text; and files, [(name, kind, length)]
    of every file it names, the first being file, kind and length. A set's kind is its first file's with KIND_SET."""
    if len(d) < TARGET_FIXED: raise Wrong('a target block is too short')
    index, kind, length = struct.unpack_from('<BBI', d); head = TARGET_FIXED; more = []
    if kind & KIND_SET:
        if len(d) < head + 1 or not 2 <= d[head] <= SET_FILES_MAX or len(d) < head + 1 + 5 * (d[head] - 1):
            raise Wrong('a target block is damaged')
        n = d[head]
        more = [struct.unpack_from('<BI', d, head + 1 + 5 * k) for k in range(n - 1)]
        if kind & ~KIND_SET not in TAPE_KINDS or any(k_ not in TAPE_KINDS for k_, _ in more): raise Wrong('a set of files may hold only tapes')
        head += 1 + 5 * (n - 1)
    body = d[head:]; name, title, others = parse_target_text(body, 1 + len(more))
    if name is None or None in others: raise Wrong('a target block has no file name')
    for x in [name] + others: check_file_name(x)
    names = [x.decode('ascii') for x in [name] + others]
    if len({x.lower() for x in names}) != len(names): raise Wrong('a target block names one file twice')
    files = [(names[0], kind & ~KIND_SET if more else kind, length)] + [(nm, k_, n_) for nm, (k_, n_) in zip(names[1:], more)]
    return dict(index=index, kind=kind, length=length, wrap=d[6:TARGET_FIXED], file=names[0], title=title, text=body, files=files)

def readable(e):
    """Whether this tool reads a target entry of that kind: a single game file, or a set of tapes."""
    return e['kind'] in KIND_NAMES or (e['kind'] & KIND_SET and e['kind'] & ~KIND_SET in TAPE_KINDS)

def is_tape(e):
    return (e['kind'] & ~KIND_SET) in TAPE_KINDS

def matches(e, game):
    """Whether a game's file, or set of files, has the kinds' count and lengths a target entry names."""
    if not readable(e): return False
    if isinstance(game, FileSet):
        return len(e['files']) == len(game) and all(n == len(x) and k == xk for (_, k, n), x, xk in zip(e['files'], game, game.kinds))
    return len(e['files']) == 1 and e['length'] == len(game)

def targets(f):
    """Every target entry, readable without the game."""
    return [parse_target(d) for t, d in blocks(f)[1] if t == b'TGT1']

def proof_text(proof):
    """PRF1's text: only the keys the format defines. Nothing merged: a replay is not an emulator run, and neither is hardware."""
    for k in proof or ():
        if k not in PROOF_KEYS and not re.match(r'toggle_[0-9]{1,3}\Z', k): raise ValueError('%s is not a PRF1 key' % k)
    return text(proof or {})

def seal(head, bl, st):
    """The file from its header's first 22 bytes and its blocks, with the check value worked out."""
    f = bytes(head) + bytes(CHECK_SIZE) + b''.join(block(t, d) for t, d in bl)
    return f[:CHECK_AT] + check_value(f, st) + f[HEADER:]

def language_info(game_language=None, codes=(), text_by=None, sets=()):
    """INF1's language keys: game_language, language_codes, text_by. codes: 'NAME=CODE' of sets the patch has, by name."""
    code = re.compile(r'[a-z]{2,3}\Z'); out = {}
    if game_language:
        if not code.match(game_language): raise Wrong('%s is not an ISO 639 code' % game_language)
        out['game_language'] = game_language
    pairs = []
    for item in codes:
        if '=' not in item: raise Wrong('%s is not NAME=CODE' % item)
        name, value = item.split('=', 1)
        if not code.match(value): raise Wrong('%s is not an ISO 639 code' % value)
        if name not in sets: raise Wrong('the patch has no language set %s' % name)
        if any(c in name for c in ',='): raise Wrong('a language with a code cannot have , or = in its name')
        pairs.append('%s=%s' % (name, value))
    if pairs: out['language_codes'] = ','.join(pairs)
    if text_by:
        if not text_by.isascii() or not text_by.isprintable(): raise Wrong('a name must be printable ASCII')
        out['text_by'] = text_by
    return out

def make(z80, nex, target, info, nonce=None, level=None, rom=0, proof=None, colours=None, trainer_blocks=(), master=None, more_dumps=(), languages=None, highest_bank=None,
         toggles=None,
         start=None, tape_banks=(), residual_max=None, tape_summary=None):
    """A patch from a game file (.z80, .sna, .tap or .tzx) and the .nex built from it. colours and languages: {name: path of
    the .nex with it, or (path, choice)}. more_dumps: (path, target fields) of others accepted. Before anything is returned,
    every dump named must rebuild exactly that .nex.
    A tape needs start, the .z80 of the state the build starts from, and may name tape_banks: banks the .nex lists beyond
    the game's own that hold blocks of the tape, such as a multiload's, taken from the tape wherever they match it. Refused
    if more than residual_max bytes (RESIDUAL_MAX by default) of the start state are not on the tape. tape_summary, a dict,
    gets what the tape table holds."""
    paths = list(z80) if isinstance(z80, (list, tuple)) else [z80]
    datas = [read_file(x) for x in paths]
    with open(nex, 'rb') as g: out = g.read()
    check_nex(out)
    want = nex_banks(out); game_kind = kind_of_name(paths[0]); tape = None
    game = datas[0] if len(paths) == 1 else FileSet(datas, [kind_of_name(x) for x in paths])
    if game_kind in TAPE_KINDS:
        if start is None: raise Wrong('a tape target needs --start, the .z80 of the state the build starts from')
        with open(start, 'rb') as g: first = g.read()
        for b in tape_banks:
            if b not in want: raise Wrong('tape bank %d is not a bank the .nex lists' % b)
        tape, made_tape = make_tape_table(game, game_kind, first, {b: want[b] for b in tape_banks})
        limit = RESIDUAL_MAX if residual_max is None else residual_max
        if made_tape['residual'] > limit:
            raise Wrong('%d bytes of the start state are not on the tape, more than %d: is the tape encrypted or packed?' % (made_tape['residual'], limit))
        if len(tape) > TAPE_TABLE_MAX: raise Wrong('the tape table is %d bytes, more than a loader holds, %d' % (len(tape), TAPE_TABLE_MAX))
        if tape_summary is not None: tape_summary.update(made_tape)
        have = TapeSnapshot(game, game_kind, tape).banks
    elif start is not None or tape_banks:
        raise Wrong('--start and --tape-bank are for a tape target')
    else:
        have = snapshot_banks(z80)
    sites = bytearray(); count = 0; whole = []
    for b, data in want.items():
        if b in have and len(have[b]) == BANK:
            old = have[b]; i = 0
            while i < BANK:
                if old[i] != data[i]:
                    j = i
                    while j < BANK and old[j] != data[j]: j += 1
                    sites += struct.pack('<BHH', b, i, j - i) + data[i:j]; count += 1; i = j
                else:
                    i += 1
        else:
            whole.append((b, data.rstrip(b'\0')))
    if count and 2 + len(sites) > SITE_TABLE_MAX: raise ValueError('the patch site table is too big for a loader')
    nonce = nonce or os.urandom(16); master = master or os.urandom(MASTER_SIZE)
    st = key_state(nonce, master)
    head = st.block(b'NEX1')(zx0(out[:512]))
    table = st.block(b'SIT1')(zx0(struct.pack('<H', count) + bytes(sites))) if count else b''
    info = dict(info); info.setdefault('credit', CREDIT)
    info = {**{k: info[k] for k in MENU_KEYS if k in info}, **{k: v for k, v in info.items() if k not in MENU_KEYS}}   # what the menu shows, first
    if info.get('fix_label') not in (None, ''): check_fix_label(info['fix_label'])
    if info.get('version') not in (None, ''): check_version(info['version'])
    if not fix_label_seen(text(info), info.get('fix_label')): raise Wrong('fix_label must end within the first %d bytes of INF1' % TEXT_READ)
    if not fix_label_seen(text(info), info.get('version'), b'version'): raise Wrong('version must end within the first %d bytes of INF1' % TEXT_READ)
    bl = [[b'TGT1', target_block(0, game_kind, game, nonce, master, target)], [b'INF1', text(info)], [b'PRF1', proof_text(proof)], [b'ROM1', bytes((rom,))]]
    names = [parse_trn1(t)[1] for t in trainer_blocks]
    if len(set(names)) != len(names): raise ValueError('two trainers have one name')
    bl += [[b'TRN1', t] for t in trainer_blocks]
    bl += [[b'OUT1', st.block(b'OUT1')(struct.pack('<II', zlib.crc32(out), len(out)))], [b'NEX1', head], [b'SIT1', table]]
    if tape is not None: bl.append([TAPE_TAG, bytes((0, 1, 0)) + st.block(TAPE_TAG, 0)(zx0(tape))])
    for b, data in whole:
        body = struct.pack('<BH', b, len(data))
        if data: body += st.block(b'BNK1', b)(zx0(data))
        bl.append([b'BNK1', body])
    # Sets: changes to the finished banks, each with the CRC of the whole file with it alone.
    screen_of_out = nex_screen(out)
    chosen = [(KIND_COLOURS, n, v) for n, v in (colours or {}).items()] + [(KIND_LANGUAGE, n, v) for n, v in (languages or {}).items()]
    toggles = toggles or {}                          # {name: (path, logic)}
    if len(toggles) > TOGGLES_MAX: raise ValueError('a patch can have at most %d toggles' % TOGGLES_MAX)
    for n, (path, logic) in toggles.items():
        chosen.append((KIND_TOGGLE_LOGIC if logic else KIND_TOGGLE, n, path))
    if len(chosen) > SETS_MAX: raise ValueError('a patch can have at most %d sets' % SETS_MAX)
    made = []; next_choice = {}; sizes = []; choice_of = {}
    for stream_index, (kind, name, source) in enumerate(chosen):
        path, choice = source if isinstance(source, tuple) else (source, None)
        next_choice[kind] = next_choice.get(kind, 0) + 1
        choice = next_choice[kind] if choice is None else choice
        choice_of[(kind, name)] = choice
        with open(path, 'rb') as g: painted = g.read()
        if painted[:512] != out[:512] or len(painted) != len(out) or nex_screen(painted) != screen_of_out:
            raise ValueError('a set must only change banks of the same build')
        paint = nex_banks(painted); ranges = []; frames = b''; plain_size = held = 0
        label = name.encode('ascii')
        if not 1 <= len(label) <= SET_NAME_MAX: raise ValueError('set name %r must be 1 to %d characters' % (name, SET_NAME_MAX))
        for b in want:                               # in .nex order, as a loader needs them
            chunk = make_chunk(want[b], paint[b])
            if chunk is None: continue
            ranges += [(b, *r) for r in spans(chunk_offsets(chunk))]; plain_size += len(chunk); held = max(held, len(chunk))
            stream = set_use(st, stream_index, b)(zx0(chunk))
            frames += struct.pack('<BH', b, len(stream)) + stream
        made.append((kind, name, sorted(ranges)))
        body = bytes((stream_index, kind, choice, BASE_SPRITE, len(label))) + label + set_use(st, stream_index, SET_CRC_INDEX)(struct.pack('<I', zlib.crc32(painted))) + frames
        bl.append([SET_TAG, body]); sizes.append(dict(name=name, decoded=plain_size, largest=held, stored=len(frames), banks=len({r[0] for r in ranges})))
    for i, one in enumerate(made):
        for other in made[i + 1:]:
            if one[0] != other[0] or one[0] in TOGGLE_KINDS:     # toggles go with everything, even each other
                clash = first_overlap(one[2], other[2])
                if clash: raise ValueError('sets %r and %r can be chosen together but both change bank %d offset %d' % (one[1], other[1], clash[0], clash[1]))
    toggled = [e for e in made if e[0] in TOGGLE_KINDS]
    for t in trainer_blocks:                         # and with every trainer
        for b, o, v in parse_trn1(t)[2]:
            for e in toggled:
                if first_overlap(e[2], [(b, o, o + 1)]): raise ValueError('trainer %r writes a byte toggle %r changes' % (parse_trn1(t)[1], e[1]))
    if len({e[1].lower() for e in toggled}) != len(toggled): raise ValueError('two toggles have one name')
    for kind, name, _ in toggled:
        if kind == KIND_TOGGLE_LOGIC:
            choice = choice_of[(kind, name)]
            if not (proof or {}).get('toggle_%d' % choice): raise ValueError('toggle %r changes the game logic: PRF1 needs a toggle_%d line saying what and how it was checked' % (name, choice))
    if len({(e[0], e[1]) for e in made}) != len(made): raise ValueError('two sets of one kind have one name')
    screen = nex_screen(out)
    for k in range(0, len(screen), SCREEN_CHUNK):
        part = screen[k:k + SCREEN_CHUNK]; index = k // SCREEN_CHUNK; plain = part.rstrip(b'\0')
        bl.append([b'SCR1', struct.pack('<BH', index, len(plain)) + (st.block(b'SCR1', index)(zx0(plain)) if plain else b'')])
    wanted, flags = options_for([game_kind | (KIND_SET if isinstance(game, FileSet) else 0)], bool(screen))
    if level is not None: wanted = level
    least = lowest_memory(out)
    if highest_bank is None: highest_bank = least
    if not least <= highest_bank <= 111: raise ValueError('the highest bank must be from %d, which the .nex needs, to 111' % least)
    bl.insert(0, [b'OPT1', bytes((wanted, flags, highest_bank))])
    f = seal(MAGIC + bytes((1, 0)) + nonce, bl, st)
    if apply(f, game=game) != out: raise Wrong('the patch does not rebuild the build it was made from')
    for path, fields in more_dumps:
        if isinstance(path, (list, tuple)): f = add_target(f, game, FileSet([read_file(x) for x in path], [kind_of_name(x) for x in path]), kind_of_name(path[0]), fields)
        else: f = add_target(f, game, read_file(path), kind_of_name(path), fields)
    return f, dict(sites=count, site_bytes=len(sites), whole=[b for b, _ in whole], whole_bytes=sum(len(d) for _, d in whole), sets=sizes)

def lowest_memory(nex):
    """The highest 16K bank a .nex is known to need: the highest it lists, or past a 1MB Next's 47 if its header asks for 1792K.
    Pages used only at run time, such as Layer 2 buffers, are not in the file: an author can only raise this."""
    listed = [b for b in range(112) if nex[18 + b]]
    return max(listed + ([48] if nex[8] else []) + [0])

def memory_text(bank):
    return '%dK of RAM, up to 16K bank %d: %s' % ((bank + 1) * 16, bank, 'a 1MB Next has it' if bank <= 47 else 'needs a 2MB Next')

def level_for(kinds, screen=False):
    """OPT1's level: 3 with .sna but no .z80 among the snapshot targets, otherwise 2 with a loading screen, otherwise 1."""
    return options_for(kinds, screen)[0]

def options_for(kinds, screen=False):
    """OPT1's level and flags. The level is worked out from the snapshot targets alone; with none, the tape flag is set, and
    with only sets of tape files (a kind with KIND_SET), the sets' flag too."""
    snaps = [k for k in kinds if k in SNAPSHOT_KINDS]
    flags = (0 if snaps else OPT_TAPE) | (OPT_TAPE_SET if all(k & KIND_SET for k in kinds) else 0)
    return (3 if snaps and KIND_Z80 not in snaps else 2 if screen else 1), flags

def add_target(f, known_game, new_game, kind, fields, residual_max=None):
    """The patch accepting one more dump. known_game unlocks it. Refused unless the new dump rebuilds the same .nex, byte
    for byte; only the banks matter, as the .nex carries its own start-up state.
    A tape joins the TAP1 of a tape it rebuilds the same banks with, which changes only that block's clear head. Otherwise
    it gets a TAP1 of its own, under the next stream index, made from the known dump's banks and start state: its extra
    banks must be wholly on the new tape."""
    opened = check_key(f, known_game); st, bl = opened[:2]
    have = targets(f)
    if len(have) >= TARGETS_MAX: raise Wrong('a patch can accept at most %d dumps' % TARGETS_MAX)
    new_files = files_of(new_game, kind)
    names = fields.get('file'); names = list(names) if isinstance(names, (list, tuple)) else [str(names or '')]
    if len(names) != len(new_files): raise Wrong('a set of files needs a name for each')
    digests = [hashlib.md5(x).hexdigest() for x, _ in new_files]
    def set_digests(t):
        found = dict(l.partition(b'=')[::2] for l in t['text'].split(b'\n') if b'=' in l)
        return [found.get(b'md5', b'').decode()] + [found.get(b'md5_%d' % k, b'').decode() for k in range(2, len(t['files']) + 1)]
    if any(set_digests(t) == digests for t in have): raise Wrong('this patch already accepts that dump')
    known_files = {}                                   # a name names one file: the same length and MD5 wherever it is used
    for t in have:
        for (nm, k_, n_), dg in zip(t['files'], set_digests(t)): known_files[nm.lower()] = (n_, dg)
    for nm, (x, _), dg in zip(names, new_files, digests):
        if nm.lower() in known_files and known_files[nm.lower()] != (len(x), dg):
            raise Wrong('this patch already has a target with that file name' if len(new_files) == 1 else 'this patch already names %s as another file' % nm)
    if len(new_files) == 1 and any(nm.lower() == names[0].lower() for t in have for nm, _, _ in t['files']):
        raise Wrong('this patch already has a target with that file name')
    first = len(new_files[0][0])
    if any(t['length'] == first and (t['kind'] & ~KIND_SET) != kind for t in have): raise Wrong('this patch has a target of another kind with that length')
    rest = [(nm.lower(), len(x)) for nm, (x, _) in zip(names[1:], new_files[1:])]
    for t in have:
        if t['length'] == first and [(nm.lower(), n_) for nm, _, n_ in t['files'][1:]] != rest:
            raise Wrong('this patch has a target whose first file has that length, but other further files')
    if not fields.get('title') and have and have[0]['title']: fields = dict(fields, title=have[0]['title'].decode('ascii', 'replace'))
    nonce = f[NONCE_AT:CHECK_AT]
    entry = target_block(len(have), kind, new_game, nonce, opened.master, fields)
    out = []; last = max(i for i, (t, _) in enumerate(bl) if t == b'TGT1')
    for i, (t, d) in enumerate(bl):
        out.append([t, d])
        if i == last: out.append([b'TGT1', entry])
    if kind in TAPE_KINDS: out = add_tape_table(out, st, opened, known_game, new_game, kind, len(have), residual_max)
    kinds = [t['kind'] for t in have] + [kind | (KIND_SET if isinstance(new_game, FileSet) else 0)]
    for e in out:
        if e[0] == b'OPT1': e[1] = bytes(options_for(kinds, any(t == b'SCR1' for t, _ in bl))) + e[1][2:3]
    made = seal(f[:CHECK_AT], out, st)
    check_structure(blocks(made)[1])
    try:
        same = apply(made, game=new_game) == apply(f, game=known_game)
    except Wrong as e:
        raise Wrong('that dump does not rebuild the same banks: %s' % e)
    if not same: raise Wrong('that dump does not rebuild the same banks')
    return made

def add_tape_table(out, st, opened, known_game, new_game, kind, index, residual_max=None):
    """The blocks with tape target index given a TAP1: a place in one that rebuilds the known dump's banks, or a new one."""
    known = game_snapshot(opened, known_game)
    for n, (t, d) in enumerate(out):
        if t != TAPE_TAG: continue
        e = parse_tap1(d)
        try:
            fits = len(e['targets']) < TARGETS_MAX and TapeSnapshot(new_game, kind, tape_table_of(st, e)).banks == known.banks
        except Wrong:
            fits = False
        if fits:
            out[n] = [t, bytes((e['stream'], len(e['targets']) + 1)) + bytes(e['targets'] + [index]) + e['data']]
            return out
    if isinstance(known, TapeSnapshot): header = known.header
    elif opened.target['kind'] == KIND_Z80: header = start_header(known_game)
    else: raise Wrong('a tape can only join a patch through a .z80 or a tape it already accepts')
    machine = machine_banks(header[34] == 3)
    table, made = build_tape_table(new_game, kind, header, {b: known.banks[b] for b in machine},
                                   {b: known.banks[b] for b in getattr(known, 'extra', ())})
    if made['residual'] > (RESIDUAL_MAX if residual_max is None else residual_max):
        raise Wrong('%d bytes of the start state are not on that tape' % made['residual'])
    if len(table) > TAPE_TABLE_MAX or TapeSnapshot(new_game, kind, table).banks != known.banks:
        raise Wrong('that tape does not hold what the patch takes from tape')
    streams = [parse_tap1(d)['stream'] for t, d in out if t == TAPE_TAG]
    stream = max(streams) + 1 if streams else 0
    if stream > 255: raise Wrong('a patch can have at most 256 tape tables')
    at = max(n for n, (t, _) in enumerate(out) if t in (TAPE_TAG, b'SIT1')) + 1
    out.insert(at, [TAPE_TAG, bytes((stream, 1, index)) + st.block(TAPE_TAG, stream)(zx0(table))])
    return out

def parse_tap1(d):
    """The clear part of a TAP1 block, or Wrong: its stream index, the tape targets it serves, and its stream."""
    if len(d) < TAPE_FIXED or not 1 <= d[1] <= TARGETS_MAX or len(d) <= TAPE_FIXED + d[1]: raise Wrong('a tape block is damaged')
    return dict(stream=d[0], targets=list(d[TAPE_FIXED:TAPE_FIXED + d[1]]), data=d[TAPE_FIXED + d[1]:])

def tape_table_of(st, e):
    """A parsed TAP1 block's table, decrypted and decoded."""
    return unzx0(st.block(TAPE_TAG, e['stream'])(e['data']), TAPE_TABLE_MAX)

def game_snapshot(opened, game):
    """The banks and paging of the game opened, as a snapshot object: from its TAP1 for a tape."""
    kind = opened.target['kind'] & ~KIND_SET
    if kind not in TAPE_KINDS: return snapshot_of(game, kind)
    for t, d in opened[1]:
        if t == TAPE_TAG:
            e = parse_tap1(d)
            if opened.target['index'] in e['targets']: return TapeSnapshot(game, kind, tape_table_of(opened[0], e))
    raise Wrong('this patch file is damaged')

def blocks(f):
    """The nonce and blocks, or Wrong: every length is checked against the file."""
    if len(f) < HEADER or f[:4] != MAGIC or f[4] != 1 or f[5] != 0:
        raise Wrong('not a .nxc v1 file')
    nonce = f[NONCE_AT:CHECK_AT]; i = HEADER; out = []
    while i < len(f):
        if i + 8 > len(f): raise Wrong('file ends inside a block header')
        tag = f[i:i + 4]; n = struct.unpack_from('<I', f, i + 4)[0]; i += 8
        if i + n > len(f): raise Wrong('file ends inside a block')
        out.append((tag, f[i:i + n])); i += n
    return nonce, out

def parse_set(d):
    """The clear part of a SET2 block, or Wrong."""
    if len(d) < SET_FIXED or not 1 <= d[4] <= SET_NAME_MAX or len(d) < SET_FIXED + d[4]: raise Wrong('a set block is damaged')
    return dict(stream=d[0], kind=d[1], choice=d[2], base=d[3], name=d[SET_FIXED:SET_FIXED + d[4]], data=d[SET_FIXED + d[4]:])

def set_use(st, stream, index):
    """The xor function for one of a set's streams: tag SEB and its stream index, index its bank or SET_CRC_INDEX."""
    return st.block(SET_STREAM + bytes((stream,)), index)

def make_chunk(old, new):
    """A bank's chunk from the bank without a set and with it: a bitmap of the bytes that differ, then those bytes in
    order. None if none differ. At most SET_CHUNK_MAX bytes, whatever the bank holds."""
    bitmap = bytearray(BITMAP); values = bytearray()
    for i in range(BANK):
        if old[i] != new[i]:
            bitmap[i >> 3] |= 0x80 >> (i & 7); values.append(new[i])
    return bytes(bitmap) + bytes(values) if values else None

def check_chunk(chunk):
    """A chunk's shape, or Wrong: a bitmap, and exactly as many bytes after it as the bitmap has bits, at least one."""
    if len(chunk) <= BITMAP or len(chunk) > SET_CHUNK_MAX: raise Wrong('a set is damaged')
    if sum(bin(c).count('1') for c in chunk[:BITMAP]) != len(chunk) - BITMAP: raise Wrong('a set is damaged')

def chunk_offsets(chunk):
    """The offsets in its bank that a chunk changes, rising, each with the place of its byte in the same order."""
    return [i * 8 + n for i, c in enumerate(chunk[:BITMAP]) if c for n in range(8) if c & 0x80 >> n]

def spans(offsets):
    """Rising offsets as (start, end) runs."""
    out = []
    for o in offsets:
        if out and out[-1][1] == o: out[-1][1] = o + 1
        else: out.append([o, o + 1])
    return [tuple(r) for r in out]

def read_set(st, e):
    """(the CRC of the file with this set alone, [(bank, chunk)]) of a parsed SET2 block, or Wrong: its CRC, then chunks of
    1 byte bank, 2 bytes stream length and the stream, in rising .nex order, each with a good stream and shape."""
    d = e['data']
    if len(d) < SET_CRC: raise Wrong('a set is damaged')
    crc = struct.unpack('<I', set_use(st, e['stream'], SET_CRC_INDEX)(d[:SET_CRC]))[0]
    i = SET_CRC; out = []; last = -1
    while i < len(d):
        if i + SET_CHUNK_HEAD > len(d): raise Wrong('a set is damaged')
        b, n = struct.unpack_from('<BH', d, i); i += SET_CHUNK_HEAD
        if b >= 112 or ORDER.index(b) <= last or i + n > len(d): raise Wrong('a set is out of order, or out of range')
        last = ORDER.index(b)
        chunk = unzx0(set_use(st, e['stream'], b)(d[i:i + n]), SET_CHUNK_MAX); i += n
        check_chunk(chunk)
        out.append((b, chunk))
    return crc, out

def first_overlap(a, b):
    """The first place two sorted lists of (bank, start, end) overlap, or None. One pass of each."""
    i = j = 0
    while i < len(a) and j < len(b):
        x, y = a[i], b[j]
        if x[0] < y[0] or (x[0] == y[0] and x[2] <= y[1]): i += 1
        elif y[0] < x[0] or (y[0] == x[0] and y[2] <= x[1]): j += 1
        else: return x[0], max(x[1], y[1])
    return None

def sets(f):
    """Every set block, readable without the game: stream, kind, choice, base, name, data."""
    return [parse_set(d) for t, d in blocks(f)[1] if t == SET_TAG]

def offered(f, kind):
    """The sets of a kind a loader offers, in file order: those whose base is the sprite build."""
    return [e for e in sets(f) if e['kind'] == kind and e['base'] == BASE_SPRITE]

def colour_sets(f):
    """The names of a patch's colour sets, readable without the game."""
    return [e['name'].decode('ascii', 'replace') for e in offered(f, KIND_COLOURS)]

def toggles_of(f):
    """The names of a patch's toggles a loader offers, in file order, and whether each changes the game logic."""
    on = [e for e in sets(f) if e['kind'] in TOGGLE_KINDS and e['base'] == BASE_SPRITE][:TOGGLES_MAX]
    return [(e['name'].decode('ascii', 'replace'), e['kind'] == KIND_TOGGLE_LOGIC) for e in on]

def languages(f):
    """The names of a patch's language sets, readable without the game."""
    return [e['name'].decode('ascii', 'replace') for e in offered(f, KIND_LANGUAGE)]

def check_structure(bl):
    """Everything that can be checked without the game, in the order a loader meets it: the first step of every route."""
    tags = [t for t, _ in bl]; indices = set()
    for need in (b'OPT1', b'INF1', b'OUT1', b'NEX1', b'SIT1'):
        if tags.count(need) != 1: raise Wrong('a required block is missing or repeated')
    d = dict(bl)
    opt = d[b'OPT1']
    if len(opt) != 3: raise Wrong('the options block must be 3 bytes')
    if opt[2] > 111: raise Wrong('the options block names a bank that cannot be')
    if opt[0] > LOADER_LEVEL or opt[1] & ~LOADER_FLAGS: raise Wrong('this patch needs a newer loader')
    if len(d[b'OUT1']) != 8: raise Wrong('the output block has the wrong length')
    count = kinds = snaps = singles = 0; tapes = set(); served = []; streams = set()
    for t, data in bl:
        if t == b'TGT1':
            e = parse_target(data)
            if e['index'] != count or count >= TARGETS_MAX: raise Wrong('a target block is out of place')
            count += 1; kinds += readable(e); snaps += e['kind'] in SNAPSHOT_KINDS; singles += e['kind'] in KIND_NAMES
            if is_tape(e) and readable(e): tapes.add(e['index'])
        elif t == b'TRN1': parse_trn1(data)
        elif t == SET_TAG:
            index = parse_set(data)['stream']
            if index in indices: raise Wrong('a set repeats a stream index')
            indices.add(index)
        elif t == TAPE_TAG:
            e = parse_tap1(data)
            if e['stream'] in streams: raise Wrong('a tape block repeats a stream index')
            streams.add(e['stream']); served += e['targets']
    if not kinds: raise Wrong('this patch needs a newer loader' if count else 'a required block is missing or repeated')
    if b'SCR1' in tags and opt[0] < 2: raise Wrong('a patch with a loading screen must say level 2 or above')
    if len(served) != len(set(served)) or set(served) != tapes: raise Wrong('a tape block does not match the tape targets')
    if tapes and not snaps and not opt[1] & OPT_TAPE: raise Wrong('a patch with only tape targets must say so in its options block')
    if kinds and not singles and not opt[1] & OPT_TAPE_SET: raise Wrong('a patch with only sets of tape files must say so in its options block')

class Opened(tuple):
    """What check_key found: (stream, blocks, .nex CRC, .nex length), with .master and .target."""
    master = None; target = None

def check_key(f, game):
    """The one validation route: every check before anything is decompressed. The file's shape, then the game against each
    target entry of its length, the master key, the keyed check over the file. Returns an Opened."""
    nonce, bl = blocks(f)
    check_structure(bl)
    base = None; found = None; master = None
    for t, d in bl:
        if t != b'TGT1': continue
        e = parse_target(d)
        if not matches(e, game): continue
        if base is None: base = dump_state(nonce, game)
        plain = base.block(b'TGT1', e['index'])(e['wrap'])
        if plain[:8] == WRAP_CHECK:
            found, master = e, plain[8:]
            break
    if found is None:
        if isinstance(game, FileSet): raise Wrong('these are not the files this patch was made for')
        for t, d in bl:
            if t == b'TGT1':
                e = parse_target(d)
                if readable(e) and len(e['files']) > 1 and e['length'] == len(game):
                    raise Wrong('this patch also needs %s beside it' % ', '.join(nm for nm, _, _ in e['files'][1:]))
        raise Wrong('this is not the game file this patch was made for')
    st = key_state(nonce, master)
    if check_value(f, st) != f[CHECK_AT:HEADER]: raise Wrong('this patch file is damaged')
    crc, size = struct.unpack('<II', st.block(b'OUT1')(dict(bl)[b'OUT1']))
    done = Opened((st, bl, crc, size)); done.master = master; done.target = found
    return done

def read_screen(bl, st, header):
    """What lies between the .nex's header and its banks, from its SCR1 blocks: one for each 16K, as the header sizes it."""
    size = screen_size(header[10]); chunks = (size + SCREEN_CHUNK - 1) // SCREEN_CHUNK; parts = {}
    for tag, d in bl:
        if tag != b'SCR1': continue
        if len(d) < 3: raise Wrong('a screen block is too short')
        k, n = struct.unpack_from('<BH', d)
        if k >= chunks or k in parts: raise Wrong('a screen block is out of range')
        room = min(SCREEN_CHUNK, size - k * SCREEN_CHUNK)
        if n > room or (not n and len(d) != 3): raise Wrong('a screen block is the wrong length')
        plain = unzx0(st.block(b'SCR1', k)(d[3:]), n) if n else b''
        if len(plain) != n: raise Wrong('a screen block is the wrong length')
        parts[k] = plain + bytes(room - n)
    if len(parts) != chunks: raise Wrong('a screen block is missing')
    return b''.join(parts[k] for k in range(chunks))

def apply(f, z80=None, game=None, banks=None, colours=None, chosen=None, language=None, toggles=()):
    """The .nex, from the patch and the player's snapshot; raises Wrong otherwise.
    Nothing is decompressed or written until the key and the keyed check pass, which is
    what keeps a damaged file away from a decompressor with no bounds checks.
    colours, language: a set of each kind, by name. chosen: trainers to apply, by number from 1 or by name, after the
    output's checksum."""
    if game is None:
        with open(z80, 'rb') as g: game = g.read()
    opened = check_key(f, game); st, bl, crc, size = opened[:4]
    header = unzx0(st.block(b'NEX1')(dict(bl)[b'NEX1']), 512)
    if len(header) != 512 or header[:4] != b'Next': raise Wrong('the .nex header is damaged')
    if any(header[18 + b] for b in range(dict(bl)[b'OPT1'][2] + 1, 112)): raise Wrong('the options block says less memory than the .nex lists')
    d = dict(bl)[b'SIT1']
    table = unzx0(st.block(b'SIT1')(d), SITE_TABLE_MAX) if d else b''
    whole = {}
    for tag, d in bl:
        if tag == b'BNK1':
            if len(d) < 3: raise Wrong('a bank block is too short')
            b, n = struct.unpack_from('<BH', d)
            if n > BANK or b >= 112 or b in whole: raise Wrong('a bank block is out of range')
            if not header[18 + b]: raise Wrong('a bank block is for a bank the .nex does not list')
            if not n and len(d) != 3: raise Wrong('a bank block is the wrong length')
            whole[b] = (unzx0(st.block(b'BNK1', b)(d[3:]), n) if n else b'')
            if len(whole[b]) != n: raise Wrong('a bank has the wrong length')
    selected = []
    for kind, wanted in ((KIND_COLOURS, colours), (KIND_LANGUAGE, language)):
        if wanted is None: continue
        found = [e for e in offered(f, kind) if e['name'] == wanted.encode()]
        if not found: raise Wrong('this patch has no %s set called %s' % (KIND_NAMES_SET[kind], wanted))
        selected.append(read_set(st, found[0]))
    on = offered(f, KIND_TOGGLE) + offered(f, KIND_TOGGLE_LOGIC)
    on = sorted(on, key=lambda e: [x['stream'] for x in sets(f)].index(e['stream']))[:TOGGLES_MAX]
    for wanted in toggles or ():
        found = [e for e in on if e['name'] == wanted.encode()]
        if not found: raise Wrong('this patch has no toggle called %s' % wanted)
        selected.append(read_set(st, found[0]))
    for i, one in enumerate(selected):
        for two in selected[i + 1:]:
            other = dict(two[1])
            for b, chunk in one[1]:
                if b in other and any(x & y for x, y in zip(chunk[:BITMAP], other[b][:BITMAP])): raise Wrong('two sets chosen together change the same bytes')
    if banks is None:
        snap = game_snapshot(opened, game); banks = snap.banks
        if any(not header[18 + b] for b in getattr(snap, 'extra', ())): raise Wrong('a tape table writes a bank the .nex does not list')
    have = {k_: bytearray(v) for k_, v in banks.items()}
    if table:
        if len(table) < 2: raise Wrong('the patch site table is damaged')
        count = struct.unpack_from('<H', table)[0]; i = 2
        for _ in range(count):
            if i + 5 > len(table): raise Wrong('the patch site table is damaged')
            b, o, l = struct.unpack_from('<BHH', table, i); i += 5
            if b not in have or b >= 112 or not header[18 + b] or b in whole or o + l > BANK or i + l > len(table):
                raise Wrong('a patch site is out of range')
            have[b][o:o + l] = table[i:i + l]; i += l
        if i != len(table): raise Wrong('the patch site table is damaged')
    out = bytearray(header) + read_screen(bl, st, header); offs = {}
    for b in ORDER:
        if header[18 + b]:
            offs[b] = len(out)
            if b in whole: out += whole[b] + bytes(BANK - len(whole[b]))
            elif b in have and len(have[b]) == BANK: out += have[b]
            else: raise Wrong('bank %d is in neither the patch nor the snapshot' % b)
    if len(out) != size: raise Wrong('the rebuilt .nex fails its checksum')
    expected = crc
    for set_crc, chunks in selected:
        expected ^= set_crc ^ crc
        for b, chunk in chunks:
            if b not in offs: raise Wrong('a set is out of range')
            for place, o in enumerate(chunk_offsets(chunk), BITMAP): out[offs[b] + o] = chunk[place]
    if zlib.crc32(bytes(out)) != expected: raise Wrong('the rebuilt .nex fails its checksum')
    written = {}
    for _, chunks in selected[len(selected) - len(toggles or ()):]:
        for b, chunk in chunks: written[b] = chunk
    for b, o, v in chosen_pokes(f, chosen):
        if b not in offs: raise Wrong('a trainer POKE is in a bank the build does not have')
        if b in written and written[b][o >> 3] & (0x80 >> (o & 7)): raise Wrong('a trainer and a toggle chosen together change the same byte')
        out[offs[b] + o] = v
    return bytes(out)

# ---------------------------------------------------------------- the menu, and a .nex that carries it

MENU_TITLE = 54   # two bar rows of 27
HELP_TAG = b'HLP1'; HELP_MAX = 64; HELP_READ = 1024; MENU_ROW = 32; MENU_LINES = 10; MENU_HOLD = 2   # help: two rows of 32
STUB = os.path.join(HERE, '..', 'firmware', 'nxcstub.bin')   # assembled from firmware/nxcstub.asm, with firmware/menu.asm
STUB_PARAMS = 8; STUB_DESC_END = 0x1D00; STUB_BLOCK = 57; MENU_ENTRY = 0xC000; NO_DATA = 0xFFFFFF
STUB_SHADOW = 16; SHADOW_ROOM = ((0x1D40, 0x2000), (0x3F80, 0x4000))   # M0's room for .nexload's bytes below a stack in the entry bank

def help_texts(f):
    """HLP1's lines as a reader takes them: from its first HELP_READ bytes, each value's first HELP_MAX characters, anything
    unprintable as ?. {} without the block."""
    body = dict(blocks(f)[1]).get(HELP_TAG, b'')[:HELP_READ]; out = {}
    for line in body.split(b'\n')[:-1] if body else ():
        k, eq, v = line.partition(b'=')
        if eq and k.decode('latin-1') not in out and v:
            out[k.decode('latin-1')] = ''.join(chr(c) if 32 <= c < 127 else '?' for c in v[:HELP_MAX])
    return out

def wrap_help(text):
    """A help text as two rows of MENU_ROW: a word that would cross the end of the first row starts the second, padded
    with spaces. Wrong if it is then longer than HELP_MAX or not printable ASCII."""
    if not text or '\n' in text or not text.isascii() or not text.isprintable(): raise Wrong('help is 1 to %d printable ASCII characters' % HELP_MAX)
    text = ' '.join(text.split())
    if len(text) > MENU_ROW and text[MENU_ROW] != ' ' and ' ' in text[:MENU_ROW]:
        cut = text.rindex(' ', 0, MENU_ROW)
        text = text[:cut].ljust(MENU_ROW) + text[cut + 1:]
    elif len(text) > MENU_ROW and text[MENU_ROW] == ' ':
        text = text[:MENU_ROW] + text[MENU_ROW + 1:]
    if len(text) > HELP_MAX: raise Wrong('help does not fit two rows of %d: %r' % (MENU_ROW, text))
    return text

def menu_lines(f):
    """The menu's lines as every reader shows them: [(kind, name, help key, payload)], kind 0 trainer, 1 the main line, 2 a
    kind of set (payload its SET2 entries), 3 a toggle (payload its entry); trainers (payload their POKEs) fill what the
    main line, the kinds and the toggles leave of ten, at most TRAINERS_SHOWN."""
    kinds = [(KIND_NAMES_SET[k], 'Enhanced colours' if k == KIND_COLOURS else 'Language', offered(f, k)) for k in (KIND_COLOURS, KIND_LANGUAGE) if offered(f, k)]
    tg = [e for e in sets(f) if e['kind'] in TOGGLE_KINDS and e['base'] == BASE_SPRITE][:TOGGLES_MAX]
    room = min(TRAINERS_SHOWN, MENU_LINES - 1 - len(kinds) - len(tg))
    out = [(0, t[1], 'trainer_%d' % (n + 1), t[2]) for n, t in enumerate(trainers(f)[:room])]
    out.append((1, fix_label(f), 'fix', None))
    out += [(2, label, key, es) for key, label, es in kinds]
    out += [(3, e['name'].decode('ascii', 'replace'), 'toggle_%d' % (n + 1), e) for n, e in enumerate(tg)]
    return out

def set_help(f, game, texts):
    """The patch with HLP1 holding texts, {key: text}, each wrapped as wrap_help does; an empty text removes its key, and
    no keys left removes the block. The same nonce and encrypted blocks, with a new check value."""
    st, bl = check_key(f, game)[:2]
    keys = {k for _, _, k, _ in menu_lines(f)} | {'colours', 'language', 'fix'}
    have = dict(help_texts(f))
    for k, v in texts.items():
        if k not in keys: raise Wrong('this patch has no menu line %s' % k)
        if v: have[k] = wrap_help(v)
        else: have.pop(k, None)
    order = [k for _, _, k, _ in menu_lines(f) if k in have]
    body = b''.join(b'%s=%s\n' % (k.encode(), have[k].encode()) for k in order)
    if len(body) > HELP_READ: raise Wrong('the help must end within the first %d bytes of its block' % HELP_READ)
    out = [[t, d] for t, d in bl if t != HELP_TAG]
    if body:
        at = max(i for i, (t, _) in enumerate(out) if t in (b'INF1', b'TRN1', SET_TAG) or t == b'TGT1') + 1
        out.insert(at, [HELP_TAG, body])
    return seal(f[:CHECK_AT], out, st)

def menu_text(v, n):
    return ''.join(chr(c) if 32 <= c < 127 else '?' for c in v[:n]).encode()

def set_runs(chunks):
    """A set as a menu .nex carries it: each chunk decoded, as a bank, its length and the chunk (its bitmap, then a byte
    for each bit set), then a bank of 0xFF."""
    return b''.join(struct.pack('<BH', b, len(chunk)) + chunk for b, chunk in chunks) + b'\xff'

def menu_presets(f, chosen=None, colours=None, language=None, toggles=()):
    """The states a menu .nex's lines start with, from choices as apply takes them: {line index: state}."""
    lines = menu_lines(f); out = {}
    numbers = [k for k, t in enumerate(trainers(f)) for c in chosen or () if t[1] == c or str(k + 1) == str(c)]
    for c in chosen or ():
        if not any(t[1] == c or str(k + 1) == str(c) for k, t in enumerate(trainers(f))): raise Wrong('this patch has no trainer %s' % c)
    for i, (kind, name, key, payload) in enumerate(lines):
        if kind == 0 and int(key.split('_')[1]) - 1 in numbers: out[i] = 1
        if kind == 2:
            want = colours if key == 'colours' else language
            if want is not None:
                names = [e['name'].decode('ascii', 'replace') for e in payload]
                if want not in names: raise Wrong('this patch has no %s set called %s' % (key, want))
                out[i] = names.index(want) + 1
        if kind == 3 and name in (toggles or ()): out[i] = 1
    for t in toggles or ():
        if not any(l[0] == 3 and l[1] == t for l in lines): raise Wrong('this patch has no toggle called %s' % t)
    if sum(1 for i, v in out.items() if lines[i][0] >= 2 and v) > MENU_HOLD: raise Wrong('at most %d sets and toggles can be on at once' % MENU_HOLD)
    return out

def menu_description(f, st=None, presets=None):
    """(the description firmware/menu.asm draws, the data its lines point at) for a menu .nex, its lines starting in the
    states presets gives ({line: state}, off without). Without st (the patch's key), sets and toggles get no data."""
    lines = menu_lines(f); helps = help_texts(f)
    title = next((t['title'] for t in targets(f) if t.get('title')), b'') or b''
    pub = inf1_value(f, 'publisher') or b''
    colours = (inf1_value(f, 'colours_by') or b'') if colour_sets(f) else b''
    ver = inf1_value(f, 'version') or b''
    d = bytearray((DESC_FIXED | (DESC_VERSION if ver else 0), MENU_HOLD, len(lines)))
    for v, n in ((title.upper() if isinstance(title, bytes) else title.encode().upper(), MENU_TITLE), (pub, MENU_ROW), (colours, CREDIT_NAME), (inf1_value(f, 'patch_by') or b'', CREDIT_NAME)):
        d += menu_text(v, n) + b'\0'
    if ver: d += menu_text(ver, VERSION_MAX) + b'\0'       # only with its flag, so a patch without one has the description it had
    data = bytearray(); where = []
    for i, (kind, name, key, payload) in enumerate(lines):
        d += bytes((kind, 1 if kind == 1 else (presets or {}).get(i, 0), len(payload) if kind == 2 else 0))
        d += menu_text(name.encode(), 25) + b'\0' + menu_text(helps.get(key, '').encode(), HELP_MAX) + b'\0'
        if kind == 2:
            for e in payload: d += menu_text(e['name'], 25) + b'\0'
        if kind == 1 or (st is None and kind != 0): where.append(NO_DATA); continue
        where.append(len(data))
        if kind == 0:
            data += bytes((len(payload),)) + b''.join(struct.pack('<BHB', b, o, v) for b, o, v in payload)
        else:
            for e in (payload if kind == 2 else [payload]): data += set_runs(read_set(st, e)[1])
    for w in where: d += struct.pack('<I', w)[:3]
    return bytes(d), bytes(data)

def stub_binary():
    with open(STUB, 'rb') as g: return g.read()

def menu_refusal(header, top):
    """Why a build cannot carry its menu, or None."""
    pc = struct.unpack_from('<H', header, 14)[0]
    if header[4:8] != b'V1.2': return 'its .nex is %s, not V1.2' % header[4:8].decode('latin-1')
    if struct.unpack_from('<H', header, 140)[0]: return 'its .nex passes its file handle on, so would read into the menu banks'
    if pc < 0x4000 + STUB_BLOCK or 1 <= pc & 0x1FFF <= 4: return 'its start address, %#06x, leaves no room for the handoff' % pc
    if top > 111: return 'it needs more banks than a Next has'
    return None

def set_or_poke_touches(f, st, bank, lo, hi):
    """Whether any trainer, set or toggle the menu offers changes bank's bytes lo to hi."""
    for kind, _, _, payload in menu_lines(f):
        if kind == 0 and any(b == bank and lo <= o < hi for b, o, _ in payload): return True
        for e in (payload if kind == 2 else [payload] if kind == 3 else []):
            for b, chunk in read_set(st, e)[1]:
                if b == bank and any(lo <= o < hi for o in chunk_offsets(chunk)): return True
    return False

def apply_menu(f, game, chosen=None, colours=None, language=None, toggles=()):
    """The .nex that carries its menu (spec, "A .nex that carries its menu"): the bare .nex with nothing chosen, its header
    changed to start the stub, then the menu banks: the stub, its parameters and the description, then the data. The
    choices, as apply takes them, are where its menu starts."""
    presets = menu_presets(f, chosen, colours, language, toggles)
    bare = apply(f, game=game)
    opened = check_key(f, game); st, bl = opened[:2]
    header = bytearray(bare[:512])
    m0 = dict(bl)[b'OPT1'][2] + 1
    desc, data = menu_description(f, st, presets)
    stub = bytearray(stub_binary())
    if len(stub) + len(desc) > STUB_DESC_END: raise Wrong('the menu is too big for its bank')
    count = 1 + -(-len(data) // BANK); top = m0 + count - 1
    why = menu_refusal(header, top)
    if why: raise Wrong('this build cannot carry its menu: %s; --bare writes it with the choices fixed' % why)
    pc, sp = struct.unpack_from('<H', header, 14)[0], struct.unpack_from('<H', header, 12)[0]
    lo = ((sp - STUB_SHADOW) & 0xFFFF) - 0xC000; shadow = lo >= 0       # the bytes .nexload may write below a stack in the entry bank
    m0_bank = bytearray(BANK)
    if shadow:
        hi = lo + STUB_SHADOW
        if not any(a <= lo and hi <= b for a, b in SHADOW_ROOM + ((len(stub) + len(desc), STUB_DESC_END),)):
            raise Wrong('this build cannot carry its menu: its stack, at %#06x, lies where the stub works; --bare writes it with the choices fixed' % sp)
        at = 512 + screen_size(header[10])
        for b in ORDER:
            if header[18 + b]:
                if b == header[139]: m0_bank[lo:hi] = bare[at + lo:at + hi]
                at += BANK
        if set_or_poke_touches(f, st, header[139], lo, hi): raise Wrong('this build cannot carry its menu: a choice changes the bytes below its stack')
    stub[-STUB_PARAMS:] = struct.pack('<BHHBBB', 2 * m0, pc, sp, 2 * header[139], count, int(shadow))
    for b in range(m0, top + 1): header[18 + b] = 1
    header[9] += count
    struct.pack_into('<H', header, 14, MENU_ENTRY); header[139] = m0
    if top > 47: header[8] = 1
    m0_bank[:len(stub) + len(desc)] = stub + desc
    banks = [bytes(m0_bank)] + [data[i:i + BANK].ljust(BANK, b'\0') for i in range(0, len(data), BANK)]
    return bytes(header) + bare[512:] + b''.join(banks)

def inf1_value(f, key):
    """An INF1 line as a loader takes it: from the first TEXT_READ bytes, ended by a newline; otherwise None."""
    text = dict(blocks(f)[1]).get(b'INF1', b'')[:TEXT_READ]
    start = 0
    while True:
        end = text.find(b'\n', start)
        if end < 0: return None
        if text[start:end].startswith(key.encode() + b'='): return text[start + len(key) + 1:end]
        start = end + 1

def check_fix_label(v):
    if not isinstance(v, str) or not 1 <= len(v) <= FIX_LABEL_MAX or not v.isascii() or not v.isprintable():
        raise Wrong('a fix label is 1 to %d printable ASCII characters: %r' % (FIX_LABEL_MAX, v))

def fix_label_seen(body, label, key=b'fix_label'):
    """Whether a loader reading the first TEXT_READ bytes of INF1 text body finds its fix_label line (or key's) whole, if it
    has one."""
    if not label: return True
    line = b'%s=%s\n' % (key, label.encode())
    at = (b'\n' + body).find(b'\n' + line)
    return at >= 0 and at + len(line) <= TEXT_READ

def fix_label(f):
    """The menu's main line as a loader names it: INF1's fix_label, its first FIX_LABEL_MAX characters with anything
    unprintable as ?, or FIX_LABEL if the key is absent, empty or cut off."""
    v = inf1_value(f, 'fix_label')
    if not v: return FIX_LABEL
    return ''.join(chr(c) if 32 <= c < 127 else '?' for c in v[:FIX_LABEL_MAX])

def check_version(v):
    if not isinstance(v, str) or not 1 <= len(v) <= VERSION_MAX or not v.isascii() or not v.isprintable() or ' ' in v or v[0] in 'vV':
        raise Wrong('a version is 1 to %d printable ASCII characters with no spaces, without the v the menu adds: %r' % (VERSION_MAX, v))

def patch_version(f):
    """The patch's version as a loader shows it, without the v: INF1's version, its first VERSION_MAX characters with
    anything unprintable as ?, or '' if the key is absent, empty or cut off."""
    v = inf1_value(f, 'version') or b''
    return ''.join(chr(c) if 32 <= c < 127 else '?' for c in v[:VERSION_MAX])

def credit_line(f):
    """The menu's credit rows, or None: "Colours: b" (only with a colour set, b cut to 23) above "Patch: a" (cut to 25),
    each only if it is there, joined by a newline. With a version, the patch row is 32 wide and ends in v and it, and a is
    cut to leave a blank column before the v; without a, the row is the version alone. Anything unprintable is ?."""
    def name(key, n):
        v = inf1_value(f, key) or b''
        return ''.join(chr(c) if 32 <= c < 127 else '?' for c in v[:CREDIT_NAME])[:n]
    rows = []
    b = name('colours_by', 23) if colour_sets(f) else ''
    ver = patch_version(f)
    a = name('patch_by', 23 - len(ver) if ver else 25)
    if b: rows.append('Colours: ' + b)
    if ver: rows.append(('Patch: ' + a if a else '').ljust(MENU_ROW - 1 - len(ver)) + 'v' + ver)
    elif a: rows.append('Patch: ' + a)
    return '\n'.join(rows) or None

def set_credits(f, game, patch_by=None, colours_by=None):
    """The patch with INF1's patch_by and colours_by set, or removed if '': the same nonce and encrypted blocks, with a
    new check value. They go right after any publisher line, and must end within the first TEXT_READ bytes, or a loader
    would never see them. None leaves a key as it is."""
    st, bl = check_key(f, game)[:2]
    def line(k, v):
        if v is not None and ('\n' in v or not v.isascii() or not v.isprintable()): raise Wrong('a name must be printable ASCII')
        return b'' if not v else b'%s=%s\n' % (k, v.encode())
    out = []
    for t, body in bl:
        if t == b'INF1':
            lines = [l + b'\n' for l in body.split(b'\n') if l]
            old = {k: next((l for l in lines if l.startswith(k + b'=')), b'') for k in (b'patch_by', b'colours_by')}
            new = [line(b'patch_by', patch_by) if patch_by is not None else old[b'patch_by'],
                   line(b'colours_by', colours_by) if colours_by is not None else old[b'colours_by']]
            rest = [l for l in lines if not l.startswith((b'patch_by=', b'colours_by='))]
            first = [l for l in rest if l.startswith(b'publisher=')]
            label = [l for l in rest if l.startswith((b'fix_label=', b'version='))]   # the menu's lines first, the fix label and version after the names
            body = b''.join(first + new + label + [l for l in rest if l not in first and l not in label])
            if len(b''.join(first + new + label)) > TEXT_READ: raise Wrong('the menu lines must end within the first %d bytes of INF1' % TEXT_READ)
        out.append([t, body])
    return seal(f[:CHECK_AT], out, st)

def set_version(f, game, version):
    """The patch with INF1's version set, or removed if '': the same nonce and encrypted blocks, with a new check value.
    It goes after the menu's other lines, which must end within the first TEXT_READ bytes, or a loader would never see it."""
    st, bl = check_key(f, game)[:2]
    if version: check_version(version)
    out = []
    for t, body in bl:
        if t == b'INF1':
            lines = [l + b'\n' for l in body.split(b'\n') if l]
            rest = [l for l in lines if not l.startswith(b'version=')]
            menu = [l for l in rest if l.partition(b'=')[0].decode('latin-1') in MENU_KEYS]
            new = [b'version=%s\n' % version.encode()] if version else []
            body = b''.join(menu + new + [l for l in rest if l not in menu])
            if len(b''.join(menu + new)) > TEXT_READ: raise Wrong('the menu lines must end within the first %d bytes of INF1' % TEXT_READ)
        out.append([t, body])
    return seal(f[:CHECK_AT], out, st)

def handoff_bas():
    """The one-line BASIC program browser.cfg merges into the snapshot loader: line 0, IF %x=1 THEN CLS:.nexload
    nexclash.nex. A browser.cfg line cannot branch by itself: IF ... ELSE and ON both fell through to the menu when
    tried from a browser line under JNext, so the branch has to be in a program. A +3DOS file, tokenised by hand."""
    code = b'\xfa%x=1\xcb\xfb:.nexload nexclash.nex\r'
    program = bytes((0, 0)) + struct.pack('<H', len(code)) + code
    head = bytearray(128)
    head[0:11] = b'PLUS3DOS\x1a\x01\x00'
    head[11:15] = struct.pack('<I', 128 + len(program))
    head[15] = 0
    head[16:22] = struct.pack('<HHH', len(program), 0x8000, len(program))
    head[127] = sum(head[:127]) & 255
    return bytes(head) + program

def refuse_same(output, *inputs):
    """An output path must not be any of its own inputs."""
    for path in inputs:
        if path and os.path.exists(output) and os.path.samefile(output, path):
            raise Wrong('the output %s is one of the inputs' % output)

def read_file(path):
    with open(path, 'rb') as g: return g.read()

def game_arg(path, also=()):
    """A game from the command line: one file, or with --also a set of tapes in that order."""
    if not also: return read_file(path)
    paths = [path] + list(also)
    return FileSet([read_file(x) for x in paths], [kind_of_name(x) for x in paths])

def main(argv):
    try:
        run(argv)
    except (Wrong, OSError) as e:
        raise SystemExit('Refused: %s' % e)
    except (ValueError, subprocess.CalledProcessError) as e:
        raise SystemExit('Cannot make that: %s' % e)

def run(argv):
    import argparse
    if argv[:1] == ['handoff-bas']:
        ap = argparse.ArgumentParser(prog='nxc.py handoff-bas', description='Write NXCHAND.BAS, for browser.cfg.')
        ap.add_argument('-o', '--output', required=True)
        a = ap.parse_args(argv[1:])
        with open(a.output, 'wb') as g: g.write(handoff_bas())
        print('wrote', a.output)
        return
    if argv[:1] == ['help']:
        ap = argparse.ArgumentParser(prog='nxc.py help', description="Set the menu's help text for its lines (HLP1).")
        ap.add_argument('patch'); ap.add_argument('game'); ap.add_argument('-o', '--output', required=True)
        ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='a further file of the game, for a set of tapes; repeatable, in order')
        ap.add_argument('--line', action='append', default=[], metavar='KEY=TEXT', help='fix, colours, language, trainer_N or toggle_N, then its help, up to two rows of %d; an empty TEXT removes it; repeatable' % MENU_ROW)
        a = ap.parse_args(argv[1:])
        refuse_same(a.output, a.patch, a.game, *a.also)
        texts = {}
        for kv in a.line:
            k, eq, v = kv.partition('=')
            if not eq: raise Wrong('--line takes KEY=TEXT')
            texts[k] = v
        f = set_help(read_file(a.patch), game_arg(a.game, a.also), texts)
        with open(a.output, 'wb') as g: g.write(f)
        for k, v in help_texts(f).items(): print('%s: %r' % (k, v))
        return
    if argv[:1] == ['version']:
        ap = argparse.ArgumentParser(prog='nxc.py version', description="Set the patch's own version, in INF1, shown on the menu's Patch: row as v and it.")
        ap.add_argument('patch'); ap.add_argument('game'); ap.add_argument('version', help="such as 1.0, up to %d characters, without the v; '' removes it" % VERSION_MAX)
        ap.add_argument('-o', '--output', required=True)
        ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='a further file of the game, for a set of tapes; repeatable, in order')
        a = ap.parse_args(argv[1:])
        refuse_same(a.output, a.patch, a.game, *a.also)
        f = set_version(read_file(a.patch), game_arg(a.game, a.also), a.version)
        with open(a.output, 'wb') as g: g.write(f)
        print('version:', patch_version(f) or '(none)'); print('menu line:', credit_line(f)); print('wrote', a.output, len(f), 'bytes')
        return
    if argv[:1] == ['import-pok']:
        ap = argparse.ArgumentParser(prog='nxc.py import-pok', description="Add a .pok's trainers to a patch.")
        ap.add_argument('patch'); ap.add_argument('pok'); ap.add_argument('game'); ap.add_argument('-o', '--output', required=True)
        ap.add_argument('--publisher', help='INF1 publisher line for the menu, such as "Ocean, 1986"')
        ap.add_argument('--only', help='import only these trainers, comma-separated, as the .pok names them: "Name,Name"')
        ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='a further file of the game, for a set of tapes; repeatable, in order')
        ap.add_argument('--top-bank', type=int, choices=range(8), metavar='0-7',
                        help='on a 128K game, the bank paged at 0xC000 in play, for .pok lines with bank 8 at 0xC000 or above')
        a = ap.parse_args(argv[1:]); notes = []
        only = [n.strip() for n in a.only.split(',')] if a.only is not None else None
        refuse_same(a.output, a.game, a.pok, *a.also)
        with open(a.pok, encoding='latin-1') as g: pok = g.read()
        f = import_pok(read_file(a.patch), game_arg(a.game, a.also), pok, a.publisher, notes, only, a.top_bank)
        with open(a.output, 'wb') as g: g.write(f)
        for n, why in notes: print('note: %s: %s' % (n, why))
        for k, t in enumerate(trainers(f)):
            print('%d  %-25s %s' % (k + 1, t[1], ' '.join('bank %d +%d=%d' % p for p in t[2])))
        print('wrote', a.output, len(f), 'bytes')
        return
    if argv[:1] == ['credit']:
        ap = argparse.ArgumentParser(prog='nxc.py credit', description="Set the names on the menu's credit line, in INF1.")
        ap.add_argument('patch'); ap.add_argument('game'); ap.add_argument('-o', '--output', required=True)
        ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='a further file of the game, for a set of tapes; repeatable, in order')
        ap.add_argument('--patch-by', help="who made the patch; an empty name removes it")
        ap.add_argument('--colours-by', help="who painted the colours, shown only if the patch has a colour set; an empty name removes it")
        a = ap.parse_args(argv[1:])
        refuse_same(a.output, a.game, *a.also)
        f = set_credits(read_file(a.patch), game_arg(a.game, a.also), a.patch_by, a.colours_by)
        with open(a.output, 'wb') as g: g.write(f)
        print('menu line:', credit_line(f)); print('wrote', a.output, len(f), 'bytes')
        return
    if argv[:1] == ['make']:
        ap = argparse.ArgumentParser(prog='nxc.py make', description="Package a finished .nex and the game it was built from as a patch.")
        ap.add_argument('nex'); ap.add_argument('game', help='the .z80, .sna, .tap or .tzx the .nex was built from'); ap.add_argument('-o', '--output', required=True)
        ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='for a tape: a further file of the release, such as its side B; repeatable, in order')
        ap.add_argument('--start', help='for a tape: the .z80 of the state the build starts from, taken from that tape')
        ap.add_argument('--tape-bank', action='append', default=[], metavar='N', help='for a tape: a bank the .nex lists beyond the game\'s own that holds blocks of the tape, such as a multiload\'s; repeatable, or N,N')
        ap.add_argument('--residual-max', type=int, help='for a tape: the most bytes of the start state not on the tape that the patch may carry (%d)' % RESIDUAL_MAX)
        ap.add_argument('--file', help='the name a player has the game under; its own name by default')
        ap.add_argument('--zxdb', help='its ZXDB entry'); ap.add_argument('--title'); ap.add_argument('--publisher', help='for the menu, such as "Ocean, 1986"')
        ap.add_argument('--patch-by'); ap.add_argument('--colours-by'); ap.add_argument('--credit', help="INF1's credit; a patch from NexClash keeps the default")
        ap.add_argument('--fix-label', metavar='TEXT', help='the menu\'s name for the NexClash build\'s line, 1 to %d characters, for a game "%s" does not fit, such as Colour' % (FIX_LABEL_MAX, FIX_LABEL))
        ap.add_argument('--patch-version', metavar='V', help="the patch's own version, such as 1.0, up to %d characters; the menu shows v1.0" % VERSION_MAX)
        ap.add_argument('--build', help="what INF1 calls the build; the .nex's own name by default")
        ap.add_argument('--rom', type=int, choices=(0, 1, 2), default=0, help='0 not stated; 1 runs on the Next\'s own ROM; 2 needs the Sinclair 48K ROM, carried in the alt ROM')
        ap.add_argument('--highest-bank', type=int, help='the highest 16K bank the build uses at run time, if above the highest it lists')
        ap.add_argument('--proof', action='append', default=[], metavar='KEY=VALUE', help='a PRF1 field; repeatable')
        ap.add_argument('--proof-file', help='PRF1 fields, as lines of KEY=VALUE')
        ap.add_argument('--colours', action='append', default=[], metavar='NAME=NEX', help='a colour set: the same build with it applied; repeatable')
        ap.add_argument('--language', action='append', default=[], metavar='NAME=NEX', help='a language set, the same way; repeatable')
        ap.add_argument('--toggle', action='append', default=[], metavar='NAME=NEX', help='a toggle that changes only what is shown: the same build with it on; repeatable, at most %d' % TOGGLES_MAX)
        ap.add_argument('--toggle-logic', action='append', default=[], metavar='NAME=NEX', help='a toggle that changes the game logic, as a bug fix does; needs a toggle_N proof line')
        ap.add_argument('--game-language', metavar='CODE', help="the language the game itself is in, as an ISO 639 code such as en")
        ap.add_argument('--language-code', action='append', default=[], metavar='NAME=CODE', help="a language set's ISO 639 code; repeatable")
        ap.add_argument('--text-by', help='who translated the text; kept in INF1, not on the menu')
        a = ap.parse_args(argv[1:])
        refuse_same(a.output, a.nex, a.game, *a.also)
        def named(items):
            out = {}
            for item in items:
                if '=' not in item: raise Wrong('%s is not NAME=NEX' % item)
                name, path = item.split('=', 1)
                refuse_same(a.output, path)
                out[name] = path
            return out
        lines = list(a.proof)
        if a.proof_file:
            with open(a.proof_file, encoding='ascii') as g: lines += [l.rstrip('\n') for l in g if l.strip() and not l.startswith('#')]
        proof = {}
        for line in lines:
            if '=' not in line: raise Wrong('%s is not KEY=VALUE' % line)
            k, v = line.split('=', 1)
            proof[k.strip()] = v.strip()
        target = dict(file=a.file or os.path.basename(a.game), title=a.title, zxdb_entry=a.zxdb)
        if a.also: target['file'] = [target['file']] + [os.path.basename(x) for x in a.also]
        with open(a.nex, 'rb') as g: built = g.read()
        info = dict(publisher=a.publisher, patch_by=a.patch_by, colours_by=a.colours_by, fix_label=a.fix_label, version=a.patch_version,
                    build=a.build or os.path.splitext(os.path.basename(a.nex))[0], nex_md5=hashlib.md5(built).hexdigest())
        if a.credit: info['credit'] = a.credit
        info.update(language_info(a.game_language, a.language_code, a.text_by, named(a.language)))
        tape_banks = [int(x, 0) for item in a.tape_bank for x in item.split(',') if x.strip()]; summary = {}
        if a.start: refuse_same(a.output, a.start)
        tog = {n: (p_, False) for n, p_ in named(a.toggle).items()}
        tog.update({n: (p_, True) for n, p_ in named(a.toggle_logic).items()})
        f, made = make([a.game] + a.also if a.also else a.game, a.nex, target, info, rom=a.rom, proof=proof, colours=named(a.colours), languages=named(a.language), highest_bank=a.highest_bank, toggles=tog,
                       start=a.start, tape_banks=tape_banks, residual_max=a.residual_max, tape_summary=summary)
        if summary:
            print('tape: %d data blocks; %d copies take %d bytes of the start state from it; %d bytes in %d sites are not on it; table %d bytes'
                  % (summary['blocks'], summary['copies'], summary['from_tape'], summary['residual'], summary['sites'], summary['table']))
        for key, value in (('publisher', a.publisher), ('patch_by', a.patch_by), ('colours_by', a.colours_by)):
            if value and inf1_value(f, key) is None: raise Wrong('the menu names must end within the first %d bytes of INF1' % TEXT_READ)
        with open(a.output, 'wb') as g: g.write(f)
        print('rebuilds it exactly, MD5', info['nex_md5']); print(memory_text(dict(blocks(f)[1])[b'OPT1'][2]))
        together = bool(colour_sets(f)) + bool(languages(f)) + len(toggles_of(f))
        if together > 2:
            print('note: %d choices can be on together; firmware/nexclash.asm holds 2 at once, so its menu lets no third be turned on' % together)
        for one in made["sets"]:
            print('set %s: %d bytes decoded in %d banks, %d at most at once, %d stored' % (one['name'], one['decoded'], one['banks'], one['largest'], one['stored']))
        print('wrote', a.output, len(f), 'bytes')
        return
    if argv[:1] in (['add-dump'], ['add-target']):
        ap = argparse.ArgumentParser(prog='nxc.py ' + argv[0], description='Accept one more dump or tape, if it rebuilds the same banks.')
        ap.add_argument('patch'); ap.add_argument('known'); ap.add_argument('new'); ap.add_argument('-o', '--output', required=True)
        ap.add_argument('--file', help='the name a player has it under; the new file\'s own name by default')
        ap.add_argument('--zxdb', help='its ZXDB entry'); ap.add_argument('--title')
        ap.add_argument('--residual-max', type=int, help='for a tape: as for make')
        ap.add_argument('--known-also', action='append', default=[], metavar='TAPE', help='a further file of the known release; repeatable, in order')
        ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='a further file of the new release; repeatable, in order')
        a = ap.parse_args(argv[1:])
        refuse_same(a.output, a.known, a.new, *a.known_also, *a.also)
        fields = dict(file=a.file or os.path.basename(a.new), zxdb_entry=a.zxdb, title=a.title)
        if a.also: fields['file'] = [fields['file']] + [os.path.basename(x) for x in a.also]
        f = add_target(read_file(a.patch), game_arg(a.known, a.known_also), game_arg(a.new, a.also), kind_of_name(a.new), fields, a.residual_max)
        with open(a.output, 'wb') as g: g.write(f)
        print('accepts', len(targets(f)), 'dumps; wrote', a.output, len(f), 'bytes')
        return
    ap = argparse.ArgumentParser(description='Apply or list a .nxc patch.')
    ap.add_argument('patch'); ap.add_argument('game', nargs='?'); ap.add_argument('-o', '--output')
    ap.add_argument('--colours', help='a colour set by name; omit for the default; has no effect with --original')
    ap.add_argument('--language', help='a language set by name; has no effect with --original')
    ap.add_argument('--toggle', action='append', default=[], help='a toggle by name, on; repeatable; no effect with --original')
    ap.add_argument('--trainer', action='append', help='a trainer by number from 1 or by name; repeatable')
    ap.add_argument('--original', action='store_true', help='no patch: write the game itself, or with trainers a snapshot of it with them in; for a tape, the start state as a .z80')
    ap.add_argument('--also', action='append', default=[], metavar='TAPE', help='a further file of the game, for a patch that wants a set of tapes; repeatable, in order')
    ap.add_argument('--bare', action='store_true', help='a .nex without the menu, with the choices given here fixed in it; by default the .nex carries the menu, which starts with the choices given here')
    a = ap.parse_args(argv); f = read_file(a.patch)
    print('colour sets:', ', '.join(['(default)'] + colour_sets(f)))
    if languages(f): print('languages:', ', '.join(['(default)'] + languages(f)))
    if toggles_of(f): print('toggles:', ', '.join(n + (' (changes the game logic)' if lg else '') for n, lg in toggles_of(f)))
    print('trainers:', ', '.join(t[1] for t in trainers(f)) or '(none)')
    print('version:', patch_version(f) or '(none)')
    print('needs', memory_text(dict(blocks(f)[1]).get(b'OPT1', bytes(3))[2:3][0] if len(dict(blocks(f)[1]).get(b'OPT1', b'')) == 3 else 0))
    for t in targets(f):
        print('accepts ' + ' + '.join('%s, %s, %d bytes' % (nm, KIND_NAMES.get(k_, 'unknown kind'), n_) for nm, k_, n_ in t['files']))
    for t, d in blocks(f)[1]:
        if t in (b'INF1', b'PRF1'): print(d.decode(errors='replace'), end='')
    if a.game:
        output = a.output or 'out.nex'
        refuse_same(output, a.patch, a.game, *a.also)
        game = game_arg(a.game, a.also)
        if a.original: d = original_with_pokes(f, game, a.trainer)
        elif a.bare: d = apply(f, game=game, colours=a.colours, chosen=a.trainer, language=a.language, toggles=a.toggle)
        else: d = apply_menu(f, game, chosen=a.trainer, colours=a.colours, language=a.language, toggles=a.toggle)
        with open(output, 'wb') as g: g.write(d)
        print('wrote', output, hashlib.md5(d).hexdigest())

if __name__ == '__main__':
    main(sys.argv[1:])
